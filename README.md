# Loop Creator Plugin

Hermes plugin for creating, validating, and summarizing loop-run scaffold packages.

## What it provides

- Slash commands: `/loop-creator`, `/loop-validate`, `/loop-summary`
- CLI command: `hermes loop-creator ...`
- Tools: `loop_creator_scaffold`, `loop_creator_validate_run`, `loop_creator_summarize_run`
- Gateway hook: `pre_gateway_dispatch`

## Purpose

Loop Creator does **not** run autonomous loops. It creates the evidence package for standard/full/GS loops, then validates whether the run has enough traces and evidence to claim readiness.

## Local smoke checks

```bash
python3 -m py_compile __init__.py schemas.py tools.py
```

Example scaffold through Hermes tool runtime is available when the plugin is enabled in the default Hermes profile.
