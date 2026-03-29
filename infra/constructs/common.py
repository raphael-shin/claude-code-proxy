from __future__ import annotations

from aws_cdk import aws_logs as logs


def retention_days(value: int) -> logs.RetentionDays:
    mapping = {
        14: logs.RetentionDays.TWO_WEEKS,
        30: logs.RetentionDays.ONE_MONTH,
        90: logs.RetentionDays.THREE_MONTHS,
    }
    try:
        return mapping[value]
    except KeyError as error:
        supported = ", ".join(str(key) for key in sorted(mapping))
        raise ValueError(f"unsupported log retention days: {value}; supported: {supported}") from error
