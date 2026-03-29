from __future__ import annotations

from typing import Protocol, runtime_checkable

from models.domain import AuditEventRecord, UsageEventRecord


@runtime_checkable
class UsageRepository(Protocol):
    def record_usage(self, event: UsageEventRecord) -> None: ...

    def record_audit(self, event: AuditEventRecord) -> None: ...

