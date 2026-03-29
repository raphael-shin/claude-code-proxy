from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


ProfileName = Literal["dev", "staging", "prod"]


@dataclass(frozen=True)
class DeploymentEnvironment:
    account: str
    region: str


@dataclass(frozen=True)
class NamingConfig:
    project: str
    environment: ProfileName

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
    nat_gateways: int
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


@dataclass(frozen=True)
class ClaudeCodeProxyStackProps:
    naming: NamingConfig
    deployment_environment: DeploymentEnvironment
    token_service: TokenServiceConfig
    admin_api: AdminApiConfig
    network: NetworkConfig
    data_plane: DataPlaneConfig
    proxy_runtime: ProxyRuntimeConfig


def load_profile(profile_name: ProfileName = "dev") -> ClaudeCodeProxyStackProps:
    profiles: dict[ProfileName, ClaudeCodeProxyStackProps] = {
        "dev": ClaudeCodeProxyStackProps(
            naming=NamingConfig(
                project="claude-code-proxy",
                environment="dev",
            ),
            deployment_environment=DeploymentEnvironment(
                account="111111111111",
                region="ap-northeast-2",
            ),
            token_service=TokenServiceConfig(
                stage_name="dev",
                throttling_rate_limit=25,
                throttling_burst_limit=50,
                log_retention_days=14,
            ),
            admin_api=AdminApiConfig(
                stage_name="admin-dev",
                throttling_rate_limit=10,
                throttling_burst_limit=20,
                log_retention_days=30,
            ),
            network=NetworkConfig(
                vpc_cidr="10.42.0.0/16",
                max_azs=2,
                nat_gateways=1,
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
                domain_name="proxy.dev.example.internal",
                hosted_zone_name="dev.example.internal",
                certificate_arn="arn:aws:acm:ap-northeast-2:111111111111:certificate/dev-placeholder",
                waf_arn="arn:aws:wafv2:ap-northeast-2:111111111111:regional/webacl/dev-placeholder/00000000-0000-0000-0000-000000000000",
            ),
        ),
        "staging": ClaudeCodeProxyStackProps(
            naming=NamingConfig(
                project="claude-code-proxy",
                environment="staging",
            ),
            deployment_environment=DeploymentEnvironment(
                account="222222222222",
                region="ap-northeast-2",
            ),
            token_service=TokenServiceConfig(
                stage_name="staging",
                throttling_rate_limit=50,
                throttling_burst_limit=100,
                log_retention_days=30,
            ),
            admin_api=AdminApiConfig(
                stage_name="admin-staging",
                throttling_rate_limit=20,
                throttling_burst_limit=40,
                log_retention_days=30,
            ),
            network=NetworkConfig(
                vpc_cidr="10.52.0.0/16",
                max_azs=2,
                nat_gateways=1,
            ),
            data_plane=DataPlaneConfig(
                database_name="claude_code_proxy",
                min_acu=0.5,
                max_acu=4.0,
                cache_ttl_minutes=15,
            ),
            proxy_runtime=ProxyRuntimeConfig(
                container_port=8000,
                desired_count=2,
                min_capacity=2,
                max_capacity=6,
                cpu=1024,
                memory_mib=2048,
                health_check_path="/health",
                idle_timeout_seconds=300,
                log_retention_days=30,
                domain_name="proxy.staging.example.internal",
                hosted_zone_name="staging.example.internal",
                certificate_arn="arn:aws:acm:ap-northeast-2:222222222222:certificate/staging-placeholder",
                waf_arn="arn:aws:wafv2:ap-northeast-2:222222222222:regional/webacl/staging-placeholder/00000000-0000-0000-0000-000000000000",
            ),
        ),
        "prod": ClaudeCodeProxyStackProps(
            naming=NamingConfig(
                project="claude-code-proxy",
                environment="prod",
            ),
            deployment_environment=DeploymentEnvironment(
                account="333333333333",
                region="ap-northeast-2",
            ),
            token_service=TokenServiceConfig(
                stage_name="prod",
                throttling_rate_limit=100,
                throttling_burst_limit=200,
                log_retention_days=90,
            ),
            admin_api=AdminApiConfig(
                stage_name="admin-prod",
                throttling_rate_limit=50,
                throttling_burst_limit=100,
                log_retention_days=90,
            ),
            network=NetworkConfig(
                vpc_cidr="10.62.0.0/16",
                max_azs=3,
                nat_gateways=2,
            ),
            data_plane=DataPlaneConfig(
                database_name="claude_code_proxy",
                min_acu=1.0,
                max_acu=8.0,
                cache_ttl_minutes=15,
            ),
            proxy_runtime=ProxyRuntimeConfig(
                container_port=8000,
                desired_count=3,
                min_capacity=3,
                max_capacity=10,
                cpu=1024,
                memory_mib=2048,
                health_check_path="/health",
                idle_timeout_seconds=300,
                log_retention_days=90,
                domain_name="proxy.example.com",
                hosted_zone_name="example.com",
                certificate_arn="arn:aws:acm:ap-northeast-2:333333333333:certificate/prod-placeholder",
                waf_arn="arn:aws:wafv2:ap-northeast-2:333333333333:regional/webacl/prod-placeholder/00000000-0000-0000-0000-000000000000",
            ),
        ),
    }
    try:
        return profiles[profile_name]
    except KeyError as error:
        supported = ", ".join(sorted(profiles))
        raise ValueError(f"unknown profile '{profile_name}', expected one of: {supported}") from error
