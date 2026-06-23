"""Tool schemas for the loop-creator plugin."""

LOOP_CREATOR_SCAFFOLD = {
    "name": "loop_creator_scaffold",
    "description": (
        "Create a Loop Creator run scaffold. Use when the user wants loop-creator, "
        "standard loop, full loop, or gs loop scaffolding with required evidence, eval, failure-taxonomy, and runner-neutral spec files. "
        "This does not execute autonomous loops; it creates the run package and templates."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "track": {"type": "string", "enum": ["standard", "full", "gs"]},
            "trigger_mode": {"type": "string", "enum": ["manual", "interval", "event"], "description": "What starts the loop: manual user kickoff, interval/cadence, or event/hook."},
            "risk_mode": {"type": "string", "enum": ["quick", "normal", "deep", "blocked"], "description": "Risk-proportional verification depth imported from fable-ish: quick, normal, deep, or blocked."},
            "depth": {"type": "string", "description": "GS depth: Quick, standard, or Full GS."},
            "grade": {"type": "string", "enum": ["LIGHT", "STANDARD", "HEAVY", "light", "standard", "heavy"], "description": "Spec gate depth. LIGHT requires acceptance evidence; STANDARD adds non-goals/context/alternatives/risks; HEAVY also blocks on forbidden paths."},
            "slug": {"type": "string"},
            "root_path": {"type": "string"},
            "artifact": {"type": "string"},
            "reader": {"type": "string"},
            "outcome": {"type": "string"},
            "constraints": {"type": "string"},
            "check_command": {"type": "string", "description": "Command or evaluation surface to run between iterations for the quick kickoff card."},
            "exit_when": {"type": "string", "description": "Observable exit condition for the quick kickoff card."},
            "step_1": {"type": "string", "description": "First concrete action for the quick kickoff card."},
            "cadence": {"type": "string", "description": "Interval cadence when trigger_mode=interval, e.g. 15m or 7d."},
            "event": {"type": "string", "description": "Event or hook name when trigger_mode=event, e.g. post-edit, pre-commit, post-merge."},
            "company": {"type": "string"},
            "growth_outcome": {"type": "string"},
            "customer": {"type": "string"},
            "payer": {"type": "string", "description": "GS: payer, buyer, or budget owner."},
            "buying_trigger": {"type": "string", "description": "GS: event or pain that causes buying intent."},
            "horizon": {"type": "string"},
            "research_allowed": {"type": "boolean"},
            "published_status": {"type": "string", "enum": ["draft", "local", "validated", "published", "retired"], "description": "Loop record lifecycle state; scaffold defaults to draft."},
            "related_loops": {"type": "string", "description": "Comma-separated related loop slugs or local loop IDs."},
            "retirement_rule": {"type": "string", "description": "When this loop should retire after success, duplication, staleness, or low value."},
            "kill_condition": {"type": "string", "description": "Evidence that should kill the loop because waste/risk exceeds value."},
            "manual_trial": {"type": "string", "description": "One bounded manual trial before scheduling or autonomy."},
        },
        "required": ["track"],
    },
}

LOOP_CREATOR_VALIDATE_RUN = {
    "name": "loop_creator_validate_run",
    "description": "Validate a Loop Creator run folder: required files, track gates, per-loop trace, min loop counts, and Full GS evidence contract.",
    "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
}

LOOP_CREATOR_SUMMARIZE_RUN = {
    "name": "loop_creator_summarize_run",
    "description": "Summarize a Loop Creator run folder: track, logs, validation blockers, and next mutation.",
    "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
}

LOOP_CREATOR_CHECK_UPDATE = {
    "name": "loop_creator_check_update",
    "description": "Read-only check for whether the installed loop-creator plugin is behind its Git remote. Does not update automatically; approval is required before running hermes plugins update loop-creator.",
    "parameters": {
        "type": "object",
        "properties": {
            "remote": {"type": "string", "description": "Git remote name, default origin."},
            "branch": {"type": "string", "description": "Remote ref, default HEAD."},
        },
    },
}
