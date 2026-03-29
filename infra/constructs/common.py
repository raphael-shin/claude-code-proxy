from __future__ import annotations

from aws_cdk import aws_apigateway as apigateway
from aws_cdk import aws_logs as logs
from constructs import Construct


def retention_days(value: int) -> logs.RetentionDays:
    mapping = {
        7: logs.RetentionDays.ONE_WEEK,
        14: logs.RetentionDays.TWO_WEEKS,
        30: logs.RetentionDays.ONE_MONTH,
        60: logs.RetentionDays.TWO_MONTHS,
        90: logs.RetentionDays.THREE_MONTHS,
        120: logs.RetentionDays.FOUR_MONTHS,
        180: logs.RetentionDays.SIX_MONTHS,
        365: logs.RetentionDays.ONE_YEAR,
    }
    try:
        return mapping[value]
    except KeyError as error:
        supported = ", ".join(str(key) for key in sorted(mapping))
        raise ValueError(f"unsupported log retention days: {value}; supported: {supported}") from error


def make_rest_api(
    scope: Construct,
    construct_id: str,
    *,
    log_group: logs.LogGroup,
    stage_name: str,
    throttling_rate_limit: float,
    throttling_burst_limit: int,
) -> apigateway.RestApi:
    return apigateway.RestApi(
        scope,
        construct_id,
        endpoint_types=[apigateway.EndpointType.REGIONAL],
        deploy_options=apigateway.StageOptions(
            stage_name=stage_name,
            throttling_rate_limit=throttling_rate_limit,
            throttling_burst_limit=throttling_burst_limit,
            access_log_destination=apigateway.LogGroupLogDestination(log_group),
            access_log_format=apigateway.AccessLogFormat.json_with_standard_fields(
                caller=True,
                http_method=True,
                ip=True,
                protocol=True,
                request_time=True,
                resource_path=True,
                response_length=True,
                status=True,
                user=True,
            ),
        ),
    )
