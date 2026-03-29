from __future__ import annotations

from aws_cdk import aws_ec2 as ec2
from constructs import Construct

from infra.config import NetworkConfig


class NetworkConstruct(Construct):
    def __init__(self, scope: Construct, construct_id: str, *, config: NetworkConfig) -> None:
        super().__init__(scope, construct_id)
        self.config = config
        self.public_subnet_selection = ec2.SubnetSelection(subnet_type=ec2.SubnetType.PUBLIC)
        self.private_subnet_selection = ec2.SubnetSelection(
            subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS
        )
        self.vpc = ec2.Vpc(
            self,
            "Vpc",
            ip_addresses=ec2.IpAddresses.cidr(config.vpc_cidr),
            max_azs=config.max_azs,
            nat_gateways=config.nat_gateways,
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name="Public",
                    subnet_type=ec2.SubnetType.PUBLIC,
                    cidr_mask=24,
                ),
                ec2.SubnetConfiguration(
                    name="Private",
                    subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS,
                    cidr_mask=24,
                ),
            ],
        )
        self.alb_security_group = ec2.SecurityGroup(
            self,
            "AlbSecurityGroup",
            vpc=self.vpc,
            allow_all_outbound=True,
        )
        self.runtime_service_security_group = ec2.SecurityGroup(
            self,
            "RuntimeServiceSecurityGroup",
            vpc=self.vpc,
            allow_all_outbound=True,
        )
        self.token_service_security_group = ec2.SecurityGroup(
            self,
            "TokenServiceSecurityGroup",
            vpc=self.vpc,
            allow_all_outbound=True,
        )
        self.db_proxy_security_group = ec2.SecurityGroup(
            self,
            "DatabaseProxySecurityGroup",
            vpc=self.vpc,
            allow_all_outbound=False,
        )
        self.database_security_group = ec2.SecurityGroup(
            self,
            "DatabaseSecurityGroup",
            vpc=self.vpc,
            allow_all_outbound=False,
        )

        self.alb_security_group.add_ingress_rule(
            ec2.Peer.any_ipv4(),
            ec2.Port.tcp(443),
            "allow public https ingress",
        )
        self.runtime_service_security_group.add_ingress_rule(
            self.alb_security_group,
            ec2.Port.tcp(config.runtime_container_port),
            "allow alb to reach runtime service",
        )
        self.db_proxy_security_group.add_ingress_rule(
            self.runtime_service_security_group,
            ec2.Port.tcp(5432),
            "allow runtime service to reach db proxy",
        )
        self.db_proxy_security_group.add_ingress_rule(
            self.token_service_security_group,
            ec2.Port.tcp(5432),
            "allow token service lambda to reach db proxy",
        )
        self.db_proxy_security_group.add_egress_rule(
            self.database_security_group,
            ec2.Port.tcp(5432),
            "allow db proxy to reach aurora",
        )
        self.database_security_group.add_ingress_rule(
            self.db_proxy_security_group,
            ec2.Port.tcp(5432),
            "allow db proxy to reach aurora",
        )
