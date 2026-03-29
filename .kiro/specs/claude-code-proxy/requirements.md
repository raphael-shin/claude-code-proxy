# Requirements Document

## Introduction

본 문서는 Claude Code 사용자를 위한 조직 표준 인증 및 중앙 통제 프록시 시스템인 **Claude Code Proxy**의 요구사항을 정의한다.

이 시스템은 조직의 SSO 기반 인증, Virtual Key를 통한 프록시 접근 제어, 사용자/팀/부서 단위 정책 및 quota 관리, Amazon Bedrock 중앙 호출 통제, 감사 로깅을 통합하여 Claude Code의 안전하고 통제된 사용을 보장한다.

## Glossary

- **Claude_Code**: Anthropic이 제공하는 AI 코딩 어시스턴트 클라이언트
- **apiKeyHelper**: Claude Code가 요청 전 호출하는 스크립트로, Virtual Key를 자동 획득하여 반환하는 헬퍼
- **Virtual_Key**: Claude Code가 LLM Proxy를 호출하기 위해 사용하는 opaque access key (JWT가 아닌 서버 조회형 키)
- **Token_Service**: API Gateway + Lambda로 구성된 서비스로, SSO 사용자를 검증하고 Virtual Key를 조회 또는 발급하는 bootstrap 계층
- **LLM_Proxy**: ALB 뒤에서 동작하는 FastAPI 기반 프록시 서비스로, Virtual Key 검증, 정책 평가, Bedrock 호출을 수행
- **Policy_Engine**: LLM Proxy 내부에서 사용자, 그룹, 부서, 모델 기준의 접근 정책을 평가하는 엔진
- **Quota_Engine**: LLM Proxy 내부에서 사용자 및 팀 단위 budget/quota를 평가하는 엔진
- **Model_Resolver**: 요청 모델명을 logical model로 변환하고, logical model을 실제 Bedrock Converse 모델 ID와 capability 집합으로 매핑하는 컴포넌트
- **IAM_Identity_Center**: AWS SSO 허브로, 조직 Active Directory와 연동하여 사용자 인증을 제공
- **DynamoDB_Cache**: Token Service의 Virtual Key lookup 캐시 역할을 하는 DynamoDB 테이블
- **Aurora_PostgreSQL**: Aurora PostgreSQL Serverless v2로, 사용자, Virtual Key, 정책, usage의 source of truth
- **ALB**: Application Load Balancer로, Claude Code의 추론 요청 진입점
- **Bedrock_Adapter**: LLM Proxy 내부에서 Anthropic 형식 요청을 Bedrock Converse API 형식으로 변환하는 어댑터
- **Admin_API**: 운영자가 사용자, 팀, 정책, 모델 매핑 등을 관리하는 관리용 API
- **Audit_Logger**: 요청, 응답 메타데이터, 정책 판단 결과, 토큰 사용량을 기록하는 감사 로깅 컴포넌트
- **user_id**: IAM Identity Center Identity Store의 stable UserId로, 시스템 전체에서 사용자를 식별하는 표준 키
- **SigV4**: AWS Signature Version 4 서명 방식으로, API Gateway IAM Auth 호출 시 사용

## Requirements

### Requirement 1: SSO 기반 사용자 인증

**User Story:** 개발자로서, 조직 SSO 한 번의 로그인으로 Claude Code를 사용할 수 있기를 원한다. 이를 통해 별도의 정적 API key를 관리하지 않아도 된다.

#### Acceptance Criteria

1. WHEN 사용자가 Claude_Code를 실행하면, THE Claude_Code SHALL apiKeyHelper를 호출하여 Virtual_Key를 요청한다.
2. WHEN apiKeyHelper가 Virtual_Key를 요청받으면, THE apiKeyHelper SHALL 로컬 캐시에 유효한 Virtual_Key가 있는지 확인한다.
3. WHILE 로컬 캐시에 유효한 Virtual_Key가 존재하면, THE apiKeyHelper SHALL 해당 Virtual_Key를 즉시 반환한다.
4. WHEN 로컬 캐시에 유효한 Virtual_Key가 없으면, THE apiKeyHelper SHALL 사용자의 SSO 세션 기반 AWS 임시 자격증명을 사용하여 Token_Service endpoint를 SigV4 서명으로 호출한다.
5. WHEN 사용자의 SSO 세션이 만료되었으면, THE apiKeyHelper SHALL `aws sso login` 재인증이 필요하다는 안내를 출력하고 빠르게 실패한다.
6. THE Claude_Code SHALL 정적 API key 대신 apiKeyHelper를 통해 동적 Virtual_Key만 사용한다.
7. THE apiKeyHelper SHALL 반환된 Virtual_Key를 로컬 캐시에 저장하고, 캐시 TTL은 5분에서 15분 범위로 설정한다.

### Requirement 2: Token Service 인증 및 사용자 식별

**User Story:** 보안 엔지니어로서, Token Service가 실제 조직 SSO 사용자만 Virtual Key를 획득할 수 있도록 보장하기를 원한다. 이를 통해 미인증 접근을 차단할 수 있다.

#### Acceptance Criteria

1. THE Token_Service API Gateway SHALL IAM Auth를 사용하여 모든 요청의 AWS 임시 자격증명을 검증한다.
2. WHEN 유효한 SigV4 서명이 없는 요청이 수신되면, THE Token_Service API Gateway SHALL 해당 요청을 거부하고 인증 실패를 반환한다.
3. WHEN 유효한 요청이 Lambda에 전달되면, THE Token_Service SHALL requestContext.identity.userArn에서 호출자 ARN을 추출한다.
4. WHEN 호출자 ARN이 추출되면, THE Token_Service SHALL ARN에서 username을 파싱하고 Aurora_PostgreSQL의 identity_user_mappings 테이블에서 user_id를 조회한다.
5. IF identity_user_mappings에 해당 username 매핑이 존재하지 않으면, THEN THE Token_Service SHALL 요청을 거부하고 사용자 미등록 오류를 반환한다.
6. THE Token_Service SHALL 모든 요청에 고유한 request ID를 부여한다.
7. THE Token_Service API Gateway SHALL rate limiting과 burst control을 지원한다.

### Requirement 3: Virtual Key 생명주기 관리

**User Story:** 플랫폼 엔지니어로서, Virtual Key가 안전하게 발급, 재사용, 폐기되기를 원한다. 이를 통해 키 남용을 방지하고 운영 통제를 유지할 수 있다.

#### Acceptance Criteria

1. WHEN Token_Service가 user_id를 결정하면, THE Token_Service SHALL DynamoDB_Cache에서 해당 user_id 기준으로 Virtual_Key 캐시를 조회한다.
2. WHILE DynamoDB_Cache에 유효한 active Virtual_Key가 존재하면, THE Token_Service SHALL 해당 Virtual_Key를 반환한다.
3. WHEN DynamoDB_Cache에 캐시가 없으면, THE Token_Service SHALL Aurora_PostgreSQL에서 해당 user row 존재 여부를 확인한다.
4. IF Aurora_PostgreSQL에 해당 user row가 존재하지 않으면, THEN THE Token_Service SHALL 요청을 거부하고 사용자 미등록 오류를 반환한다.
5. IF 해당 user row가 존재하지만 proxy_access_enabled가 false이면, THEN THE Token_Service SHALL 요청을 거부하고 접근 권한 없음 오류를 반환한다.
6. WHEN Aurora_PostgreSQL에 기존 active Virtual_Key가 존재하면, THE Token_Service SHALL 해당 Virtual_Key를 재사용하고 DynamoDB_Cache를 갱신한다.
7. WHEN Aurora_PostgreSQL에 기존 active Virtual_Key가 존재하지 않고 사용자가 허용 대상이면, THE Token_Service SHALL 새 Virtual_Key를 발급하고 Aurora_PostgreSQL에 저장한 뒤 DynamoDB_Cache를 갱신한다.
8. THE Token_Service SHALL Virtual_Key를 Aurora_PostgreSQL에 저장할 때 평문이 아닌 key_hash와 encrypted_key_blob 형태로 저장한다.
9. WHEN 운영자가 Virtual_Key revoke를 요청하면, THE Admin_API SHALL 해당 Virtual_Key의 상태를 revoked로 변경하고 DynamoDB_Cache 삭제와 LLM_Proxy auth cache 무효화를 함께 수행한다.
10. WHEN 운영자가 Virtual_Key rotate를 요청하면, THE Admin_API SHALL 기존 Virtual_Key를 비활성화하고 새 Virtual_Key를 발급한 뒤 캐시를 갱신한다.
11. WHEN 운영자가 Virtual_Key disable을 요청하면, THE Admin_API SHALL 해당 Virtual_Key의 상태를 disabled로 변경하고 캐시 무효화를 수행한다.
12. THE Token_Service SHALL DynamoDB_Cache TTL을 기본 15분, 최대 1시간으로 설정한다.

### Requirement 4: LLM Proxy Virtual Key 검증 및 사용자 컨텍스트 복원

**User Story:** 보안 엔지니어로서, LLM Proxy가 모든 요청에서 Virtual Key를 검증하고 신뢰할 수 있는 사용자 컨텍스트를 복원하기를 원한다. 이를 통해 위조된 요청을 차단할 수 있다.

#### Acceptance Criteria

1. WHEN Claude_Code가 요청을 보내면, THE Claude_Code SHALL Authorization: Bearer <virtual_key> 헤더에 Virtual_Key를 포함하여 ALB를 통해 LLM_Proxy를 호출한다.
2. WHEN LLM_Proxy가 요청을 수신하면, THE LLM_Proxy SHALL Authorization 헤더에서 Virtual_Key를 추출하고 해시하여 Aurora_PostgreSQL 또는 auth cache에서 검증한다.
3. IF Virtual_Key가 유효하지 않거나 revoked 또는 disabled 상태이면, THEN THE LLM_Proxy SHALL 요청을 거부하고 인증 실패를 반환한다.
4. WHEN Virtual_Key 검증이 성공하면, THE LLM_Proxy SHALL 해당 Virtual_Key에 연결된 user_id를 최종 사용자 식별자로 사용하고, email, groups, department를 포함한 요청 컨텍스트를 복원한다.
5. THE LLM_Proxy SHALL 클라이언트가 임의로 추가한 X-User 헤더, body 내 사용자 정보, 검증되지 않은 토큰 payload를 신뢰하지 않는다.
6. IF user_id가 복원되지 않으면, THEN THE LLM_Proxy SHALL 요청을 거부한다.
7. THE LLM_Proxy SHALL auth cache TTL을 30초에서 60초로 설정한다.

### Requirement 5: 정책 기반 인가

**User Story:** 플랫폼 엔지니어로서, 사용자, 그룹, 부서, 모델 기준으로 세밀한 접근 정책을 적용하기를 원한다. 이를 통해 조직의 보안 및 비용 정책을 강제할 수 있다.

#### Acceptance Criteria

1. WHEN LLM_Proxy가 사용자 컨텍스트를 복원하면, THE Policy_Engine SHALL 다음 순서로 정책을 평가한다: 사용자 상태 확인, 모델 정책 평가, budget/quota 평가, rate limit 평가.
2. IF 사용자가 비활성 상태이거나 proxy_access_enabled가 false이면, THEN THE Policy_Engine SHALL 요청을 즉시 거부한다.
3. THE Policy_Engine SHALL 모델 정책을 user, group, department, global default 순서로 평가한다.
4. WHEN 동일 항목에 여러 정책이 존재하면, THE Policy_Engine SHALL deny가 allow보다 우선하는 규칙을 적용하고, 가장 보수적인 값을 최종 effective policy로 결정한다.
5. IF groups 또는 department 정보가 누락되면, THEN THE Policy_Engine SHALL 보수적으로 동작한다.
6. IF 정책 위반이 감지되면, THEN THE LLM_Proxy SHALL Bedrock 호출 전에 요청을 차단하고 사용자에게 이해 가능한 차단 사유 메시지를 반환한다.
7. THE Policy_Engine SHALL 요청 크기, 최대 출력 토큰, 허용 기능 등을 정책으로 제한할 수 있다.
8. THE LLM_Proxy SHALL 사용자별 rate limit을 지원한다.

### Requirement 6: Budget 및 Quota 관리

**User Story:** FinOps 담당자로서, 사용자 및 팀 단위로 일간/월간 budget과 quota를 설정하고 soft_limit 및 hard_limit를 관리하기를 원한다. 이를 통해 비용을 통제할 수 있다.

#### Acceptance Criteria

1. THE Quota_Engine SHALL 사용자별 일간 및 월간 기준의 budget/quota를 확인한다.
2. THE Quota_Engine SHALL 팀별 일간 및 월간 기준의 budget/quota를 확인한다.
3. THE Quota_Engine SHALL 전역 default budget policy가 구성된 경우 이를 함께 평가한다.
4. THE Quota_Engine SHALL soft_limit와 hard_limit를 지원한다.
5. THE Quota_Engine SHALL soft_limit를 운영 설정값으로 저장 및 조회할 수 있으나, 현재 런타임 차단 기준으로 사용하지 않는다.
6. WHEN 사용량이 hard_limit에 도달하면, THE Quota_Engine SHALL 요청을 차단하고 THE LLM_Proxy SHALL Bedrock 호출 전에 요청을 종료한다.
7. WHEN 사용자 단위 policy, 팀 단위 policy, 전역 default policy가 동시에 존재하면, THE Quota_Engine SHALL 가장 보수적인 정책(가장 낮은 hard_limit, 가장 낮은 budget limit)을 최종 결정으로 적용한다.
8. THE Quota_Engine SHALL budget metric으로 tokens와 cost_usd를 지원한다.
9. THE Quota_Engine SHALL 비용 산정 시 model_pricing_catalog의 요청 시점 단가 snapshot을 사용하여 estimated_input_cost_usd, estimated_output_cost_usd, estimated_cache_write_cost_usd, estimated_cache_read_cost_usd, estimated_total_cost_usd를 계산한다.
10. WHEN 동일 사용자에게 여러 팀 policy가 적용되면, THE Quota_Engine SHALL 가장 보수적인 정책(가장 낮은 hard_limit, 가장 낮은 budget limit)을 적용한다.
11. THE model_pricing_catalog SHALL 초기 구현에서 Admin_API 또는 운영 CLI를 통해서만 갱신되며, 외부 vendor pricing 자동 동기화는 현재 범위에 포함하지 않는다.
12. THE Quota_Engine SHALL 요청 admission과 usage snapshot 계산에 동일한 활성 pricing row를 사용해야 하며, runtime은 이를 인메모리 cache로 제공하더라도 Admin_API 갱신 시 즉시 reload 할 수 있어야 한다.
13. THE Audit_Logger SHALL 각 usage event에 비용 계산에 사용한 `pricing_catalog_id` 또는 동등한 immutable pricing snapshot reference를 함께 기록한다.

### Requirement 7: 모델 라우팅 및 Bedrock 호출

**User Story:** 플랫폼 엔지니어로서, Claude Code의 모델 요청을 Bedrock의 실제 모델로 자동 매핑하고, Proxy 서비스 역할로만 Bedrock를 호출하기를 원한다. 이를 통해 사용자에게 Bedrock 직접 권한을 부여하지 않아도 된다.

#### Acceptance Criteria

1. WHEN Claude_Code가 모델명을 포함한 요청을 보내면, THE Model_Resolver SHALL 요청 모델명을 logical model로 변환하고, logical model을 실제 Bedrock Converse 모델 ID로 매핑한다.
2. THE Model_Resolver SHALL 매핑 결과에 최소한 `bedrock_api_route=converse`, `bedrock_model_id`, `aws_region_name` 또는 cross-region inference profile, `supports_native_structured_output`, `supports_reasoning`, `supports_prompt_cache_ttl`, `supports_disable_parallel_tool_use` capability를 포함한다.
3. IF 요청 모델명이 허용 모델 목록에 없거나 Bedrock Converse 지원 모델이 아니면, THEN THE LLM_Proxy SHALL 요청을 거부한다.
4. THE LLM_Proxy SHALL Bedrock runtime 호출에 `Converse` 또는 `ConverseStream`만 사용하고 `InvokeModel` 계열 경로를 사용하지 않는다.
5. THE Bedrock_Adapter SHALL Anthropic 호환 inbound 요청을 Bedrock `Converse` 또는 `ConverseStream` 요청 형식으로 변환한다.
6. THE Bedrock_Adapter SHALL Bedrock `Converse` 또는 `ConverseStream` 응답을 Anthropic 호환 response 또는 SSE stream으로 역변환한다.
7. THE Bedrock_Adapter SHALL structured output 처리에서 `supports_native_structured_output=true` 이고 명시적 JSON schema가 제공된 경우에만 Bedrock native `outputConfig.textFormat`을 사용한다.
8. THE Bedrock_Adapter SHALL native structured output용 schema를 Bedrock 요구사항에 맞게 정규화하고, 모든 object node에 `additionalProperties: false`를 재귀적으로 보장한다.
9. THE Bedrock_Adapter SHALL native structured output을 사용할 수 없는 경우 schema 없는 `json_object`를 포함한 unsupported structured output 요청을 Converse tool fallback 규칙으로 처리하거나, 운영 정책에 따라 명시적으로 거부하되 동작을 일관되게 유지한다.
10. THE Bedrock_Adapter SHALL reasoning 요청에서 외부 `reasoning_effort` 입력을 내부 canonical `thinking` 구성으로 정규화할 수 있어야 한다.
11. THE Bedrock_Adapter SHALL `thinking.budget_tokens`가 Bedrock 최소 요구치보다 작은 경우 이를 보정하거나 요청을 거부하되, 구현 선택은 전역적으로 일관되어야 한다.
12. THE Bedrock_Adapter SHALL reasoning이 활성화된 turn에서 forced tool choice를 허용하지 않으며, 필요 시 `auto`로 완화한다.
13. THE Bedrock_Adapter SHALL Bedrock 응답의 reasoning 관련 provider raw field와 함께 Anthropic 호환 `thinking_blocks`를 보존한다.
14. THE LLM_Proxy SHALL 후속 turn reasoning continuity를 위해 assistant history의 `thinking_blocks`를 보존하여 재전달해야 하며, 이전 reasoning turn의 `thinking_blocks`를 신뢰성 있게 복원할 수 없는 경우 reasoning을 비활성화해야 한다.
15. THE LLM_Proxy SHALL streaming 응답을 지원한다.
16. THE LLM_Proxy SHALL Bedrock 호출 시 Proxy 서비스 역할의 자격증명만 사용한다.
17. THE LLM_Proxy SHALL 사용자에게 Bedrock endpoint 직접 호출 권한을 부여하지 않는다.
18. WHEN 운영자가 모델 매핑을 변경하면, THE Admin_API SHALL 변경사항을 LLM_Proxy에 반영한다.
19. THE Model_Resolver SHALL Bedrock cross-region inference profile을 기본 target으로 사용할 수 있다.
20. THE Bedrock_Adapter SHALL provider usage metadata에 포함된 Bedrock 기준 `input_tokens`, `output_tokens`, `total_tokens`, `cache_write_input_tokens`, `cache_read_input_tokens`, `cache_details`를 non-streaming 및 streaming 응답 모두에서 보존한다. `total_tokens`는 provider가 반환한 의미를 그대로 유지하며, 내부에서 재계산하지 않는다.
21. THE LLM_Proxy SHALL 토큰 사용량 원장에 Bedrock provider usage 지표만을 단순 저장 기준으로 사용하고, 파생 또는 normalized token total을 별도 필수 컬럼으로 요구하지 않는다.
22. THE Bedrock_Adapter SHALL non-streaming response와 streaming SSE 모두에서 design.md에 정의된 Anthropic ↔ Converse 필드 매핑 계약을 일관되게 적용한다.

### Requirement 7A: Claude 4.5+ Feature Gate

**User Story:** 플랫폼 엔지니어로서, Claude 4.5+/4.6+ Bedrock Converse 모델에서만 열리는 기능을 별도 capability gate로 관리하기를 원한다. 이를 통해 route 지원 여부와 기능 지원 여부를 혼동하지 않도록 한다.

#### Acceptance Criteria

1. THE Model_Resolver SHALL Claude 4.5+/4.6+ 전용 capability를 일반 Converse 지원 여부와 분리해서 관리한다.
2. THE LLM_Proxy SHALL `supports_prompt_cache_ttl=true` 인 경우에만 `cache_control.ttl` 값 `5m` 또는 `1h`를 Bedrock 요청으로 전달한다.
3. THE LLM_Proxy SHALL `supports_disable_parallel_tool_use=true` 인 경우에만 `parallel_tool_calls=false`를 Bedrock `disable_parallel_tool_use=true` 규칙으로 변환한다.
4. THE LLM_Proxy SHALL Claude 4.5+/4.6+ capability gate를 모델명 substring 추론에만 의존하지 않고 resolver source of truth에서 관리할 수 있어야 한다.
5. THE LLM_Proxy SHALL route가 Converse라는 이유만으로 4.5+ feature gate를 자동 허용하지 않는다.

### Requirement 8: 감사 로깅 및 사용량 추적

**User Story:** 감사 담당자로서, 모든 요청의 인증, 인가, 모델 사용, 토큰 사용량, 정책 판단 결과를 추적할 수 있기를 원한다. 이를 통해 규제 대응과 보안 감사를 수행할 수 있다.

#### Acceptance Criteria

1. THE LLM_Proxy SHALL 모든 요청에 고유한 request_id를 부여한다.
2. THE Audit_Logger SHALL 각 요청에 대해 user_id, user_email, groups, 요청 모델, 해석된 모델, input_tokens, output_tokens, cache_write_input_tokens, cache_read_input_tokens, cache_details, total_tokens, 요청 시각, 정책 결과, denial_reason, latency_ms를 기록한다.
3. THE Audit_Logger SHALL 인증 실패와 정책 차단 이벤트를 별도로 기록한다.
4. THE Audit_Logger SHALL 최소한 auth_success, auth_failure, policy_denied, quota_hard_limit_blocked, virtual_key_rotated, virtual_key_revoked, model_route_resolved, user_provisioned, team_membership_changed 유형의 감사 이벤트를 기록한다.
5. THE Audit_Logger SHALL 감사 로그를 변경 불가능한 저장소 또는 중앙 로그 시스템으로 전달한다.
6. THE Audit_Logger SHALL 프롬프트 원문을 기본적으로 저장하지 않고, 감사 목적상 필요한 최소 메타데이터만 저장한다.
7. THE LLM_Proxy SHALL 사용자별 토큰 사용량과 비용 추정치를 usage_events에 집계하며, cache_write_input_tokens, cache_read_input_tokens, cache_details, estimated_cache_write_cost_usd, estimated_cache_read_cost_usd를 별도 필드로 보존한다.
8. WHEN Bedrock 호출 주체가 Proxy 역할이더라도, THE Audit_Logger SHALL 사용자 단위 추적이 가능하도록 사용자 식별 로그를 별도로 유지한다.
9. THE Audit_Logger와 usage_events SHALL 실제 Bedrock `Converse` 또는 `ConverseStream` 응답의 usage만 최종 토큰 사용량 source of truth로 사용하고, `/v1/messages/count_tokens` 결과로 최종 usage를 대체하거나 보정하지 않는다.
10. WHEN 사용자가 여러 팀에 속해 있으면, THE Audit_Logger SHALL 명시적 primary team membership이 있으면 그 team_id를 기록하고, primary 지정이 없고 active team이 하나뿐이면 그 team_id를 기록하며, 그 외에는 `NULL`을 기록한다.

### Requirement 9: 운영 관리

**User Story:** 플랫폼 엔지니어로서, 사용자, 팀, 정책, 모델 매핑, Virtual Key를 중앙에서 관리하기를 원한다. 이를 통해 운영 효율성을 확보할 수 있다.

#### Acceptance Criteria

1. THE Admin_API SHALL 사용자를 등록, 조회, 수정, 활성화, 비활성화할 수 있다.
2. THE Admin_API SHALL 팀을 생성, 조회, 수정, 활성화, 비활성화할 수 있다.
3. THE Admin_API SHALL 사용자와 팀의 membership을 관리(추가, 제거, 조회)할 수 있다.
4. THE Admin_API SHALL 사용자 단위, 팀 단위, 전역 default budget policy를 생성, 조회, 수정, 삭제할 수 있다.
5. THE Admin_API SHALL budget policy 생성 시 period_type(day, month), metric_type(tokens, cost_usd), limit_value, soft_limit_percent, hard_limit_percent를 설정할 수 있다.
6. THE Admin_API SHALL soft_limit_percent <= hard_limit_percent <= 100 검증을 수행한다.
7. THE Admin_API SHALL 모델 alias rule과 model route를 생성, 조회, 수정, 삭제할 수 있다.
8. THE Admin_API SHALL 특정 사용자, 그룹, 부서를 차단할 수 있다.
9. THE Admin_API SHALL 특정 모델을 전역 차단 또는 허용할 수 있다.
10. WHEN 운영자가 DynamoDB_Cache 무효화를 요청하면, THE Admin_API SHALL 캐시를 무효화하여 다음 apiKeyHelper 요청 시 Aurora_PostgreSQL 재조회가 수행되도록 한다.
11. THE Admin_API SHALL public runtime ALB와 분리된 전용 admin ingress에서 제공되어야 한다.
12. THE Admin_API SHALL 조직 SSO에서 얻은 AWS 임시 자격증명의 SigV4 요청과 API Gateway IAM Auth를 사용하여 운영자를 인증한다.
13. THE Admin_API SHALL PostgreSQL `admin_identities` allowlist를 source of truth로 사용하여 운영자 권한을 판별해야 하며, 최소 `operator`와 `auditor` role을 구분해야 한다.
14. THE Admin_API SHALL 사용자별, 팀별, 모델별 usage와 cost estimate를 조회할 수 있다.
15. THE Admin_API SHALL 감사 이벤트를 조회할 수 있다.

### Requirement 10: 사용자 프로비저닝

**User Story:** 플랫폼 엔지니어로서, 사용자를 명시적으로 등록하고 Identity Center user_id와 매핑하기를 원한다. 이를 통해 미등록 사용자의 자동 접근을 방지할 수 있다.

#### Acceptance Criteria

1. WHEN 운영자가 사용자를 등록하면, THE Admin_API SHALL users 테이블과 identity_user_mappings 테이블을 함께 생성한다.
2. THE Token_Service SHALL Aurora_PostgreSQL 원장에 없는 사용자를 자동 생성하지 않는다.
3. THE Admin_API SHALL 사용자 등록 시 user_id, email, display_name, department, cost_center, groups, proxy_access_enabled를 설정할 수 있다.
4. THE Admin_API SHALL identity_user_mappings에 username과 user_id의 매핑을 관리할 수 있다.
5. IF 비활성 상태의 사용자에 대해 새 budget policy 생성이 요청되면, THEN THE Admin_API SHALL 해당 요청을 거부한다.

### Requirement 11: 보안 요구사항

**User Story:** 보안 엔지니어로서, 시스템 전체에서 장기 비밀값 노출을 방지하고, 통신 경로를 보호하며, Virtual Key 남용을 탐지하기를 원한다. 이를 통해 보안 사고를 예방할 수 있다.

#### Acceptance Criteria

1. THE apiKeyHelper SHALL 사용자 단말에 장기 비밀값을 저장하지 않고, 세션 기반 Token_Service만 사용한다.
2. THE Token_Service SHALL Token_Service와 LLM_Proxy 간 통신 경로를 TLS로 보호한다.
3. THE LLM_Proxy SHALL Bedrock 호출 권한을 Proxy 서비스 역할에만 부여하고, 사용자에게는 Bedrock 직접 권한을 부여하지 않는다.
4. WHEN revoked 또는 blocked Virtual_Key로 요청이 수신되면, THE LLM_Proxy SHALL 해당 요청을 즉시 차단한다.
5. THE LLM_Proxy SHALL 동일 Virtual_Key의 비정상 반복 사용을 탐지할 수 있다.
6. WHEN Virtual_Key revoke, disable, rotate가 수행되면, THE Admin_API SHALL DynamoDB_Cache 삭제와 LLM_Proxy auth cache 무효화를 함께 수행하고, revoke 전파 목표는 p95 1분 이내로 한다.
7. THE LLM_Proxy SHALL IP 기반 rate limiting과 사용자 기반 rate limiting을 지원한다.
8. THE ALB SHALL TLS termination을 지원하고, WAF와 rate limiting을 함께 적용한다.
9. IF 인증 실패가 발생하면, THEN THE LLM_Proxy SHALL fail-open이 아닌 fail-closed로 동작한다.

### Requirement 12: 데이터 저장소 및 캐시 관리

**User Story:** 플랫폼 엔지니어로서, DynamoDB를 캐시로, Aurora PostgreSQL을 source of truth로 사용하여 데이터 일관성을 보장하기를 원한다. 이를 통해 캐시 미스 시에도 정확한 데이터를 제공할 수 있다.

#### Acceptance Criteria

1. THE Aurora_PostgreSQL SHALL 사용자, Virtual Key, 정책, usage_events, group/department 매핑, model_alias_rules, model_routes, budget_policies, model_pricing_catalog의 source of truth 역할을 수행한다.
2. THE DynamoDB_Cache SHALL Token_Service의 Virtual Key lookup 캐시 역할만 수행한다.
3. THE Token_Service SHALL DynamoDB_Cache 미스를 "사용자 없음"으로 해석하지 않고, 반드시 Aurora_PostgreSQL을 재조회한다.
4. THE DynamoDB_Cache SHALL user_id 기준 캐시 키와 Aurora_PostgreSQL의 users.id가 동일한 user_id를 사용한다.
5. IF DynamoDB_Cache의 사용자 식별자와 Aurora_PostgreSQL의 사용자 식별자가 일치하지 않으면, THEN THE Token_Service SHALL 기존 Virtual_Key 조회를 허용하지 않는다.
6. THE DynamoDB_Cache SHALL encrypted key reference만 저장하고, plaintext key를 저장하지 않는다.
7. THE Aurora_PostgreSQL application schema SHALL Alembic migration으로만 변경되어야 하며, CDK custom resource나 앱 startup DDL로 직접 변경하지 않는다.
8. THE deployed AWS environments SHALL Lambda와 ECS Fargate에서 Aurora로 연결할 때 RDS Proxy를 기본 경로로 사용하고, direct DB connection은 local/test harness에서만 허용한다.

### Requirement 13: 관측성 및 모니터링

**User Story:** 플랫폼 엔지니어로서, 서비스의 기본 health, metrics, logs를 통해 시스템 상태를 빠르게 파악하기를 원한다. 이를 통해 Proxy가 정상 동작하는지 확인하고 장애에 대응할 수 있다.

#### Acceptance Criteria

1. THE LLM_Proxy SHALL request count, error rate, p50/p95 latency와 같은 기본 runtime 메트릭을 제공한다.
2. THE Token_Service SHALL DynamoDB_Cache hit rate, error count, latency 메트릭을 제공한다.
3. THE ALB SHALL target health check와 기본 request/error 메트릭을 제공한다.
4. THE ECS Fargate service SHALL container log와 기본 서비스 메트릭을 제공한다.
5. THE LLM_Proxy SHALL 모든 실패를 correlation ID(request_id)와 함께 기록한다.

### Requirement 14: 장애 처리

**User Story:** 개발자로서, 시스템 장애 시 명확한 오류 메시지를 받고, 시스템이 보수적으로 동작하기를 원한다. 이를 통해 장애 상황에서도 보안이 유지된다.

#### Acceptance Criteria

1. WHEN apiKeyHelper가 Token_Service에 연결할 수 없으면, THE apiKeyHelper SHALL 명확한 오류 메시지와 함께 빠르게 실패한다.
2. WHEN DynamoDB_Cache 미스가 발생하면, THE Token_Service SHALL Aurora_PostgreSQL 재조회로 이어진다.
3. IF Aurora_PostgreSQL 연결 오류가 발생하면, THEN THE Token_Service SHALL 명확한 실패를 반환한다.
4. IF Aurora_PostgreSQL에 사용자가 없으면, THEN THE Token_Service SHALL 명확한 사용자 미등록 실패를 반환한다.
5. WHEN quota backend 실패가 발생하면, THE LLM_Proxy SHALL 환경별 정책에 따라 fail-open 또는 fail-closed로 동작한다.
6. IF Aurora_PostgreSQL 조회 장애 시 DynamoDB_Cache hit가 있더라도, THEN THE LLM_Proxy SHALL 운영 정책에 따라 보수적으로 동작할 수 있다.
7. THE LLM_Proxy SHALL 모든 실패를 correlation ID(request_id)와 함께 기록한다.
8. WHEN quota 초과 또는 정책 차단이 발생하면, THE LLM_Proxy SHALL 사용자에게 이해 가능한 차단 사유 메시지를 제공한다.

### Requirement 15: Public Runtime API

**User Story:** 개발자로서, Claude Code가 Anthropic 호환 API를 통해 LLM Proxy를 호출할 수 있기를 원한다. 이를 통해 기존 Claude Code 설정을 최소한으로 변경할 수 있다.

#### Acceptance Criteria

1. THE LLM_Proxy SHALL POST /v1/messages endpoint를 제공하여 Claude_Code의 기본 추론 요청을 처리한다.
2. THE LLM_Proxy SHALL POST /v1/messages/count_tokens endpoint를 제공하여 토큰 카운팅 요청을 처리한다.
3. THE LLM_Proxy SHALL GET /health endpoint를 제공하여 liveness probe를 지원한다.
4. THE LLM_Proxy SHALL GET /ready endpoint를 제공하여 DB 연결, resolver 초기화, 필수 dependency 상태를 확인하는 readiness probe를 지원한다.
5. THE LLM_Proxy SHALL Anthropic 호환 inbound API 형식을 유지한다.
6. THE LLM_Proxy SHALL 무중단 배포가 가능하다.
7. THE LLM_Proxy SHALL `/v1/messages/count_tokens`를 request validation, trimming, preflight estimation 용도로만 사용하고, 최종 usage ledger source로 사용하지 않는다.
8. THE LLM_Proxy SHALL `/v1/messages/count_tokens`에서 `/v1/messages`와 동일한 normalized Converse request mapping을 만든 뒤 Bedrock `CountTokens`의 `input.converse` 형식으로 호출해야 한다.
9. IF Bedrock `CountTokens` 호출이 실패하거나 지원되지 않으면, THEN THE LLM_Proxy SHALL local tokenizer나 heuristic fallback 없이 해당 실패를 그대로 반환해야 한다.

### Requirement 16: 성능 요구사항

**User Story:** 개발자로서, 인증 및 프록시 과정에서 체감 지연이 최소화되기를 원한다. 이를 통해 Claude Code 사용 경험이 저하되지 않는다.

#### Acceptance Criteria

1. WHILE apiKeyHelper 로컬 캐시가 유효하면, THE apiKeyHelper SHALL 100ms 이내에 Virtual_Key를 반환한다.
2. WHEN DynamoDB_Cache hit가 발생하면, THE Token_Service SHALL p95 200ms 이하로 응답한다.
3. THE LLM_Proxy SHALL streaming 응답을 지원하여 첫 토큰 응답 지연을 최소화한다.
4. THE Token_Service SHALL 무중단 배포가 가능하다.
