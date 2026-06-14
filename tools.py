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
GS_DEPTHS = {"quick": "Quick", "standard": "standard", "full": "Full GS", "full gs": "Full GS", "full-gs": "Full GS", "full_gs": "Full GS"}
SKILL_ROOT = Path(get_hermes_home()) / "skills" / "strategy" / "loop-harness-creator"
GS_SOURCE_ROOT = Path.home() / "haven-synk" / "30-Output" / "Teaching" / "lectures-challenges" / "50-harnesses" / "growth-strategy-ralph-kit"
TRACE_SECTIONS = ["Loop Goal", "Input State", "Learning Trace", "Action Taken", "Evaluation Surface", "Result", "Failure Taxonomy", "Evidence Update", "Next Loop Condition"]
TRACE_FIELD_HINTS = ["Target predicate", "Why this loop now", "Starting artifact", "Current constraint", "Controlled variable", "Prediction before change", "Measurement method", "Expected result", "Observed result", "Study delta", "Act decision", "Learning level", "Change made", "Mutation policy applied", "Rubric/test/review used", "Negative assertion checked", "Verdict", "Score or qualitative delta", "Type:", "New evidence added", "Continue / stop / escalate", "Next target"]
GOAL_CONTRACT_FIELDS = ["goal_id", "objective", "completion_criteria", "hard_fails", "verification_surface", "budget", "lifecycle_state", "owner", "current_artifact_hash", "stale_update_guard", "next_continuation_condition"]
LEARNING_TRACE_REQUIRED = ["Current constraint", "Controlled variable", "Prediction before change", "Measurement method", "Observed result", "Study delta", "Act decision", "Learning level"]
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
    lines = [
        "# Loop Run Brief", "", f"- run_id: `{run_id}`", f"- track: `{track}` / {TRACK_LABELS[track]}", f"- gs_depth: `{depth or 'n/a'}`", f"- created_at: {_now().isoformat(timespec='seconds')}", f"- source_skill: `{SKILL_ROOT}`", "",
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


def _harness_template(track: str, depth: str) -> str:
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


def _goal_contract_template(track: str, depth: str, args: dict[str, Any], run_id: str) -> str:
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
- objective: {args.get('outcome') or 'TODO: specific outcome this loop must achieve'}
- completion_criteria: TODO: observable criteria that make completion auditable
- hard_fails: TODO: conditions that block PASS/PASS_WITH_RISKS
- verification_surface: TODO: files, commands, rubrics, reviewer, or live checks used to judge completion
- budget: {budget}
- lifecycle_state: active
- owner: human final approval / harness scaffolding / verifier completion gate
- current_artifact_hash: TODO: hash, version, or source path of the starting artifact
- stale_update_guard: goal_id + run_id + iteration_id + artifact_hash must match before state mutation
- next_continuation_condition: TODO: named failed predicate, remaining hard-fail, material expected gain, or explicit human instruction

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
    now = _now()
    slug = _safe_slug(args.get("slug"), f"{track}-loop")
    run_path = _default_root(args.get("root_path")) / f"{now.strftime('%Y-%m-%d')}_{slug}"
    if run_path.exists():
        run_path = run_path.with_name(run_path.name + "-" + now.strftime("%H%M%S"))
    for d in ["state", "final", "logs"]:
        (run_path / d).mkdir(parents=True, exist_ok=True)
    _write(run_path / "state" / "brief.md", _brief_template(track, depth, args, run_path.name))
    _write(run_path / "state" / "goal-contract.md", _goal_contract_template(track, depth, args, run_path.name))
    _write(run_path / "state" / "current.md", "# Current Artifact\n\nTODO: paste or link the current artifact/draft here.\n")
    if track == "gs":
        _write(run_path / "state" / "research-notes.md", f"# GS Research Notes\n\n- GS depth: `{depth}`\n- Public research allowed:\n- Revenue baseline / proxy:\n- Payer evidence:\n- Buying trigger evidence:\n- ICP evidence:\n- Channel evidence:\n- Assumptions / Unknowns:\n")
    else:
        _write(run_path / "state" / "research-notes.md", "# Research Notes / Limitation\n\nNo external research required yet. Add evidence if factual claims matter.\n")
    _write(run_path / "final" / ("gs-harness.md" if track == "gs" else "harness.md"), _harness_template(track, depth))
    if track == "full" or depth == "Full GS":
        _write(run_path / "final" / "loop-spec.md", _loop_spec_template(track, depth))
    _write(run_path / "final" / "improved-draft.md", "# Improved Draft\n\nTODO: produce after loop iterations.\n")
    if track == "gs":
        _write(run_path / "final" / "growth-strategy.md", "# Growth Strategy\n\nTODO: money path, ICP, offer/channel, experiments, 7/30/90 roadmap.\n")
        _write(run_path / "final" / "experiment-plan.md", "# Experiment Plan\n\nTODO: 30-day experiment, decision rule, owner, measurement, stop/scale/pivot.\n")
    _write(run_path / "final" / "review-report.md", _review_template())
    _write(run_path / "final" / "user-facing-summary.md", _summary_template(run_path))
    _write(run_path / "logs" / "iteration-001.md", _iteration_template(1))
    _write(run_path / "loop-creator.json", _json({"track": track, "label": TRACK_LABELS[track], "depth": depth, "created_at": now.isoformat(timespec="seconds"), "source_skill": str(SKILL_ROOT), "gs_source": _source_status() if (track == "gs" and depth == "Full GS") else None}))
    return _json({"success": True, "path": str(run_path), "track": track, "label": TRACK_LABELS[track], "depth": depth, "validation": _validate_path(run_path), "next_action": "Fill state/brief.md and complete logs/iteration-001.md with a real predicate check."})


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
    return {"track": track, "depth": "" if not depth_match else depth_match.group(1)}


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


def _validate_path(run_path: Path) -> dict[str, Any]:
    issues: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    if not run_path.exists() or not run_path.is_dir():
        return {"ok": False, "passable": False, "issues": [{"type": "scaffold_gap", "path": str(run_path), "message": "run folder missing"}], "warnings": []}
    meta = _meta(run_path)
    track = _normalize_track(meta.get("track")) or "standard"
    depth = _normalize_depth(meta.get("depth"), track)
    required = ["state/brief.md", "state/goal-contract.md", "state/current.md", "state/research-notes.md", "final/improved-draft.md", "final/review-report.md", "final/user-facing-summary.md", "final/gs-harness.md" if track == "gs" else "final/harness.md"]
    if track == "full" or depth == "Full GS":
        required.append("final/loop-spec.md")
    if track == "gs":
        required += ["final/growth-strategy.md", "final/experiment-plan.md"]
    for rel in required:
        if not (run_path / rel).exists():
            issues.append({"type": "scaffold_gap", "path": rel, "message": "required file missing"})
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
    warnings.extend(_quality_warnings_for_fields(goal_contract, ["completion_criteria", "hard_fails", "next_continuation_condition"], path="state/goal-contract.md", min_chars=40))
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
    return {"ok": not any(i["type"] == "scaffold_gap" for i in issues), "passable": len(issues) == 0, "track": track, "depth": depth, "min_logs": min_logs, "log_count": len(logs), "issues": issues, "issue_counts": by_type, "warnings": warnings}


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
    return _json({"success": True, "path": str(run_path), "track": meta.get("track"), "depth": meta.get("depth"), "passable": validation.get("passable", False), "issue_counts": validation.get("issue_counts", {}), "warning_count": len(validation.get("warnings", [])), "warnings": validation.get("warnings", [])[:5], "loop_trace": loop_lines, "top_blockers": top_issues, "next_mutation": next_mutation})


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
- `/loop-creator standard slug=proposal artifact=... outcome=...`
- `/loop-creator full slug=agent-workflow artifact=... outcome=...`
- `/loop-creator gs depth=Quick slug=gtm-plan company=... customer=... payer=... buying_trigger=... outcome=...`

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
    return "\n".join(["## loop-creator 생성 완료", f"- track: `{data['label']}`" + (f" / `{data.get('depth')}`" if data.get('depth') else ""), f"- path: `{data['path']}`", f"- scaffold_ok: `{v.get('ok')}` / passable: `{v.get('passable')}`", f"- blockers: `{v.get('issue_counts', {})}`", f"👉 다음 액션: `{data['path']}/state/brief.md` 채우고 `logs/iteration-001.md`를 실제 predicate check로 작성해."])


def handle_loop_validate(raw_args: str) -> str:
    path = (raw_args or "").strip()
    if not path:
        return "사용법: `/loop-validate <run-path>`"
    data = json.loads(validate_run({"path": path}))
    v = data["validation"]
    lines = ["## loop-validate 결과", f"- path: `{data['path']}`", f"- track: `{v.get('track')}` / depth: `{v.get('depth') or 'n/a'}`", f"- scaffold_ok: `{v.get('ok')}` / passable: `{v.get('passable')}`", f"- logs: `{v.get('log_count')}/{v.get('min_logs')}`", f"- issue_counts: `{v.get('issue_counts', {})}`", f"- warnings: `{len(v.get('warnings', []))}`"]
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
    lines = ["## loop-summary", f"- path: `{data['path']}`", f"- track: `{data.get('track')}` / depth: `{data.get('depth') or 'n/a'}`", f"- passable: `{data.get('passable')}`", f"- issue_counts: `{data.get('issue_counts')}`", f"- warnings: `{data.get('warning_count', 0)}`"]
    for item in data.get("loop_trace", [])[:5]:
        lines.append(f"- {item['file']}: {item['goal']} → {item['result']} → {item['next']}")
    lines.append(f"👉 다음 액션: {data.get('next_mutation')}")
    return "\n".join(lines)


def pre_gateway_dispatch(event=None, **kwargs: Any):
    text = getattr(event, "text", "") if event is not None else ""
    stripped = (text or "").strip()
    lowered = stripped.lower()
    for cmd in ["loop-creator", "loop-validate", "loop-summary"]:
        if lowered == cmd or lowered.startswith(cmd + " "):
            return {"action": "rewrite", "text": "/" + stripped}
    if lowered == "loop creator" or lowered.startswith("loop creator "):
        return {"action": "rewrite", "text": "/loop-creator" + stripped[len("loop creator"):]}
    return None
