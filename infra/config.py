from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class DeploymentEnvironment:
    account: str
    region: str


@dataclass(frozen=True)
class NamingConfig:
    project: str
    environment: str

    @property
    def stack_name(self) -> str:
        return f"ClaudeCodeProxy-{self.environment}"


@dataclass(frozen=True)
class OptionalAuthorizerConfig:
    enabled: bool = False
    identity_header: str = "Authorization"
    results_cache_ttl_seconds: int = 0


@dataclass(frozen=True)
class TokenServiceConfig:
    stage_name: str
    throttling_rate_limit: float
    throttling_burst_limit: int
    log_retention_days: int
    authorizer: OptionalAuthorizerConfig = field(default_factory=OptionalAuthorizerConfig)


@dataclass(frozen=True)
class AdminApiConfig:
    stage_name: str
    throttling_rate_limit: float
    throttling_burst_limit: int
    log_retention_days: int


@dataclass(frozen=True)
class NetworkConfig:
    vpc_cidr: str
    max_azs: int
    runtime_container_port: int = 8000


@dataclass(frozen=True)
class DataPlaneConfig:
    database_name: str
    min_acu: float
    max_acu: float
    cache_ttl_minutes: int


@dataclass(frozen=True)
class ProxyRuntimeConfig:
    container_port: int
    desired_count: int
    min_capacity: int
    max_capacity: int
    cpu: int
    memory_mib: int
    health_check_path: str
    idle_timeout_seconds: int
    log_retention_days: int
    domain_name: str
    hosted_zone_name: str
    certificate_arn: str
    waf_arn: str
    image_repository_name: str
    image_tag: str


@dataclass(frozen=True)
class ClaudeCodeProxyStackProps:
    naming: NamingConfig
    deployment_environment: DeploymentEnvironment
    token_service: TokenServiceConfig
    admin_api: AdminApiConfig
    network: NetworkConfig
    data_plane: DataPlaneConfig
    proxy_runtime: ProxyRuntimeConfig


_PROJECT_NAME = "claude-code-proxy"


def build_stack_props(environment_name: str = "dev") -> ClaudeCodeProxyStackProps:
    env_name = _normalize_environment_name(environment_name)
    account = os.environ.get("CDK_DEFAULT_ACCOUNT", "000000000000")
    region = (
        os.environ.get("CDK_DEFAULT_REGION")
        or os.environ.get("AWS_REGION")
        or os.environ.get("AWS_DEFAULT_REGION")
        or "ap-northeast-2"
    )
    hosted_zone_name = os.environ.get(
        "CLAUDE_CODE_PROXY_HOSTED_ZONE_NAME",
        f"{env_name}.example.internal",
    )
    domain_name = os.environ.get(
        "CLAUDE_CODE_PROXY_DOMAIN_NAME",
        f"proxy.{hosted_zone_name}",
    )
    runtime_image_repository_name = os.environ.get(
        "CLAUDE_CODE_PROXY_RUNTIME_IMAGE_REPOSITORY_NAME",
        "claude-code-proxy/runtime",
    )
    runtime_image_tag = os.environ.get(
        "CLAUDE_CODE_PROXY_RUNTIME_IMAGE_TAG",
        "latest",
    )
    certificate_arn = os.environ.get(
        "CLAUDE_CODE_PROXY_CERTIFICATE_ARN",
        (
            f"arn:aws:acm:{region}:{account}:certificate/"
            f"{env_name}-placeholder"
        ),
    )
    waf_arn = os.environ.get(
        "CLAUDE_CODE_PROXY_WAF_ARN",
        (
            f"arn:aws:wafv2:{region}:{account}:regional/webacl/"
            f"{env_name}-placeholder/00000000-0000-0000-0000-000000000000"
        ),
    )
    return ClaudeCodeProxyStackProps(
        naming=NamingConfig(
            project=_PROJECT_NAME,
            environment=env_name,
        ),
        deployment_environment=DeploymentEnvironment(
            account=account,
            region=region,
        ),
        token_service=TokenServiceConfig(
            stage_name=env_name,
            throttling_rate_limit=25,
            throttling_burst_limit=50,
            log_retention_days=14,
        ),
        admin_api=AdminApiConfig(
            stage_name=f"admin-{env_name}",
            throttling_rate_limit=10,
            throttling_burst_limit=20,
            log_retention_days=30,
        ),
        network=NetworkConfig(
            vpc_cidr="10.42.0.0/16",
            max_azs=2,
        ),
        data_plane=DataPlaneConfig(
            database_name="claude_code_proxy",
            min_acu=0.5,
            max_acu=2.0,
            cache_ttl_minutes=15,
        ),
        proxy_runtime=ProxyRuntimeConfig(
            container_port=8000,
            desired_count=2,
            min_capacity=2,
            max_capacity=4,
            cpu=512,
            memory_mib=1024,
            health_check_path="/health",
            idle_timeout_seconds=300,
            log_retention_days=30,
            domain_name=domain_name,
            hosted_zone_name=hosted_zone_name,
            certificate_arn=certificate_arn,
            waf_arn=waf_arn,
            image_repository_name=runtime_image_repository_name,
            image_tag=runtime_image_tag,
        ),
    )


def default_environment_name() -> str:
    return _normalize_environment_name(
        os.environ.get("CLAUDE_CODE_PROXY_ENV")
        or os.environ.get("AWS_PROFILE")
        or "dev"
    )


def _normalize_environment_name(value: str) -> str:
    normalized = value.strip().lower()
    sanitized = "".join(character if character.isalnum() or character == "-" else "-" for character in normalized)
    collapsed = "-".join(part for part in sanitized.split("-") if part)
    return collapsed or "dev"
