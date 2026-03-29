from __future__ import annotations

import time
from datetime import datetime, timezone

import boto3
import pytest
from testcontainers.core.container import DockerContainer

from models.domain import VirtualKeyCacheEntry, VirtualKeyStatus
from repositories.virtual_key_repository import Boto3DynamoDbTable, DynamoDbVirtualKeyCache


def _build_dynamodb_resource(endpoint_url: str):
    return boto3.resource(
        "dynamodb",
        endpoint_url=endpoint_url,
        region_name="us-east-1",
        aws_access_key_id="fake",
        aws_secret_access_key="fake",
    )


@pytest.fixture()
def dynamodb_table():
    container = (
        DockerContainer("amazon/dynamodb-local:latest")
        .with_exposed_ports(8000)
        .with_command("-jar DynamoDBLocal.jar -inMemory -sharedDb")
    )
    with container:
        endpoint_url = f"http://{container.get_container_host_ip()}:{container.get_exposed_port(8000)}"

        dynamodb = _build_dynamodb_resource(endpoint_url)
        for _ in range(20):
            try:
                table = dynamodb.create_table(
                    TableName="virtual-key-cache",
                    KeySchema=[{"AttributeName": "user_id", "KeyType": "HASH"}],
                    AttributeDefinitions=[{"AttributeName": "user_id", "AttributeType": "S"}],
                    BillingMode="PAY_PER_REQUEST",
                )
                table.wait_until_exists()
                yield table
                break
            except Exception:
                time.sleep(0.5)
        else:
            raise RuntimeError("DynamoDB Local container did not become ready in time.")


def test_dynamodb_cache_stores_only_non_plaintext_fields_with_local_emulator(dynamodb_table) -> None:
    repository = DynamoDbVirtualKeyCache(Boto3DynamoDbTable(dynamodb_table))
    entry = VirtualKeyCacheEntry(
        user_id="user-1",
        virtual_key_id="key-1",
        encrypted_key_ref="enc::vk_cached",
        key_prefix="vk_cached",
        status=VirtualKeyStatus.ACTIVE,
        ttl=1000,
    )

    repository.put_active_key(entry)

    raw_item = dynamodb_table.get_item(Key={"user_id": "user-1"})["Item"]
    assert set(raw_item.keys()) == {
        "user_id",
        "virtual_key_id",
        "encrypted_key_ref",
        "key_prefix",
        "status",
        "ttl",
    }
    assert raw_item["encrypted_key_ref"] == "enc::vk_cached"
    assert raw_item["key_prefix"] == "vk_cached"
    assert raw_item["status"] == "active"
    assert int(raw_item["ttl"]) == 1000
    assert repository.get_active_key("missing-user", datetime(2026, 1, 1, tzinfo=timezone.utc)) is None


def test_dynamodb_cache_miss_is_not_interpreted_as_user_absence(dynamodb_table) -> None:
    repository = DynamoDbVirtualKeyCache(Boto3DynamoDbTable(dynamodb_table))

    result = repository.get_active_key("unknown-user", datetime.now(timezone.utc))

    assert result is None
