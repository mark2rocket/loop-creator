# Loop Creator Plugin

Hermes용 `loop-creator` 플러그인이다. Standard / Full / GS Loop 실행 패키지를 만들고, 각 루프가 실제 증거를 남겼는지 검증하고, 남은 blocker와 다음 mutation을 요약한다.

## 왜 필요한가

Loop Creator는 “자율 루프를 알아서 돌리는 플러그인”이 아니다. 더 중요한 역할은 **좋은 루프가 돌아갈 수밖에 없는 증거 패키지**를 만드는 것이다.

일반적인 반복 개선은 쉽게 이렇게 망가진다.

- 목표가 한 줄 prompt로만 남아서 중간에 drift가 생김
- iteration log가 “수정함 / 개선됨” 같은 말만 남김
- worker가 스스로 완료를 선언하고 verifier/human gate가 분리되지 않음
- pass/fail 판단이 실제 hard-fail과 evidence를 보지 않음

이 플러그인은 그 문제를 막기 위해 scaffold 단계부터 Goal Contract, Learning Trace, review report, validator를 강제한다.

## 제공 기능

- Slash commands: `/loop-creator`, `/loop-validate`, `/loop-summary`, `/loop-update-check`
- CLI command: `hermes loop-creator ...`
- Hermes tools:
  - `loop_creator_scaffold`
  - `loop_creator_validate_run`
  - `loop_creator_summarize_run`
  - `loop_creator_check_update`
- Gateway hook:
  - `pre_gateway_dispatch`
  - `loop creator ...` 형태를 `/loop-creator ...`로 rewrite

## 지원 트랙

- `standard loop`
  - 실용 artifact 품질 개선용 기본 트랙
  - 보통 5–8개 predicate-level micro-loop를 요구

- `full loop`
  - reusable loop / policy / replay / transfer evidence까지 검증해야 하는 트랙
  - agent workflow, system design, loop-policy promotion에 적합

- `gs loop`
  - growth / revenue / GTM / ICP / offer / channel 전략용 트랙
  - `Quick`, `standard`, `Full GS` depth를 지원

## Spec Grade

`grade`는 Spec Contract Addendum의 강도를 조절한다.

- `LIGHT`: acceptance evidence 중심. 간단한 문서/카피/정리용.
- `STANDARD`: `non_goals`, `must_read`, `rejected_alternatives`, `risks`, `acceptance_criteria`를 blocker로 본다.
- `HEAVY`: STANDARD에 더해 `forbidden_paths`까지 blocker로 본다. 코드/운영/보안/돈/마이그레이션에 적합하다.

기본값은 `standard`/`gs`는 `STANDARD`, `full`과 `Full GS`는 `HEAVY`다.

## Trigger Mode

`trigger_mode`는 track과 별개다. track은 품질 깊이, trigger mode는 루프를 무엇이 시작하는지 정한다.

- `manual`: 사람이 명시적으로 시작한다.
- `interval`: `15m`, `7d` 같은 주기로 점검한다.
- `event`: `post-edit`, `pre-commit`, `post-merge` 같은 hook/event 뒤에 돈다.

이 값은 `state/brief.md`, `state/goal-contract.md`, `final/harness.md`, `final/quick-loop-card.md`, `loop-creator.json`에 남는다.

## 생성되는 주요 파일

`/loop-creator standard slug=my-run ...`을 실행하면 run folder 아래에 다음 구조가 생긴다.

```text
state/
  brief.md
  goal-contract.md
  current.md
  research-notes.md
final/
  harness.md 또는 gs-harness.md
  loop-spec.md       # full 또는 Full GS에서 생성
  improved-draft.md
  review-report.md
  quick-loop-card.md
  user-facing-summary.md
logs/
  iteration-001.md
loop-creator.json
```

## Goal Contract

모든 scaffold는 `state/goal-contract.md`를 만든다. 이 파일은 사용자 요청을 한 번 쓰고 사라지는 prompt가 아니라, 실행 전체에서 참조되는 durable goal state로 바꾼다.

핵심 필드:

- `goal_id`
- `objective`
- `completion_criteria`
- `hard_fails`
- `verification_surface`
- `budget`
- `lifecycle_state`
- `owner`
- `current_artifact_hash`
- `stale_update_guard`
- `kickoff_boundary`
- `next_continuation_condition`

Spec Contract Addendum 필드:

- `non_goals`
- `must_read`
- `rejected_alternatives`
- `risks`
- `acceptance_criteria`
- `forbidden_paths`

이 addendum은 `why-was-fable-banned`의 spec-first gate에서 가져온 부분이다. 목적은 “무엇을 할지”뿐 아니라 **무엇을 안 할지, 무엇을 읽어야 할지, 어떤 대안을 왜 버렸는지, 어떤 evidence가 완료를 증명하는지**를 남기는 것이다.

중요한 경계:

- worker는 `candidate_complete`까지만 주장할 수 있다.
- `achieved` / `PASS` 승격은 verifier 또는 human gate가 맡는다.
- `budget_limited`는 조용한 성공/실패가 아니라 evidence-backed soft stop이다.
- `kickoff_boundary`는 kickoff/deeplink 텍스트가 파일 설치, hook 활성화, autonomous execution 증거가 아님을 명시한다.

## Quick Loop Card

`final/quick-loop-card.md`는 긴 하네스를 읽지 않고도 다른 agent나 사람이 바로 붙여넣을 수 있는 짧은 카드다.

포함 필드:

- `Goal`
- `Max iterations`
- `Trigger mode`
- `Between iterations run`
- `Exit when`
- `Step 1`
- `Self-pace this loop`

또한 사용자-facing anti-gaming 3줄을 항상 포함한다.

- check command나 exit criteria를 성공처럼 보이게 바꾸지 않는다.
- checks를 skip/disable/bypass하지 않는다.
- 막히면 metric 조작 대신 blocker를 보고한다.

중요: Quick card는 실행 지시문이지 install bundle이 아니다. hook/event bundle은 실제 repo/runtime에 파일로 써지고 agent/session이 재시작되어야 존재한다.

## Learning Trace

각 `logs/iteration-*.md`는 `## Learning Trace` 섹션을 가져야 한다.

필수 필드:

- `Current constraint`
- `Controlled variable`
- `Prediction before change`
- `Measurement method`
- `Expected result`
- `Observed result`
- `Study delta`
- `Act decision`
- `Learning level`

목적은 단순히 “무엇을 고쳤는지”가 아니라 **왜 이 루프가 필요했고, 무엇을 예측했고, 실제 결과가 어떻게 달랐고, 다음 루프 조건이 어떻게 생겼는지**를 남기는 것이다.

## Validator 정책

`loop_creator_validate_run`은 다음을 검사한다.

- 필수 scaffold 파일 존재 여부
- brief 핵심 필드가 TODO 상태인지 여부
- goal contract 필드 completeness
- Spec Contract Addendum: `non_goals`, `must_read`, `rejected_alternatives`, `risks`, `acceptance_criteria`, `forbidden_paths`
- fake evidence marker: `not run`, `would pass`, `should pass`, `pending`, `placeholder` 등
- completion boundary: `candidate_complete`와 `achieved/PASS` 분리 여부
- `budget_limited` soft-stop rule 존재 여부
- `kickoff_boundary` 존재 여부
- `final/quick-loop-card.md`의 kickoff schema, anti-gaming, install/hook boundary, lightweight learning trace 존재 여부
- track별 최소 iteration log 수
- iteration log의 필수 section/field 존재 여부
- review report의 Loop Trace Summary 존재 여부
- Full GS 전용 evidence marker와 wall-clock evidence 조건

### Blocker와 Warning

Validator는 두 단계로 판단한다.

- `issues`: passable을 막는 blocker
- `warnings`: passable은 허용하지만 품질이 의심되는 신호

현재 warning은 다음을 잡는다.

- `completion_criteria`, `hard_fails`, `next_continuation_condition`이 너무 짧아 audit하기 어려운 경우
- `Prediction before change`, `Observed result`, `Act decision`이 너무 짧은 경우
- 여러 iteration log에서 prediction / observed result / act decision이 복붙처럼 반복되는 경우

즉, 형식만 채운 가짜 passable을 바로 실패 처리하지는 않지만, 품질 경고로 드러낸다.

## 사용 예시

```bash
/loop-creator standard trigger_mode=manual grade=LIGHT slug=proposal artifact="draft.md" reader="buyer" outcome="review-ready proposal" check_command="python3 scripts/verify_run.py" exit_when="verify_run exits 0"
/loop-creator full trigger_mode=event event=post-merge grade=HEAVY slug=agent-workflow artifact="workflow.md" outcome="reusable loop policy"
/loop-creator gs trigger_mode=interval cadence=7d depth=Quick grade=STANDARD slug=gtm-plan company="Acme" customer="B2B SaaS marketer" payer="marketing lead" buying_trigger="pipeline gap" outcome="30-day growth experiment"
```

검증:

```bash
/loop-validate /path/to/run-folder
```

요약:

```bash
/loop-summary /path/to/run-folder
```

업데이트 확인:

```bash
/loop-update-check
hermes loop-creator check-update
python3 scripts/check_update.py --format text
```

업데이트 확인은 읽기 전용이다. 원격 commit이 더 새로우면 `hermes plugins update loop-creator`를 제안하지만 자동 적용하지 않는다. 실제 업데이트는 사용자가 승인한 뒤 실행한다.

## 로컬 smoke check

```bash
python3 -m py_compile __init__.py schemas.py tools.py scripts/smoke_passable.py scripts/check_update.py
python3 scripts/smoke_passable.py
python3 scripts/check_update.py --format json
```

`smoke_passable.py`는 세 가지를 검증한다.

1. fresh scaffold는 goal/trace evidence gap 때문에 passable이 아니어야 한다.
2. low-quality filled fixture는 `passable: true`라도 quality warning을 내야 한다.
3. good filled fixture는 `passable: true`, `final_warning_count: 0`이어야 한다.

예상 출력 요약:

```json
{
  "success": true,
  "low_quality_warning_count": 3,
  "final_passable": true,
  "final_issue_counts": {},
  "final_warning_count": 0
}
```

## 설계 원칙

- Loop Creator는 autonomous loop runner가 아니라 evidence package creator다.
- Goal은 prompt가 아니라 durable run state다.
- 각 iteration은 edit pass가 아니라 learning loop여야 한다.
- worker completion claim과 verifier/human pass decision은 분리한다.
- validator는 launch-ready를 과장하지 않고, blocker와 warning을 분리한다.
