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
RISK_MODES = {"quick", "normal", "deep", "blocked"}
COVERAGE_RELATIONS = {"direct", "generic", "uncertain", "none"}
PASS_POLICIES = {"pass_once", "pass_2_of_3", "pass_3_of_3", "deterministic_only", "judge_with_trace_citations"}
AGENT_BACKENDS = {"hermes", "codex", "claude-code", "opencode", "openhands", "shell", "external"}
AUTOMATION_LEVELS = {"advisory", "step-mode", "supervised", "autonomous"}
FAILURE_TAXONOMY_TYPES = [
    "artifact_gap", "evidence_gap", "evaluator_gap", "process_gap", "human_decision_gap",
    "wrong_tool_selection", "tool_call_error", "semantic_mismatch", "goal_drift", "goal_hijacking",
    "context_contamination", "memory_poisoning", "plugin_or_mcp_abuse", "permission_escalation",
    "resource_exhaustion", "repeated_no_progress", "human_in_the_loop_bypass", "insufficient_traceability",
]
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

HERMES_HOOK_EVENTS = [
    "gateway:startup",
    "session:start",
    "session:end",
    "session:reset",
    "agent:start",
    "agent:step",
    "agent:end",
    "command:*",
]
DEFAULT_CONTROL_POLICY = {
    "hooks": {
        "gateway:startup": ["check_active_loop_registry"],
        "session:start": ["read_loop_handoff_if_active"],
        "session:end": ["require_session_handoff_for_active_run"],
        "session:reset": ["surface_resume_state_after_reset"],
        "agent:start": ["load_goal_contract_if_referenced"],
        "agent:step": ["append_step_observation_if_loop_run_active"],
        "agent:end": ["suggest_evidence_ledger_update"],
        "command:*": ["rewrite_or_validate_loop_commands"],
    },
    "event_rules": {
        "agent:start": ["must_read_goal_contract_before_mutating_run"],
        "agent:step": ["one_controlled_variable_per_iteration", "record_observed_result_before_next_mutation"],
        "agent:end": ["candidate_complete_requires_evidence_ledger_update"],
        "session:end": ["active_run_requires_session_handoff"],
        "command:*": ["loop_creator_commands_must_not_modify_exit_criteria_to_pass"],
    },
    "blocking_boundary": {
        "advisory_only": ["gateway:startup", "session:start", "agent:start", "agent:step", "agent:end", "session:reset"],
        "validator_blocker": ["missing_boundary_rule", "fake_evidence", "missing_handoff_for_active_run", "completion_without_observed_verification"],
        "hard_block_allowed_only_when": ["command:* policy returns explicit deny/rewrite", "future execution runner reaches permission or forbidden-path gate"],
    },
    "deletion_rule": "Remove or downgrade any hook/rule that does not reduce a named failure mode after three reviewed uses.",
}

INTAKE_ALIASES = {
    "goal": ["goal", "outcome"],
    "artifact": ["artifact", "draft"],
    "reader": ["reader", "evaluator"],
    "verify": ["verify", "verification", "check_command", "exit_when", "success"],
    "hard_fail": ["hard_fail", "hard_fails", "constraints"],
    "context": ["context", "must_read", "source", "sources"],
    "hook_moment": ["hook_moment", "hook", "hooks", "event"],
    "boundary_rule": ["boundary_rule", "boundary", "forbidden"],
    "escalation_rule": ["escalation_rule", "escalation", "human_gate"],
    "deletion_rule": ["deletion_rule", "delete_rule", "remove_when"],
}

INTAKE_QUESTION_ORDER = [
    "goal",
    "artifact",
    "verify",
    "reader",
    "hard_fail",
    "context",
    "hook_moment",
    "boundary_rule",
    "escalation_rule",
    "deletion_rule",
]

INTAKE_QUESTION_COPY = {
    "goal": {
        "blocked": "이번 run이 실제로 성공시켜야 할 목표가 비어 있음",
        "recommendation": "현재 초안을 특정 독자 기준으로 review-ready 상태까지 개선한다.",
        "question": "이번 루프가 만들거나 개선할 산출물의 목표는 뭐야?",
    },
    "artifact": {
        "blocked": "무엇을 읽고 고칠 artifact인지 불명확함",
        "recommendation": 'artifact="draft.md" 또는 artifact="현재 제안서 초안"처럼 넣어.',
        "question": "이번 루프가 다룰 artifact 또는 초안은 뭐야?",
    },
    "verify": {
        "blocked": "완료를 무엇으로 판정할지 비어 있음",
        "recommendation": 'verify="review rubric pass" 또는 check_command="python3 scripts/verify_run.py".',
        "question": "이 루프는 무엇이 통과되면 완료라고 볼까?",
    },
    "reader": {
        "blocked": "품질 기준을 누구 관점으로 볼지 불명확함",
        "recommendation": 'reader="B2B 마케팅 리드"처럼 실제 평가자를 적어.',
        "question": "누구 기준으로 이 artifact를 평가해야 해?",
    },
    "hard_fail": {
        "blocked": "PASS를 막아야 할 실패 조건이 비어 있음",
        "recommendation": 'hard_fail="검증 없이 완료 선언, exit criteria 조작, secret 저장".',
        "question": "이 루프에서 절대 허용하면 안 되는 실패는 뭐야?",
    },
    "context": {
        "blocked": "반드시 읽어야 할 기존 맥락이 있는지 불명확함",
        "recommendation": 'must_read="README.md, product brief, prior review" 또는 context="none".',
        "question": "시작 전에 반드시 읽어야 할 파일/맥락이 있어?",
    },
    "hook_moment": {
        "blocked": "언제 자동 점검/기록/차단이 필요한지 비어 있음",
        "recommendation": 'hook_moment="agent:step evidence 기록, agent:end PASS gate, session:end handoff".',
        "question": "이 루프에서 꼭 걸어야 할 hook moment는 뭐야?",
    },
    "boundary_rule": {
        "blocked": "Hook 시점에서 무엇을 막을지 boundary rule이 비어 있음",
        "recommendation": 'boundary_rule="no_fake_evidence, no_secret_in_artifacts, do_not_modify_exit_criteria_to_pass".',
        "question": "그 hook에서 절대 막아야 할 행동은 뭐야?",
    },
    "escalation_rule": {
        "blocked": "언제 사람에게 넘길지 기준이 비어 있음",
        "recommendation": 'escalation_rule="같은 실패 2회 반복 또는 forbidden path 필요 시 human approval".',
        "question": "몇 번 막히거나 어떤 위험이 생기면 사람에게 넘길까?",
    },
    "deletion_rule": {
        "blocked": "hook/rule이 효과 없을 때 제거할 기준이 비어 있음",
        "recommendation": 'deletion_rule="3회 사용 후 실패 감소/검토비용 감소/재시작성 개선이 없으면 제거".',
        "question": "이 hook/rule이 어떤 실패를 줄이지 못하면 제거하거나 강등할까?",
    },
}

ACO_ISSUE_MAP = {
    "scaffold_gap": "A6.Structure",
    "brief_gap": "A6.Context/A6.Plan",
    "goal_contract_gap": "A6.Plan/O3.State",
    "spec_contract_gap": "A6.Plan/C3.Rule",
    "trace_gap": "C3.Loop/O3.Evidence",
    "quick_card_gap": "C3.Rule/O3.State",
    "evidence_gap": "O3.Evidence/O3.Gate",
    "evidence_ledger_gap": "O3.Evidence/O3.Gate",
    "stop_gate_gap": "O3.Gate",
    "fresh_snapshot_gap": "O3.State/O3.Evidence",
    "coverage_gap": "O3.Evidence/O3.Gate",
    "gs_contract_gap": "A6.Plan/O3.Evidence",
    "predicate_state_gap": "O3.State/C3.Loop",
    "approval_gate_gap": "O3.Gate",
    "story_ledger_gap": "O3.State/O3.Evidence",
    "steering_ledger_gap": "O3.State/O3.Evidence",
    "review_receipt_gap": "O3.Evidence/O3.Gate",
    "handoff_gap": "O3.State",
    "init_check_gap": "A6.Structure/O3.State",
    "clean_state_gap": "O3.State/O3.Gate",
    "quality_doc_gap": "A6.Improvement/O3.Evidence",
    "control_policy_gap": "C3.Hook/C3.Rule",
    "aco_design_gap": "A6.Structure/C3.Control/O3.Operation",
    "eval_pack_gap": "A6.Verification/O3.Evidence",
    "failure_taxonomy_gap": "A6.Improvement/C3.Loop",
    "reliability_gate_gap": "O3.Gate",
    "harness_identity_gap": "A6.Verification/O3.Evidence",
    "fit_score_gap": "A6.Plan/O3.Gate",
    "runner_spec_gap": "A6.Execution/C3.Rule",
    "quality_warning": "A6.Improvement",
}


def _redact(text: str) -> str:
    return SECRET_RE.sub(lambda m: f"{m.group(1)}=[REDACTED]", text or "")


def _json(data: dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)


def _aco_layer_for_issue(issue_type: str) -> str:
    return ACO_ISSUE_MAP.get(issue_type, "ACO.Unmapped")


def _annotate_findings(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    for item in findings:
        if isinstance(item, dict) and "aco_layer" not in item:
            item["aco_layer"] = _aco_layer_for_issue(str(item.get("type") or ""))
    return findings


def _aco_summary(issues: list[dict[str, Any]], warnings: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    counts: dict[str, int] = {}
    for item in issues:
        layer = str(item.get("aco_layer") or _aco_layer_for_issue(str(item.get("type") or "")))
        counts[layer] = counts.get(layer, 0) + 1
    top_layer = "none"
    if counts:
        top_layer = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
    first_issue = issues[0] if issues else None
    return {
        "bottleneck": top_layer,
        "issue_counts_by_layer": counts,
        "first_blocker": first_issue,
        "warning_count": len(warnings or []),
    }


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



def _normalize_risk_mode(value: str | None, track: str, grade: str) -> str:
    raw = (value or "").strip().lower().replace("_", "-")
    aliases = {
        "quick": "quick", "q": "quick", "light": "quick",
        "normal": "normal", "standard": "normal", "n": "normal",
        "deep": "deep", "heavy": "deep", "d": "deep",
        "blocked": "blocked", "block": "blocked", "b": "blocked",
    }
    if raw in aliases:
        return aliases[raw]
    if grade == "HEAVY" or track in {"full", "gs"}:
        return "deep"
    if grade == "LIGHT":
        return "quick"
    return "normal"

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


def _arg_value(args: dict[str, Any], field: str) -> Any:
    for key in INTAKE_ALIASES.get(field, [field]):
        value = args.get(key)
        if value not in (None, ""):
            return value
    return None


def _has_arg(args: dict[str, Any], field: str) -> bool:
    value = _arg_value(args, field)
    if value is None:
        return False
    text = str(value).strip()
    return bool(text and text.lower() not in {"todo", "tbd", "n/a", "none?"})


def _intake_status(args: dict[str, Any], track: str) -> dict[str, Any]:
    allow_todo = bool(args.get("allow_todo") or args.get("force") or args.get("yes"))
    missing = [field for field in INTAKE_QUESTION_ORDER if not _has_arg(args, field)]
    next_field = "" if allow_todo or not missing else missing[0]
    return {"allow_todo": allow_todo, "missing": missing, "next_field": next_field, "ready": allow_todo or not missing}


def intake_question_text(args: dict[str, Any]) -> str:
    track = _normalize_track(args.get("track")) or "standard"
    status = _intake_status(args, track)
    field = status.get("next_field") or "goal"
    copy = INTAKE_QUESTION_COPY.get(field, INTAKE_QUESTION_COPY["goal"])
    current = _arg_value(args, "goal") or _arg_value(args, "artifact") or f"{TRACK_LABELS.get(track, track)} 하네스를 만들려는 상태"
    examples = [
        "```text",
        f"/loop-creator {track} goal=\"제안서 설득력 개선\" artifact=\"proposal.md\" reader=\"B2B 마케팅 리드\" verify=\"buyer-perspective review passes\" hard_fail=\"AI 티, 검증 없는 완료 선언\" context=\"README.md, prior review\" hook_moment=\"agent:step evidence 기록; agent:end PASS gate; session:end handoff\" boundary_rule=\"no_fake_evidence; do_not_modify_exit_criteria_to_pass\" escalation_rule=\"같은 실패 2회 반복 시 human approval\" deletion_rule=\"3회 후 실패 감소 없으면 제거\"",
        "```",
    ]
    return "\n".join([
        "## Loop Creator Intake",
        f"현재 이해: {current}",
        f"막힌 결정: {copy['blocked']}",
        f"추천 답안: {copy['recommendation']}",
        f"질문: {copy['question']}",
        "",
        "선택지는 2~3개만 쓰고 자유 입력도 가능해. 답을 한 줄 KV로 주면 바로 scaffold로 넘길게.",
        "",
        "예시:",
        *examples,
        "",
        "급하면 `allow_todo=true`를 붙여서 빈칸 포함 scaffold를 만들 수 있어.",
    ])


def _intake_template(track: str, depth: str, args: dict[str, Any], run_id: str) -> str:
    status = _intake_status(args, track)
    lines = [
        "# Intake",
        "",
        f"- run_id: `{run_id}`",
        f"- track: `{track}` / {TRACK_LABELS[track]}",
        f"- missing_at_creation: {', '.join(status['missing']) if status['missing'] else 'none'}",
        f"- allow_todo: `{status['allow_todo']}`",
        "",
        "## Goal Intake",
        f"- Goal: {_arg_value(args, 'goal') or 'TODO'}",
        f"- Artifact: {_arg_value(args, 'artifact') or 'TODO'}",
        f"- Reader / evaluator: {_arg_value(args, 'reader') or 'TODO'}",
        f"- Success / verify: {_arg_value(args, 'verify') or 'TODO'}",
        f"- Hard fail: {_arg_value(args, 'hard_fail') or 'TODO'}",
        f"- Must-read context: {_arg_value(args, 'context') or 'TODO'}",
        "",
        "## Control Intake",
        f"- Hook moment: {_arg_value(args, 'hook_moment') or 'TODO'}",
        f"- Boundary rule: {_arg_value(args, 'boundary_rule') or 'TODO'}",
        f"- Escalation rule: {_arg_value(args, 'escalation_rule') or 'TODO'}",
        f"- Deletion rule: {_arg_value(args, 'deletion_rule') or 'TODO'}",
        "",
        "## Interview Rule",
        "- Ask one question at a time.",
        "- Prefer existing args, files, and track presets over asking the user for what can be inferred.",
        "- Stop asking when goal, scope, constraints, completion gate, hook moment, boundary rule, escalation rule, and deletion rule are good enough to scaffold.",
    ]
    return "\n".join(lines)


def _hsd_values(track: str, depth: str, args: dict[str, Any]) -> dict[str, str]:
    trigger_mode = _normalize_trigger_mode(args.get("trigger_mode"))
    grade = _normalize_grade(args.get("grade"), track, depth)
    verify = _arg_value(args, "verify") or "TODO: observable verification surface"
    if args.get("check_command") and args.get("exit_when"):
        verify = f"{args.get('check_command')} → {args.get('exit_when')}"
    return {
        "track": track,
        "label": TRACK_LABELS[track],
        "depth": depth or "n/a",
        "grade": grade,
        "trigger_mode": trigger_mode,
        "goal": str(_arg_value(args, "goal") or "TODO"),
        "artifact": str(_arg_value(args, "artifact") or "TODO"),
        "reader": str(_arg_value(args, "reader") or "TODO"),
        "verify": str(verify),
        "hard_fail": str(_arg_value(args, "hard_fail") or "TODO"),
        "context": str(_arg_value(args, "context") or "TODO"),
        "hook_moment": str(_arg_value(args, "hook_moment") or "TODO"),
        "boundary_rule": str(_arg_value(args, "boundary_rule") or "TODO"),
        "escalation_rule": str(_arg_value(args, "escalation_rule") or "TODO"),
        "deletion_rule": str(_arg_value(args, "deletion_rule") or DEFAULT_CONTROL_POLICY["deletion_rule"]),
    }


def _hsd_improvement_suggestions(values: dict[str, str]) -> list[str]:
    suggestions: list[str] = []
    hard_fail = values["hard_fail"].lower()
    boundary = values["boundary_rule"].lower()
    hook = values["hook_moment"].lower()
    escalation = values["escalation_rule"].lower()
    if "todo" in values["verify"].lower() or len(values["verify"]) < 18:
        suggestions.append("검증 표면이 약해. command, rubric, reviewer, live check 중 하나를 더 구체화해.")
    if "no_fake_evidence" not in boundary and "검증" not in hard_fail and "evidence" not in hard_fail:
        suggestions.append("Boundary Rule에 `no_fake_evidence` 또는 '검증 없는 완료 선언 금지'를 명시해.")
    if "agent:step" not in hook and "iteration" not in hook:
        suggestions.append("매 iteration 후 evidence 기록 hook(`agent:step`)을 추가하면 trace 품질이 좋아져.")
    if "agent:end" not in hook and "pass" not in hook and "완료" not in hook:
        suggestions.append("완료 전 PASS gate(`agent:end`)를 넣어 worker 완료 선언과 verifier 판정을 분리해.")
    if "todo" in escalation or len(values["escalation_rule"]) < 12:
        suggestions.append("Escalation Rule이 약해. 같은 실패 2회 반복, forbidden path 필요, 비용 초과 중 하나를 기준으로 잡아.")
    if not suggestions:
        suggestions.append("현재 HSD는 scaffold로 넘길 수 있어. 다만 첫 iteration에서 실제 evidence surface를 반드시 관찰값으로 남겨.")
    return suggestions[:3]


def _hsd_template(track: str, depth: str, args: dict[str, Any], run_id: str) -> str:
    v = _hsd_values(track, depth, args)
    suggestions = _hsd_improvement_suggestions(v)
    return f"""# Harness Specification Document

- run_id: `{run_id}`
- track: `{v['track']}` / {v['label']}
- depth: `{v['depth']}`
- grade: `{v['grade']}`
- trigger_mode: `{v['trigger_mode']}`

## 1. Goal
- Goal: {v['goal']}
- Artifact: {v['artifact']}
- Reader / evaluator: {v['reader']}

## 2. Requirement Contract
- Success / verify: {v['verify']}
- Hard fail: {v['hard_fail']}
- Must-read context: {v['context']}

## 3. Control Contract
- Hook moment: {v['hook_moment']}
- Boundary rule: {v['boundary_rule']}
- Escalation rule: {v['escalation_rule']}
- Deletion rule: {v['deletion_rule']}

## 4. ACO Mapping
- A6.Plan: Goal, artifact, reader, verify, hard-fail.
- C3.Control: Hook moment, boundary rule, escalation rule, deletion rule.
- O3.Operation: Evidence ledger, approval gate, predicate list, review report, handoff.

## 5. Design Review Suggestions
{chr(10).join(f'- {item}' for item in suggestions)}

## Approval Gate
- Design gate status: {'approved for scaffold' if args.get('approve_hsd') else 'preview / awaiting approval'}
- To scaffold from slash command: add `approve_hsd=true`.
"""


def _hsd_diagram_template(track: str, depth: str, args: dict[str, Any]) -> str:
    v = _hsd_values(track, depth, args)
    suggestions = _hsd_improvement_suggestions(v)
    return f"""# HSD Diagram

## Design Flow

```text
Goal
  └─ {v['goal']}
      ↓
Artifact
  └─ {v['artifact']}
      ↓
Evaluator
  └─ {v['reader']}
      ↓
Success Gate
  └─ {v['verify']}
      ↓
Hard Fail / Boundary
  ├─ hard_fail: {v['hard_fail']}
  └─ boundary_rule: {v['boundary_rule']}
      ↓
Hook / Rule
  ├─ hook_moment: {v['hook_moment']}
  ├─ escalation_rule: {v['escalation_rule']}
  └─ deletion_rule: {v['deletion_rule']}
      ↓
Scaffold Build
  └─ state/ + final/ + logs/ evidence package
```

## 보강 제안
{chr(10).join(f'- {item}' for item in suggestions)}
"""


def _harness_diagram_template(track: str, depth: str, args: dict[str, Any], run_path: Path) -> str:
    harness_file = "final/gs-harness.md" if track == "gs" else "final/harness.md"
    return f"""# Harness Build Diagram

```text
state/intake.md
  ↓
state/hsd.md
  ↓
state/goal-contract.md ── state/control-policy.md
  ↓                         ↓
{harness_file}        state/predicate-list.json
  ↓                         ↓
logs/iteration-*.md → state/evidence-ledger.json
  ↓
final/review-report.md
  ↓
final/user-facing-summary.md
```

## Restart Point
- Run folder: `{run_path}`
- Start from: `state/session-handoff.md`
- Validate with: `/loop-validate {run_path}`
"""


def _harness_improvement_suggestions_template(track: str, depth: str, args: dict[str, Any], run_path: Path) -> str:
    v = _hsd_values(track, depth, args)
    suggestions = _hsd_improvement_suggestions(v)
    return f"""# Harness Improvement Suggestions

## Build Review
- Built run folder: `{run_path}`
- Track: `{v['track']}` / {v['label']}
- Current readiness: scaffold only; not passable until real iteration/evidence/review fields are filled.

## Suggested Reinforcements
{chr(10).join(f'- {item}' for item in suggestions)}

## Next Check
- Fill `logs/iteration-001.md` with one real predicate check.
- Record observed verification in `state/evidence-ledger.json`.
- Run `/loop-validate {run_path}` before claiming candidate completion.
"""


def hsd_preview_text(args: dict[str, Any]) -> str:
    track = _normalize_track(args.get("track")) or "standard"
    depth = _normalize_depth(args.get("depth"), track)
    v = _hsd_values(track, depth, args)
    suggestions = _hsd_improvement_suggestions(v)
    diagram = _hsd_diagram_template(track, depth, args)
    compact_diagram = diagram.split("## 보강 제안", 1)[0].strip()
    return "\n".join([
        "## HSD Preview — Harness Specification Document",
        f"- track: `{v['label']}` / trigger: `{v['trigger_mode']}` / grade: `{v['grade']}`",
        f"- goal: {v['goal']}",
        f"- artifact: {v['artifact']}",
        f"- evaluator: {v['reader']}",
        f"- success gate: {v['verify']}",
        "",
        compact_diagram,
        "",
        "## 보강 제안",
        *(f"- {item}" for item in suggestions),
        "",
        "👉 다음 액션: 이 설계가 맞으면 같은 명령에 `approve_hsd=true`를 붙여 scaffold를 생성해.",
    ])


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_redact(content).rstrip() + "\n", encoding="utf-8")


def _source_status() -> dict[str, Any]:
    required = [GS_SOURCE_ROOT / "AGENTS.md", GS_SOURCE_ROOT / "prompts" / "00-mission-anchor.md", GS_SOURCE_ROOT / "rubrics" / "growth-strategy-rubric.md"]
    return {"root": str(GS_SOURCE_ROOT), "exists": GS_SOURCE_ROOT.exists(), "required_files": {str(p.relative_to(GS_SOURCE_ROOT)): p.exists() for p in required}, "ready": GS_SOURCE_ROOT.exists() and all(p.exists() for p in required)}


def _brief_template(track: str, depth: str, args: dict[str, Any], run_id: str) -> str:
    grade = _normalize_grade(args.get("grade"), track, depth)
    lines = [
        "# Loop Run Brief", "", f"- run_id: `{run_id}`", f"- track: `{track}` / {TRACK_LABELS[track]}", f"- trigger_mode: `{_normalize_trigger_mode(args.get('trigger_mode'))}`", f"- risk_mode: `{_normalize_risk_mode(args.get('risk_mode'), track, grade)}`", f"- gs_depth: `{depth or 'n/a'}`", f"- grade: `{grade}`", f"- created_at: {_now().isoformat(timespec='seconds')}", f"- source_skill: `{SKILL_ROOT}`", "",
        "## Minimum Brief", f"- Artifact / draft: {_arg_value(args, 'artifact') or 'TODO: paste path or draft text'}", f"- Reader / evaluator: {_arg_value(args, 'reader') or 'TODO'}", f"- Desired outcome: {_arg_value(args, 'goal') or 'TODO'}", f"- Constraints / evidence permission: {args.get('constraints') or _arg_value(args, 'hard_fail') or _arg_value(args, 'context') or 'TODO'}", "", "## Track Selection Rationale",
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

## ACO Architecture Layer
### A6 — Architecture
- Structure: run folder layout, artifact placement, permission boundary.
- Context: required source/brief/current artifact boundaries.
- Plan: completion criteria, hard-fails, verifier surface, budget.
- Execution: maker/checker split, approval boundary, side-effect limits.
- Verification: static/domain/execution/human gate ladder.
- Improvement: failure taxonomy, policy update, skill/rule promotion or deletion.

### C3 — Control
- Hook: existing Hermes events from `state/control-policy.md`.
- Rule: guiding/boundary/escalation rules tied to events.
- Loop: one controlled variable, observed result, act decision, next mutation.

### O3 — Operation
- State: goal contract, predicate list, ledgers, handoff.
- Gate: plan, permission, verification, completion, handoff.
- Evidence: source/execution/review/user/business evidence with coverage relation.

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
- objective: {_arg_value(args, 'goal') or 'TODO: specific outcome this loop must achieve'}
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
    goal = _arg_value(args, "goal") or "TODO: observable goal for this loop"
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


def _evidence_ledger_template(track: str, grade: str, risk_mode: str) -> str:
    data = {
        "schema": "loop-creator-evidence-ledger-v2",
        "risk_mode": risk_mode,
        "verification_depth": risk_mode,
        "rules": {
            "observed_verification_required": risk_mode in {"normal", "deep"},
            "direct_or_generic_coverage_required": risk_mode == "deep",
            "completion_claim_requires_successful_verification": True,
            "completion_claim_requires_trace_citation": True,
            "do_not_record_failed_verification_as_success": True,
        },
        "changed_files": [],
        "verification_commands": [],
        "verification_results": [],
        "claims": [
            {
                "claim": "TODO: completion or quality claim being made",
                "evidence_path": "TODO: path to observed evidence",
                "trace_ref": "TODO: logs/iteration-001.md#evidence-update",
                "observed_action": "TODO: command/readback/review that actually happened",
                "coverage_relation": "none",
                "judge_rationale": "TODO: why this evidence supports the claim",
            }
        ],
        "coverage_relation": "none",
        "latest_artifact_hash": "",
        "latest_verified_at": "",
        "completion_claims": [],
        "failures": [],
        "stop_gate": {
            "candidate_complete_claimed": False,
            "successful_verification_observed": False,
            "blocked_reason": "No observed verification yet.",
        },
        "notes": "Record observed commands/results only. Do not use planned/would-pass verification as evidence.",
    }
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"


def _fit_score(track: str, depth: str, args: dict[str, Any], risk_mode: str) -> dict[str, Any]:
    checks = {
        "goal_clarity": _has_arg(args, "goal"),
        "verifier_availability": bool(args.get("check_command") or args.get("exit_when") or _has_arg(args, "verify")),
        "artifact_accessibility": _has_arg(args, "artifact"),
        "safety_risk_named": _has_arg(args, "hard_fail") or _has_arg(args, "boundary_rule"),
        "iteration_cost_bounded": bool(args.get("check_command") or risk_mode in {"quick", "normal"}),
        "restartability": True,
        "human_gate_named": _has_arg(args, "escalation_rule") or risk_mode in {"deep", "blocked"},
        "automation_suitability": risk_mode != "blocked",
    }
    score = round(100 * sum(1 for v in checks.values() if v) / len(checks))
    verdict = "FIT" if score >= 85 else "FIT_WITH_RISKS" if score >= 60 else "NEEDS_HUMAN_DECISION" if score >= 35 else "DO_NOT_SCAFFOLD"
    return {
        "schema": "loop-creator-fit-score-v1",
        "score": score,
        "verdict": verdict,
        "dimensions": checks,
        "track": track,
        "depth": depth or "n/a",
        "risk_mode": risk_mode,
        "automation_level": "advisory" if verdict != "FIT" else "supervised",
        "next_action": "Scaffold allowed; fill evidence before PASS." if verdict in {"FIT", "FIT_WITH_RISKS"} else "Clarify goal/verifier/artifact before execution.",
    }


def _eval_spec_template(track: str, depth: str, grade: str, risk_mode: str, args: dict[str, Any]) -> str:
    data = {
        "schema": "loop-creator-eval-spec-v1",
        "goal_id": "TODO: copy from state/goal-contract.md",
        "artifact": str(_arg_value(args, "artifact") or "TODO"),
        "track": track,
        "depth": depth or "n/a",
        "risk_mode": risk_mode,
        "behavior_categories": ["completion", "safety", "robustness"],
        "acceptance_criteria": [str(_arg_value(args, "verify") or args.get("exit_when") or "TODO: observable criterion")],
        "deterministic_checks": [args.get("check_command") or "TODO: command/readback/static check"],
        "judge_checks": ["TODO: rubric or reviewer question; cite evidence_path and trace_ref"],
        "safety_checks": ["no_fake_evidence", "no_secret_in_artifacts", "do_not_modify_exit_criteria_to_pass"],
        "evidence_required": ["evidence_path", "trace_ref", "observed_action", "coverage_relation"],
        "pass_policy": "pass_3_of_3" if risk_mode == "deep" else "pass_once",
        "grader_id": "mixed",
    }
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"


def _task_yaml_template(track: str, depth: str, args: dict[str, Any]) -> str:
    return f'''schema: loop-creator-task-v1
prompt: |
  TODO: task prompt grounded in state/goal-contract.md
track: {track}
depth: {depth or 'n/a'}
fixtures:
  - path: state/brief.md
  - path: state/goal-contract.md
tools:
  - loop_creator_validate_run
scoring:
  rubric: eval/rubric.yaml
  pass_policy: pass_once
safety:
  - no_fake_evidence
  - no_secret_in_artifacts
  - human approval for dangerous side effects
'''


def _rubric_yaml_template() -> str:
    return '''schema: loop-creator-rubric-v1
criteria:
  - id: acceptance
    weight: 40
    description: Artifact satisfies the acceptance criteria with cited evidence.
  - id: evidence
    weight: 25
    description: PASS claims cite observed evidence paths and trace refs.
  - id: safety
    weight: 20
    description: Boundary rules are respected; no fake evidence or secret leakage.
  - id: restartability
    weight: 15
    description: State, handoff, and next continuation condition are recoverable.
score_cap_rules:
  - cap: 79
    when: any hard-fail remains
  - cap: 84
    when: acceptance criteria or evidence are vague
  - cap: 89
    when: only single-run evidence exists for a reliability-sensitive claim
'''


def _cases_jsonl_template() -> str:
    row = {"case_id": "case-001", "source": "acceptance_criteria", "input": "TODO", "expected": "TODO", "checks": ["eval/rubric.yaml"], "trace_required": True}
    return json.dumps(row, ensure_ascii=False) + "\n"


def _latest_result_template() -> str:
    data = {"schema": "loop-creator-eval-result-v1", "status": "not_run", "pass_policy": "pass_once", "trials": [], "summary": "No eval run observed yet."}
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"


def _failure_taxonomy_template() -> str:
    return "schema: loop-creator-failure-taxonomy-v2\nallowed_types:\n" + "".join(f"  - {item}\n" for item in FAILURE_TAXONOMY_TYPES) + "repair_policy:\n  artifact_gap: revise artifact against acceptance criteria.\n  evidence_gap: add observed evidence with path and trace ref.\n  evaluator_gap: tighten rubric, grader, or human review rule.\n  process_gap: change loop step, state, or handoff policy.\n  human_decision_gap: stop and request explicit human judgment.\n"


def _runner_spec_template(track: str, depth: str, trigger_mode: str, args: dict[str, Any]) -> str:
    return f'''schema: loop-creator-runner-spec-v1
task: TODO: copy from state/goal-contract.md objective
environment: local-run-folder
agent_backend: hermes
agent_command: TODO: optional; this spec does not prove a runner is installed or executed
track: {track}
depth: {depth or 'n/a'}
trigger_mode: {trigger_mode}
max_iterations: {15 if track == 'full' else 10 if track == 'gs' else 8}
between_iterations: {args.get('check_command') or 'TODO: verification command or review surface'}
exit_when: {args.get('exit_when') or 'TODO: observable pass condition'}
evidence_required:
  - state/evidence-ledger.json claims[].evidence_path
  - state/evidence-ledger.json claims[].trace_ref
permission_policy:
  automation_level: supervised
  dangerous_side_effects_require_human: true
handoff_required: state/session-handoff.md
install_boundary: Runner spec is portable planning metadata, not proof of execution.
'''

def _approval_gate_template(track: str, risk_mode: str) -> str:
    return f"""# Approval Gate

Purpose: separate planning/refinement/execution consent so the run does not silently mutate scope.

## Gate State
- current_stage: `scaffolded`
- track: `{track}`
- risk_mode: `{risk_mode}`
- execution_approval_required: true
- latest_approval_status: `pending`

## Stage Gates
| Stage | Required artifact | Approval required before next stage | Status | Evidence |
|---|---|---:|---|---|
| Spec / brief crystallized | `state/brief.md` | true | TODO | TODO |
| Harness accepted | `final/harness.md` or `final/gs-harness.md` | true | TODO | TODO |
| Execution / rewrite started | `logs/iteration-*.md` | true for non-trivial side effects | TODO | TODO |
| Final handoff | `final/user-facing-summary.md` | false | TODO | TODO |

## Rules
- Do not treat scaffold creation as execution approval.
- Do not auto-promote from plan/refinement to execution when a human approval gate is pending.
- If the user approved in chat, record the quote or message handle in `state/steering-ledger.jsonl`.
"""


def _story_ledger_template() -> str:
    row = {
        "schema": "loop-creator-story-ledger-v1",
        "event": "story_created",
        "story_id": "G001",
        "title": "Complete first predicate loop",
        "objective": "Turn the scaffolded run into at least one verified predicate loop.",
        "status": "active",
        "evidence": [],
        "blocker": "",
        "next_story": "G002 only after G001 has observed verification evidence.",
        "created_at": _now().isoformat(timespec="seconds"),
    }
    return json.dumps(row, ensure_ascii=False) + "\n"


def _steering_ledger_template() -> str:
    row = {
        "schema": "loop-creator-steering-ledger-v1",
        "event": "run_scaffolded",
        "kind": "annotate_ledger",
        "rationale": "Initial scaffold created; no steering changes accepted yet.",
        "evidence": "loop-creator scaffold output",
        "allowed_kinds": ["split_story", "reorder_pending", "revise_wording", "mark_blocked", "mark_superseded", "annotate_ledger"],
        "created_at": _now().isoformat(timespec="seconds"),
    }
    return json.dumps(row, ensure_ascii=False) + "\n"


def _review_receipts_template() -> str:
    row = {
        "schema": "loop-creator-review-receipts-v1",
        "review_id": "review-001",
        "role": "critic|architect|planner|human",
        "artifact_path": "TODO",
        "artifact_sha256": "TODO",
        "verdict": "TODO: CLEAR|WATCH|BLOCK",
        "summary": "TODO: one-line receipt; keep detailed review in its own file.",
        "created_at": _now().isoformat(timespec="seconds"),
    }
    return json.dumps(row, ensure_ascii=False) + "\n"

def _aco_design_card_template(track: str, depth: str) -> str:
    return f"""# ACO Harness Design Card

## Goal
- This run should improve: artifact quality for `{track}` loop{f' / {depth}' if depth else ''}.

## A6 — Architecture
- Structure: run package separates `state/`, `final/`, and `logs/` so work state, outputs, and trace evidence do not mix.
- Context: `state/brief.md`, `state/current.md`, and `state/research-notes.md` define what the agent should read and what remains unknown.
- Plan: `state/goal-contract.md` defines objective, completion criteria, hard-fails, verification surface, budget, and stale update guard.
- Execution: `state/approval-gate.md`, `state/story-ledger.jsonl`, and `logs/iteration-*.md` separate approved execution from scaffold creation.
- Verification: `state/evidence-ledger.json`, predicate checks, and `final/review-report.md` decide candidate completion versus PASS.
- Improvement: `final/quality-document.md`, failure taxonomy, and policy update candidates record what should change next time.

## C3 — Control
- Hook: use existing Hermes events in `state/control-policy.md`; do not invent runtime events that Hermes cannot emit.
- Rule: boundary rules block fake evidence, secret leakage, exit-criteria gaming, and completion without observed verification.
- Loop: each iteration records target predicate, controlled variable, prediction, measurement, observed result, and act decision.

## O3 — Operation
- State: goal contract, predicate state, story ledger, and session handoff are the restartable state spine.
- Gate: approval, verification, completion, and handoff gates separate worker claims from verifier/human PASS.
- Evidence: source, execution, review, user/business evidence must be recorded as observed evidence, not planned evidence.

## Deletion Rule
- Remove or downgrade any hook/rule/template that does not reduce a named failure mode after three reviewed uses.
"""


def _control_policy_template() -> str:
    policy = json.dumps(DEFAULT_CONTROL_POLICY, ensure_ascii=False, indent=2)
    event_lines = "\n".join(f"- `{event}`: {', '.join(DEFAULT_CONTROL_POLICY['hooks'].get(event, []))}" for event in HERMES_HOOK_EVENTS)
    rule_lines = "\n".join(f"- `{event}`: {', '.join(DEFAULT_CONTROL_POLICY['event_rules'].get(event, []))}" for event in sorted(DEFAULT_CONTROL_POLICY["event_rules"]))
    return f"""# Control Policy

Purpose: bind ACO Control 3 to real Hermes lifecycle events. These names must match Hermes gateway hook events, not abstract labels.

## Existing Hermes Events Used
{event_lines}

## Event Rules
{rule_lines}

## Non-blocking / Blocking Boundary
- advisory only: `gateway:startup`, `session:start`, `agent:start`, `agent:step`, `agent:end`, `session:reset`
- validator blocker: missing boundary rule, fake evidence, missing handoff for active run, completion without observed verification
- hard block allowed only when: `command:*` policy explicitly denies/rewrites, or a future execution runner reaches a permission/forbidden-path gate

## Rule Classes
### Guiding Rules
- one_controlled_variable_per_iteration
- record_observed_result_before_next_mutation

### Boundary Rules
- no_fake_evidence
- no_secret_in_artifacts
- do_not_modify_exit_criteria_to_pass
- candidate_complete_requires_evidence_ledger_update

### Escalation Rules
- three_failed_iterations_requires_human_or_policy_update
- dangerous_side_effect_requires_approval

## Rule Deletion Criteria
- Failure reduced: drift, fake evidence, missing handoff, uncontrolled iteration, or unsafe side effect.
- Remove or downgrade if: after three reviewed uses the hook/rule does not catch a real failure, reduce review cost, or improve restartability.

## Machine-readable Policy
```json
{policy}
```
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
    risk_mode = _normalize_risk_mode(args.get("risk_mode"), track, grade)
    now = _now()
    slug = _safe_slug(args.get("slug"), f"{track}-loop")
    run_path = _default_root(args.get("root_path")) / f"{now.strftime('%Y-%m-%d')}_{slug}"
    if run_path.exists():
        run_path = run_path.with_name(run_path.name + "-" + now.strftime("%H%M%S"))
    for d in ["state", "final", "logs"]:
        (run_path / d).mkdir(parents=True, exist_ok=True)
    _write(run_path / "state" / "intake.md", _intake_template(track, depth, args, run_path.name))
    _write(run_path / "state" / "hsd.md", _hsd_template(track, depth, args, run_path.name))
    _write(run_path / "state" / "brief.md", _brief_template(track, depth, args, run_path.name))
    _write(run_path / "state" / "goal-contract.md", _goal_contract_template(track, depth, args, run_path.name, trigger_mode))
    _write(run_path / "state" / "aco-design-card.md", _aco_design_card_template(track, depth))
    _write(run_path / "state" / "control-policy.md", _control_policy_template())
    _write(run_path / "state" / "predicate-list.json", _predicate_list_template(track, depth))
    _write(run_path / "state" / "evidence-ledger.json", _evidence_ledger_template(track, grade, risk_mode))
    _write(run_path / "state" / "failure-taxonomy.yaml", _failure_taxonomy_template())
    _write(run_path / "eval" / "eval_spec.yaml", _eval_spec_template(track, depth, grade, risk_mode, args))
    _write(run_path / "eval" / "task.yaml", _task_yaml_template(track, depth, args))
    _write(run_path / "eval" / "rubric.yaml", _rubric_yaml_template())
    _write(run_path / "eval" / "cases.jsonl", _cases_jsonl_template())
    _write(run_path / "eval" / "latest-result.json", _latest_result_template())
    _write(run_path / "runner" / "loop.yaml", _runner_spec_template(track, depth, trigger_mode, args))
    _write(run_path / "state" / "approval-gate.md", _approval_gate_template(track, risk_mode))
    _write(run_path / "state" / "story-ledger.jsonl", _story_ledger_template())
    _write(run_path / "state" / "steering-ledger.jsonl", _steering_ledger_template())
    _write(run_path / "state" / "review-receipts.jsonl", _review_receipts_template())
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
    _write(run_path / "final" / "hsd-diagram.md", _hsd_diagram_template(track, depth, args))
    _write(run_path / "final" / "harness-diagram.md", _harness_diagram_template(track, depth, args, run_path))
    _write(run_path / "final" / "harness-improvement-suggestions.md", _harness_improvement_suggestions_template(track, depth, args, run_path))
    _write(run_path / "final" / "quick-loop-card.md", _quick_loop_card_template(track, depth, trigger_mode, args, run_path))
    _write(run_path / "final" / "clean-state-checklist.md", _clean_state_checklist_template())
    _write(run_path / "final" / "quality-document.md", _quality_document_template(track, depth))
    _write(run_path / "final" / "user-facing-summary.md", _summary_template(run_path))
    _write(run_path / "logs" / "iteration-001.md", _iteration_template(1))
    identity = {"model_id": str(args.get("model_id") or "unknown"), "harness_id": "loop-creator@1.5.0", "grader_id": "mixed", "task_slice": track, "regression_attribution": "unknown"}
    fit = _fit_score(track, depth, args, risk_mode)
    _write(run_path / "loop-creator.json", _json({"track": track, "label": TRACK_LABELS[track], "trigger_mode": trigger_mode, "risk_mode": risk_mode, "depth": depth, "grade": grade, "created_at": now.isoformat(timespec="seconds"), "source_skill": str(SKILL_ROOT), "gs_source": _source_status() if (track == "gs" and depth == "Full GS") else None, "intake": _intake_status(args, track), "hsd": {"approved": bool(args.get("approve_hsd") or args.get("allow_todo")), "diagram": "final/hsd-diagram.md"}, "control_policy": DEFAULT_CONTROL_POLICY, "identity": identity, "fit_score": fit, "eval_pack": {"path": "eval/eval_spec.yaml", "pass_policy": "pass_3_of_3" if risk_mode == "deep" else "pass_once"}, "runner_spec": "runner/loop.yaml"}))
    return _json({"success": True, "path": str(run_path), "track": track, "label": TRACK_LABELS[track], "trigger_mode": trigger_mode, "risk_mode": risk_mode, "depth": depth, "grade": grade, "validation": _validate_path(run_path), "next_action": "Fill state/brief.md, state/evidence-ledger.json, and logs/iteration-001.md with real predicate evidence."})


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
    grade = _normalize_grade(grade_match.group(1) if grade_match else None, track, depth)
    risk_match = re.search(r"risk_mode:\s*`([^`]+)`", brief)
    return {"track": track, "trigger_mode": _normalize_trigger_mode(trigger_match.group(1) if trigger_match else None), "risk_mode": _normalize_risk_mode(risk_match.group(1) if risk_match else None, track, grade), "depth": depth, "grade": grade}


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




def _validate_evidence_ledger(run_path: Path, *, risk_mode: str) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    issues: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    rel = "state/evidence-ledger.json"
    path = run_path / rel
    if not path.exists():
        return ([{"type": "evidence_ledger_gap", "path": rel, "message": "evidence ledger missing"}], warnings)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return ([{"type": "evidence_ledger_gap", "path": rel, "message": f"invalid JSON: {type(exc).__name__}"}], warnings)
    coverage = data.get("coverage_relation", "none")
    if coverage not in COVERAGE_RELATIONS:
        issues.append({"type": "evidence_ledger_gap", "path": rel, "message": f"invalid coverage_relation: {coverage}"})
    results = data.get("verification_results")
    if not isinstance(results, list):
        issues.append({"type": "evidence_ledger_gap", "path": rel, "message": "verification_results must be a list"})
        results = []
    commands = data.get("verification_commands")
    if not isinstance(commands, list):
        issues.append({"type": "evidence_ledger_gap", "path": rel, "message": "verification_commands must be a list"})
        commands = []
    successful = any(isinstance(r, dict) and r.get("success") is True for r in results)
    failed_marked_success = [r for r in results if isinstance(r, dict) and r.get("success") is True and re.search(r"(?i)(failed|failure|error|traceback|exit code [1-9])", str(r.get("summary") or ""))]
    if failed_marked_success:
        issues.append({"type": "evidence_ledger_gap", "path": rel, "message": "failed verification appears recorded as success"})
    completion_claims = data.get("completion_claims")
    if completion_claims is None:
        completion_claims = []
    if not isinstance(completion_claims, list):
        issues.append({"type": "evidence_ledger_gap", "path": rel, "message": "completion_claims must be a list"})
        completion_claims = []
    stop_gate = data.get("stop_gate") if isinstance(data.get("stop_gate"), dict) else {}
    candidate_complete = bool(stop_gate.get("candidate_complete_claimed")) or any(str(c).strip() for c in completion_claims)
    if candidate_complete and not successful:
        issues.append({"type": "stop_gate_gap", "path": rel, "message": "candidate completion claimed without observed successful verification"})
    if candidate_complete:
        if not str(data.get("latest_artifact_hash") or "").strip():
            issues.append({"type": "fresh_snapshot_gap", "path": rel, "message": "completion claim requires latest_artifact_hash"})
        if not str(data.get("latest_verified_at") or "").strip():
            issues.append({"type": "fresh_snapshot_gap", "path": rel, "message": "completion claim requires latest_verified_at"})
    if risk_mode in {"normal", "deep"} and not successful:
        issues.append({"type": "evidence_ledger_gap", "path": rel, "message": f"{risk_mode} risk mode requires observed successful verification"})
    if risk_mode == "deep" and coverage not in {"direct", "generic"}:
        issues.append({"type": "coverage_gap", "path": rel, "message": "deep risk mode requires direct or generic verification coverage"})
    claims = data.get("claims") if isinstance(data.get("claims"), list) else []
    if candidate_complete and not claims:
        issues.append({"type": "evidence_ledger_gap", "path": rel, "message": "completion claim requires at least one trace-grounded claim citation"})
    for idx, claim in enumerate(claims, 1):
        if not isinstance(claim, dict):
            issues.append({"type": "evidence_ledger_gap", "path": rel, "message": f"claims[{idx}] must be an object"})
            continue
        for field in ["claim", "evidence_path", "trace_ref", "observed_action", "coverage_relation", "judge_rationale"]:
            value = str(claim.get(field) or "")
            if not value or "TODO" in value:
                if candidate_complete:
                    issues.append({"type": "evidence_ledger_gap", "path": rel, "message": f"completion claim requires claims[{idx}].{field}"})
                else:
                    warnings.append({"type": "quality_warning", "path": rel, "message": f"claims[{idx}].{field} is not filled yet"})
        if claim.get("coverage_relation") and claim.get("coverage_relation") not in COVERAGE_RELATIONS:
            issues.append({"type": "coverage_gap", "path": rel, "message": f"claims[{idx}] invalid coverage_relation: {claim.get('coverage_relation')}"})
    if risk_mode == "normal" and coverage == "none":
        warnings.append({"type": "quality_warning", "path": rel, "message": "normal risk mode has no coverage relation recorded"})
    if successful and not commands:
        warnings.append({"type": "quality_warning", "path": rel, "message": "successful verification exists but verification_commands is empty"})
    return issues, warnings



def _completion_claimed(run_path: Path) -> bool:
    try:
        data = json.loads((run_path / "state" / "evidence-ledger.json").read_text(encoding="utf-8"))
    except Exception:
        return False
    stop_gate = data.get("stop_gate") if isinstance(data, dict) and isinstance(data.get("stop_gate"), dict) else {}
    claims = data.get("completion_claims") if isinstance(data, dict) else []
    return bool(stop_gate.get("candidate_complete_claimed")) or any(str(c).strip() for c in (claims or []) if isinstance(claims, list))

def _read_jsonl(path: Path) -> tuple[list[dict[str, Any]], str | None]:
    rows: list[dict[str, Any]] = []
    try:
        text = path.read_text(encoding="utf-8")
    except Exception as exc:
        return rows, f"read error: {type(exc).__name__}"
    for idx, raw in enumerate(text.splitlines(), 1):
        if not raw.strip():
            continue
        try:
            obj = json.loads(raw)
        except Exception as exc:
            return rows, f"line {idx} invalid JSON: {type(exc).__name__}"
        if not isinstance(obj, dict):
            return rows, f"line {idx} must be an object"
        rows.append(obj)
    return rows, None


def _validate_goal_story_artifacts(run_path: Path, *, completion_claimed: bool) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    issues: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    approval_rel = "state/approval-gate.md"
    approval = _read(run_path / approval_rel)
    issues.extend(_require_markers(approval, rel=approval_rel, issue_type="approval_gate_gap", markers=["## Gate State", "## Stage Gates", "execution_approval_required", "latest_approval_status"]))
    if "TODO" in approval:
        issues.append({"type": "approval_gate_gap", "path": approval_rel, "message": "approval gate still contains TODO"})
    if "latest_approval_status: `approved`" not in approval and completion_claimed:
        issues.append({"type": "approval_gate_gap", "path": approval_rel, "message": "completion claimed while latest approval is not recorded as approved"})

    story_rel = "state/story-ledger.jsonl"
    story_rows, err = _read_jsonl(run_path / story_rel)
    if err:
        issues.append({"type": "story_ledger_gap", "path": story_rel, "message": err})
    elif not story_rows:
        issues.append({"type": "story_ledger_gap", "path": story_rel, "message": "story ledger has no events"})
    else:
        valid_statuses = {"pending", "active", "complete", "blocked", "failed", "superseded"}
        for idx, row in enumerate(story_rows, 1):
            for field in ["story_id", "status", "evidence"]:
                if field not in row:
                    issues.append({"type": "story_ledger_gap", "path": story_rel, "message": f"line {idx} missing {field}"})
            status = row.get("status")
            if status not in valid_statuses:
                issues.append({"type": "story_ledger_gap", "path": story_rel, "message": f"line {idx} invalid status: {status}"})
            evidence = row.get("evidence")
            if status == "complete" and not evidence:
                issues.append({"type": "story_ledger_gap", "path": story_rel, "message": f"line {idx} complete story requires evidence"})
            if status == "blocked" and not str(row.get("blocker") or "").strip():
                issues.append({"type": "story_ledger_gap", "path": story_rel, "message": f"line {idx} blocked story requires blocker"})
        if completion_claimed and not any(r.get("status") == "complete" and r.get("evidence") for r in story_rows):
            issues.append({"type": "story_ledger_gap", "path": story_rel, "message": "completion claimed without a complete story event with evidence"})

    steering_rel = "state/steering-ledger.jsonl"
    steering_rows, err = _read_jsonl(run_path / steering_rel)
    if err:
        issues.append({"type": "steering_ledger_gap", "path": steering_rel, "message": err})
    elif not steering_rows:
        issues.append({"type": "steering_ledger_gap", "path": steering_rel, "message": "steering ledger has no events"})
    else:
        valid_kinds = {"split_story", "reorder_pending", "revise_wording", "mark_blocked", "mark_superseded", "annotate_ledger"}
        for idx, row in enumerate(steering_rows, 1):
            kind = row.get("kind")
            if kind not in valid_kinds:
                issues.append({"type": "steering_ledger_gap", "path": steering_rel, "message": f"line {idx} invalid kind: {kind}"})
            if not str(row.get("rationale") or "").strip():
                warnings.append({"type": "quality_warning", "path": steering_rel, "message": f"line {idx} has no rationale"})

    receipts_rel = "state/review-receipts.jsonl"
    receipt_rows, err = _read_jsonl(run_path / receipts_rel)
    if err:
        issues.append({"type": "review_receipt_gap", "path": receipts_rel, "message": err})
    elif not receipt_rows:
        issues.append({"type": "review_receipt_gap", "path": receipts_rel, "message": "review receipts ledger has no rows"})
    else:
        for idx, row in enumerate(receipt_rows, 1):
            verdict = row.get("verdict")
            if verdict not in {"CLEAR", "WATCH", "BLOCK"}:
                issues.append({"type": "review_receipt_gap", "path": receipts_rel, "message": f"line {idx} invalid verdict: {verdict}"})
            for field in ["artifact_path", "artifact_sha256"]:
                value = str(row.get(field) or "")
                if not value or "TODO" in value:
                    issues.append({"type": "review_receipt_gap", "path": receipts_rel, "message": f"line {idx} missing {field}"})
    return issues, warnings

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

def _validate_aco_control_artifacts(run_path: Path, meta: dict[str, Any]) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    issues: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    aco_rel = "state/aco-design-card.md"
    aco = _read(run_path / aco_rel)
    issues.extend(_require_markers(aco, rel=aco_rel, issue_type="aco_design_gap", markers=["## A6 — Architecture", "## C3 — Control", "## O3 — Operation", "## Deletion Rule", "Structure:", "Context:", "Plan:", "Execution:", "Verification:", "Improvement:", "Hook:", "Rule:", "Loop:", "State:", "Gate:", "Evidence:"]))
    if "TODO" in aco:
        warnings.append({"type": "quality_warning", "path": aco_rel, "message": "ACO design card still contains TODO"})

    control_rel = "state/control-policy.md"
    control = _read(run_path / control_rel)
    issues.extend(_require_markers(control, rel=control_rel, issue_type="control_policy_gap", markers=["## Existing Hermes Events Used", "## Event Rules", "## Non-blocking / Blocking Boundary", "## Rule Classes", "### Boundary Rules", "## Rule Deletion Criteria", "## Machine-readable Policy"]))
    for event in HERMES_HOOK_EVENTS:
        if f"`{event}`" not in control:
            issues.append({"type": "control_policy_gap", "path": control_rel, "message": f"missing existing Hermes hook event: {event}"})
    for rule in ["no_fake_evidence", "no_secret_in_artifacts", "do_not_modify_exit_criteria_to_pass", "candidate_complete_requires_evidence_ledger_update"]:
        if rule not in control:
            issues.append({"type": "control_policy_gap", "path": control_rel, "message": f"missing boundary rule: {rule}"})
    if "pre_start" in control or "post_iteration" in control or "pre_completion" in control:
        issues.append({"type": "control_policy_gap", "path": control_rel, "message": "control policy uses abstract hook names instead of existing Hermes events"})
    if "TODO" in control:
        warnings.append({"type": "quality_warning", "path": control_rel, "message": "control policy still contains TODO"})

    cp = meta.get("control_policy") if isinstance(meta, dict) else None
    if not isinstance(cp, dict):
        issues.append({"type": "control_policy_gap", "path": "loop-creator.json", "message": "metadata control_policy missing"})
    else:
        hooks = cp.get("hooks") if isinstance(cp.get("hooks"), dict) else {}
        event_rules = cp.get("event_rules") if isinstance(cp.get("event_rules"), dict) else {}
        for event in ["agent:start", "agent:step", "agent:end", "session:end", "command:*"]:
            if event not in hooks and event not in event_rules:
                issues.append({"type": "control_policy_gap", "path": "loop-creator.json", "message": f"control_policy does not bind event: {event}"})
    return issues, warnings



def _simple_yaml_values(text: str, key: str) -> list[str]:
    vals: list[str] = []
    capture = False
    for line in text.splitlines():
        if line.startswith(f"{key}:"):
            capture = True
            rest = line.split(":", 1)[1].strip()
            if rest:
                vals.append(rest)
            continue
        if capture:
            if line.startswith("  - "):
                vals.append(line[4:].strip())
            elif line and not line.startswith(" "):
                break
    return vals


def _validate_eval_pack(run_path: Path, meta: dict[str, Any]) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    issues: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    required = ["eval/eval_spec.yaml", "eval/task.yaml", "eval/rubric.yaml", "eval/cases.jsonl", "eval/latest-result.json"]
    for rel in required:
        if not (run_path / rel).exists():
            issues.append({"type": "eval_pack_gap", "path": rel, "message": "required eval pack file missing"})
    spec = _read(run_path / "eval" / "eval_spec.yaml")
    if spec:
        for marker in ["schema", "acceptance_criteria", "deterministic_checks", "judge_checks", "safety_checks", "evidence_required", "pass_policy"]:
            if marker not in spec:
                issues.append({"type": "eval_pack_gap", "path": "eval/eval_spec.yaml", "message": f"missing marker: {marker}"})
        pass_policy = (_simple_yaml_values(spec, "pass_policy") or [""])[0].strip().strip('"')
        if pass_policy and pass_policy not in PASS_POLICIES:
            issues.append({"type": "reliability_gate_gap", "path": "eval/eval_spec.yaml", "message": f"invalid pass_policy: {pass_policy}"})
        if "TODO" in spec:
            issues.append({"type": "eval_pack_gap", "path": "eval/eval_spec.yaml", "message": "eval spec still contains TODO"})
    cases_path = run_path / "eval" / "cases.jsonl"
    if cases_path.exists():
        rows, err = _read_jsonl(cases_path)
        if err:
            issues.append({"type": "eval_pack_gap", "path": "eval/cases.jsonl", "message": err})
        elif not rows:
            issues.append({"type": "eval_pack_gap", "path": "eval/cases.jsonl", "message": "no eval cases"})
        else:
            for idx, row in enumerate(rows, 1):
                for field in ["case_id", "source", "input", "expected", "checks", "trace_required"]:
                    if field not in row or str(row.get(field)) in {"", "TODO"}:
                        issues.append({"type": "eval_pack_gap", "path": "eval/cases.jsonl", "message": f"line {idx} missing {field}"})
    result_path = run_path / "eval" / "latest-result.json"
    if result_path.exists():
        try:
            result = json.loads(result_path.read_text(encoding="utf-8"))
        except Exception as exc:
            issues.append({"type": "eval_pack_gap", "path": "eval/latest-result.json", "message": f"invalid JSON: {type(exc).__name__}"})
        else:
            if result.get("status") not in {"not_run", "pass", "fail", "uncertain"}:
                issues.append({"type": "eval_pack_gap", "path": "eval/latest-result.json", "message": f"invalid status: {result.get('status')}"})
            if result.get("status") in {"pass", "fail", "uncertain"} and not result.get("trials"):
                warnings.append({"type": "quality_warning", "path": "eval/latest-result.json", "message": "observed eval status has no trials"})
    return issues, warnings


def _validate_failure_taxonomy(run_path: Path) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    issues: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    rel = "state/failure-taxonomy.yaml"
    text = _read(run_path / rel)
    if not text:
        return ([{"type": "failure_taxonomy_gap", "path": rel, "message": "failure taxonomy missing"}], warnings)
    for item in FAILURE_TAXONOMY_TYPES:
        if f"- {item}" not in text:
            issues.append({"type": "failure_taxonomy_gap", "path": rel, "message": f"missing failure type: {item}"})
    return issues, warnings


def _validate_identity_fit_runner(run_path: Path, meta: dict[str, Any]) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    issues: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    identity = meta.get("identity") if isinstance(meta.get("identity"), dict) else {}
    for field in ["model_id", "harness_id", "grader_id", "task_slice", "regression_attribution"]:
        if not str(identity.get(field) or "").strip():
            issues.append({"type": "harness_identity_gap", "path": "loop-creator.json", "message": f"identity missing {field}"})
    fit = meta.get("fit_score") if isinstance(meta.get("fit_score"), dict) else {}
    if not fit:
        issues.append({"type": "fit_score_gap", "path": "loop-creator.json", "message": "fit_score missing"})
    else:
        if fit.get("verdict") not in {"FIT", "FIT_WITH_RISKS", "NEEDS_HUMAN_DECISION", "DO_NOT_SCAFFOLD"}:
            issues.append({"type": "fit_score_gap", "path": "loop-creator.json", "message": f"invalid fit verdict: {fit.get('verdict')}"})
        if not isinstance(fit.get("score"), int):
            issues.append({"type": "fit_score_gap", "path": "loop-creator.json", "message": "fit_score.score must be integer"})
        if fit.get("verdict") in {"NEEDS_HUMAN_DECISION", "DO_NOT_SCAFFOLD"}:
            warnings.append({"type": "quality_warning", "path": "loop-creator.json", "message": f"pre-scaffold fit verdict was {fit.get('verdict')}"})
    runner_rel = "runner/loop.yaml"
    runner = _read(run_path / runner_rel)
    if not runner:
        issues.append({"type": "runner_spec_gap", "path": runner_rel, "message": "runner-neutral loop spec missing"})
    else:
        for marker in ["schema", "agent_backend", "max_iterations", "between_iterations", "exit_when", "evidence_required", "permission_policy", "install_boundary"]:
            if marker not in runner:
                issues.append({"type": "runner_spec_gap", "path": runner_rel, "message": f"missing marker: {marker}"})
        backend = (_simple_yaml_values(runner, "agent_backend") or [""])[0].strip()
        if backend and backend not in AGENT_BACKENDS:
            issues.append({"type": "runner_spec_gap", "path": runner_rel, "message": f"invalid agent_backend: {backend}"})
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
    risk_mode = _normalize_risk_mode(meta.get("risk_mode"), track, grade)
    required = ["state/intake.md", "state/hsd.md", "state/brief.md", "state/goal-contract.md", "state/aco-design-card.md", "state/control-policy.md", "state/predicate-list.json", "state/evidence-ledger.json", "state/failure-taxonomy.yaml", "eval/eval_spec.yaml", "eval/task.yaml", "eval/rubric.yaml", "eval/cases.jsonl", "eval/latest-result.json", "runner/loop.yaml", "state/approval-gate.md", "state/story-ledger.jsonl", "state/steering-ledger.jsonl", "state/review-receipts.jsonl", "state/session-handoff.md", "state/init-check.md", "state/current.md", "state/research-notes.md", "final/improved-draft.md", "final/review-report.md", "final/hsd-diagram.md", "final/harness-diagram.md", "final/harness-improvement-suggestions.md", "final/quick-loop-card.md", "final/clean-state-checklist.md", "final/quality-document.md", "final/user-facing-summary.md", "final/gs-harness.md" if track == "gs" else "final/harness.md"]
    if track == "full" or depth == "Full GS":
        required.append("final/loop-spec.md")
    if track == "gs":
        required += ["final/growth-strategy.md", "final/experiment-plan.md"]
    for rel in required:
        if not (run_path / rel).exists():
            issues.append({"type": "scaffold_gap", "path": rel, "message": "required file missing"})
    aco_control_issues, aco_control_warnings = _validate_aco_control_artifacts(run_path, meta)
    issues.extend(aco_control_issues)
    warnings.extend(aco_control_warnings)
    pred_issues, pred_warnings = _validate_predicate_list(run_path)
    issues.extend(pred_issues)
    warnings.extend(pred_warnings)
    evidence_issues, evidence_warnings = _validate_evidence_ledger(run_path, risk_mode=risk_mode)
    issues.extend(evidence_issues)
    warnings.extend(evidence_warnings)
    eval_issues, eval_warnings = _validate_eval_pack(run_path, meta)
    issues.extend(eval_issues)
    warnings.extend(eval_warnings)
    tax_issues, tax_warnings = _validate_failure_taxonomy(run_path)
    issues.extend(tax_issues)
    warnings.extend(tax_warnings)
    id_issues, id_warnings = _validate_identity_fit_runner(run_path, meta)
    issues.extend(id_issues)
    warnings.extend(id_warnings)
    story_issues, story_warnings = _validate_goal_story_artifacts(run_path, completion_claimed=_completion_claimed(run_path))
    issues.extend(story_issues)
    warnings.extend(story_warnings)
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
    issues = _annotate_findings(issues)
    warnings = _annotate_findings(warnings)
    by_type: dict[str, int] = {}
    for issue in issues:
        by_type[issue["type"]] = by_type.get(issue["type"], 0) + 1
    aco = _aco_summary(issues, warnings)
    return {"ok": not any(i["type"] == "scaffold_gap" for i in issues), "passable": len(issues) == 0, "track": track, "trigger_mode": _normalize_trigger_mode(meta.get("trigger_mode")), "risk_mode": risk_mode, "depth": depth, "grade": grade, "min_logs": min_logs, "log_count": len(logs), "issues": issues, "issue_counts": by_type, "aco_bottleneck": aco.get("bottleneck"), "aco_issue_counts": aco.get("issue_counts_by_layer", {}), "aco_summary": aco, "warnings": warnings}


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
    return _json({"success": True, "path": str(run_path), "track": meta.get("track"), "trigger_mode": _normalize_trigger_mode(meta.get("trigger_mode")), "risk_mode": validation.get("risk_mode"), "depth": meta.get("depth"), "grade": validation.get("grade"), "passable": validation.get("passable", False), "issue_counts": validation.get("issue_counts", {}), "aco_bottleneck": validation.get("aco_bottleneck"), "aco_issue_counts": validation.get("aco_issue_counts", {}), "warning_count": len(validation.get("warnings", [])), "warnings": validation.get("warnings", [])[:5], "loop_trace": loop_lines, "top_blockers": top_issues, "next_mutation": next_mutation})


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

`/loop-creator standard`처럼 track만 주면 바로 scaffold하지 않고 Goal + Control Intake 질문을 먼저 반환해.
빈칸 포함 scaffold가 필요하면 `allow_todo=true`를 붙여.

생성된 run은 `state/intake.md`, `state/goal-contract.md`, `state/control-policy.md`, `logs/iteration-*.md`의 Learning Trace를 채워야 passable이 돼.
이제 공식 이름은 `/loop-creator`야.
""".strip()


def handle_loop_creator(raw_args: str) -> str:
    args = parse_kv_args(raw_args)
    if not args.get("track"):
        return selector_text()
    track = _normalize_track(args.get("track")) or "standard"
    if not _intake_status(args, track)["ready"]:
        return intake_question_text(args)
    if not (args.get("approve_hsd") or args.get("allow_todo")):
        return hsd_preview_text(args)
    data = json.loads(create_scaffold(args))
    if not data.get("success"):
        return f"실패: {data.get('error')}"
    v = data.get("validation", {})
    return "\n".join(["## loop-creator 생성 완료", f"- track: `{data['label']}`" + (f" / `{data.get('depth')}`" if data.get('depth') else "") + f" / trigger: `{data.get('trigger_mode')}` / grade: `{data.get('grade')}`", f"- path: `{data['path']}`", f"- quick card: `{data['path']}/final/quick-loop-card.md`", f"- scaffold_ok: `{v.get('ok')}` / passable: `{v.get('passable')}`", f"- blockers: `{v.get('issue_counts', {})}`", f"👉 다음 액션: `{data['path']}/final/harness-diagram.md`와 `final/harness-improvement-suggestions.md`를 확인하고 `logs/iteration-001.md`를 실제 predicate check로 작성해."])


def handle_loop_validate(raw_args: str) -> str:
    path = (raw_args or "").strip()
    if not path:
        return "사용법: `/loop-validate <run-path>`"
    data = json.loads(validate_run({"path": path}))
    v = data["validation"]
    lines = ["## loop-validate 결과", f"- path: `{data['path']}`", f"- track: `{v.get('track')}` / trigger: `{v.get('trigger_mode')}` / depth: `{v.get('depth') or 'n/a'}` / grade: `{v.get('grade')}`", f"- scaffold_ok: `{v.get('ok')}` / passable: `{v.get('passable')}`", f"- logs: `{v.get('log_count')}/{v.get('min_logs')}`", f"- issue_counts: `{v.get('issue_counts', {})}`", f"- ACO bottleneck: `{v.get('aco_bottleneck')}`", f"- warnings: `{len(v.get('warnings', []))}`"]
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
    lines = ["## loop-summary", f"- path: `{data['path']}`", f"- track: `{data.get('track')}` / trigger: `{data.get('trigger_mode', 'manual')}` / depth: `{data.get('depth') or 'n/a'}`", f"- passable: `{data.get('passable')}`", f"- issue_counts: `{data.get('issue_counts')}`", f"- ACO bottleneck: `{data.get('aco_bottleneck')}`", f"- warnings: `{data.get('warning_count', 0)}`"]
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
