# AGENTS.md

## Authoring Principles For This File

- Only put **non-discoverable context** here. If an agent can learn it from the code, tests, `pyproject.toml`, `README.md`, or normal repository exploration, do not duplicate it here.
- Do **not** paste `/init`-style repository summaries into this file. Directory trees, obvious tech-stack notes, and generated project overviews add noise, increase cost, and bias the agent toward stale context.
- Every line in this file must earn its place. Add a rule only when at least one of these is true:
  - agents repeatedly make the same mistake,
  - the constraint is hard to discover from the repo itself,
  - breaking the rule is expensive, risky, or irreversible.
- Write rules in a compact **WHAT / WHY / HOW** shape. Prefer instructions like: "When X, do Y, because Z."
- Keep this file short. If guidance needs more than a few lines, move the details into `docs/` and leave a short pointer here with the trigger for when to read it.
- Prefer executable guardrails over prose. Style rules belong in formatters, linters, types, tests, or CI whenever possible.
- Delete stale rules aggressively. If the codebase, tooling, or tests now encode a rule, remove it from this file.
- Treat this file as an **operational contract**, not a wishlist or a dumping ground for preferences.

## Maintenance Rules

- Before adding a new instruction, ask: "Can the agent discover this on its own?"
- Before keeping an old instruction, ask: "Does this still reduce ambiguity in current sessions?"
- Revisit this file when the model, harness, or workflow changes. Newer models often make older instructions unnecessary.
- If a rule is broad but only relevant in a narrow situation, make the trigger explicit instead of leaving a universal instruction.

## Project-Specific Guidance

- Add repo-specific instructions below this section only when they satisfy the principles above.
- Prefer short trigger bullets that point to durable sources of truth in `docs/` rather than copying long procedures here.

### Implementation Workflow

- When implementing features, read `.kiro/specs/**/*.md` first. These specs are the source of truth for requirements and design decisions.

## Mistake Log

Record repeated or critical mistakes here to prevent recurrence. Format: `[Date] Mistake → Fix`

- [2026-03-29] `__init__.py`에서 re-export하는 심볼을 삭제하면서 `__init__.py` 업데이트를 누락해 ImportError 발생 → 모듈에서 public 심볼을 제거할 때 반드시 `__init__.py`와 `__all__`도 함께 수정할 것
- [2026-03-29] `@property`로 전환한 필드를 생성자에서 여전히 kwarg로 전달해 Pyright `reportCallIssue` 발생 → dataclass 필드를 `@property`로 변경하면 모든 construction site에서 해당 kwarg를 제거할 것
- [2026-03-29] `frozen=True` dataclass에 `@property`를 추가할 때 `slots=True`와 충돌 가능성 간과 → `slots=True` dataclass에 property를 추가하면 슬롯 미할당 에러가 발생할 수 있으므로 테스트로 확인할 것
- [2026-03-29] 함수 시그니처에서 파라미터를 제거하면서 테스트 스텁/호출부 업데이트 누락 → 함수 시그니처 변경 시 `Grep`으로 모든 호출부(프로덕션 + 테스트 스텁)를 검색해 함께 수정할 것
- [2026-03-29] 패키지 `__init__.py`에 상수를 정의하고 하위 모듈에서 import할 때 circular import 위험 간과 → `__init__.py`에서 상수를 하위 모듈 import보다 먼저 정의하면 circular import를 피할 수 있음
