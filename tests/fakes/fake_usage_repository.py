from __future__ import annotations

from models.domain import AuditEventRecord, UsageEventRecord


class InMemoryUsageRepository:
    def __init__(self) -> None:
        self.usage_events: list[UsageEventRecord] = []
        self.audit_events: list[AuditEventRecord] = []

    def record_usage(self, event: UsageEventRecord) -> None:
        self.usage_events.append(event)

    def record_audit(self, event: AuditEventRecord) -> None:
        self.audit_events.append(event)
