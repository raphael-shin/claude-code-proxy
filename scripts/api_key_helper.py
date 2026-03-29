from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
from botocore.credentials import Credentials

from security.keys import VIRTUAL_KEY_PREFIX

MIN_CACHE_TTL_SECONDS = 300
MAX_CACHE_TTL_SECONDS = 900


class ApiKeyHelperError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class CachedVirtualKey:
    virtual_key: str
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class ExportedAwsCredentials:
    access_key_id: str
    secret_access_key: str
    session_token: str | None = None


@dataclass(frozen=True, slots=True)
class ApiKeyHelperConfig:
    token_service_url: str
    aws_region: str
    aws_profile: str | None = None
    cache_path: Path = Path.home() / ".claude-code-proxy" / "cache.json"
    cache_ttl_seconds: int = MIN_CACHE_TTL_SECONDS
    request_timeout_seconds: float = 2.0
    session_probe_timeout_seconds: float = 2.0
    login_timeout_seconds: float = 60.0

    def __post_init__(self) -> None:
        normalized_ttl = min(max(self.cache_ttl_seconds, MIN_CACHE_TTL_SECONDS), MAX_CACHE_TTL_SECONDS)
        object.__setattr__(self, "cache_ttl_seconds", normalized_ttl)

    @classmethod
    def from_env(cls) -> ApiKeyHelperConfig:
        token_service_url = os.environ.get("CLAUDE_CODE_PROXY_TOKEN_SERVICE_URL")
        aws_region = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION")
        if not token_service_url or not aws_region:
            raise ApiKeyHelperError(
                "CLAUDE_CODE_PROXY_TOKEN_SERVICE_URL and AWS_REGION must be configured."
            )

        cache_path = Path(
            os.environ.get(
                "CLAUDE_CODE_PROXY_CACHE_PATH",
                str(Path.home() / ".claude-code-proxy" / "cache.json"),
            )
        )
        cache_ttl_seconds = int(
            os.environ.get("CLAUDE_CODE_PROXY_CACHE_TTL_SECONDS", str(MIN_CACHE_TTL_SECONDS))
        )
        request_timeout_seconds = float(
            os.environ.get("CLAUDE_CODE_PROXY_REQUEST_TIMEOUT_SECONDS", "2.0")
        )
        return cls(
            token_service_url=token_service_url,
            aws_region=aws_region,
            aws_profile=os.environ.get("AWS_PROFILE"),
            cache_path=cache_path,
            cache_ttl_seconds=cache_ttl_seconds,
            request_timeout_seconds=request_timeout_seconds,
        )


class CommandRunner(Protocol):
    def run(self, args: list[str], *, timeout_seconds: float) -> str: ...


class SessionBootstrapper(Protocol):
    def ensure_session(self) -> None: ...

    def export_credentials(self) -> ExportedAwsCredentials: ...


class TokenServiceClient(Protocol):
    def get_or_create_key(self, credentials: ExportedAwsCredentials) -> str: ...


class SubprocessCommandRunner:
    def run(self, args: list[str], *, timeout_seconds: float) -> str:
        try:
            result = subprocess.run(
                args,
                capture_output=True,
                check=True,
                text=True,
                timeout=timeout_seconds,
            )
        except subprocess.TimeoutExpired as error:
            raise ApiKeyHelperError(f"Command timed out: {' '.join(args)}") from error
        except subprocess.CalledProcessError as error:
            message = error.stderr.strip() or error.stdout.strip() or "command failed"
            raise ApiKeyHelperError(message) from error
        return result.stdout


class CacheFileHelper:
    def __init__(self, *, path: Path) -> None:
        self._path = path

    def load(self, *, now: datetime) -> CachedVirtualKey | None:
        if not self._path.exists():
            return None
        try:
            payload = json.loads(self._path.read_text())
            virtual_key = payload["virtual_key"]
            expires_at = datetime.fromisoformat(payload["expires_at"])
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            self._delete_if_present()
            return None

        if not isinstance(virtual_key, str) or not virtual_key.startswith(VIRTUAL_KEY_PREFIX):
            self._delete_if_present()
            return None
        if expires_at <= now:
            return None

        return CachedVirtualKey(virtual_key=virtual_key, expires_at=expires_at)

    def store(self, *, virtual_key: str, now: datetime, ttl_seconds: int) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        expires_at = now + timedelta(seconds=ttl_seconds)
        payload = {
            "virtual_key": virtual_key,
            "expires_at": expires_at.isoformat(),
        }
        self._path.write_text(json.dumps(payload))

    def _delete_if_present(self) -> None:
        try:
            self._path.unlink(missing_ok=True)
        except OSError:
            return


class AwsCliSessionBootstrapper:
    def __init__(
        self,
        *,
        runner: CommandRunner,
        profile: str | None,
        session_probe_timeout_seconds: float,
        login_timeout_seconds: float,
        export_timeout_seconds: float,
    ) -> None:
        self._runner = runner
        self._profile = profile
        self._session_probe_timeout_seconds = session_probe_timeout_seconds
        self._login_timeout_seconds = login_timeout_seconds
        self._export_timeout_seconds = export_timeout_seconds

    def ensure_session(self) -> None:
        if self._profile is None:
            return
        probe_command = ["aws", "sts", "get-caller-identity", "--profile", self._profile]
        try:
            self._runner.run(probe_command, timeout_seconds=self._session_probe_timeout_seconds)
        except ApiKeyHelperError:
            login_command = ["aws", "sso", "login", "--profile", self._profile]
            self._runner.run(login_command, timeout_seconds=self._login_timeout_seconds)

    def export_credentials(self) -> ExportedAwsCredentials:
        command = ["aws", "configure", "export-credentials", "--format", "process"]
        if self._profile is not None:
            command.extend(["--profile", self._profile])
        raw_output = self._runner.run(command, timeout_seconds=self._export_timeout_seconds)
        try:
            payload = json.loads(raw_output)
            return ExportedAwsCredentials(
                access_key_id=payload["AccessKeyId"],
                secret_access_key=payload["SecretAccessKey"],
                session_token=payload.get("SessionToken"),
            )
        except (KeyError, TypeError, json.JSONDecodeError) as error:
            raise ApiKeyHelperError("Failed to export AWS credentials from aws configure.") from error


class SigV4TokenServiceClient:
    def __init__(
        self,
        *,
        url: str,
        region: str,
        timeout_seconds: float,
        service_name: str = "execute-api",
    ) -> None:
        self._url = url
        self._region = region
        self._timeout_seconds = timeout_seconds
        self._service_name = service_name

    def get_or_create_key(self, credentials: ExportedAwsCredentials) -> str:
        body = b"{}"
        aws_request = AWSRequest(
            method="POST",
            url=self._url,
            data=body,
            headers={
                "Content-Type": "application/json",
                "Host": urlsplit(self._url).netloc,
            },
        )
        SigV4Auth(
            Credentials(
                credentials.access_key_id,
                credentials.secret_access_key,
                credentials.session_token,
            ),
            self._service_name,
            self._region,
        ).add_auth(aws_request)
        request = Request(
            self._url,
            data=body,
            method="POST",
            headers=dict(aws_request.headers.items()),
        )
        try:
            with urlopen(request, timeout=self._timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError) as error:
            raise ApiKeyHelperError("Failed to connect to Token Service.") from error
        except json.JSONDecodeError as error:
            raise ApiKeyHelperError("Token Service returned an invalid JSON payload.") from error

        virtual_key = payload.get("virtual_key")
        if not isinstance(virtual_key, str) or not virtual_key.startswith(VIRTUAL_KEY_PREFIX):
            raise ApiKeyHelperError("Token Service response did not include a valid virtual_key.")
        return virtual_key


class ApiKeyHelper:
    def __init__(
        self,
        *,
        cache: CacheFileHelper,
        session_bootstrapper: SessionBootstrapper,
        token_service_client: TokenServiceClient,
        clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
        cache_ttl_seconds: int = MIN_CACHE_TTL_SECONDS,
    ) -> None:
        self._cache = cache
        self._session_bootstrapper = session_bootstrapper
        self._token_service_client = token_service_client
        self._clock = clock
        self._cache_ttl_seconds = min(
            max(cache_ttl_seconds, MIN_CACHE_TTL_SECONDS),
            MAX_CACHE_TTL_SECONDS,
        )

    def get_api_key(self) -> str:
        now = self._clock()
        cached = self._cache.load(now=now)
        if cached is not None:
            return cached.virtual_key

        self._session_bootstrapper.ensure_session()
        credentials = self._session_bootstrapper.export_credentials()
        virtual_key = self._token_service_client.get_or_create_key(credentials)
        self._cache.store(
            virtual_key=virtual_key,
            now=self._clock(),
            ttl_seconds=self._cache_ttl_seconds,
        )
        return virtual_key


def build_default_helper(config: ApiKeyHelperConfig | None = None) -> ApiKeyHelper:
    resolved_config = config or ApiKeyHelperConfig.from_env()
    runner = SubprocessCommandRunner()
    cache = CacheFileHelper(path=resolved_config.cache_path)
    bootstrapper = AwsCliSessionBootstrapper(
        runner=runner,
        profile=resolved_config.aws_profile,
        session_probe_timeout_seconds=resolved_config.session_probe_timeout_seconds,
        login_timeout_seconds=resolved_config.login_timeout_seconds,
        export_timeout_seconds=resolved_config.request_timeout_seconds,
    )
    client = SigV4TokenServiceClient(
        url=resolved_config.token_service_url,
        region=resolved_config.aws_region,
        timeout_seconds=resolved_config.request_timeout_seconds,
    )
    return ApiKeyHelper(
        cache=cache,
        session_bootstrapper=bootstrapper,
        token_service_client=client,
        cache_ttl_seconds=resolved_config.cache_ttl_seconds,
    )


def main(argv: list[str] | None = None) -> int:
    del argv
    try:
        virtual_key = build_default_helper().get_api_key()
    except ApiKeyHelperError as error:
        print(str(error), file=sys.stderr)
        return 1

    print(virtual_key)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
