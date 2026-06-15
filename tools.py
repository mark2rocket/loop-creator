"""Handlers for the loop-creator plugin.

The plugin preserves Loop Harness Creator quality by forcing route -> scaffold ->
trace logs -> validate -> summarize. It does not pretend to run autonomous LLM
loops; it blocks PASS when evidence is missing.
"""
from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover
    ZoneInfo = None  # type: ignore

try:
    from hermes_constants import get_hermes_home
except Exception:  # pragma: no cover
    def get_hermes_home() -> str:
        return str(Path.home() / ".hermes")

TRACK_LABELS = {"standard": "standard loop", "full": "full loop", "gs": "gs loop"}
TRIGGER_MODES = {"manual": "manual", "interval": "interval", "event": "event"}
GS_DEPTHS = {"quick": "Quick", "standard": "standard", "full": "Full GS", "full gs": "Full GS", "full-gs": "Full GS", "full_gs": "Full GS"}
GRADES = {"light": "LIGHT", "standard": "STANDARD", "heavy": "HEAVY", "l": "LIGHT", "s": "STANDARD", "h": "HEAVY"}
SKILL_ROOT = Path(get_hermes_home()) / "skills" / "strategy" / "loop-harness-creator"
GS_SOURCE_ROOT = Path.home() / "haven-synk" / "30-Output" / "Teaching" / "lectures-challenges" / "50-harnesses" / "growth-strategy-ralph-kit"
TRACE_SECTIONS = ["Loop Goal", "Input State", "Learning Trace", "Action Taken", "Evaluation Surface", "Result", "Failure Taxonomy", "Evidence Update", "Next Loop Condition"]
TRACE_FIELD_HINTS = ["Target predicate", "Why this loop now", "Starting artifact", "Current constraint", "Controlled variable", "Prediction before change", "Measurement method", "Expected result", "Observed result", "Study delta", "Act decision", "Learning level", "Change made", "Mutation policy applied", "Rubric/test/review used", "Negative assertion checked", "Verdict", "Score or qualitative delta", "Type:", "New evidence added", "Continue / stop / escalate", "Next target"]
GOAL_CONTRACT_FIELDS = ["goal_id", "grade", "trigger_mode", "objective", "completion_criteria", "hard_fails", "verification_surface", "budget", "lifecycle_state", "owner", "current_artifact_hash", "stale_update_guard", "next_continuation_condition"]
LEARNING_TRACE_REQUIRED = ["Current constraint", "Controlled variable", "Prediction before change", "Measurement method", "Observed result", "Study delta", "Act decision", "Learning level"]
SPEC_CONTRACT_FIELDS = ["non_goals", "must_read", "rejected_alternatives", "risks", "acceptance_criteria"]
FAKE_EVIDENCE_MARKERS = ("not run", "notrun", "did not run", "didn't run", "assumed", "would pass", "should pass", "to be done", "tbd", "todo", "n/a", "pending", "placeholder", "will run", "not yet")
SECRET_RE = re.compile(r"(?i)\b(api[_-]?key|secret|token|cookie|authorization|refresh[_-]?token|access[_-]?token)\s*[:=]\s*([^\s`'\"]{8,})")


def _redact(text: str) -> str:
    return SECRET_RE.sub(lambda m: f"{m.group(1)}=[REDACTED]", text or "")


def _json(data: dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)


def _now() -> datetime:
    return datetime.now(ZoneInfo("Asia/Seoul")) if ZoneInfo else datetime.now()


def _safe_slug(raw: str | None, fallback: str) -> str:
    base = (raw or fallback or "loop-run").strip().lower()
    base = re.sub(r"[^a-z0-9가-힣._-]+", "-", base)
    base = re.sub(r"-+", "-", base).strip("-._")
    return base[:80] or "loop-run"


def _normalize_track(value: str | None) -> str | None:
    raw = (value or "").strip().lower().replace("_", "-")
    aliases = {
        "standard": "standard", "standard-loop": "standard", "standard loop": "standard", "1": "standard",
        "full": "full", "full-loop": "full", "full loop": "full", "2": "full",
        "gs": "gs", "gs-loop": "gs", "gs loop": "gs", "growth": "gs", "growth-strategy": "gs", "3": "gs",
    }
    return aliases.get(raw)


def _normalize_depth(value: str | None, track: str) -> str:
    if track != "gs":
        return ""
    raw = (value or "standard").strip().lower().replace("_", "-")
    return GS_DEPTHS.get(raw, "standard")


def _normalize_trigger_mode(value: str | None) -> str:
    raw = (value or "manual").strip().lower().replace("_", "-")
    aliases = {
        "manual": "manual", "manually": "manual", "start": "manual", "once": "manual", "1": "manual",
        "interval": "interval", "cadence": "interval", "schedule": "interval", "scheduled": "interval", "cron": "interval", "2": "interval",
        "event": "event", "hook": "event", "hooks": "event", "pre-commit": "event", "post-edit": "event", "post-merge": "event", "3": "event",
    }
    return aliases.get(raw, "manual")


def _default_grade(track: str, depth: str = "") -> str:
    if track == "full" or depth == "Full GS":
        return "HEAVY"
    return "STANDARD"


def _normalize_grade(value: str | None, track: str, depth: str = "") -> str:
    raw = (value or "").strip().lower().replace("_", "-")
    return GRADES.get(raw, _default_grade(track, depth))


def _default_root(root_path: str | None) -> Path:
    if root_path:
        return Path(root_path).expanduser()
    return Path(os.getenv("TERMINAL_CWD") or os.getcwd()).expanduser() / "loop-runs"


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_redact(content).rstrip() + "\n", encoding="utf-8")


def _source_status() -> dict[str, Any]:
    required = [GS_SOURCE_ROOT / "AGENTS.md", GS_SOURCE_ROOT / "prompts" / "00-mission-anchor.md", GS_SOURCE_ROOT / "rubrics" / "growth-strategy-rubric.md"]
    return {"root": str(GS_SOURCE_ROOT), "exists": GS_SOURCE_ROOT.exists(), "required_files": {str(p.relative_to(GS_SOURCE_ROOT)): p.exists() for p in required}, "ready": GS_SOURCE_ROOT.exists() and all(p.exists() for p in required)}


def _brief_template(track: str, depth: str, args: dict[str, Any], run_id: str) -> str:
    grade = _normalize_grade(args.get("grade"), track, depth)
    lines = [
        "# Loop Run Brief", "", f"- run_id: `{run_id}`", f"- track: `{track}` / {TRACK_LABELS[track]}", f"- trigger_mode: `{_normalize_trigger_mode(args.get('trigger_mode'))}`", f"- gs_depth: `{depth or 'n/a'}`", f"- grade: `{grade}`", f"- created_at: {_now().isoformat(timespec='seconds')}", f"- source_skill: `{SKILL_ROOT}`", "",
        "## Minimum Brief", f"- Artifact / draft: {args.get('artifact') or 'TODO: paste path or draft text'}", f"- Reader / evaluator: {args.get('reader') or 'TODO'}", f"- Desired outcome: {args.get('outcome') or 'TODO'}", f"- Constraints / evidence permission: {args.get('constraints') or 'TODO'}", "", "## Track Selection Rationale",
    ]
    if track == "standard":
        lines.append("Standard Loop selected: artifact quality is the product; reusable loop-policy evidence is not required.")
    elif track == "full":
        lines.append("Full Loop selected: artifact plus loop architecture/policy/replay/transfer evidence must be explicit.")
    else:
        lines += ["GS Loop selected: core claim is growth/revenue/GTM, so money path and revenue-learning evidence are first-class.", "", "## GS Brief", f"- Company / product / offer: {args.get('company') or 'TODO'}", f"- Target growth outcome: {args.get('growth_outcome') or args.get('outcome') or 'TODO'}", f"- Target customer / buyer: {args.get('customer') or 'TODO'}", f"- Time horizon: {args.get('horizon') or 'TODO: 7/30/90 days'}", f"- Public research allowed: {args.get('research_allowed') if args.get('research_allowed') is not None else 'TODO'}", f"- Payer / buying trigger / budget authority: {args.get('payer') or args.get('buying_trigger') or 'TODO'}"]
        if depth == "Full GS":
            status = _source_status()
            lines += ["", "## Full GS Source Contract", f"- canonical_source_root: `{status['root']}`", f"- source_ready: `{status['ready']}`"]
            for rel, ok in status["required_files"].items():
                lines.append(f"- {rel}: {'present' if ok else 'MISSING'}")
    lines += ["", "## Required References", "- loop-track-selection.md", "- per-loop-trace-requirement.md", "- generative-sequence-loop-harness.md for full/gs or whenever the run risks becoming a checklist"]
    if track == "gs":
        lines.append("- gs-loop-type.md")
    return "\n".join(lines)


def _harness_template(track: str, depth: str, trigger_mode: str = "manual") -> str:
    title = "GS Harness" if track == "gs" else "Harness"
    if track == "gs":
        weights = "Money path 25 / ICP+offer 20 / Channel 15 / Evidence 15 / Experiment 15 / Handoff 10"
        hard_fails = "payer/buying trigger missing; concrete outcome missing; no decision rule; generic advice; hidden assumptions"
    elif track == "full":
        weights = "Artifact quality + loop architecture + observability + policy/update path + replay/transfer evidence"
        hard_fails = "missing loop-spec; no failure taxonomy; no replay/transfer statement; unverifiable claims; no policy boundary"
    else:
        weights = "Artifact quality + reader fit + evidence hygiene + hard-fail removal + next action clarity"
        hard_fails = "unclear artifact/outcome/evaluator; vague acceptance criteria; no negative assertions; inflated score"
    return f"""# {title}

## Route
- selected_track: `{track}` / {TRACK_LABELS[track]}
- trigger_mode: `{trigger_mode}`
- gs_depth: `{depth or 'n/a'}`

## Artifact Definition
- Artifact:
- Reader / evaluator:
- Job-to-be-done:
- Failure condition:

## Quality Bar
- Rubric weights: {weights}
- Evidence standard: [Strong] / [Moderate] / [Emerging] / [Expert] / [Contested] / [Assumption] / [Unknown]
- Hard-fails: {hard_fails}

## Generative Sequence Map
1. Intent Seed:
2. Fitness Criteria:
3. Smallest Viable Artifact:
4. Evaluation Surface:
5. Failure Taxonomy:
6. Mutation Policy:
7. Memory / Evidence Update:
8. Transfer Check:

## Predicate Test Plan
- Predicate 1:
  - Success signal:
  - Negative assertion:
  - Evidence source:
- Predicate 2:
  - Success signal:
  - Negative assertion:
  - Evidence source:

## Iteration Rule
- Standard: normally 5–8 predicate-level micro-loops.
- Full: normally 8–15 loops plus loop architecture evidence.
- GS Quick: 3–5 loops; GS standard: 6–10 loops; Full GS: canonical GS kit evidence rules.

## Stop Rule
Stop only when hard-fails are cleared, per-loop traces are complete, and expected next gain is below 5 points or blocked by human/domain input.

## Anti-gaming Rules
- Do not modify the check command or exit criteria to force success.
- Do not skip, disable, or bypass checks to pass the exit condition.
- If stuck after several iterations, stop and report blockers instead of gaming metrics.
"""


def _loop_spec_template(track: str, depth: str) -> str:
    return f"""# Loop Spec

## Scope
- track: `{track}`
- gs_depth: `{depth or 'n/a'}`
- This is separate from the artifact harness. It defines loop architecture and evidence policy.

## Predicate Contract
- success_predicate:
- hard_fail_predicate:
- negative_assertion:
- observation_method:
- from_scratch_replay_condition:

## Control Surface Placement
- context_load:
- input_gate:
- pre_action_veto:
- post_action_readback:
- stop_handoff:
- permission/compression/idle risk:

## Failure-Mode Library
- artifact_gap:
- evidence_gap:
- evaluator_gap:
- process_gap:
- human_decision_gap:

## Policy Update Plan
- promotion_status: record-only / candidate / approved / applied
- update_trigger:
- regression_check:

## Replay / Regression / Mutation / Transfer
- replay evidence:
- regression matrix:
- mutation negative tests:
- transfer smoke test:

## Honest Level Claim
- current claim:
- cap reason:
"""


def _goal_contract_template(track: str, depth: str, args: dict[str, Any], run_id: str, trigger_mode: str = "manual") -> str:
    grade = _normalize_grade(args.get("grade"), track, depth)
    budget = "TODO: token / wall-clock / iteration / cost budget"
    if track == "standard":
        budget = "TODO: 5-8 predicate loops or explicit lower bound with reason"
    elif track == "full":
        budget = "TODO: 8-15 loops plus replay/regression/transfer evidence budget"
    elif track == "gs":
        budget = f"TODO: GS {depth or 'standard'} depth budget and revenue-learning evidence budget"
    return f"""# Goal Contract

## Persistent Goal State
- goal_id: `{run_id}`
- grade: {grade}
- trigger_mode: {trigger_mode}
- objective: {args.get('outcome') or 'TODO: specific outcome this loop must achieve'}
- completion_criteria: TODO: observable criteria that make completion auditable
- hard_fails: TODO: conditions that block PASS/PASS_WITH_RISKS
- verification_surface: TODO: files, commands, rubrics, reviewer, or live checks used to judge completion
- budget: {budget}
- lifecycle_state: active
- owner: human final approval / harness scaffolding / verifier completion gate
- current_artifact_hash: TODO: hash, version, or source path of the starting artifact
- stale_update_guard: goal_id + run_id + iteration_id + artifact_hash must match before state mutation
- kickoff_boundary: kickoff/deeplink text does not install files, enable hooks, or prove autonomous execution
- next_continuation_condition: TODO: named failed predicate, remaining hard-fail, material expected gain, or explicit human instruction

## Spec Contract Addendum
- non_goals: TODO: over-broad scopes or tempting expansions this run will not do
- must_read: TODO: path + authority_reason for contract/boundary files or source artifacts
- rejected_alternatives: TODO: at least two alternatives with category, alternative, and broken_boundary
- risks: TODO: risk + severity + runnable mitigation + acceptance_ref when relevant
- acceptance_criteria: TODO: criterion + verify.type/value + live evidence once verified
- forbidden_paths: TODO: globs or paths that must not be touched, or explicit none with reason

## Completion Boundary
- worker_claim_allowed: candidate_complete only
- achieved_owner: verifier or human gate only
- pass_mapping: achieved may map to PASS or PASS_WITH_RISKS only after hard-fails clear
- budget_limited_rule: soft stop with evidence, remaining work, and next-start condition; not silent success/failure

## Control Surface
- pause_resume_clear_replace_owner: human/runtime control, not model-inferred
- replacement_rule: archive previous goal state and issue a new goal_id before continuing
- pending_input_priority: pending human input or mailbox work preempts autonomous continuation
"""


def _iteration_template(num: int = 1) -> str:
    return f"""# Iteration {num:03d}

## Loop Goal
- Target predicate / hard-fail:
- Why this loop now:

## Input State
- Starting artifact/version:
- Known evidence:
- Known uncertainty:

## Learning Trace
- Current constraint:
- Controlled variable:
- Prediction before change:
- Measurement method:
- Expected result:
- Observed result:
- Study delta:
- Act decision: continue | mutate | stop | escalate | policy_update_candidate
- Learning level: single_loop | double_loop

## Action Taken
- Change made:
- Changed sections/files:
- Mutation policy applied:

## Evaluation Surface
- Rubric/test/review used:
- Negative assertion checked:
- Evidence source:

## Result
- Verdict:
- Score or qualitative delta:
- What improved:
- What got worse / tradeoff:
- Remaining hard-fails:

## Failure Taxonomy
- Type: artifact_gap | evidence_gap | evaluator_gap | process_gap | human_decision_gap | domain-specific subtype
- Root cause:

## Evidence Update
- New evidence added:
- Assumption resolved or still open:
- Score movement reason:

## Next Loop Condition
- Continue / stop / escalate:
- Next target:
"""


def _review_template() -> str:
    return """# Review Report

## Verdict
- Verdict: FAIL_INSUFFICIENT_INPUT
- Readiness tier: BLOCKED
- Score / cap:
- Cap reason:

## Loop Trace Summary
- Iteration 001: TODO — tried X → result Y → next mutation Z

## Hard-fails
- TODO

## Failure Taxonomy Counts
- artifact_gap:
- evidence_gap:
- evaluator_gap:
- process_gap:
- human_decision_gap:

## Next Mutation
- TODO
"""


def _quick_loop_card_template(track: str, depth: str, trigger_mode: str, args: dict[str, Any], run_path: Path) -> str:
    label = TRACK_LABELS[track]
    max_iter = "15" if track in {"standard", "full"} else "5" if depth == "Quick" else "10"
    check = args.get("check_command") or "TODO: verification command or document/rubric check"
    exit_when = args.get("exit_when") or "TODO: observable exit condition passes"
    step_one = args.get("step_1") or "Fill state/brief.md, then complete logs/iteration-001.md with a real predicate check."
    goal = args.get("outcome") or "TODO: observable goal for this loop"
    cadence = args.get("cadence") or ("TODO: interval cadence" if trigger_mode == "interval" else "n/a")
    event = args.get("event") or ("TODO: event hook" if trigger_mode == "event" else "n/a")
    return f"""# Quick Loop Card

## Copyable Kickoff
```text
Start the "{label}" loop.
Goal: {goal}
Max iterations: {max_iter}
Trigger mode: {trigger_mode}
Between iterations run: {check}
Exit when: {exit_when}
Step 1: {step_one}

Self-pace this loop. After each iteration, run the check command or evaluation surface, read the output, and only continue if the exit condition is not met. Stop when the exit condition passes or max iterations is reached. Give a short status update each pass.
```

## Trigger
- mode: `{trigger_mode}`
- interval cadence: {cadence}
- event hook: {event}

## Anti-gaming
- Do not modify the check command or exit criteria to force success.
- Do not skip, disable, or bypass checks to pass the exit condition.
- If stuck after several iterations, stop and report blockers instead of gaming metrics.

## Install / Hook Boundary
- This kickoff only gives the agent instructions. It does not install files or enable hooks.
- Hook/event bundles must be written into the repo/runtime and the agent or session restarted before they exist.
- Scaffold generation is not autonomous execution; validation evidence must be produced and read back.

## Lightweight Learning Trace
- Independent verifier pass: trust command/readback output, not implementer claims.
- Guardrails learning: if the same failure repeats twice, record a guardrail before trying another fix.
- Reflexion debug: after a failed repro, write the reflection to the iteration log before retrying.
- Spec-first execution: process exactly one unchecked requirement/story per iteration, verify it, then mark it complete.

## State Spine
- Run folder: `{run_path}`
- Durable goal: `state/goal-contract.md`
- Learning trace: `logs/iteration-*.md`
- Verifier-owned verdict: `final/review-report.md`
"""



def _predicate_list_template(track: str, depth: str) -> str:
    data = {
        "schema": "loop-creator-predicate-list-v1",
        "rules": {
            "single_active_predicate": True,
            "passing_requires_evidence": True,
            "blocked_requires_next_action": True,
            "do_not_skip_verification": True,
        },
        "status_legend": {
            "not_started": "Predicate has not been tested yet.",
            "active": "Current predicate under test.",
            "blocked": "Cannot continue until a documented blocker is resolved.",
            "passing": "Verification passed and evidence is recorded.",
        },
        "predicates": [
            {
                "id": "pred-001",
                "priority": 1,
                "behavior": "The final artifact satisfies the primary reader outcome.",
                "verification": "Run the declared check command or review surface and record evidence in logs/iteration-001.md.",
                "status": "active",
                "evidence": [],
                "blocker": "",
                "next_action": "Fill the first iteration with a real predicate check.",
            }
        ],
    }
    if track == "full" or depth == "Full GS":
        data["predicates"].append(
            {
                "id": "pred-002",
                "priority": 2,
                "behavior": "The loop policy is replayable from repo/run state without chat history.",
                "verification": "Read final/loop-spec.md plus session handoff and run replay/regression checks when available.",
                "status": "not_started",
                "evidence": [],
                "blocker": "",
                "next_action": "Define replay evidence before claiming architecture readiness.",
            }
        )
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"


def _session_handoff_template() -> str:
    return """# Session Handoff

## Verified Now
- What is currently working: TODO: record verified behavior and evidence.
- What verification actually ran: TODO: command, review surface, or readback.

## Changed This Session
- Artifact or behavior added: TODO: summarize material changes.
- Infrastructure or harness changes: TODO: summarize scaffold/harness changes.

## Broken Or Unverified
- Known defect: TODO: record known defect or `none observed with evidence`.
- Unverified path: TODO: record paths not yet checked.
- Risk for the next session: TODO: state the main restart risk.

## Next Best Step
- Highest-priority unfinished predicate: TODO: predicate id.
- Why it is next: TODO: reason.
- What counts as passing: TODO: exact evidence.
- What must not change during that step: TODO: constants/locked checks.

## Commands
- Startup: TODO: startup/readback command or `n/a with reason`.
- Verification: TODO: validation/check command.
- Focused debug command: TODO: focused command or `n/a with reason`.
"""


def _init_check_template(track: str, trigger_mode: str) -> str:
    return f"""# Initialization Check

Purpose: prove the run can be resumed and verified before implementation or rewriting starts.

## Startup Readiness
- standard startup path: TODO: command or readback path.
- standard verification path: TODO: validation command or evaluator surface.
- required files readable: state/brief.md, state/goal-contract.md, state/predicate-list.json, logs/iteration-001.md.
- trigger mode: `{trigger_mode}`.
- track: `{track}`.

## Initialization Result
- environment/readback status: TODO: PASS / BLOCKED with evidence.
- missing prerequisites: TODO: list or `none with evidence`.
- next safe action: TODO: first predicate or blocker resolution.
"""


def _clean_state_checklist_template() -> str:
    return """# Clean State Checklist

- [ ] The standard startup/readback path still works.
- [ ] The standard verification path still runs.
- [ ] Current progress is recorded in state/session-handoff.md.
- [ ] state/predicate-list.json reflects what is passing versus unverified.
- [ ] No half-finished step is left undocumented.
- [ ] Temporary/debug artifacts are removed or explicitly justified.
- [ ] The next session can continue without manual repair.

## Evidence
- Startup evidence: TODO.
- Verification evidence: TODO.
- Cleanup evidence: TODO.
- Next session instruction: TODO.
"""


def _quality_document_template(track: str, depth: str) -> str:
    return f"""# Quality Document

Quality snapshot for the generated loop run. Update after material iteration batches and before final handoff.

## Metadata
- track: `{track}`
- depth: `{depth or 'n/a'}`
- last_updated: TODO

## Artifact Domains

| Domain | Grade | Verification | Key Gaps | Last Updated |
|---|---|---|---|---|
| Goal Contract | TODO | TODO | TODO | TODO |
| Predicate State | TODO | TODO | TODO | TODO |
| Iteration Evidence | TODO | TODO | TODO | TODO |
| Final Artifact | TODO | TODO | TODO | TODO |
| Handoff Cleanliness | TODO | TODO | TODO | TODO |

## Change History

### TODO
- Changes:
- Domains promoted:
- New gaps identified:
- Gaps closed:
"""

def _summary_template(run_path: Path) -> str:
    return f"""# User-facing Summary

- Run folder: `{run_path}`
- Verdict: FAIL_INSUFFICIENT_INPUT until required brief/log/final evidence is filled.
- Readiness: BLOCKED
- Blocker: scaffold created; real loops and evaluation evidence still required.
- 👉 Next 30-minute action: fill `state/brief.md`, then complete `logs/iteration-001.md` with a real predicate check.
"""


def create_scaffold(args: dict[str, Any], **kwargs: Any) -> str:
    track = _normalize_track(args.get("track"))
    if not track:
        return _json({"success": False, "error": "track must be one of: standard, full, gs"})
    depth = _normalize_depth(args.get("depth"), track)
    grade = _normalize_grade(args.get("grade"), track, depth)
    trigger_mode = _normalize_trigger_mode(args.get("trigger_mode"))
    now = _now()
    slug = _safe_slug(args.get("slug"), f"{track}-loop")
    run_path = _default_root(args.get("root_path")) / f"{now.strftime('%Y-%m-%d')}_{slug}"
    if run_path.exists():
        run_path = run_path.with_name(run_path.name + "-" + now.strftime("%H%M%S"))
    for d in ["state", "final", "logs"]:
        (run_path / d).mkdir(parents=True, exist_ok=True)
    _write(run_path / "state" / "brief.md", _brief_template(track, depth, args, run_path.name))
    _write(run_path / "state" / "goal-contract.md", _goal_contract_template(track, depth, args, run_path.name, trigger_mode))
    _write(run_path / "state" / "predicate-list.json", _predicate_list_template(track, depth))
    _write(run_path / "state" / "session-handoff.md", _session_handoff_template())
    _write(run_path / "state" / "init-check.md", _init_check_template(track, trigger_mode))
    _write(run_path / "state" / "current.md", "# Current Artifact\n\nTODO: paste or link the current artifact/draft here.\n")
    if track == "gs":
        _write(run_path / "state" / "research-notes.md", f"# GS Research Notes\n\n- GS depth: `{depth}`\n- Public research allowed:\n- Revenue baseline / proxy:\n- Payer evidence:\n- Buying trigger evidence:\n- ICP evidence:\n- Channel evidence:\n- Assumptions / Unknowns:\n")
    else:
        _write(run_path / "state" / "research-notes.md", "# Research Notes / Limitation\n\nNo external research required yet. Add evidence if factual claims matter.\n")
    _write(run_path / "final" / ("gs-harness.md" if track == "gs" else "harness.md"), _harness_template(track, depth, trigger_mode))
    if track == "full" or depth == "Full GS":
        _write(run_path / "final" / "loop-spec.md", _loop_spec_template(track, depth))
    _write(run_path / "final" / "improved-draft.md", "# Improved Draft\n\nTODO: produce after loop iterations.\n")
    if track == "gs":
        _write(run_path / "final" / "growth-strategy.md", "# Growth Strategy\n\nTODO: money path, ICP, offer/channel, experiments, 7/30/90 roadmap.\n")
        _write(run_path / "final" / "experiment-plan.md", "# Experiment Plan\n\nTODO: 30-day experiment, decision rule, owner, measurement, stop/scale/pivot.\n")
    _write(run_path / "final" / "review-report.md", _review_template())
    _write(run_path / "final" / "quick-loop-card.md", _quick_loop_card_template(track, depth, trigger_mode, args, run_path))
    _write(run_path / "final" / "clean-state-checklist.md", _clean_state_checklist_template())
    _write(run_path / "final" / "quality-document.md", _quality_document_template(track, depth))
    _write(run_path / "final" / "user-facing-summary.md", _summary_template(run_path))
    _write(run_path / "logs" / "iteration-001.md", _iteration_template(1))
    _write(run_path / "loop-creator.json", _json({"track": track, "label": TRACK_LABELS[track], "trigger_mode": trigger_mode, "depth": depth, "grade": grade, "created_at": now.isoformat(timespec="seconds"), "source_skill": str(SKILL_ROOT), "gs_source": _source_status() if (track == "gs" and depth == "Full GS") else None}))
    return _json({"success": True, "path": str(run_path), "track": track, "label": TRACK_LABELS[track], "trigger_mode": trigger_mode, "depth": depth, "grade": grade, "validation": _validate_path(run_path), "next_action": "Fill state/brief.md and complete logs/iteration-001.md with a real predicate check."})


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return ""


def _meta(run_path: Path) -> dict[str, Any]:
    meta_path = run_path / "loop-creator.json"
    if meta_path.exists():
        try:
            data = json.loads(meta_path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except Exception:
            pass
    brief = _read(run_path / "state" / "brief.md")
    track = "gs" if "track: `gs`" in brief else "full" if "track: `full`" in brief else "standard"
    depth_match = re.search(r"gs_depth:\s*`([^`]+)`", brief)
    grade_match = re.search(r"grade:\s*`([^`]+)`", brief)
    trigger_match = re.search(r"trigger_mode:\s*`([^`]+)`", brief)
    depth = "" if not depth_match else depth_match.group(1)
    return {"track": track, "trigger_mode": _normalize_trigger_mode(trigger_match.group(1) if trigger_match else None), "depth": depth, "grade": _normalize_grade(grade_match.group(1) if grade_match else None, track, depth)}


def _field_value(text: str, label: str) -> str:
    m = re.search(rf"(?im)^\s*-\s*{re.escape(label)}\s*:\s*(.+)$", text)
    return m.group(1).strip() if m else ""


def _has_non_todo_value(text: str, label: str) -> bool:
    val = _field_value(text, label)
    return bool(val and "TODO" not in val and val not in {"`n/a`", "n/a"})


def _quality_warnings_for_fields(text: str, labels: list[str], *, path: str, min_chars: int = 24) -> list[dict[str, str]]:
    warnings: list[dict[str, str]] = []
    for label in labels:
        val = _field_value(text, label)
        if val and "TODO" not in val and len(val.strip(" `")) < min_chars:
            warnings.append({"type": "quality_warning", "path": path, "message": f"{label} may be too short to be auditable"})
    return warnings


def _normalize_quality_value(value: str) -> str:
    value = re.sub(r"`[^`]*`", "`X`", value.lower())
    value = re.sub(r"\b\d+\b", "N", value)
    value = re.sub(r"iteration-\d+|log\s+\d+|predicate\s+\d+", "item N", value)
    return re.sub(r"\s+", " ", value).strip()


def _fake_evidence_hits(text: str) -> list[str]:
    lowered = (text or "").lower()
    return [marker for marker in FAKE_EVIDENCE_MARKERS if marker in lowered]


def _fake_evidence_issues(text: str, *, path: str) -> list[dict[str, str]]:
    return [{"type": "evidence_gap", "path": path, "message": f"fake evidence marker present: {marker}"} for marker in _fake_evidence_hits(text)]


def _check_trace(log_path: Path) -> list[str]:
    text = _read(log_path)
    issues: list[str] = []
    for section in TRACE_SECTIONS:
        if not re.search(rf"(?m)^##\s+{re.escape(section)}\s*$", text):
            issues.append(f"missing section: {section}")
    for hint in TRACE_FIELD_HINTS:
        if hint not in text:
            issues.append(f"missing field hint: {hint}")
    empty_fields = re.findall(r"(?m)^-\s+([^:\n]+):\s*$", text)
    if empty_fields:
        issues.append(f"blank trace fields: {', '.join(empty_fields[:8])}{'…' if len(empty_fields) > 8 else ''}")
    for label in LEARNING_TRACE_REQUIRED:
        if not _has_non_todo_value(text, label):
            issues.append(f"missing real learning trace value: {label}")
    if "TODO" in text:
        issues.append("contains TODO placeholder")
    if re.search(r"(?i)iteration completed|score improved|revised draft", text):
        issues.append("opaque loop wording without trace detail")
    return issues



def _validate_predicate_list(run_path: Path) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    issues: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    rel = "state/predicate-list.json"
    path = run_path / rel
    if not path.exists():
        return ([{"type": "predicate_state_gap", "path": rel, "message": "predicate state file missing"}], warnings)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return ([{"type": "predicate_state_gap", "path": rel, "message": f"invalid JSON: {type(exc).__name__}"}], warnings)
    predicates = data.get("predicates")
    if not isinstance(predicates, list) or not predicates:
        issues.append({"type": "predicate_state_gap", "path": rel, "message": "predicates must be a non-empty list"})
        return issues, warnings
    active_count = 0
    for idx, pred in enumerate(predicates, 1):
        prefix = f"predicate {idx}"
        if not isinstance(pred, dict):
            issues.append({"type": "predicate_state_gap", "path": rel, "message": f"{prefix} must be an object"})
            continue
        for field in ["id", "behavior", "verification", "status", "evidence", "next_action"]:
            value = pred.get(field)
            if value in (None, "") or (isinstance(value, str) and "TODO" in value):
                issues.append({"type": "predicate_state_gap", "path": rel, "message": f"{prefix} missing or TODO: {field}"})
        status = pred.get("status")
        if status not in {"not_started", "active", "blocked", "passing"}:
            issues.append({"type": "predicate_state_gap", "path": rel, "message": f"{prefix} invalid status: {status}"})
        if status == "active":
            active_count += 1
        evidence = pred.get("evidence")
        if not isinstance(evidence, list):
            issues.append({"type": "predicate_state_gap", "path": rel, "message": f"{prefix} evidence must be a list"})
        elif status == "passing" and not evidence:
            issues.append({"type": "predicate_state_gap", "path": rel, "message": f"{prefix} passing requires evidence"})
        if status == "blocked":
            if not str(pred.get("blocker") or "").strip():
                issues.append({"type": "predicate_state_gap", "path": rel, "message": f"{prefix} blocked requires blocker"})
            if not str(pred.get("next_action") or "").strip():
                issues.append({"type": "predicate_state_gap", "path": rel, "message": f"{prefix} blocked requires next_action"})
    if active_count > 1:
        issues.append({"type": "predicate_state_gap", "path": rel, "message": "only one active predicate allowed"})
    if active_count == 0 and not any(isinstance(p, dict) and p.get("status") == "passing" for p in predicates):
        warnings.append({"type": "quality_warning", "path": rel, "message": "no active or passing predicate recorded"})
    return issues, warnings


def _require_markers(text: str, *, rel: str, markers: list[str], issue_type: str) -> list[dict[str, str]]:
    return [{"type": issue_type, "path": rel, "message": f"missing marker: {marker}"} for marker in markers if marker not in text]


def _validate_restartability_artifacts(run_path: Path) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    issues: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    handoff = _read(run_path / "state" / "session-handoff.md")
    issues.extend(_require_markers(handoff, rel="state/session-handoff.md", issue_type="handoff_gap", markers=["## Verified Now", "## Changed This Session", "## Broken Or Unverified", "## Next Best Step", "## Commands"]))
    if "TODO" in handoff:
        issues.append({"type": "handoff_gap", "path": "state/session-handoff.md", "message": "session handoff still contains TODO"})
    init_check = _read(run_path / "state" / "init-check.md")
    issues.extend(_require_markers(init_check, rel="state/init-check.md", issue_type="init_check_gap", markers=["## Startup Readiness", "standard startup path", "standard verification path", "## Initialization Result"]))
    if "TODO" in init_check:
        issues.append({"type": "init_check_gap", "path": "state/init-check.md", "message": "init check still contains TODO"})
    clean = _read(run_path / "final" / "clean-state-checklist.md")
    issues.extend(_require_markers(clean, rel="final/clean-state-checklist.md", issue_type="clean_state_gap", markers=["# Clean State Checklist", "## Evidence", "Startup evidence", "Verification evidence", "Next session instruction"]))
    if "- [ ]" in clean:
        issues.append({"type": "clean_state_gap", "path": "final/clean-state-checklist.md", "message": "clean-state checklist has unchecked items"})
    if "TODO" in clean:
        issues.append({"type": "clean_state_gap", "path": "final/clean-state-checklist.md", "message": "clean-state checklist still contains TODO"})
    quality = _read(run_path / "final" / "quality-document.md")
    issues.extend(_require_markers(quality, rel="final/quality-document.md", issue_type="quality_doc_gap", markers=["## Artifact Domains", "Goal Contract", "Predicate State", "Iteration Evidence", "Handoff Cleanliness", "## Change History"]))
    if "TODO" in quality:
        issues.append({"type": "quality_doc_gap", "path": "final/quality-document.md", "message": "quality document still contains TODO"})
    return issues, warnings

def _validate_path(run_path: Path) -> dict[str, Any]:
    issues: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    if not run_path.exists() or not run_path.is_dir():
        return {"ok": False, "passable": False, "issues": [{"type": "scaffold_gap", "path": str(run_path), "message": "run folder missing"}], "warnings": []}
    meta = _meta(run_path)
    track = _normalize_track(meta.get("track")) or "standard"
    depth = _normalize_depth(meta.get("depth"), track)
    grade = _normalize_grade(meta.get("grade"), track, depth)
    required = ["state/brief.md", "state/goal-contract.md", "state/predicate-list.json", "state/session-handoff.md", "state/init-check.md", "state/current.md", "state/research-notes.md", "final/improved-draft.md", "final/review-report.md", "final/quick-loop-card.md", "final/clean-state-checklist.md", "final/quality-document.md", "final/user-facing-summary.md", "final/gs-harness.md" if track == "gs" else "final/harness.md"]
    if track == "full" or depth == "Full GS":
        required.append("final/loop-spec.md")
    if track == "gs":
        required += ["final/growth-strategy.md", "final/experiment-plan.md"]
    for rel in required:
        if not (run_path / rel).exists():
            issues.append({"type": "scaffold_gap", "path": rel, "message": "required file missing"})
    pred_issues, pred_warnings = _validate_predicate_list(run_path)
    issues.extend(pred_issues)
    warnings.extend(pred_warnings)
    restart_issues, restart_warnings = _validate_restartability_artifacts(run_path)
    issues.extend(restart_issues)
    warnings.extend(restart_warnings)
    brief = _read(run_path / "state" / "brief.md")
    for label in ["Artifact / draft", "Reader / evaluator", "Desired outcome", "Constraints / evidence permission"]:
        if not _has_non_todo_value(brief, label):
            issues.append({"type": "brief_gap", "path": "state/brief.md", "message": f"missing or TODO: {label}"})
    goal_contract = _read(run_path / "state" / "goal-contract.md")
    for label in GOAL_CONTRACT_FIELDS:
        if not _has_non_todo_value(goal_contract, label):
            issues.append({"type": "goal_contract_gap", "path": "state/goal-contract.md", "message": f"missing or TODO: {label}"})
    if "candidate_complete" not in goal_contract or "achieved_owner" not in goal_contract:
        issues.append({"type": "goal_contract_gap", "path": "state/goal-contract.md", "message": "completion boundary must distinguish candidate_complete from achieved/PASS"})
    if "budget_limited" not in goal_contract:
        issues.append({"type": "goal_contract_gap", "path": "state/goal-contract.md", "message": "budget_limited soft-stop rule missing"})
    if "kickoff_boundary" not in goal_contract:
        issues.append({"type": "goal_contract_gap", "path": "state/goal-contract.md", "message": "kickoff/install boundary missing"})
    quick_card = _read(run_path / "final" / "quick-loop-card.md")
    for marker in ["## Copyable Kickoff", "Goal:", "Max iterations:", "Between iterations run:", "Exit when:", "Step 1:", "## Anti-gaming", "## Install / Hook Boundary", "## Lightweight Learning Trace"]:
        if marker not in quick_card:
            issues.append({"type": "quick_card_gap", "path": "final/quick-loop-card.md", "message": f"missing quick card marker: {marker}"})
    warnings.extend(_quality_warnings_for_fields(goal_contract, ["completion_criteria", "hard_fails", "next_continuation_condition"], path="state/goal-contract.md", min_chars=40))
    spec_required_by_grade = {
        "LIGHT": ["acceptance_criteria"],
        "STANDARD": ["non_goals", "must_read", "rejected_alternatives", "risks", "acceptance_criteria"],
        "HEAVY": ["non_goals", "must_read", "rejected_alternatives", "risks", "acceptance_criteria", "forbidden_paths"],
    }
    for label in spec_required_by_grade[grade]:
        if not _has_non_todo_value(goal_contract, label):
            issues.append({"type": "spec_contract_gap", "path": "state/goal-contract.md", "message": f"missing or TODO for {grade}: {label}"})
    for label in set(SPEC_CONTRACT_FIELDS + ["forbidden_paths"]) - set(spec_required_by_grade[grade]):
        if not _has_non_todo_value(goal_contract, label):
            warnings.append({"type": "quality_warning", "path": "state/goal-contract.md", "message": f"{label} is optional for {grade} but useful for auditability"})
    if track == "gs":
        for label in ["Company / product / offer", "Target growth outcome", "Target customer / buyer", "Payer / buying trigger / budget authority"]:
            if not _has_non_todo_value(brief, label):
                issues.append({"type": "gs_contract_gap", "path": "state/brief.md", "message": f"missing or TODO: {label}"})
    logs = sorted((run_path / "logs").glob("iteration-*.md")) if (run_path / "logs").exists() else []
    min_logs = 5 if track == "standard" else 8 if track == "full" else 3 if depth == "Quick" else 9 if depth == "Full GS" else 6
    if len(logs) < min_logs:
        issues.append({"type": "trace_gap", "path": "logs/", "message": f"only {len(logs)} iteration logs; required minimum is {min_logs}"})
    trace_quality_values: dict[str, list[tuple[str, str]]] = {label: [] for label in ["Prediction before change", "Observed result", "Act decision"]}
    for log in logs:
        log_rel = str(log.relative_to(run_path))
        log_text = _read(log)
        for issue in _check_trace(log):
            issues.append({"type": "trace_gap", "path": log_rel, "message": issue})
        for label in ["Observed result", "Evidence source", "New evidence added"]:
            value = _field_value(log_text, label)
            if value:
                issues.extend(_fake_evidence_issues(value, path=log_rel))
        warnings.extend(_quality_warnings_for_fields(log_text, ["Prediction before change", "Observed result", "Act decision"], path=log_rel, min_chars=32))
        for label in trace_quality_values:
            value = _field_value(log_text, label)
            if value and "TODO" not in value:
                trace_quality_values[label].append((log_rel, value))
    for label, values in trace_quality_values.items():
        if len(values) >= 3:
            normalized = {_normalize_quality_value(value) for _, value in values}
            if len(normalized) == 1:
                warnings.append({"type": "quality_warning", "path": "logs/", "message": f"{label} appears copy-pasted across {len(values)} iteration logs"})
    report = _read(run_path / "final" / "review-report.md")
    issues.extend(_fake_evidence_issues(report, path="final/review-report.md"))
    if "## Loop Trace Summary" not in report:
        issues.append({"type": "trace_gap", "path": "final/review-report.md", "message": "missing Loop Trace Summary"})
    if "TODO" in report:
        issues.append({"type": "evidence_gap", "path": "final/review-report.md", "message": "review report still contains TODO"})
    if depth == "Full GS":
        status = _source_status()
        if not status["ready"]:
            issues.append({"type": "gs_contract_gap", "path": str(GS_SOURCE_ROOT), "message": "Full GS canonical source package incomplete or unreadable"})
        span = max((p.stat().st_mtime for p in logs), default=0) - min((p.stat().st_mtime for p in logs), default=0)
        if span < 40 * 60:
            issues.append({"type": "gs_contract_gap", "path": "logs/", "message": "Full GS requires 40 minutes real wall-clock evidence across iteration mtimes"})
        text_all = "\n".join(_read(p) for p in [run_path / "final" / "review-report.md", run_path / "final" / "growth-strategy.md", run_path / "state" / "research-notes.md"] if p.exists())
        for marker in ["challenger", "comparison", "synthesis", "92", "hard_fail_count"]:
            if marker.lower() not in text_all.lower():
                issues.append({"type": "gs_contract_gap", "path": "final/", "message": f"Full GS missing evidence marker: {marker}"})
    by_type: dict[str, int] = {}
    for issue in issues:
        by_type[issue["type"]] = by_type.get(issue["type"], 0) + 1
    return {"ok": not any(i["type"] == "scaffold_gap" for i in issues), "passable": len(issues) == 0, "track": track, "trigger_mode": _normalize_trigger_mode(meta.get("trigger_mode")), "depth": depth, "grade": grade, "min_logs": min_logs, "log_count": len(logs), "issues": issues, "issue_counts": by_type, "warnings": warnings}


def validate_run(args: dict[str, Any], **kwargs: Any) -> str:
    raw = args.get("path") or ""
    if not raw:
        return _json({"success": False, "error": "path is required"})
    path = Path(raw).expanduser()
    return _json({"success": True, "path": str(path), "validation": _validate_path(path)})


def summarize_run(args: dict[str, Any], **kwargs: Any) -> str:
    raw = args.get("path") or ""
    if not raw:
        return _json({"success": False, "error": "path is required"})
    run_path = Path(raw).expanduser()
    validation = _validate_path(run_path)
    meta = _meta(run_path)
    logs = sorted((run_path / "logs").glob("iteration-*.md")) if (run_path / "logs").exists() else []
    loop_lines = []
    for log in logs[:20]:
        text = _read(log)
        goal = re.search(r"(?m)^- Target predicate / hard-fail:[ \t]*([^\n]*)$", text)
        result = re.search(r"(?m)^- Verdict:[ \t]*([^\n]*)$", text)
        nxt = re.search(r"(?m)^- Next target:[ \t]*([^\n]*)$", text)
        loop_lines.append({"file": str(log.relative_to(run_path)), "goal": (goal.group(1).strip() or "missing") if goal else "missing", "result": (result.group(1).strip() or "missing") if result else "missing", "next": (nxt.group(1).strip() or "missing") if nxt else "missing"})
    top_issues = validation.get("issues", [])[:8]
    next_mutation = "No validation blockers — review the artifact quality and decide whether to hand off, run another loop, or archive evidence."
    if top_issues:
        first = top_issues[0]
        next_mutation = f"Fix {first['type']} in {first['path']}: {first['message']}"
    return _json({"success": True, "path": str(run_path), "track": meta.get("track"), "trigger_mode": _normalize_trigger_mode(meta.get("trigger_mode")), "depth": meta.get("depth"), "grade": validation.get("grade"), "passable": validation.get("passable", False), "issue_counts": validation.get("issue_counts", {}), "warning_count": len(validation.get("warnings", [])), "warnings": validation.get("warnings", [])[:5], "loop_trace": loop_lines, "top_blockers": top_issues, "next_mutation": next_mutation})


def check_update(args: dict[str, Any], **kwargs: Any) -> str:
    remote = args.get("remote") or "origin"
    branch = args.get("branch") or "HEAD"
    script = Path(__file__).parent / "scripts" / "check_update.py"
    try:
        proc = subprocess.run(
            ["python3", str(script), "--remote", str(remote), "--branch", str(branch), "--format", "json"],
            cwd=Path(__file__).parent,
            text=True,
            capture_output=True,
            timeout=45,
        )
    except Exception as exc:
        return _json({"success": False, "error": f"update check failed: {type(exc).__name__}: {exc}"})
    if proc.returncode != 0:
        return _json({"success": False, "error": (proc.stderr or proc.stdout).strip()})
    try:
        return _json(json.loads(proc.stdout))
    except Exception:
        return _json({"success": False, "error": "update check returned invalid JSON", "stdout": proc.stdout[-1000:]})


def parse_kv_args(raw: str) -> dict[str, Any]:
    args: dict[str, Any] = {}
    tokens = shlex.split(raw or "")
    rest: list[str] = []
    if tokens:
        maybe = _normalize_track(tokens[0])
        if maybe:
            args["track"] = maybe
            tokens = tokens[1:]
    for token in tokens:
        if "=" in token:
            k, v = token.split("=", 1)
            k = k.strip().replace("-", "_")
            val: Any = v.strip()
            if val.lower() in {"true", "yes", "1"}:
                val = True
            elif val.lower() in {"false", "no", "0"}:
                val = False
            args[k] = val
        else:
            rest.append(token)
    if rest and "slug" not in args:
        args["slug"] = "-".join(rest)
    return args


def selector_text() -> str:
    return """어떤 하네스를 만들까?
1. standard loop — 실용 artifact 품질 개선
2. full loop — reusable loop/policy/evidence까지 검증
3. gs loop — growth/revenue/GTM 전략 하네스

바로 만들려면:
- `/loop-creator standard trigger_mode=manual grade=LIGHT slug=proposal artifact=... outcome=... check_command="python3 scripts/verify_run.py" exit_when="verifier exits 0"`
- `/loop-creator full trigger_mode=event event=post-merge grade=HEAVY slug=agent-workflow artifact=... outcome=...`
- `/loop-creator gs trigger_mode=interval cadence=7d depth=Quick grade=STANDARD slug=gtm-plan company=... customer=... payer=... buying_trigger=... outcome=...`

trigger_mode는 track과 별개야. track은 품질 깊이, trigger_mode는 시작 방식(manual/interval/event)을 뜻해.

Spec grade: LIGHT는 acceptance 중심, STANDARD는 non_goals/must_read/rejected_alternatives/risks/acceptance, HEAVY는 forbidden_paths까지 blocker로 봐.

생성된 run은 `state/goal-contract.md`와 `logs/iteration-*.md`의 Learning Trace를 채워야 passable이 돼.
이제 공식 이름은 `/loop-creator`야.
""".strip()


def handle_loop_creator(raw_args: str) -> str:
    args = parse_kv_args(raw_args)
    if not args.get("track"):
        return selector_text()
    data = json.loads(create_scaffold(args))
    if not data.get("success"):
        return f"실패: {data.get('error')}"
    v = data.get("validation", {})
    return "\n".join(["## loop-creator 생성 완료", f"- track: `{data['label']}`" + (f" / `{data.get('depth')}`" if data.get('depth') else "") + f" / trigger: `{data.get('trigger_mode')}` / grade: `{data.get('grade')}`", f"- path: `{data['path']}`", f"- quick card: `{data['path']}/final/quick-loop-card.md`", f"- scaffold_ok: `{v.get('ok')}` / passable: `{v.get('passable')}`", f"- blockers: `{v.get('issue_counts', {})}`", f"👉 다음 액션: `{data['path']}/state/brief.md` 채우고 `logs/iteration-001.md`를 실제 predicate check로 작성해."])


def handle_loop_validate(raw_args: str) -> str:
    path = (raw_args or "").strip()
    if not path:
        return "사용법: `/loop-validate <run-path>`"
    data = json.loads(validate_run({"path": path}))
    v = data["validation"]
    lines = ["## loop-validate 결과", f"- path: `{data['path']}`", f"- track: `{v.get('track')}` / trigger: `{v.get('trigger_mode')}` / depth: `{v.get('depth') or 'n/a'}` / grade: `{v.get('grade')}`", f"- scaffold_ok: `{v.get('ok')}` / passable: `{v.get('passable')}`", f"- logs: `{v.get('log_count')}/{v.get('min_logs')}`", f"- issue_counts: `{v.get('issue_counts', {})}`", f"- warnings: `{len(v.get('warnings', []))}`"]
    for issue in v.get("issues", [])[:8]:
        lines.append(f"- {issue['type']} @ `{issue['path']}`: {issue['message']}")
    for warning in v.get("warnings", [])[:5]:
        lines.append(f"- warning @ `{warning['path']}`: {warning['message']}")
    lines.append("👉 다음 액션: 첫 blocker부터 고쳐." if v.get("issues") else "👉 다음 액션: 없음 — passable 상태야.")
    return "\n".join(lines)


def handle_loop_summary(raw_args: str) -> str:
    path = (raw_args or "").strip()
    if not path:
        return "사용법: `/loop-summary <run-path>`"
    data = json.loads(summarize_run({"path": path}))
    lines = ["## loop-summary", f"- path: `{data['path']}`", f"- track: `{data.get('track')}` / trigger: `{data.get('trigger_mode', 'manual')}` / depth: `{data.get('depth') or 'n/a'}`", f"- passable: `{data.get('passable')}`", f"- issue_counts: `{data.get('issue_counts')}`", f"- warnings: `{data.get('warning_count', 0)}`"]
    for item in data.get("loop_trace", [])[:5]:
        lines.append(f"- {item['file']}: {item['goal']} → {item['result']} → {item['next']}")
    lines.append(f"👉 다음 액션: {data.get('next_mutation')}")
    return "\n".join(lines)


def handle_loop_update_check(raw_args: str) -> str:
    args = parse_kv_args(raw_args)
    data = json.loads(check_update(args))
    if not data.get("success"):
        return f"## loop-update-check 실패\n- error: {data.get('error')}\n👉 다음 액션: remote/auth/network 상태를 확인해."
    if data.get("update_available"):
        return "\n".join([
            "## loop-creator 업데이트 감지",
            f"- version: `{data.get('local_version')}`",
            f"- local: `{data.get('local_short')}`",
            f"- remote: `{data.get('remote_short')}`",
            "- 자동 적용: `false` — 승인 필요",
            f"👉 다음 액션: 승인 후 `{data.get('apply_command')}` 실행",
        ])
    return "\n".join([
        "## loop-creator 업데이트 확인",
        f"- version: `{data.get('local_version')}`",
        f"- status: 최신 상태 (`{data.get('local_short')}`)",
        "👉 다음 액션: 없음",
    ])


def pre_gateway_dispatch(event=None, **kwargs: Any):
    text = getattr(event, "text", "") if event is not None else ""
    stripped = (text or "").strip()
    lowered = stripped.lower()
    for cmd in ["loop-creator", "loop-validate", "loop-summary", "loop-update-check"]:
        if lowered == cmd or lowered.startswith(cmd + " "):
            return {"action": "rewrite", "text": "/" + stripped}
    if lowered == "loop creator" or lowered.startswith("loop creator "):
        return {"action": "rewrite", "text": "/loop-creator" + stripped[len("loop creator"):]}
    return None
