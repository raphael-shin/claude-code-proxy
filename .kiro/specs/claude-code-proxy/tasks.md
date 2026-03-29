# Implementation Plan: Claude Code Proxy

## Current State

- Spec source is limited to `requirements.md` and `design.md`.
- There is no production code, test suite, `plan.md`, or TODO inventory in the repository yet.
- Because the repo is still empty, the first plan must bias toward fast in-memory tests and a narrow vertical slice first, but AWS/CDK는 후속 optional work가 아니라 반드시 구현해야 하는 deliverable로 남겨둔다.

## Goal

- 등록되고 `proxy_access_enabled=true` 인 사용자가 Token Service를 통해 Virtual Key를 재사용 또는 발급받고, 그 키로 `POST /v1/messages`에 단일 non-streaming Anthropic 호환 요청을 보내면 Proxy가 인증, 모델 해석, 정책/쿼터/속도 제한 평가, Bedrock 어댑터 호출, 감사 기록까지 수행한 뒤 Anthropic 호환 응답을 반환한다.
- 인증, 인가, quota, rate limit 실패는 모두 Bedrock 호출 전에 fail-closed 로 끝나야 한다.
- 동일한 시스템이 AWS 위에서 `API Gateway + Lambda`, `ALB + ECS Fargate`, `Aurora + DynamoDB`, IAM/Secrets/basic CloudWatch log-metric wiring까지 CDK로 재현 가능해야 하며, 수동 콘솔 설정이 남지 않아야 한다.

## Design Alignment

- 구현 작업은 `design.md`의 `모듈 구조 및 코드베이스 골격 (권장)`을 기준으로 한다.
- 상위 패키지 경계는 먼저 고정한다: `api`, `models`, `token_service`, `proxy`, `repositories`, `security`, `scripts`, `infra`, `tests`.
- `api`는 transport/orchestration만 담당하고, Token Service와 Proxy의 공용 타입은 `models`로 올린다.
- 테스트 디렉터리는 production 구조를 따라가며, 초기 increment는 `tests/fakes` 기반 in-memory 검증을 기본으로 한다.
- `tests/fakes`는 unit/service contract의 기본 계층이고, `tests/repositories`는 Testcontainers PostgreSQL + DynamoDB Local 계열 emulator를 사용하는 storage-backed integration test 계층으로 분리한다.
- `infra`는 config schema placeholder가 아니라 CDK app/single stack/constructs를 담는 실제 구현 영역으로 취급한다.

## Tasks

- [x] 1. 코드베이스 골격 및 기반 설정
  - [x] 1.1 `design.md`의 모듈 구조를 따라 상위 패키지 골격(`api`, `models`, `token_service`, `proxy`, `repositories`, `security`, `scripts`, `infra`, `tests`)과 테스트 하위 디렉터리(`tests/api`, `tests/models`, `tests/token_service`, `tests/proxy`, `tests/bedrock_converse`, `tests/admin`, `tests/repositories`, `tests/security`, `tests/scripts`, `tests/iac`, `tests/observability`, `tests/perf`, `tests/fakes`)를 만들고 `pytest`, `pytest-asyncio`만 먼저 설정한다. Verify: `pytest -q`
  - [x] 1.2 Token Service와 Proxy가 공유하는 도메인 모델, 에러 envelope, request context 타입을 `models/`에 추가한다. 아직 AWS SDK나 실제 DB 연결은 넣지 않는다. Verify: `pytest tests/models -q`
  - [x] 1.3 PostgreSQL, DynamoDB, Bedrock, clock, request-id generator에 대한 in-memory fake를 `tests/fakes`에 만들고, production code는 이를 repository/service 경계를 통해 사용 가능하게 둔다. 첫 번째 vertical slice에서는 네트워크 없이 테스트가 돌아가야 한다. Verify: `pytest tests/fakes -q`
  - [x] 1.4 FastAPI 앱 팩토리와 dependency injection 슬롯을 `api/app.py`, `api/dependencies.py`에만 만든다. 라우팅의 실제 동작은 뒤의 behavioral increment에서 채운다. Verify: `pytest tests/api/test_app_factory.py -q`

- [x] 2. Security 모듈 구현
  - [x] 2.1 Test: `generate_virtual_key()`는 항상 `vk_` 접두사를 반환하고 `hash_virtual_key()`는 같은 입력에 항상 같은 해시를 반환한다. Code: `security/keys.py`에 key generator, hash, key prefix helper만 추가한다. Verify: `pytest tests/security/test_keys.py -q`. Refactor after green: key 길이와 encoding 상수를 한 곳으로 모은다. Covers: R3.8, R11.1.

- [x] 3. Token Service 구현
  - [x] 3.1 Test: Token Service는 API Gateway event의 `requestContext.identity.userArn`에서 username을 안정적으로 추출한다. Code: `token_service/identity.py`에 ARN parser만 추가한다. Verify: `pytest tests/token_service/test_identity.py -q`. Refactor after green: event parsing helper를 분리한다. Covers: R2.3, R2.4.
  - [x] 3.2 Test: username 매핑이 없으면 Token Service는 403 사용자 미등록 오류를 반환하고 key lookup이나 발급을 시도하지 않는다. Code: `token_service/handler.py`에 최소 handler와 `models/errors.py` 기반 error envelope 연결만 추가한다. Verify: `pytest tests/token_service/test_handler_unregistered_user.py -q`. Refactor after green: error response builder를 공용화한다. Covers: R2.5, R14.4.
  - [x] 3.3 Test: DynamoDB cache hit에 active key가 있으면 Token Service는 PostgreSQL lookup 없이 기존 key를 반환한다. Code: `token_service/issue_service.py`에 cache-first lookup만 추가한다. Verify: `pytest tests/token_service/test_issue_service_cache_hit.py -q`. Refactor after green: repository protocol을 도입한다. Covers: R3.1, R3.2, R12.2.
  - [x] 3.4 Test: DynamoDB cache miss는 사용자 부재를 의미하지 않으며 Token Service는 반드시 PostgreSQL에서 user row를 다시 조회한다. Code: `token_service/issue_service.py`에 fallback lookup을 추가한다. Verify: `pytest tests/token_service/test_issue_service_cache_miss_falls_back.py -q`. Refactor after green: cache miss branch를 작은 함수로 분리한다. Covers: R3.3, R12.3.
  - [x] 3.5 Test: PostgreSQL에 user row가 없거나 `proxy_access_enabled=false` 이면 Token Service는 새 key를 만들지 않고 403을 반환한다. Code: `issue_service`에 user gate만 추가한다. Verify: `pytest tests/token_service/test_issue_service_user_gate.py -q`. Refactor after green: denial reason enum을 도입한다. Covers: R3.4, R3.5, R10.2.
  - [x] 3.6 Test: PostgreSQL에 기존 active key가 있으면 Token Service는 복호화 후 그 key를 재사용하고 DynamoDB cache를 갱신한다. Code: `security/encryption.py`와 `issue_service`에 재사용 경로만 추가한다. Verify: `pytest tests/token_service/test_issue_service_reuses_existing_key.py -q`. Refactor after green: 암복호화 포트를 인터페이스로 분리한다. Covers: R3.6, R3.8, R12.6.
  - [x] 3.7 Test: 허용된 사용자에게 active key가 없으면 Token Service는 새 key를 발급하고 `key_hash`와 `encrypted_key_blob`만 저장한 뒤 cache를 갱신한다. Code: `issue_service`와 virtual key repository fake에 신규 발급 경로를 추가한다. Verify: `pytest tests/token_service/test_issue_service_issues_new_key.py -q`. Refactor after green: persistence payload builder를 분리한다. Covers: R3.7, R3.8, R3.12.
  - [x] 3.8 Structural: `repositories/` 경계에 user, admin identity, virtual key, policy, model route, usage/pricing repository protocol을 추가하고, FastAPI/Lambda/AWS SDK 타입이 repository 바깥으로 새지 않도록 import 규칙을 고정한다. Verify: `pytest tests/repositories/test_repository_protocols.py -q`
  - [x] 3.9 Test: PostgreSQL schema contract는 `users`, `identity_user_mappings`, `admin_identities`, `virtual_keys`, `teams`, `team_memberships`, `policies`, `budget_policies`, `model_alias_rules`, `model_routes`, `usage_events`, `audit_events`, `model_pricing_catalog`와 `key_hash` 인덱스 및 budget policy check constraint를 정의하며, `team_memberships`에는 `is_primary`, `model_routes`에는 `bedrock_api_route`, `bedrock_model_id`, `inference_profile_id`, `supports_native_structured_output`, `supports_reasoning`, `supports_prompt_cache_ttl`, `supports_disable_parallel_tool_use`가, `usage_events`에는 `pricing_catalog_id`, `cache_write_input_tokens`, `cache_read_input_tokens`, `cache_details`, `estimated_cache_write_cost_usd`, `estimated_cache_read_cost_usd`가, `model_pricing_catalog`에는 cache write/read 단가 컬럼이 포함된다. `virtual_keys`에는 `quota_policy_id`, `model_policy_id`를 만들지 않는다. Code: Alembic migration revision과 schema contract 파일을 최소 단위로 추가한다. Verify: `pytest tests/repositories/test_postgres_schema_contract.py -q`. Refactor after green: schema constants를 모듈화한다. Covers: R6.6, R8.1, R8.2, R12.1.
  - [x] 3.10 Test: PostgreSQL-backed `user_repository`, `admin_identity_repository`, `virtual_key_repository`는 fake와 같은 username mapping lookup, admin allowlist lookup, active key reuse, status persistence behavior를 만족한다. 이 테스트는 Testcontainers PostgreSQL로 실행한다. Code: `repositories/user_repository.py`, `repositories/admin_identity_repository.py`, `repositories/virtual_key_repository.py`에 PostgreSQL adapter를 추가한다. Verify: `pytest tests/repositories/test_postgres_repositories.py -q`. Refactor after green: SQL statement builder를 작은 함수로 분리한다. Covers: R2.4, R3.6, R3.7, R9.13, R12.1.
  - [x] 3.11 Test: DynamoDB-backed virtual key cache adapter는 plaintext key 없이 `encrypted_key_ref`, `key_prefix`, `status`, `ttl`만 저장하고, cache miss를 user absence로 해석하지 않는다. 이 테스트는 DynamoDB Local 계열 emulator를 사용한다. Code: `repositories/virtual_key_repository.py` 또는 별도 cache adapter에 DynamoDB 구현을 추가한다. Verify: `pytest tests/repositories/test_dynamodb_virtual_key_cache.py -q`. Refactor after green: cache payload serializer를 분리한다. Covers: R3.1, R3.12, R12.2, R12.3, R12.6.
  - [x] 3.12 Test: Token Service wiring은 `tests/fakes` 기반 repository 세트와 storage-backed repository 세트를 같은 service contract로 교체 가능하다. Code: `token_service/handler.py`, `token_service/issue_service.py`, `api/dependencies.py`에 composition slot만 추가한다. Verify: `pytest tests/token_service/test_repository_swap_contract.py -q`. Refactor after green: composition root를 한 파일로 모은다. Covers: R12.1, R12.2, R14.2, R14.3.

- [x] 4. Proxy Auth Service 구현
  - [x] 4.1 Test: Proxy는 missing, malformed, unknown, revoked, disabled Virtual Key를 모두 거부하고 Bedrock을 호출하지 않는다. Code: `proxy/auth.py`에 bearer parser와 key verification 최소 구현을 추가한다. Verify: `pytest tests/proxy/test_auth_rejects_invalid_keys.py -q`. Refactor after green: auth failure mapping을 공용 에러 타입으로 연결한다. Covers: R4.1, R4.2, R4.3, R11.4, R11.9.
  - [x] 4.2 Test: Proxy는 `X-User-*` 헤더나 body의 사용자 정보를 무시하고, 검증된 Virtual Key에서만 `user_id`, `email`, `groups`, `department`를 복원한다. Code: `models/context.py`, `proxy/context.py`, `proxy/auth.py`에 trusted context restoration만 추가한다. Verify: `pytest tests/proxy/test_auth_restores_trusted_context.py -q`. Refactor after green: request context builder를 추출한다. Covers: R4.4, R4.5, R4.6.

- [x] 5. Model Resolver 구현
  - [x] 5.1 Test: Model Resolver는 요청 모델명을 `logical_model`로 해석한 뒤 Bedrock Converse model ID와 capability bundle(`bedrock_api_route=converse`, region/profile, `supports_native_structured_output`, `supports_reasoning`, `supports_prompt_cache_ttl`, `supports_disable_parallel_tool_use`)로 매핑한다. Code: `proxy/model_resolver.py`에 alias rule match와 route lookup 최소 구현을 추가한다. Verify: `pytest tests/proxy/test_model_resolver_happy_path.py -q`. Refactor after green: priority sort helper를 분리한다. Covers: R7.1, R7.2, R7.19, R7A.1.
  - [x] 5.2 Test: 허용 모델 목록에 없는 요청 모델 또는 Bedrock Converse 미지원 모델은 Proxy가 즉시 거부한다. Code: `model_resolver.py`에 unknown/non-converse model denial만 추가한다. Verify: `pytest tests/proxy/test_model_resolver_rejects_unknown_model.py -q`. Refactor after green: resolver result 타입을 명시화한다. Covers: R7.3, R7.4.
  - [x] 5.3 Test: Claude 4.5+/4.6+ feature gate는 일반 Converse 지원 여부와 분리되어 resolver source of truth에서 결정된다. Code: `proxy/model_resolver.py`와 resolver repository contract에 feature gate 필드를 추가한다. Verify: `pytest tests/proxy/test_model_resolver_feature_gates.py -q`. Refactor after green: capability normalization helper를 분리한다. Covers: R7A.1, R7A.4, R7A.5.

- [x] 6. Policy Engine 구현
  - [x] 6.1 Test: Policy Engine은 비활성 사용자 또는 `proxy_access_enabled=false` 사용자를 다른 평가보다 먼저 거부한다. Code: `proxy/policy_engine.py`에 user status gate만 추가한다. Verify: `pytest tests/proxy/test_policy_engine_user_gate.py -q`. Refactor after green: evaluation trace 구조체를 추가한다. Covers: R5.1, R5.2.
  - [x] 6.2 Test: Policy Engine은 `user -> group -> department -> global` 순서를 결정적으로 따르고 `deny > allow` 및 가장 restrictive한 값을 적용한다. Code: `policy_engine.py`에 scope merge 로직만 추가한다. Verify: `pytest tests/proxy/test_policy_engine_resolution_order.py -q`. Refactor after green: merge rules를 pure function으로 분리한다. Covers: R5.3, R5.4, R5.5.

- [x] 7. Quota Engine 구현
  - [x] 7.1 Test: Quota Engine은 soft limit를 기록용으로만 다루고 hard limit 초과에서만 요청을 차단한다. Code: `proxy/quota_engine.py`에 single-policy evaluator만 추가한다. Verify: `pytest tests/proxy/test_quota_engine_soft_vs_hard.py -q`. Refactor after green: quota decision 모델을 공용화한다. Covers: R6.4, R6.5, R6.6.
  - [x] 7.2 Test: 사용자, 팀, 전역 budget policy가 동시에 있으면 Quota Engine은 가장 보수적인 정책을 선택한다. Code: `quota_engine.py`에 multi-scope merge만 추가한다. Verify: `pytest tests/proxy/test_quota_engine_conservative_merge.py -q`. Refactor after green: policy ordering helper를 분리한다. Covers: R6.1, R6.2, R6.3, R6.7, R6.10.
  - [x] 7.3 Test: Quota Engine은 활성 `model_pricing_catalog` row 하나를 선택해 admission cost 계산과 usage snapshot에 동일한 `pricing_catalog_id`를 사용하고, Admin API reload 이전/이후에 서로 다른 가격 row를 섞지 않는다. Code: `proxy/quota_engine.py`와 pricing repository cache contract를 확장한다. Verify: `pytest tests/proxy/test_quota_engine_pricing_snapshot.py -q`. Refactor after green: active pricing selector를 helper로 분리한다. Covers: R6.9, R6.11, R6.12, R6.13.

- [x] 8. Rate Limiter 구현
  - [x] 8.1 Test: 사용자별 분당 rate limit 초과 시 Proxy는 429와 `Retry-After`를 반환한다. Code: `proxy/rate_limiter.py`에 in-memory window limiter만 추가한다. Verify: `pytest tests/proxy/test_rate_limiter.py -q`. Refactor after green: clock injection을 추가한다. Covers: R5.8, R11.5.

- [ ] 9. Bedrock Adapter 구현
  - [ ] 9.1 Test: Anthropic 호환 요청의 최소 messages payload가 Bedrock Converse 요청으로 변환되며 adapter는 `system` 분리, text block 정규화, `tool_use`/`tool_result` 매핑을 포함한 design.md의 필드 매핑 계약을 만족하고, `Converse`/`ConverseStream` 이외의 runtime path를 사용하지 않는다. Code: `proxy/bedrock_converse/request_builder.py`에 non-streaming 최소 request mapping만 추가한다. Verify: `pytest tests/bedrock_converse/test_request_builder.py -q`. Refactor after green: field mapping table을 정리한다. Covers: R7.5, R7.6, R7.22, R15.5.
  - [ ] 9.2 Test: native structured output capability와 명시적 JSON schema가 있으면 adapter는 `outputConfig.textFormat`을 만들고 schema의 모든 object node에 `additionalProperties: false`를 재귀 주입한다. capability가 없거나 schema 없는 `json_object`이면 일관된 Converse tool fallback 또는 명시적 reject 규칙을 적용한다. Code: `proxy/bedrock_converse/request_builder.py`와 schema helper를 확장한다. Verify: `pytest tests/bedrock_converse/test_structured_output_mapping.py -q`. Refactor after green: schema normalization helper를 분리한다. Covers: R7.7, R7.8, R7.9.
  - [ ] 9.3 Test: reasoning 요청에서 adapter는 `reasoning_effort`를 canonical `thinking`으로 정규화하고, 최소 budget 규칙을 적용하며, reasoning 활성화 시 forced tool choice를 `auto`로 완화한다. Code: `proxy/bedrock_converse/request_builder.py`에 reasoning parameter mapper를 추가한다. Verify: `pytest tests/bedrock_converse/test_reasoning_mapping.py -q`. Refactor after green: reasoning normalization helper를 분리한다. Covers: R7.10, R7.11, R7.12.
  - [ ] 9.4 Test: Bedrock Converse 응답의 최소 payload가 Anthropic 호환 응답과 usage 정보로 역변환되며, usage에는 Bedrock 기준 `input_tokens`, `output_tokens`, `total_tokens`, `cache_write_input_tokens`, `cache_read_input_tokens`, `cache_details`만 포함된다. adapter는 normalized total이나 기타 파생 토큰 필드를 기본 응답 계약에 추가하지 않는다. reasoning 응답에서는 `thinking_blocks`와 provider raw reasoning field가 함께 보존된다. Code: `proxy/bedrock_converse/response_parser.py`에 minimal response mapping만 추가한다. Verify: `pytest tests/bedrock_converse/test_response_parser.py -q && pytest tests/bedrock_converse/test_reasoning_response_parser.py -q`. Refactor after green: stop reason mapper를 분리한다. Covers: R7.6, R7.13, R7.20, R7.21.
  - [ ] 9.5 Test: 후속 turn 요청 빌더는 assistant history의 `thinking_blocks`를 재전달하고, 이전 reasoning turn의 `thinking_blocks`를 신뢰성 있게 복원할 수 없으면 reasoning을 비활성화한다. Code: `proxy/bedrock_converse/request_builder.py`와 transcript normalizer를 확장한다. Verify: `pytest tests/bedrock_converse/test_thinking_blocks_continuity.py -q`. Refactor after green: transcript continuity policy를 helper로 분리한다. Covers: R7.14.

- [ ] 10. Public Runtime API 구현
  - [ ] 10.1 Test: `/v1/messages`는 인증 실패 시 resolver, policy, quota, rate limiter, bedrock을 호출하지 않고 Anthropic 호환 401 envelope를 반환한다. Code: `api/proxy_router.py`에 auth dependency와 최소 실패 매핑만 연결한다. Verify: `pytest tests/api/test_messages_requires_auth.py -q`. Refactor after green: auth dependency wrapper를 분리한다. Covers: R4.1, R4.3, R15.1.
  - [ ] 10.2 Test: 인증된 `/v1/messages` 요청은 pre-approved resolver/policy/quota/rate-limit stub과 bedrock stub을 통해 non-streaming Anthropic 호환 응답을 반환한다. Code: `api/proxy_router.py`에 happy-path orchestration만 추가한다. Verify: `pytest tests/api/test_messages_returns_response.py -q`. Refactor after green: endpoint orchestration을 service 함수로 분리한다. Covers: R15.1, R15.5.
  - [ ] 10.3 Test: `/v1/messages`에서 policy, quota, rate limit 중 어느 단계가 deny 하더라도 Bedrock은 호출되지 않고 이해 가능한 차단 메시지와 `request_id`가 반환된다. Code: `api/proxy_router.py`와 `api/errors.py`에 fail-closed branch를 추가한다. Verify: `pytest tests/api/test_messages_fail_closed.py -q`. Refactor after green: denial-to-envelope 매핑을 공용화한다. Covers: R5.6, R6.6, R7.6, R14.8.
  - [ ] 10.4 Test: 성공한 `/v1/messages` 요청은 resolver -> policy -> quota -> rate limiter -> bedrock 순서로 각 의존성을 정확히 한 번씩 호출한다. Code: `api/proxy_router.py`에 호출 순서 고정만 추가한다. Verify: `pytest tests/api/test_messages_pipeline_order.py -q`. Refactor after green: orchestration trace helper를 분리한다. Covers: R5.1, R7.1, R15.1.
  - [ ] 10.5 Test: `/health`는 항상 200을 반환하고 `/ready`는 DB/resolver/dependency 상태에 따라 green/red를 구분한다. Code: `api/health_router.py`와 readiness probe 최소 구현을 추가한다. Verify: `pytest tests/api/test_health_and_ready.py -q`. Refactor after green: readiness dependency contract를 분리한다. Covers: R15.3, R15.4.
  - [ ] 10.6 Test: `/v1/messages/count_tokens`는 동일한 인증/모델 해석/Anthropic→Converse normalization 경로를 사용하고 Bedrock `CountTokens(input.converse=...)`를 호출해 Anthropic 호환 count 응답을 반환하되, 결과를 최종 usage ledger source로 기록하지 않는다. local tokenizer fallback은 허용하지 않는다. Code: `api/proxy_router.py` 또는 별도 router에 count endpoint 최소 구현을 추가한다. Verify: `pytest tests/api/test_count_tokens.py -q`. Refactor after green: request auth dependency를 공용화한다. Covers: R15.2, R15.7, R15.8, R15.9.

- [ ] 11. Streaming 지원
  - [ ] 11.1 Test: streaming 요청은 첫 SSE chunk를 전체 응답 버퍼링 없이 전달하고, `messageStart/contentBlockStart/contentBlockDelta/contentBlockStop/messageStop+metadata`를 Anthropic `message_start/content_block_start/content_block_delta/content_block_stop/message_delta/message_stop` framing으로 매핑한다. Code: `proxy/bedrock_converse/stream_decoder.py`와 streaming branch를 추가한다. Verify: `pytest tests/api/test_messages_streaming.py -q`. Refactor after green: chunk translator를 순수 함수로 분리한다. Covers: R7.4, R7.5, R7.22, R16.3.
  - [ ] 11.2 Test: streaming usage collector는 Bedrock ConverseStream의 최종 `metadata`/`usage` 이벤트에서 `input_tokens`, `output_tokens`, `total_tokens`, `cache_write_input_tokens`, `cache_read_input_tokens`, `cache_details`를 누락 없이 수집하고, cache 토큰 필드가 `None`이면 0으로 처리한다. `total_tokens`는 provider 값 그대로 유지한다. Code: `proxy/bedrock_converse/stream_decoder.py` 또는 별도 usage collector를 확장한다. Verify: `pytest tests/bedrock_converse/test_streaming_usage_collection.py -q`. Refactor after green: streaming usage merge 규칙을 helper로 분리한다. Covers: R7.4, R8.2.
  - [ ] 11.3 Test: streaming decoder는 reasoning이 포함된 ConverseStream 응답에서 `thinking_blocks`와 provider raw reasoning field를 손실 없이 수집해 Anthropic SSE로 전달한다. Code: `proxy/bedrock_converse/stream_decoder.py`를 확장한다. Verify: `pytest tests/bedrock_converse/test_streaming_reasoning_blocks.py -q`. Refactor after green: reasoning chunk accumulator를 helper로 분리한다. Covers: R7.13, R7.14.

- [ ] 12. Audit Logger 구현
  - [ ] 12.1 Test: Audit Logger는 `request_id`, 정책 결과, token usage를 기록하되 prompt 원문과 plaintext Virtual Key는 남기지 않고, `pricing_catalog_id`, `cache_write_input_tokens`, `cache_read_input_tokens`, `cache_details`, `estimated_cache_write_cost_usd`, `estimated_cache_read_cost_usd`를 usage ledger에 함께 남긴다. 토큰 원장은 Bedrock provider raw usage 필드만 저장하고 normalized total 같은 파생 토큰 필드는 추가하지 않는다. Code: `proxy/audit_logger.py`와 usage/audit repository를 추가한다. Verify: `pytest tests/proxy/test_audit_logger_redaction.py -q`. Refactor after green: redaction helper를 공용화한다. Covers: R8.1, R8.2, R8.3, R8.6.
  - [ ] 12.2 Test: 성공한 `/v1/messages` 요청은 실제 `Converse` / `ConverseStream` response mapping 이후 cache token/cost를 포함한 usage/audit record를 남기고, deny된 요청은 denial audit만 남긴다. `/v1/messages/count_tokens` 호출은 최종 usage_event를 만들지 않는다. Code: `proxy/audit_logger.py`와 `api/proxy_router.py` 사이의 audit wiring만 추가한다. Verify: `pytest tests/api/test_messages_audit_integration.py -q`. Refactor after green: endpoint audit hook을 분리한다. Covers: R8.1, R8.3, R8.4, R8.9.

- [ ] 13. CDK 앱 기반 구조
  - [ ] 13.1 Test: CDK app은 단일 `ClaudeCodeProxyStack`만 생성하고, 네트워크/데이터/bootstrap ingress/runtime ingress를 별도 stack이 아닌 construct 조합으로 포함한다. Code: `infra/app.py`, `infra/stack.py`, `infra/config.py`, `infra/constructs/` 골격을 추가한다. Verify: `pytest tests/iac/test_single_stack_composition.py -q && cdk synth`. Refactor after green: construct factory와 stack props 모델을 분리한다. Covers: R11.8, R15.6.
  - [ ] 13.2 Structural: 환경별 설정은 `app.py`에서 typed stack props로 조립해 `ClaudeCodeProxyStack`에 전달하고, CDK context나 임의 환경 변수에 애플리케이션 동작을 의존시키지 않는다. Code: `infra/config.py`와 `infra/app.py`에 profile -> stack props 경로를 추가한다. Verify: `pytest tests/iac/test_stack_props_config.py -q && cdk synth`. Refactor after green: profile loader와 validation model을 분리한다. Covers: R12.1, R13.4, R15.6.
  - [ ] 13.3 Structural: CDK 테스트는 `Template.from_stack` + `has_resource_properties`를 기본으로 하고, snapshot test를 보조로 추가한다. Code: `tests/iac/`의 공용 assertion helper와 snapshot fixture를 추가한다. Verify: `pytest tests/iac/test_cdk_test_harness.py -q`. Refactor after green: assertion helper를 공용 모듈로 분리한다.

- [ ] 14. Token Service Construct
  - [ ] 14.1 Test: `TokenServiceConstruct`는 API Gateway stage, IAM Auth, Lambda integration, invoke permission, access logs, throttling, TLS/WAF-ready 설정을 단일 stack 안에서 선언한다. Code: `infra/constructs/token_service_construct.py`를 추가하고 `infra/stack.py`에 연결한다. Verify: `pytest tests/iac/test_token_service_construct.py -q && cdk synth`. Refactor after green: API defaults와 route wiring helper를 분리한다. Covers: R2.1, R2.2, R2.7, R11.8.
  - [ ] 14.2 Structural: 배포 프로파일이 요구할 경우 API Gateway auth Lambda/request authorizer를 같은 stack의 optional construct로 붙일 수 있어야 하며, Virtual Key issuance logic은 Token Service Lambda에 남아 있어야 한다. Code: `infra/constructs/token_service_construct.py`에 optional authorizer hook을 추가한다. Verify: `pytest tests/iac/test_token_service_authorizer_profile.py -q && cdk synth`. Refactor after green: route auth config model을 분리한다. Covers: R2.1, R2.2, R11.8.
  - [ ] 14.3 Test: `AdminApiConstruct`는 public runtime ALB와 분리된 전용 API Gateway ingress, IAM Auth, access logs, throttling, 그리고 admin application integration 경로를 단일 stack 안에서 선언한다. Code: `infra/constructs/admin_api_construct.py`를 추가하고 `infra/stack.py`에 연결한다. Verify: `pytest tests/iac/test_admin_api_construct.py -q && cdk synth`. Refactor after green: admin route defaults와 auth wiring helper를 분리한다. Covers: R9.11, R9.12, R11.8.

- [ ] 15. Proxy Runtime / Data Plane Construct
  - [ ] 15.1 Test: `NetworkConstruct`와 `DataPlaneConstruct`는 VPC, subnet, security group, Aurora PostgreSQL Serverless v2, DB secret, RDS Proxy, DynamoDB cache table을 단일 stack 내부에 선언하고 cross-stack export 없이 참조된다. direct DB connection은 local/test harness를 제외한 배포 프로파일에서 허용하지 않는다. Code: `infra/constructs/network_construct.py`, `infra/constructs/data_plane_construct.py`를 추가한다. Verify: `pytest tests/iac/test_data_plane_construct.py -q && cdk synth`. Refactor after green: network/data props builder를 분리한다. Covers: R3.12, R11.2, R12.1, R12.2, R12.6, R12.8.
  - [ ] 15.2 Test: `ProxyRuntimeConstruct`는 ECS Cluster, TaskDefinition, Fargate Service, ALB listener/target group, `/health` health check, streaming-friendly idle timeout, private subnet placement를 단일 stack 안에서 선언한다. Code: `infra/constructs/proxy_runtime_construct.py`를 추가하고 `infra/stack.py`에 연결한다. Verify: `pytest tests/iac/test_proxy_runtime_construct.py -q && cdk synth`. Refactor after green: container/task/service props builder를 분리한다. Covers: R11.8, R15.3, R15.4, R15.6, R16.3.
  - [ ] 15.3 Test: Proxy runtime construct는 ACM HTTPS listener, WAF association, ECS rolling deployment/circuit breaker, autoscaling, CloudWatch log group을 선언하고 runtime endpoint metadata를 export한다. Code: `infra/constructs/proxy_runtime_construct.py`를 확장한다. Verify: `pytest tests/iac/test_proxy_runtime_edge_controls.py -q && cdk synth`. Refactor after green: listener/WAF/log defaults를 helper로 분리한다. Covers: R11.8, R13.1, R15.6, R16.3.
  - [ ] 15.4 Test: Token Service와 Proxy 관련 IAM은 가능한 한 `grant_*` 패턴으로 최소 권한을 부여하고, broad admin policy 또는 불필요한 수동 statement를 포함하지 않는다. Code: `infra/constructs/data_plane_construct.py`, `infra/constructs/token_service_construct.py`, `infra/constructs/proxy_runtime_construct.py`를 확장한다. Verify: `pytest tests/iac/test_iam_grants_and_least_privilege.py -q && cdk synth`. Refactor after green: IAM grant helper를 분리한다. Covers: R7.6, R7.7, R11.3, R11.8.

- [ ] 16. Minimal Ops / Security Guard
  - [ ] 16.1 Test: `ClaudeCodeProxyStack`는 ALB health check, CloudWatch log retention, API Gateway/Lambda/ALB/ECS 기본 메트릭 조회에 필요한 최소 운영 설정만 선언하며, 별도 tracing/OTEL/X-Ray 리소스는 만들지 않는다. Code: `infra/stack.py`와 관련 construct들을 확장한다. Verify: `pytest tests/iac/test_minimal_ops_defaults.py -q && cdk synth`. Refactor after green: log retention과 metric defaults를 helper로 분리한다. Covers: R13.1-R13.5, R15.3, R15.4.
  - [ ] 16.2 Structural: `cdk-nag` 또는 custom aspect를 사용해 public DB, public task IP, missing encryption, missing log retention 같은 배포 실수를 synth 단계에서 잡아야 한다. Code: `infra/aspects/security_guards.py` 또는 동등 모듈을 추가한다. Verify: `pytest tests/iac/test_security_guards.py -q && cdk synth`. Refactor after green: reusable aspect rules를 분리한다. Covers: R11.2-R11.9.

- [ ] 17. Admin API 구현
  - [ ] 17.1 Test: Admin API는 dedicated admin ingress에서 전달된 IAM-authenticated principal을 PostgreSQL `admin_identities` allowlist와 대조해 인증/인가하고, non-admin은 전체 차단, `auditor`는 read-only endpoint만 허용한다. Code: `api/admin_auth.py`, `api/dependencies.py`에 admin principal gate를 추가한다. Verify: `pytest tests/admin/test_admin_auth.py -q`. Refactor after green: admin role matrix를 공용화한다. Covers: R9.11, R9.12, R9.13.
  - [ ] 17.2 Test: Admin user provisioning은 `users`와 `identity_user_mappings`를 함께 생성하고 비활성 사용자에 대한 budget policy 생성을 거부한다. Code: `api/admin_users.py`와 provisioning service를 추가한다. Verify: `pytest tests/admin/test_user_provisioning.py -q`. Refactor after green: write transaction boundary를 분리한다. Covers: R10.1, R10.3, R10.4, R10.5.
  - [ ] 17.3 Test: Virtual Key revoke, disable, rotate는 DynamoDB cache와 Proxy auth cache를 함께 무효화하고 이전 key를 즉시 거부한다. Code: `api/admin_virtual_keys.py`와 internal invalidation port를 추가한다. Verify: `pytest tests/admin/test_virtual_key_lifecycle.py -q`. Refactor after green: invalidation dispatcher를 분리한다. Covers: R3.9, R3.10, R3.11, R11.6.
  - [ ] 17.4 Test: Admin budget policy CRUD는 `soft_limit_percent <= hard_limit_percent <= 100`을 강제한다. Code: `api/admin_budget_policies.py`와 validation model을 추가한다. Verify: `pytest tests/admin/test_budget_policy_validation.py -q`. Refactor after green: percent validator를 공용화한다. Covers: R9.4, R9.5, R9.6.
  - [ ] 17.5 Test: Admin model mapping 또는 pricing catalog 변경은 resolver/pricing cache reload로 이어진다. Code: `api/admin_model_mappings.py`와 reload hook을 추가한다. Verify: `pytest tests/admin/test_model_mapping_reload.py -q`. Refactor after green: reload notifier 인터페이스를 분리한다. Covers: R7.8, R9.7, R6.11.
  - [ ] 17.6 Test: Internal cache invalidation 호출 후 다음 Token Service lookup은 PostgreSQL을 다시 조회한다. Code: `api/internal_ops.py`와 invalidation endpoint를 추가한다. Verify: `pytest tests/admin/test_internal_cache_invalidation.py -q`. Refactor after green: internal auth boundary를 명시화한다. Covers: R9.10, R12.3.
  - [ ] 17.7 Test: 사용량/감사 조회 API는 사용자별, 팀별, 모델별 usage와 audit event를 필터링해 반환한다. Code: `api/admin_usage.py`와 query service를 추가한다. Verify: `pytest tests/admin/test_usage_queries.py -q`. Refactor after green: pagination/filter object를 도입한다. Covers: R9.14, R9.15.

- [ ] 18. apiKeyHelper 스크립트 구현
  - [ ] 18.1 Test: `apiKeyHelper`는 유효한 로컬 cache가 있으면 100ms 이내에 key를 반환하고, cache miss나 손상 시 Token Service를 다시 호출하며, 연결 실패 시 빠르게 실패한다. Code: `scripts/apiKeyHelper`와 cache file helper를 추가한다. Verify: `pytest tests/scripts/test_api_key_helper.py -q`. Refactor after green: CLI command runner를 분리한다. Covers: R1.1-R1.7, R11.1, R14.1, R16.1.

- [ ] 19. 최소 로깅 및 에러 처리 통합
  - [ ] 19.1 Test: 모든 failure path는 `request_id`를 포함한 구조화 로그와 최소 runtime metrics를 남긴다. Code: logging middleware와 basic metrics hooks를 추가한다. Verify: `pytest tests/observability/test_request_id_and_metrics.py -q`. Refactor after green: metric names/constants를 모듈화한다. Covers: R13.1-R13.5, R14.7.
  - [ ] 19.2 Test: Anthropic 호환 에러 응답은 auth, permission, rate limit, invalid request, upstream failure를 올바른 HTTP status와 envelope로 매핑한다. Code: `models/errors.py`와 `api/errors.py`를 잇는 공용 error handler를 추가한다. Verify: `pytest tests/api/test_error_envelopes.py -q`. Refactor after green: error enum과 mapper를 통합한다. Covers: R14.8, R15.5.

- [ ] 20. 성능 계약 검증
  - [ ] 20.1 Test: 성능 probe는 local cache hit, Token Service response, first streaming token latency에 대한 계약을 검증한다. Code: lightweight benchmark/contract test harness를 추가한다. Verify: `pytest tests/perf/test_contracts.py -q`. Refactor after green: perf thresholds를 설정 파일로 이동한다. Covers: R16.1, R16.2, R16.3.

## Current Increment

- Task: `1.1` 코드베이스 골격과 테스트 디렉터리를 `design.md`의 상위 패키지 경계에 맞춰 만든다.
- Code: `api`, `models`, `token_service`, `proxy`, `repositories`, `security`, `scripts`, `infra`, `tests` 패키지와 대응 테스트 디렉터리만 만들고, 아직 새 동작은 추가하지 않는다.
- Verify: `pytest -q`

## Stop Signals

- 현재 increment가 새 동작 두 개 이상을 동시에 요구하면 다시 쪼갠다.
- AWS 연결, FastAPI wiring, DB schema, business rule을 한 increment 안에 같이 넣으려 하면 structural work와 behavioral work를 다시 분리한다.
- streaming, Admin API, 과한 observability 같은 후속 범위가 현재 happy-path slice에 섞이기 시작하면 즉시 backlog로 되돌린다.
- 테스트를 약화하거나 우회해야만 green 이 되는 순간, production code가 아니라 계획을 다시 쓴다.
- API Gateway, Lambda, ALB, ECS Fargate, Aurora, DynamoDB, IAM, 기본 CloudWatch logging/metrics 설정을 수동 콘솔 작업으로 남기려 하면 중단하고 CDK task로 되돌린다.
- spec에 없는 자동 사용자 생성, fail-open 인증, plaintext key 저장 같은 동작이 떠오르면 범위 드리프트로 보고 중단한다.
