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
    return pathlib.Path(created["path"])


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
                "summary_next_mutation": final_summary["next_mutation"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
