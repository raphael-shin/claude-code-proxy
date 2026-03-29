from __future__ import annotations

from aws_cdk import CfnOutput
from aws_cdk import aws_certificatemanager as acm
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_ecs as ecs
from aws_cdk import aws_elasticloadbalancingv2 as elbv2
from aws_cdk import aws_iam as iam
from aws_cdk import aws_logs as logs
from aws_cdk import aws_wafv2 as wafv2
from constructs import Construct

from infra.config import ProxyRuntimeConfig
from infra.constructs.common import retention_days
from infra.constructs.data_plane_construct import DataPlaneConstruct
from infra.constructs.network_construct import NetworkConstruct


class ProxyRuntimeConstruct(Construct):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        config: ProxyRuntimeConfig,
        network: NetworkConstruct,
        data_plane: DataPlaneConstruct,
    ) -> None:
        super().__init__(scope, construct_id)
        self.config = config
        self.network = network
        self.data_plane = data_plane
        self.log_group = logs.LogGroup(
            self,
            "RuntimeLogs",
            retention=retention_days(config.log_retention_days),
        )
        self.cluster = ecs.Cluster(
            self,
            "Cluster",
            vpc=network.vpc,
        )
        self.task_definition = ecs.FargateTaskDefinition(
            self,
            "TaskDefinition",
            cpu=config.cpu,
            memory_limit_mib=config.memory_mib,
        )
        self.task_definition.add_container(
            "ProxyContainer",
            image=ecs.ContainerImage.from_registry("public.ecr.aws/docker/library/python:3.12-slim"),
            command=["python", "-m", "http.server", str(config.container_port)],
            port_mappings=[
                ecs.PortMapping(
                    container_port=config.container_port,
                    protocol=ecs.Protocol.TCP,
                )
            ],
            logging=ecs.LogDrivers.aws_logs(
                stream_prefix="proxy-runtime",
                log_group=self.log_group,
            ),
            environment={
                "PORT": str(config.container_port),
                "DB_PROXY_ENDPOINT": data_plane.database_endpoint,
                "DB_SECRET_ARN": data_plane.database_secret.secret_arn,
                "VIRTUAL_KEY_CACHE_TABLE": data_plane.cache_table.table_name,
            },
        )
        data_plane.cache_table.grant_read_write_data(self.task_definition.task_role)
        data_plane.database_secret.grant_read(self.task_definition.task_role)
        self.task_definition.task_role.add_to_principal_policy(
            iam.PolicyStatement(
                actions=[
                    "bedrock:InvokeModel",
                    "bedrock:InvokeModelWithResponseStream",
                ],
                resources=["*"],
            )
        )

        self.service = ecs.FargateService(
            self,
            "Service",
            cluster=self.cluster,
            task_definition=self.task_definition,
            desired_count=config.desired_count,
            assign_public_ip=False,
            security_groups=[network.runtime_service_security_group],
            vpc_subnets=network.private_subnet_selection,
            circuit_breaker=ecs.DeploymentCircuitBreaker(rollback=True),
            min_healthy_percent=100,
            max_healthy_percent=200,
        )
        self.load_balancer = elbv2.ApplicationLoadBalancer(
            self,
            "LoadBalancer",
            vpc=network.vpc,
            internet_facing=True,
            security_group=network.alb_security_group,
            vpc_subnets=network.public_subnet_selection,
        )
        self.load_balancer.set_attribute(
            "idle_timeout.timeout_seconds",
            str(config.idle_timeout_seconds),
        )
        self.certificate = acm.Certificate.from_certificate_arn(
            self,
            "RuntimeCertificate",
            config.certificate_arn,
        )
        self.https_listener = self.load_balancer.add_listener(
            "HttpsListener",
            port=443,
            protocol=elbv2.ApplicationProtocol.HTTPS,
            certificates=[self.certificate],
            open=False,
        )
        self.target_group = elbv2.ApplicationTargetGroup(
            self,
            "TargetGroup",
            vpc=network.vpc,
            port=config.container_port,
            protocol=elbv2.ApplicationProtocol.HTTP,
            target_type=elbv2.TargetType.IP,
            health_check=elbv2.HealthCheck(path=config.health_check_path),
        )
        self.service.attach_to_application_target_group(self.target_group)
        self.https_listener.add_target_groups(
            "RuntimeTargets",
            target_groups=[self.target_group],
        )
        self.web_acl_association = wafv2.CfnWebACLAssociation(
            self,
            "WebAclAssociation",
            resource_arn=self.load_balancer.load_balancer_arn,
            web_acl_arn=config.waf_arn,
        )
        self.scaling = self.service.auto_scale_task_count(
            min_capacity=config.min_capacity,
            max_capacity=config.max_capacity,
        )
        self.scaling.scale_on_cpu_utilization(
            "CpuTargetTracking",
            target_utilization_percent=60,
        )
        self.endpoint_url_output = CfnOutput(
            self,
            "RuntimeEndpointUrl",
            value=f"https://{self.load_balancer.load_balancer_dns_name}",
        )
        self.endpoint_url_output.override_logical_id("RuntimeEndpointUrl")
        self.load_balancer_dns_output = CfnOutput(
            self,
            "RuntimeAlbDnsName",
            value=self.load_balancer.load_balancer_dns_name,
        )
        self.load_balancer_dns_output.override_logical_id("RuntimeAlbDnsName")
        self.listener_arn_output = CfnOutput(
            self,
            "RuntimeHttpsListenerArn",
            value=self.https_listener.listener_arn,
        )
        self.listener_arn_output.override_logical_id("RuntimeHttpsListenerArn")
