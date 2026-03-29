from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path


def test_shell_api_key_helper_fetches_and_caches_virtual_key(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    script_path = repo_root / "scripts" / "api_key_helper.sh"
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    cache_path = tmp_path / "cache.json"
    curl_log = tmp_path / "curl.log"

    aws_stub = fake_bin / "aws"
    aws_stub.write_text(
        """#!/usr/bin/env bash
set -euo pipefail
if [[ "$1" == "configure" && "$2" == "export-credentials" ]]; then
  cat <<'EOF'
export AWS_ACCESS_KEY_ID=AKIA123
export AWS_SECRET_ACCESS_KEY=secret123
export AWS_SESSION_TOKEN=session123
EOF
  exit 0
fi
exit 1
"""
    )
    aws_stub.chmod(0o755)

    curl_stub = fake_bin / "curl"
    curl_stub.write_text(
        f"""#!/usr/bin/env bash
set -euo pipefail
echo "$*" >> "{curl_log}"
echo '{{"virtual_key":"vk_shell_cached_1234567890"}}'
"""
    )
    curl_stub.chmod(0o755)

    env = os.environ.copy()
    env["PATH"] = f"{fake_bin}:{env['PATH']}"
    env["HOME"] = str(tmp_path)
    env["CLAUDE_CODE_PROXY_TOKEN_SERVICE_URL"] = "https://token.example.com/token-service/get-or-create-key"
    env["AWS_REGION"] = "ap-northeast-2"
    env["AWS_PROFILE"] = "my-sandbox"
    env["CLAUDE_CODE_PROXY_CACHE_PATH"] = str(cache_path)

    first_run = subprocess.run(
        ["bash", str(script_path)],
        cwd=repo_root,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert first_run.returncode == 0, first_run.stderr
    assert first_run.stdout.strip() == "vk_shell_cached_1234567890"
    assert curl_log.exists()

    curl_log.unlink()
    second_run = subprocess.run(
        ["bash", str(script_path)],
        cwd=repo_root,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert second_run.returncode == 0, second_run.stderr
    assert second_run.stdout.strip() == "vk_shell_cached_1234567890"
    assert not curl_log.exists()

    cache_payload = json.loads(cache_path.read_text())
    assert cache_payload["virtual_key"] == "vk_shell_cached_1234567890"
    assert isinstance(cache_payload["expires_at_epoch"], int)


def test_shell_api_key_helper_requests_sso_login_when_credentials_are_missing(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    script_path = repo_root / "scripts" / "api_key_helper.sh"
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()

    aws_stub = fake_bin / "aws"
    aws_stub.write_text(
        """#!/usr/bin/env bash
set -euo pipefail
exit 255
"""
    )
    aws_stub.chmod(0o755)

    curl_stub = fake_bin / "curl"
    curl_stub.write_text(
        """#!/usr/bin/env bash
set -euo pipefail
exit 1
"""
    )
    curl_stub.chmod(0o755)

    env = os.environ.copy()
    env["PATH"] = f"{fake_bin}:{env['PATH']}"
    env["HOME"] = str(tmp_path)
    env["CLAUDE_CODE_PROXY_TOKEN_SERVICE_URL"] = "https://token.example.com/token-service/get-or-create-key"
    env["AWS_REGION"] = "ap-northeast-2"
    env["AWS_PROFILE"] = "my-sandbox"

    completed = subprocess.run(
        ["bash", str(script_path)],
        cwd=repo_root,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 1
    assert "aws sso login --profile my-sandbox" in completed.stderr


def test_shell_api_key_helper_refetches_when_cache_is_corrupt(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    script_path = repo_root / "scripts" / "api_key_helper.sh"
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    cache_path = tmp_path / "cache.json"
    cache_path.write_text("{not-json")
    curl_log = tmp_path / "curl.log"

    aws_stub = fake_bin / "aws"
    aws_stub.write_text(
        """#!/usr/bin/env bash
set -euo pipefail
if [[ "$1" == "configure" && "$2" == "export-credentials" ]]; then
  cat <<'EOF'
export AWS_ACCESS_KEY_ID=AKIA123
export AWS_SECRET_ACCESS_KEY=secret123
export AWS_SESSION_TOKEN=session123
EOF
  exit 0
fi
exit 1
"""
    )
    aws_stub.chmod(0o755)

    curl_stub = fake_bin / "curl"
    curl_stub.write_text(
        f"""#!/usr/bin/env bash
set -euo pipefail
echo "$*" >> "{curl_log}"
echo '{{"virtual_key":"vk_shell_refetched_1234567890"}}'
"""
    )
    curl_stub.chmod(0o755)

    env = os.environ.copy()
    env["PATH"] = f"{fake_bin}:{env['PATH']}"
    env["HOME"] = str(tmp_path)
    env["CLAUDE_CODE_PROXY_TOKEN_SERVICE_URL"] = "https://token.example.com/token-service/get-or-create-key"
    env["AWS_REGION"] = "ap-northeast-2"
    env["AWS_PROFILE"] = "my-sandbox"
    env["CLAUDE_CODE_PROXY_CACHE_PATH"] = str(cache_path)

    completed = subprocess.run(
        ["bash", str(script_path)],
        cwd=repo_root,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == "vk_shell_refetched_1234567890"
    assert curl_log.exists()

    cache_payload = json.loads(cache_path.read_text())
    assert cache_payload["virtual_key"] == "vk_shell_refetched_1234567890"
    assert isinstance(cache_payload["expires_at_epoch"], int)


def test_shell_api_key_helper_fails_fast_when_token_service_is_unreachable(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    script_path = repo_root / "scripts" / "api_key_helper.sh"
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()

    aws_stub = fake_bin / "aws"
    aws_stub.write_text(
        """#!/usr/bin/env bash
set -euo pipefail
if [[ "$1" == "configure" && "$2" == "export-credentials" ]]; then
  cat <<'EOF'
export AWS_ACCESS_KEY_ID=AKIA123
export AWS_SECRET_ACCESS_KEY=secret123
export AWS_SESSION_TOKEN=session123
EOF
  exit 0
fi
exit 1
"""
    )
    aws_stub.chmod(0o755)

    curl_stub = fake_bin / "curl"
    curl_stub.write_text(
        """#!/usr/bin/env bash
set -euo pipefail
exit 28
"""
    )
    curl_stub.chmod(0o755)

    env = os.environ.copy()
    env["PATH"] = f"{fake_bin}:{env['PATH']}"
    env["HOME"] = str(tmp_path)
    env["CLAUDE_CODE_PROXY_TOKEN_SERVICE_URL"] = "https://token.example.com/token-service/get-or-create-key"
    env["AWS_REGION"] = "ap-northeast-2"
    env["AWS_PROFILE"] = "my-sandbox"

    started_at = time.perf_counter()
    completed = subprocess.run(
        ["bash", str(script_path)],
        cwd=repo_root,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    elapsed_ms = (time.perf_counter() - started_at) * 1000

    assert completed.returncode == 1
    assert "Failed to connect to Token Service." in completed.stderr
    assert elapsed_ms < 1000
