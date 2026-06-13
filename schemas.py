"""Tool schemas for the loop-creator plugin."""

LOOP_CREATOR_SCAFFOLD = {
    "name": "loop_creator_scaffold",
    "description": (
        "Create a Loop Creator run scaffold. Use when the user wants loop-creator, "
        "standard loop, full loop, or gs loop scaffolding with required evidence files. "
        "This does not execute autonomous loops; it creates the run package and templates."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "track": {"type": "string", "enum": ["standard", "full", "gs"]},
            "depth": {"type": "string", "description": "GS depth: Quick, standard, or Full GS."},
            "slug": {"type": "string"},
            "root_path": {"type": "string"},
            "artifact": {"type": "string"},
            "reader": {"type": "string"},
            "outcome": {"type": "string"},
            "constraints": {"type": "string"},
            "company": {"type": "string"},
            "growth_outcome": {"type": "string"},
            "customer": {"type": "string"},
            "payer": {"type": "string", "description": "GS: payer, buyer, or budget owner."},
            "buying_trigger": {"type": "string", "description": "GS: event or pain that causes buying intent."},
            "horizon": {"type": "string"},
            "research_allowed": {"type": "boolean"},
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
