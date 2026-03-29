from __future__ import annotations

from aws_cdk import RemovalPolicy
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_iam as iam
from aws_cdk import aws_rds as rds
from constructs import Construct

from infra.config import DataPlaneConfig, NamingConfig
from infra.constructs.network_construct import NetworkConstruct


class DataPlaneConstruct(Construct):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        config: DataPlaneConfig,
        naming: NamingConfig,
        network: NetworkConstruct,
    ) -> None:
        super().__init__(scope, construct_id)
        self.config = config
        self.naming = naming
        self.network = network
        database_cluster_kwargs: dict[str, object] = {}
        if not self._is_ephemeral_environment():
            database_cluster_kwargs["readers"] = [
                rds.ClusterInstance.serverless_v2(
                    "reader",
                    scale_with_writer=True,
                )
            ]
        self.database_cluster = rds.DatabaseCluster(
            self,
            "AuroraCluster",
            engine=rds.DatabaseClusterEngine.aurora_postgres(
                version=rds.AuroraPostgresEngineVersion.VER_16_4
            ),
            writer=rds.ClusterInstance.serverless_v2("writer"),
            serverless_v2_min_capacity=config.min_acu,
            serverless_v2_max_capacity=config.max_acu,
            default_database_name=config.database_name,
            credentials=rds.Credentials.from_generated_secret("proxyapp"),
            vpc=network.vpc,
            vpc_subnets=network.private_subnet_selection,
            security_groups=[network.database_security_group],
            storage_encrypted=True,
            removal_policy=self._database_removal_policy(),
            **database_cluster_kwargs,
        )
        if self.database_cluster.secret is None:
            raise ValueError("database cluster secret must be present")
        self.database_secret = self.database_cluster.secret
        self.database_proxy = rds.DatabaseProxy(
            self,
            "AuroraProxy",
            proxy_target=rds.ProxyTarget.from_cluster(self.database_cluster),
            secrets=[self.database_secret],
            vpc=network.vpc,
            vpc_subnets=network.private_subnet_selection,
            security_groups=[network.db_proxy_security_group],
            require_tls=True,
            iam_auth=False,
        )
        self.database_endpoint = self.database_proxy.endpoint
        self.cache_table = dynamodb.Table(
            self,
            "VirtualKeyCache",
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            partition_key=dynamodb.Attribute(
                name="user_id",
                type=dynamodb.AttributeType.STRING,
            ),
            time_to_live_attribute="ttl",
            encryption=dynamodb.TableEncryption.AWS_MANAGED,
            removal_policy=self._cache_table_removal_policy(),
        )

    def env_vars(self) -> dict[str, str]:
        return {
            "VIRTUAL_KEY_CACHE_TABLE": self.cache_table.table_name,
            "DB_PROXY_ENDPOINT": self.database_endpoint,
            "DB_SECRET_ARN": self.database_secret.secret_arn,
        }

    def grant_access(self, grantee: iam.IGrantable) -> None:
        self.cache_table.grant_read_write_data(grantee)
        self.database_secret.grant_read(grantee)

    def _is_ephemeral_environment(self) -> bool:
        return self.naming.environment == "dev"

    def _database_removal_policy(self) -> RemovalPolicy:
        if self._is_ephemeral_environment():
            return RemovalPolicy.DESTROY
        return RemovalPolicy.SNAPSHOT

    def _cache_table_removal_policy(self) -> RemovalPolicy:
        if self._is_ephemeral_environment():
            return RemovalPolicy.DESTROY
        return RemovalPolicy.RETAIN
