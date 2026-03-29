from __future__ import annotations

from repositories.admin_identity_repository import AdminIdentityRepository
from repositories.model_alias_repository import ModelAliasRepository
from repositories.model_route_repository import ModelRouteRepository
from repositories.policy_repository import PolicyRepository
from repositories.pricing_repository import PricingRepository
from repositories.usage_repository import UsageRepository
from repositories.user_repository import PostgresUserRepository, UserRepository
from repositories.virtual_key_repository import DynamoDbVirtualKeyCache, PostgresVirtualKeyRepository, VirtualKeyAuthRepository, VirtualKeyCacheRepository, VirtualKeyLedgerRepository
from tests.fakes import FakeDynamoDbTable, FakePostgresConnection, InMemoryPricingRepository, InMemoryUserRepository, InMemoryVirtualKeyCacheRepository, InMemoryVirtualKeyLedgerRepository


class StubPolicyRepository:
    def list_policies_for_subject(self, *, user_id: str, groups: tuple[str, ...], department: str | None):
        return []

    def list_budget_policies_for_subject(self, *, user_id: str, team_ids: tuple[str, ...]):
        return []


class StubModelAliasRepository:
    def list_alias_rules(self):
        return []


class StubModelRouteRepository:
    def list_model_routes(self):
        return []


class StubUsageRepository:
    def record_usage(self, event):
        return None

    def record_audit(self, event):
        return None


class StubPricingRepository:
    def get_active_pricing(self, *, model_id: str, at_date=None):
        return None

    def reload(self):
        return None


class StubAdminIdentityRepository:
    def get_admin_role(self, principal_id: str):
        return None


def test_repository_protocols_are_runtime_checkable() -> None:
    postgres = FakePostgresConnection()
    dynamodb = FakeDynamoDbTable()

    assert isinstance(InMemoryUserRepository(), UserRepository)
    assert isinstance(PostgresUserRepository(postgres), UserRepository)
    assert isinstance(InMemoryVirtualKeyLedgerRepository(), VirtualKeyLedgerRepository)
    assert isinstance(PostgresVirtualKeyRepository(postgres), VirtualKeyLedgerRepository)
    assert isinstance(InMemoryVirtualKeyLedgerRepository(), VirtualKeyAuthRepository)
    assert isinstance(PostgresVirtualKeyRepository(postgres), VirtualKeyAuthRepository)
    assert isinstance(InMemoryVirtualKeyCacheRepository(), VirtualKeyCacheRepository)
    assert isinstance(DynamoDbVirtualKeyCache(dynamodb), VirtualKeyCacheRepository)
    assert isinstance(StubAdminIdentityRepository(), AdminIdentityRepository)
    assert isinstance(StubPolicyRepository(), PolicyRepository)
    assert isinstance(StubModelAliasRepository(), ModelAliasRepository)
    assert isinstance(StubModelRouteRepository(), ModelRouteRepository)
    assert isinstance(StubUsageRepository(), UsageRepository)
    assert isinstance(StubPricingRepository(), PricingRepository)
    assert isinstance(InMemoryPricingRepository(), PricingRepository)
