#!/usr/bin/env python3
"""Regression smoke test for loop-creator goal-contract + learning-trace gates.

This script verifies three critical paths:
1. A fresh scaffold is intentionally not passable and reports goal/trace evidence gaps.
2. A low-quality but structurally complete fixture remains passable yet emits warnings.
3. A filled local fixture can become passable with no blocker issues or quality warnings.
"""
from __future__ import annotations

import json
import pathlib
import sys
import tempfile

PLUGIN_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN_ROOT))

import tools  # noqa: E402


def _create_run(root: str) -> pathlib.Path:
    created = json.loads(
        tools.create_scaffold(
            {
                "track": "standard",
                "grade": "STANDARD",
                "slug": "filled-run",
                "root_path": root,
                "artifact": "sample draft v1",
                "reader": "test evaluator",
                "outcome": "prove validator can reach passable after real evidence fields are filled",
                "constraints": "local smoke fixture only",
            }
        )
    )
    assert created["success"] is True, created
    run = pathlib.Path(created["path"])
    intake = (run / "state" / "intake.md").read_text(encoding="utf-8")
    assert "## Goal Intake" in intake and "## Control Intake" in intake, intake
    assert "missing_at_creation" in intake, intake
    hsd = (run / "state" / "hsd.md").read_text(encoding="utf-8")
    assert "Harness Specification Document" in hsd and "## Approval Gate" in hsd, hsd
    assert "Verification System Design Gate" in hsd and "Deterministic / explainable check first" in hsd, hsd
    harness = (run / "final" / "harness.md").read_text(encoding="utf-8")
    assert "## Verification System Design" in harness and "Deterministic checks first" in harness, harness
    goal_contract = (run / "state" / "goal-contract.md").read_text(encoding="utf-8")
    assert "deterministic_checks" in goal_contract and "verification_integration_point" in goal_contract, goal_contract
    for rel in ["final/hsd-diagram.md", "final/harness-diagram.md", "final/harness-improvement-suggestions.md"]:
        assert (run / rel).exists(), rel
    return run


def _fill_goal_contract(run: pathlib.Path) -> None:
    (run / "state" / "goal-contract.md").write_text(
        """# Goal Contract

## Persistent Goal State
- goal_id: `filled-run-smoke`
- grade: STANDARD
- trigger_mode: manual
- objective: prove validator can reach passable after real evidence fields are filled
- completion_criteria: five predicate-level logs include measured results, final review summarizes evidence, and no required validator field remains blank
- hard_fails: missing goal contract, missing learning trace, opaque iteration wording, placeholder residue, or final review without loop summary
- verification_surface: loop_creator_validate_run plus direct readback of generated files and warning-count inspection
- budget: 5 standard predicate loops in local smoke fixture
- lifecycle_state: active
- owner: human final approval / verifier completion gate
- current_artifact_hash: sample-draft-v1-local-fixture
- stale_update_guard: goal_id filled-run-smoke + run_id + iteration_id + artifact_hash must match
- kickoff_boundary: kickoff prompt is instruction text only; it does not install files, enable hooks, or prove autonomous execution
- next_continuation_condition: continue only while validator reports a concrete blocker or warning that changes passability confidence
- success_stop: validator returns passable true with five concrete trace logs and a final review summary
- no_op_stop: validator reports no actionable blocker and no artifact mutation is needed beyond evidence recording
- stagnation_stop: stop after two validation passes show the same blocker without a new repair hypothesis
- exhausted_stop: stop when the five-log smoke budget is complete or local verification cannot run
- approval_required_stop: stop before changing plugin policy outside this local smoke fixture
- retirement_rule: retire this fixture shape if three reviewed plugin changes show it no longer catches validator regressions
- kill_condition: kill this fixture if it repeatedly passes while a seeded blocker remains undetected

## Exit / Next-Action Gate
- task_status: PASS
- next_action_gate: HOLD
- allowed_next_action: rerun smoke_passable.py after the next validator change
- off_limits: production deployment, credential access, and weakening validator checks

## Spec Contract Addendum
- non_goals: do not claim real domain artifact quality, do not mutate external repositories, do not bypass validator checks
- must_read: README.md — plugin user contract; tools.py — validator contract; scripts/smoke_passable.py — regression evidence contract
- rejected_alternatives: tempting_shortcut: mark scaffold passable without traces would break auditability; scope: require autonomous execution would exceed plugin MVP boundary
- risks: synthetic fixture may overfit validator, medium severity, mitigated by low-quality warning fixture and final zero-warning fixture, acceptance_ref smoke_passable final_warning_count
- acceptance_criteria: fresh scaffold fails with goal/trace gaps; low-quality fixture emits warnings; final fixture passes with zero warnings and live script output
- forbidden_paths: no external repo paths, no credential files, no runtime profile secrets

## Completion Boundary
- worker_claim_allowed: candidate_complete only
- achieved_owner: verifier or human gate only
- pass_mapping: achieved may map to PASS or PASS_WITH_RISKS only after hard-fails clear
- budget_limited_rule: soft stop with evidence, remaining work, and next-start condition; not silent success/failure

## Control Surface
- pause_resume_clear_replace_owner: human/runtime control, not model-inferred
- replacement_rule: archive previous goal state and issue a new goal_id before continuing
- pending_input_priority: pending human input or mailbox work preempts autonomous continuation
""",
        encoding="utf-8",
    )


def _fill_iteration_logs(run: pathlib.Path, *, low_quality: bool = False) -> None:
    predictions = [
        "filling the goal contract will remove blocker checks tied to missing persistent state",
        "adding a measured learning trace will remove trace completeness blockers for this log",
        "recording the actual observation will distinguish evidence from a generic edit pass",
        "using an explicit act decision will make the next continuation condition auditable",
        "summarizing five trace-backed logs will let the final report clear validator blockers",
    ]
    observed = [
        "goal contract fields are now concrete and validator can inspect completion boundaries",
        "learning trace fields are populated with a measurable predicate and evidence source",
        "the observation records what changed versus the prediction instead of claiming progress",
        "the act decision states whether to continue, stop, escalate, or update policy candidates",
        "the final log set gives the review report enough evidence to summarize the run honestly",
    ]
    act_decisions = [
        "continue to the first trace because persistent state blockers are resolved",
        "continue to observation quality because trace structure alone is not enough",
        "continue to decision quality because measured evidence needs a next action",
        "continue to final review because each log now has a continuation rationale",
        "stop after final review if validator shows no blockers and no quality warnings",
    ]
    if low_quality:
        predictions = ["same copied prediction text repeated across all logs"] * 5
        observed = ["same copied observation text repeated across all logs"] * 5
        act_decisions = ["same copied act decision repeated across all logs"] * 5

    log_template = """# Iteration {n:03d}

## Loop Goal
- Target predicate / hard-fail: predicate {n} validates trace field completeness
- Why this loop now: validator must prove learning trace quality, not just scaffold existence

## Input State
- Starting artifact/version: sample draft v{n}
- Known evidence: previous validator issue count and file readback
- Known uncertainty: whether field completeness catches opaque logs

## Learning Trace
- Current constraint: validator passability is blocked by missing or weak trace evidence
- Controlled variable: count and specificity of non-placeholder learning trace fields
- Prediction before change: {prediction}
- Measurement method: run tools.validate_run, inspect issue_counts, and inspect warning list
- Expected result: no trace_gap for log {n} and no copy-paste quality warning when content is specific
- Observed result: {observed}
- Study delta: evidence changed from blank template to auditable predicate trace with a specific observation
- Act decision: {act_decision}
- Learning level: single_loop

## Action Taken
- Change made: filled log {n} with concrete learning trace values
- Changed sections/files: logs/iteration-{n:03d}.md
- Mutation policy applied: constraint-targeted evidence completion

## Evaluation Surface
- Rubric/test/review used: loop_creator_validate_run trace checks
- Negative assertion checked: no opaque completion claim without details
- Evidence source: this log and validator output

## Result
- Verdict: candidate_complete
- Score or qualitative delta: trace evidence complete for this log
- What improved: learning trace can be audited
- What got worse / tradeoff: fixture remains synthetic and local
- Remaining hard-fails: none for this log

## Failure Taxonomy
- Type: process_gap
- Root cause: scaffold templates require real evidence before passable

## Evidence Update
- New evidence added: log {n} has prediction, measurement, observed result, and act decision
- Assumption resolved or still open: resolved for local validator behavior
- Score movement reason: required trace fields moved from blank to non-placeholder

## Next Loop Condition
- Continue / stop / escalate: continue until minimum log count and final report are complete
- Next target: next log or final review
"""
    for idx in range(5):
        n = idx + 1
        (run / "logs" / f"iteration-{n:03d}.md").write_text(
            log_template.format(n=n, prediction=predictions[idx], observed=observed[idx], act_decision=act_decisions[idx]),
            encoding="utf-8",
        )


def _fill_review(run: pathlib.Path) -> None:
    (run / "final" / "review-report.md").write_text(
        """# Review Report

## Verdict
- Verdict: PASS_WITH_RISKS
- Readiness tier: REVIEW_READY
- Score / cap: 86
- Cap reason: local smoke fixture proves validator path, not real domain artifact quality

## Loop Trace Summary
- Iteration 001: filled trace contract → candidate_complete → next predicate
- Iteration 002: filled trace contract → candidate_complete → next predicate
- Iteration 003: filled trace contract → candidate_complete → next predicate
- Iteration 004: filled trace contract → candidate_complete → next predicate
- Iteration 005: filled trace contract → candidate_complete → final validator

## Hard-fails
- none in local smoke fixture

## Failure Taxonomy Counts
- artifact_gap: 0
- evidence_gap: 0
- evaluator_gap: 0
- process_gap: 0
- human_decision_gap: 0

## Next Mutation
- promote this smoke shape into a durable regression test if plugin complexity increases
""",
        encoding="utf-8",
    )



def _fill_restartability_artifacts(run: pathlib.Path) -> None:
    (run / "state" / "evidence-ledger.json").write_text(
        json.dumps(
            {
                "schema": "loop-creator-evidence-ledger-v1",
                "risk_mode": "normal",
                "verification_depth": "normal",
                "rules": {
                    "observed_verification_required": True,
                    "direct_or_generic_coverage_required": False,
                    "completion_claim_requires_successful_verification": True,
                    "do_not_record_failed_verification_as_success": True,
                },
                "changed_files": ["state/goal-contract.md", "logs/iteration-001.md", "final/review-report.md"],
                "verification_commands": ["python3 scripts/smoke_passable.py"],
                "verification_results": [
                    {
                        "command": "python3 scripts/smoke_passable.py",
                        "success": True,
                        "coverage_relation": "generic",
                        "summary": "final_validation passable true with zero issue counts and zero warnings",
                    }
                ],
                "claims": [
                    {
                        "claim": "candidate_complete after smoke validator returned passable true",
                        "evidence_path": "scripts/smoke_passable.py final_validation output",
                        "trace_ref": "logs/iteration-005.md#Evidence Update",
                        "observed_action": "tools.validate_run returned passable true during smoke script",
                        "coverage_relation": "generic",
                        "judge_rationale": "The smoke script reads validator output and asserts zero issue counts before candidate completion.",
                    }
                ],
                "coverage_relation": "generic",
                "latest_artifact_hash": "sample-draft-v1-local-fixture",
                "latest_verified_at": "2026-06-16T00:00:00+09:00",
                "completion_claims": ["candidate_complete after smoke validator returned passable true"],
                "failures": [],
                "stop_gate": {
                    "candidate_complete_claimed": True,
                    "successful_verification_observed": True,
                    "blocked_reason": "",
                },
                "notes": "Observed local smoke command only; no planned verification is counted as evidence.",
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    (run / "state" / "approval-gate.md").write_text(
        """# Approval Gate

Purpose: separate planning/refinement/execution consent so the run does not silently mutate scope.

## Gate State
- current_stage: `final_handoff`
- track: `standard`
- risk_mode: `normal`
- execution_approval_required: true
- latest_approval_status: `approved`

## Stage Gates
| Stage | Required artifact | Approval required before next stage | Status | Evidence |
|---|---|---:|---|---|
| Spec / brief crystallized | `state/brief.md` | true | approved | local smoke fixture accepted |
| Harness accepted | `final/harness.md` | true | approved | validator scaffold readback |
| Execution / rewrite started | `logs/iteration-*.md` | true for non-trivial side effects | approved | five logs written |
| Final handoff | `final/user-facing-summary.md` | false | approved | final validation passable |

## Rules
- Do not treat scaffold creation as execution approval.
- Do not auto-promote from plan/refinement to execution when a human approval gate is pending.
- If the user approved in chat, record the quote or message handle in `state/steering-ledger.jsonl`.
""",
        encoding="utf-8",
    )
    (run / "state" / "story-ledger.jsonl").write_text(
        json.dumps({"schema":"loop-creator-story-ledger-v1","event":"story_created","story_id":"G001","title":"Complete first predicate loop","objective":"Turn the scaffolded run into one verified predicate loop.","status":"complete","evidence":["python3 scripts/smoke_passable.py final_validation passable true"],"blocker":"","next_story":"none; smoke run complete","created_at":"2026-06-16T00:00:00+09:00"}, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (run / "state" / "steering-ledger.jsonl").write_text(
        json.dumps({"schema":"loop-creator-steering-ledger-v1","event":"approval_recorded","kind":"annotate_ledger","rationale":"Local smoke fixture records explicit approval gate for completion path.","evidence":"approval-gate.md latest_approval_status approved","created_at":"2026-06-16T00:00:00+09:00"}, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (run / "state" / "review-receipts.jsonl").write_text(
        json.dumps({"schema":"loop-creator-review-receipts-v1","review_id":"review-001","role":"critic","artifact_path":"final/review-report.md","artifact_sha256":"sample-draft-v1-local-fixture","verdict":"CLEAR","summary":"Review report summarizes five iteration traces and validator evidence.","created_at":"2026-06-16T00:00:00+09:00"}, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    (run / "state" / "predicate-list.json").write_text(
        json.dumps(
            {
                "schema": "loop-creator-predicate-list-v1",
                "rules": {
                    "single_active_predicate": True,
                    "passing_requires_evidence": True,
                    "blocked_requires_next_action": True,
                    "do_not_skip_verification": True,
                },
                "predicates": [
                    {
                        "id": "pred-001",
                        "priority": 1,
                        "behavior": "final report summarizes five measured iteration traces",
                        "verification": "loop_creator_validate_run returns passable true with zero issue counts",
                        "status": "passing",
                        "evidence": ["scripts/smoke_passable.py final_validation passable true", "final/review-report.md Loop Trace Summary"],
                        "blocker": "",
                        "next_action": "archive smoke evidence and keep validator strict",
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (run / "state" / "session-handoff.md").write_text(
        """# Session Handoff

## Verified Now
- What is currently working: local smoke fixture has five concrete iteration logs and a final review report.
- What verification actually ran: tools.validate_run and tools.summarize_run through scripts/smoke_passable.py.

## Changed This Session
- Artifact or behavior added: restartability artifacts are filled with concrete evidence.
- Infrastructure or harness changes: predicate-list, init-check, clean-state, and quality-document are checked by validator.

## Broken Or Unverified
- Known defect: none observed in local validator fixture.
- Unverified path: external production artifact quality remains outside this smoke test.
- Risk for the next session: synthetic fixtures can overfit if new checks are added without new negative cases.

## Next Best Step
- Highest-priority unfinished predicate: pred-001 maintenance only.
- Why it is next: validator shape should remain stable after plugin changes.
- What counts as passing: final validation has no blockers and no warnings.
- What must not change during that step: do not weaken evidence checks to make the fixture pass.

## Commands
- Startup: python3 -m py_compile __init__.py schemas.py tools.py scripts/smoke_passable.py scripts/check_update.py
- Verification: python3 scripts/smoke_passable.py
- Focused debug command: python3 - <<'PY' import tools, json; print(json.loads(tools.validate_run({'path':'<run>'}))) PY
""",
        encoding="utf-8",
    )
    (run / "state" / "init-check.md").write_text(
        """# Initialization Check

Purpose: prove the run can be resumed and verified before implementation or rewriting starts.

## Startup Readiness
- standard startup path: python3 -m py_compile __init__.py schemas.py tools.py scripts/smoke_passable.py scripts/check_update.py
- standard verification path: python3 scripts/smoke_passable.py
- required files readable: state/brief.md, state/goal-contract.md, state/predicate-list.json, logs/iteration-001.md.
- trigger mode: `manual`.
- track: `standard`.

## Initialization Result
- environment/readback status: PASS with local Python compile and smoke script evidence.
- missing prerequisites: none observed in local fixture.
- next safe action: run final validator and inspect warning count.
""",
        encoding="utf-8",
    )
    (run / "final" / "clean-state-checklist.md").write_text(
        """# Clean State Checklist

- [x] The standard startup/readback path still works.
- [x] The standard verification path still runs.
- [x] Current progress is recorded in state/session-handoff.md.
- [x] state/predicate-list.json reflects what is passing versus unverified.
- [x] No half-finished step is left undocumented.
- [x] Temporary/debug artifacts are removed or explicitly justified.
- [x] The next session can continue without manual repair.

## Evidence
- Startup evidence: py_compile command completed in smoke workflow.
- Verification evidence: scripts/smoke_passable.py final validation passable true.
- Cleanup evidence: no unchecked checklist item remains in this fixture.
- Next session instruction: rerun smoke_passable.py after changing validator behavior.
""",
        encoding="utf-8",
    )
    (run / "final" / "quality-document.md").write_text(
        """# Quality Document

Quality snapshot for the generated loop run. Update after material iteration batches and before final handoff.

## Metadata
- track: `standard`
- depth: `n/a`
- last_updated: local smoke fixture run

## Artifact Domains

| Domain | Grade | Verification | Key Gaps | Last Updated |
|---|---|---|---|---|
| Goal Contract | A | validator checks required fields and spec addendum | synthetic fixture only | smoke run |
| Predicate State | A | predicate-list passing state has evidence | one predicate fixture | smoke run |
| Iteration Evidence | A | five concrete learning traces pass validator | local-only evidence | smoke run |
| Final Artifact | B | review report summarizes trace and blockers | no real domain artifact | smoke run |
| Handoff Cleanliness | A | session handoff and clean checklist are complete | no external runtime | smoke run |

## Change History

### smoke run
- Changes: filled restartability artifacts and validator evidence.
- Domains promoted: predicate state and handoff cleanliness.
- New gaps identified: external artifact quality is out of scope.
- Gaps closed: scaffold placeholders removed for local passable fixture.
""",
        encoding="utf-8",
    )


def _fill_loop_library_artifacts(run: pathlib.Path) -> None:
    record_path = run / "final" / "loop-record.json"
    record = json.loads(record_path.read_text(encoding="utf-8"))
    record.update({
        "prompt": "Validate the local fixture, repair one concrete blocker, and stop when validation is passable with evidence.",
        "why": "This regression fixture proves Loop Library-style governance fields do not break passable runs when filled with evidence.",
        "authority_boundary": "Local plugin fixture only; no production, credentials, external repos, or deployment side effects.",
        "retirement_rule": "Retire this fixture shape if three reviewed plugin changes show it no longer catches validator regressions.",
        "kill_condition": "Kill this fixture if it repeatedly passes while a deliberately seeded blocker remains undetected.",
        "manual_trial": "Run once manually through scripts/smoke_passable.py before relying on the validator change.",
        "published_status": "validated",
    })
    record["terminal_states"] = {
        "success": "validator passable true with zero issue counts and final zero warnings",
        "clean_no_op": "no code change needed after validation readback",
        "blocked": "validator reports a concrete blocker with path and issue type",
        "approval_required": "plugin policy change exceeds local smoke fixture scope",
        "exhausted": "five-log smoke budget is complete without passable validation",
        "stagnated": "two validation passes return the same unresolved blocker",
    }
    record["next_action_gate"] = {
        "task_status": "PASS",
        "gate": "HOLD",
        "allowed_next_action": "rerun smoke_passable.py after the next validator change",
        "off_limits": "production deployment, credential access, and weakening validator checks",
    }
    record_path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    (run / "final" / "loop-doctor.md").write_text("""# Loop Doctor

Purpose: audit or minimally repair this loop without changing its intended outcome.

## Verdict
- status: Ready

## Diagnosis
- material finding 1: no repair needed; fresh validation, bounded action, evidence record, and stop state are explicit.

## Cycle Trace
- fresh observation can change next action: validator issue counts decide the next repair.
- bounded action: repair one validator blocker or warning fixture at a time.
- reproducible verification: python3 scripts/smoke_passable.py.
- record/handoff state: evidence-ledger, review-report, and session-handoff are filled.
- explicit stop states: success, clean no-op, blocked, approval-required, exhausted, and stagnated are in loop-record.json.

## Minimal Repair
> No repair needed.
""", encoding="utf-8")
    (run / "final" / "loop-audit.md").write_text("""# Loop Portfolio Audit

Purpose: read-only review of whether this loop should continue, change, retire, or be killed.

## Status
- audit_status: KEEP
- evidence_window: local smoke regression run
- evaluation_version: loop-creator-validator-current

## Scorecard
| Dimension | Evidence | Verdict |
|---|---|---|
| Purpose / success criteria | final validation passable true | KEEP |
| Budget / kill condition | five-log budget and kill condition recorded | KEEP |
| Ledger / raw evidence | evidence-ledger and review-report filled | KEEP |
| Operational delivery or measured result | smoke script asserts passable and zero warnings | KEEP |

## Measured-loop Metrics, if applicable
- hit_rate: 1/1 local final validation pass
- waste_ratio: 0/1 no extra run beyond fixture budget
- mean_gain: scaffold blockers reduced to zero issue counts

## Recommendation
- KEEP / PIVOT / RETIRE / KILL / INSUFFICIENT_EVIDENCE: KEEP
- reason: local regression catches blocker and warning paths while preserving strict final passability.
""", encoding="utf-8")
    (run / "final" / "adaptation-plan.md").write_text("""# Adaptation Plan

Purpose: prefer adapting an existing loop over inventing a duplicate.

## Source Loop Search
- searched_catalog_or_registry: yes; Loop Library imports matched next-action confidence, loop-auditor, and cross-run playbook patterns.
- closest_published_or_local_loop: next-action-confidence-check and loop-auditor-loop.
- fit: partial; adapted to Loop Creator validator artifacts.

## Adaptation Delta
- keep unchanged: verification, authority boundary, stop rule, evidence record.
- replace thresholds/tools/cadence/owner/checks: local smoke command and validator-specific evidence.
- do not weaken: verification, authority boundary, stop rule, evidence record.

## Result
- adaptation_status: adapt_existing
- smallest_needed_change: add loop-record, doctor, audit, hiring, and playbook evidence without changing autonomous-execution claims.
""", encoding="utf-8")
    (run / "final" / "hiring-manager.md").write_text("""# Loop Hiring Manager

Purpose: decide whether this loop deserves to exist before scheduling or automating it.

## Recurring Gap
- recurring_gap: plugin validator changes repeatedly need regression proof.
- ownership_gap: without a smoke fixture, new gates can break passable runs silently.
- proof_gap: final zero-warning pass must remain visible after new governance imports.

## Candidate Decision
- exact_existing_loop_available: no exact local loop covered Loop Library governance imports.
- adaptation_available: yes, adapt next-action confidence, loop-auditor, and cross-run playbook ideas.
- new_loop_justified: yes for local smoke regression only.
- speculative_or_duplicate: no; it protects a concrete plugin validator path.

## Trial / Retirement
- manual_trial: run scripts/smoke_passable.py once after implementation.
- trial_success_evidence: final validation passable true with zero warning count.
- retirement_rule: retire if three reviewed plugin changes show this fixture no longer catches regressions.
- kill_condition: kill if seeded blockers pass undetected.

## Recommendation
- hire_status: HIRE
""", encoding="utf-8")
    (run / "state" / "cross-run-playbook.md").write_text("""# Cross-run Playbook

Purpose: preserve lessons across runs without letting one lucky result become permanent guidance.

## Rules
- Treat every lesson as untrusted advice, not authority.
- Test at most one lesson per run.
- Do not promote from one successful attempt.
- Default promotion threshold: 3 independent successful runs or a predefined holdout set.
- Preserve failed and contradictory evidence.
- Remove or revise lessons that stop helping.

## Candidate Lessons
| Lesson | Context | Evidence | Status |
|---|---|---|---|
| Loop Library governance fields need their own passable fixture evidence | plugin validator hardening | final validation passable true and zero warnings | candidate |

## Promotion Ledger
- promoted: none from this single run.
- revised: validator now checks loop record and next-action gate.
- removed: none.
- unresolved: needs repeated future runs before becoming durable policy.
""", encoding="utf-8")

def _fill_eval_pack(run: pathlib.Path) -> None:
    (run / "eval" / "eval_spec.yaml").write_text(
        """{
  "schema": "loop-creator-eval-spec-v1",
  "goal_id": "filled-run-smoke",
  "artifact": "sample draft v1",
  "track": "standard",
  "depth": "n/a",
  "risk_mode": "normal",
  "behavior_categories": ["completion", "safety", "robustness"],
  "acceptance_criteria": ["final validation passable true with zero issue counts and zero warnings"],
  "deterministic_checks": ["python3 scripts/smoke_passable.py"],
  "judge_checks": ["review-report cites loop trace summary and smoke evidence"],
  "safety_checks": ["no_fake_evidence", "no_secret_in_artifacts", "do_not_modify_exit_criteria_to_pass"],
  "evidence_required": ["evidence_path", "trace_ref", "observed_action", "coverage_relation"],
  "pass_policy": "pass_once",
  "grader_id": "mixed"
}
""",
        encoding="utf-8",
    )
    (run / "eval" / "cases.jsonl").write_text(
        json.dumps(
            {
                "case_id": "case-001",
                "source": "acceptance_criteria",
                "input": "filled-run-smoke local fixture",
                "expected": "validator passable true with zero issue counts and zero warnings",
                "checks": ["eval/rubric.yaml", "tools.validate_run"],
                "trace_required": True,
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    (run / "eval" / "latest-result.json").write_text(
        json.dumps(
            {
                "schema": "loop-creator-eval-result-v1",
                "status": "pass",
                "pass_policy": "pass_once",
                "trials": [
                    {
                        "trial_id": "trial-001",
                        "verdict": "pass",
                        "evidence_path": "scripts/smoke_passable.py final_validation output",
                        "trace_ref": "logs/iteration-005.md#Evidence Update",
                    }
                ],
                "summary": "Observed local smoke validator pass after concrete trace and evidence fields were filled.",
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def main() -> int:
    root = tempfile.mkdtemp(prefix="loop-creator-smoke-")
    run = _create_run(root)

    fresh_validation = json.loads(tools.validate_run({"path": str(run)}))["validation"]
    assert fresh_validation["ok"] is True, fresh_validation
    assert fresh_validation["passable"] is False, fresh_validation
    assert "goal_contract_gap" in fresh_validation.get("issue_counts", {}), fresh_validation
    assert (run / "state" / "goal-contract.md").exists(), fresh_validation
    assert "## Learning Trace" in (run / "logs" / "iteration-001.md").read_text(encoding="utf-8")

    _fill_goal_contract(run)
    _fill_iteration_logs(run, low_quality=True)
    _fill_review(run)
    _fill_restartability_artifacts(run)
    _fill_eval_pack(run)
    _fill_loop_library_artifacts(run)

    low_quality_validation = json.loads(tools.validate_run({"path": str(run)}))["validation"]
    assert low_quality_validation["passable"] is True, low_quality_validation
    assert low_quality_validation.get("issue_counts") == {}, low_quality_validation
    assert len(low_quality_validation.get("warnings", [])) >= 1, low_quality_validation

    _fill_iteration_logs(run, low_quality=False)

    final_validation = json.loads(tools.validate_run({"path": str(run)}))["validation"]
    final_summary = json.loads(tools.summarize_run({"path": str(run)}))

    assert final_validation["passable"] is True, final_validation
    assert final_validation.get("issue_counts") == {}, final_validation
    assert final_validation.get("warnings") == [], final_validation
    assert final_summary.get("warning_count") == 0, final_summary
    assert final_validation.get("aco_bottleneck") == "none", final_validation
    assert final_summary.get("aco_bottleneck") == "none", final_summary
    assert "No validation blockers" in final_summary["next_mutation"], final_summary

    print(
        json.dumps(
            {
                "success": True,
                "path": str(run),
                "fresh_issue_counts": fresh_validation.get("issue_counts"),
                "low_quality_warning_count": len(low_quality_validation.get("warnings", [])),
                "final_passable": final_validation["passable"],
                "final_issue_counts": final_validation.get("issue_counts"),
                "final_warning_count": len(final_validation.get("warnings", [])),
                "final_aco_bottleneck": final_validation.get("aco_bottleneck"),
                "summary_next_mutation": final_summary["next_mutation"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
