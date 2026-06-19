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

## Goal + Control Intake

`/loop-creator standard`처럼 track만 주면 바로 scaffold하지 않는다. 먼저 deep-interview식 질문 카드를 반환한다.

```md
현재 이해: <지금까지 받은 목표/산출물 요약>
막힌 결정: <scaffold 전에 정해야 하는 가장 큰 불확실성>
추천 답안: <Loop Creator의 기본 추천>
질문: <한 가지 질문>
```

질문은 한 번에 하나만 묻는다. 부족한 값은 아래 순서로 처리한다.

1. `goal` / `outcome`
2. `artifact`
3. `verify` / `check_command` / `exit_when`
4. `reader`
5. `hard_fail` / `boundary_rule`
6. `context` / `must_read`
7. `hook_moment`
8. `boundary_rule`
9. `escalation_rule`
10. `deletion_rule`

답변을 한 줄 KV로 주면 다음 단계로 넘어간다. 모든 intake 필드가 충분하면 바로 scaffold하지 않고 먼저 **HSD Preview**를 보여준다.

```bash
/loop-creator standard goal="제안서 설득력 개선" artifact="proposal.md" reader="B2B 마케팅 리드" verify="buyer review passes" hard_fail="AI 티, 검증 없는 완료 선언" context="prior review" hook_moment="agent:step evidence; agent:end PASS gate; session:end handoff" boundary_rule="no_fake_evidence" escalation_rule="같은 실패 2회 반복 시 human approval" deletion_rule="3회 후 실패 감소 없으면 제거"
```

## HSD Design Gate

HSD는 Harness Specification Document다. intake 답변을 하네스 요구사항/설계안으로 정리하고, 도식화와 보강 제안을 보여준다.

```text
Goal
  ↓
Artifact
  ↓
Evaluator
  ↓
Success Gate
  ↓
Hard Fail / Boundary
  ↓
Hook / Rule
  ↓
Scaffold Build
```

HSD preview가 마음에 들면 같은 명령에 `approve_hsd=true`를 붙인다.

```bash
/loop-creator standard ... approve_hsd=true
```

급하게 빈칸 포함 scaffold가 필요하면 `allow_todo=true`를 붙인다. Hermes tool `loop_creator_scaffold`는 자동화/테스트 호환성을 위해 직접 scaffold를 생성하지만, slash command UX는 intake gate와 HSD Design Gate를 먼저 탄다.

## 생성되는 주요 파일

`/loop-creator standard slug=my-run ...`을 실행하면 run folder 아래에 다음 구조가 생긴다.

```text
state/
  intake.md
  hsd.md
  brief.md
  goal-contract.md
  failure-taxonomy.yaml
  predicate-list.json
  evidence-ledger.json
  approval-gate.md
  story-ledger.jsonl
  steering-ledger.jsonl
  review-receipts.jsonl
  session-handoff.md
  init-check.md
  current.md
  research-notes.md
eval/
  eval_spec.yaml
  task.yaml
  rubric.yaml
  cases.jsonl
  latest-result.json
runner/
  loop.yaml
final/
  harness.md 또는 gs-harness.md
  loop-spec.md       # full 또는 Full GS에서 생성
  improved-draft.md
  review-report.md
  hsd-diagram.md
  harness-diagram.md
  harness-improvement-suggestions.md
  quick-loop-card.md
  clean-state-checklist.md
  quality-document.md
  user-facing-summary.md
logs/
  iteration-001.md
loop-creator.json
```

## v1.5 Eval / Trace / Runner Layer

- `state/evidence-ledger.json`은 v2부터 `claim`, `evidence_path`, `trace_ref`, `observed_action`, `coverage_relation`, `judge_rationale`를 가진 trace-grounded claim citation을 요구한다.
- `state/failure-taxonomy.yaml`은 goal drift, context contamination, plugin/MCP abuse, permission escalation, repeated no-progress, HITL bypass를 포함한 failure taxonomy v2를 둔다.
- `eval/` pack은 acceptance criteria를 deterministic checks, judge checks, safety checks, cases, latest result로 분리한다.
- `loop-creator.json`은 `model_id`, `harness_id`, `grader_id`, `fit_score`, `runner_spec`을 기록해 model × harness × grader를 섞지 않는다.
- `runner/loop.yaml`은 runner-neutral planning metadata다. 설치나 실행 증거가 아니다.

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

## Restartability / Clean Handoff

`learn-harness-engineering`에서 가져온 핵심 운영 프리미티브는 교육용 course 구조가 아니라 **재시작 가능한 상태 파일**이다.

- `state/intake.md`: deep-interview식 Goal + Control Intake 결과. 목표/산출물/평가자/검증/하드페일과 hook moment/boundary/escalation/deletion rule을 한 곳에 남긴다.
- `state/hsd.md`: Harness Specification Document. intake를 하네스 설계안으로 정리하고 Design Gate 승인 상태와 보강 제안을 남긴다.
- `final/hsd-diagram.md`: scaffold 전 설계 도식화와 보강 제안.
- `final/harness-diagram.md`: scaffold 후 실제 run folder의 state/final/logs 연결 도식화.
- `final/harness-improvement-suggestions.md`: 구축 완료 후 한 번 더 보는 보강 제안.
- `state/predicate-list.json`: predicate별 `behavior`, `verification`, `status`, `evidence`, `next_action`을 갖는 state machine. `passing`은 evidence 없이는 허용하지 않는다.
- `state/aco-design-card.md`: ACO Framework 기준으로 A6(Structure/Context/Plan/Execution/Verification/Improvement), C3(Hook/Rule/Loop), O3(State/Gate/Evidence)를 한 장에 묶는다. 실패했을 때 어느 레이어 문제인지 귀속하기 위한 카드다.
- `state/control-policy.md`: Hermes의 실제 gateway hook 이벤트(`gateway:startup`, `session:start`, `session:end`, `session:reset`, `agent:start`, `agent:step`, `agent:end`, `command:*`)에 Hook/Rule을 연결한다. 추상 `pre_start` 같은 이름은 쓰지 않는다.
- `state/evidence-ledger.json`: fable-ish에서 가져온 observed verification ledger. 변경 파일, 검증 명령, 성공/실패, `coverage_relation`, completion claim, stop-gate 상태를 기록한다.
- `state/approval-gate.md`: Gajae-Code의 approval-gated pipeline에서 가져온 stage gate. spec/refinement/execution 전환마다 승인 상태를 명시한다.
- `state/story-ledger.jsonl`: Ultragoal 스타일 story ledger. G001/G002 단위 목표, 상태, evidence, blocker, next story를 append-only로 남긴다.
- `state/steering-ledger.jsonl`: split/reorder/revise/block/supersede 같은 중간 변경을 audit event로 남긴다.
- `state/review-receipts.jsonl`: Planner/Architect/Critic/Human review의 본문 대신 artifact path, sha256, verdict, summary receipt를 남긴다.
- `state/session-handoff.md`: 다음 세션이 바로 이어받도록 `Verified Now`, `Changed This Session`, `Broken Or Unverified`, `Next Best Step`, `Commands`를 남긴다.
- `state/init-check.md`: 작업 전 startup/readback/verification path가 살아 있는지 확인한다.
- `final/clean-state-checklist.md`: 종료 시 unchecked item, TODO, 임시/debug residue, stale state가 남지 않았는지 확인한다.
- `final/quality-document.md`: Goal Contract, Predicate State, Iteration Evidence, Final Artifact, Handoff Cleanliness를 domain별로 등급화한다.

이 레이어의 목적은 “좋은 루프가 한 번 돌았다”가 아니라 **새 세션/다른 agent가 같은 run folder만 보고 이어갈 수 있음**을 증명하는 것이다.

## Approval / Story Ledger

`gajae-code`에서 가져온 핵심은 runner 자체가 아니라 **승인-게이트와 목표 변경 auditability**다.

- scaffold 생성은 실행 승인으로 간주하지 않는다.
- execution/rewrite로 넘어가기 전 `state/approval-gate.md`에 승인 상태를 남긴다.
- G001/G002 같은 story 단위 목표는 `state/story-ledger.jsonl`에 append-only로 남긴다.
- 목표를 쪼개거나 순서를 바꾸거나 막힌 목표를 supersede하면 `state/steering-ledger.jsonl`에 남긴다.
- reviewer의 긴 본문을 복붙하지 않고 `state/review-receipts.jsonl`에 path/hash/verdict receipt를 남긴다.
- completion claim이 있으면 `evidence-ledger`의 `latest_artifact_hash`와 `latest_verified_at`이 있어야 한다.

한 줄 원칙: **목표가 바뀌면 기록하고, 완료 전에는 fresh snapshot을 남긴다.**

## Runtime Evidence Ledger

`fable-ish`에서 가져온 핵심은 Claude Code hook 자체가 아니라 **관찰된 검증만 완료 근거로 인정하는 장부 패턴**이다.

- `risk_mode`: `quick`, `normal`, `deep`, `blocked` 중 하나. 기본값은 grade/track에서 추론한다.
- `coverage_relation`: `direct`, `generic`, `uncertain`, `none` 중 하나.
- `normal`/`deep` risk mode는 성공한 검증 결과가 있어야 passable이다.
- `deep` risk mode는 `direct` 또는 `generic` coverage가 필요하다.
- candidate completion claim이 있는데 성공 검증이 없으면 stop-gate blocker다.
- 실패/에러 출력을 success로 기록하면 blocker다.

한 줄 원칙: **검증했다고 말한 것보다 ledger에 관찰된 검증을 우선한다.**

## ACO / Control Policy

`loop-creator`는 ACO Framework를 새 track 이름으로 만들지 않는다. Standard / Full / GS Loop는 그대로 두고, ACO를 **진단·귀속·제어 정책 레이어**로 쓴다.

- A6 — Architecture: `scaffold_gap`, `brief_gap`, `goal_contract_gap` 같은 문제를 Structure/Context/Plan/Execution/Verification/Improvement 중 어디가 빈칸인지로 귀속한다.
- C3 — Control: Hook은 Hermes의 실제 이벤트명에 붙이고, Rule은 그 이벤트에서 무엇을 허용/금지/우선할지로 둔다.
- O3 — Operation: State/Gate/Evidence는 기존 goal contract, predicate list, approval gate, evidence ledger, handoff로 운영한다.

현재 control policy는 선언형이다. Hermes gateway hook 시스템은 기본적으로 에러를 로그로만 남기고 main pipeline을 막지 않으므로, MVP에서는 hard block을 만들지 않는다. 대신 validator와 completion gate가 아래를 검사한다.

- 기존 Hermes 이벤트명을 사용했는가: `gateway:startup`, `session:start`, `session:end`, `session:reset`, `agent:start`, `agent:step`, `agent:end`, `command:*`
- Boundary rule이 있는가: `no_fake_evidence`, `no_secret_in_artifacts`, `do_not_modify_exit_criteria_to_pass`, `candidate_complete_requires_evidence_ledger_update`
- 추상 hook 이름(`pre_start`, `post_iteration`, `pre_completion`)으로 도망가지 않았는가
- hook/rule 삭제 기준이 있는가: 3회 사용 후 실패 감소, review cost 감소, restartability 개선이 없으면 제거/강등

`/loop-validate`와 `/loop-summary`는 blocker에 `aco_layer`를 붙이고 `ACO bottleneck`을 출력한다. 이 값은 “어느 파일을 고칠까”보다 “이번 실패가 A6/C3/O3 중 어디서 난 건가”를 보여주기 위한 것이다.

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
- `state/predicate-list.json`의 state machine: status enum, single active predicate, passing evidence, blocked next action
- `state/aco-design-card.md`의 A6/C3/O3/Deletion Rule marker
- `state/control-policy.md`의 기존 Hermes hook event, boundary rule, blocking boundary, machine-readable policy
- `state/evidence-ledger.json`의 observed verification: successful result, coverage relation, completion claim stop gate, failed-as-success 차단
- `state/approval-gate.md`의 승인 상태와 completion claim 전 approval gate
- `state/story-ledger.jsonl`의 story status/evidence/blocker
- `state/steering-ledger.jsonl`의 steering event kind/rationale
- `state/review-receipts.jsonl`의 reviewer verdict/path/hash receipt
- completion claim 전 fresh snapshot: `latest_artifact_hash`, `latest_verified_at`
- `state/session-handoff.md`, `state/init-check.md`, `final/clean-state-checklist.md`, `final/quality-document.md`의 재시작/clean handoff marker와 TODO residue
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
/loop-creator standard trigger_mode=manual risk_mode=normal grade=LIGHT slug=proposal artifact="draft.md" reader="buyer" outcome="review-ready proposal" check_command="python3 scripts/verify_run.py" exit_when="verify_run exits 0"
/loop-creator full trigger_mode=event risk_mode=deep event=post-merge grade=HEAVY slug=agent-workflow artifact="workflow.md" outcome="reusable loop policy"
/loop-creator gs trigger_mode=interval risk_mode=deep cadence=7d depth=Quick grade=STANDARD slug=gtm-plan company="Acme" customer="B2B SaaS marketer" payer="marketing lead" buying_trigger="pipeline gap" outcome="30-day growth experiment"
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
4. validation/summary에는 `aco_bottleneck`과 ACO issue layer 정보가 포함되어야 한다.

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
