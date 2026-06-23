"""loop-creator plugin registration."""
from __future__ import annotations

from . import schemas, tools


def _setup_cli(subparser):
    subs = subparser.add_subparsers(dest="loop_command")

    create = subs.add_parser("create", help="Create a loop run scaffold")
    create.add_argument("track", nargs="?", choices=["standard", "full", "gs"], help="standard, full, or gs")
    create.add_argument("--trigger-mode", default="manual", choices=["manual", "interval", "event"], help="What starts the loop: manual, interval, or event")
    create.add_argument("--risk-mode", default="", choices=["", "quick", "normal", "deep", "blocked"], help="Risk-proportional verification depth")
    create.add_argument("--depth", default="", help="GS depth: Quick, standard, or Full GS")
    create.add_argument("--slug", default="", help="Folder slug")
    create.add_argument("--root-path", default="", help="Parent folder for loop-runs")
    create.add_argument("--artifact", default="", help="Artifact path/text/TODO")
    create.add_argument("--reader", default="", help="Reader/evaluator")
    create.add_argument("--outcome", default="", help="Desired outcome")
    create.add_argument("--constraints", default="", help="Constraints/evidence limits")
    create.add_argument("--check-command", default="", help="Command or evaluation surface between iterations")
    create.add_argument("--exit-when", default="", help="Observable exit condition")
    create.add_argument("--step-1", default="", help="First concrete action")
    create.add_argument("--cadence", default="", help="Interval cadence, e.g. 15m or 7d")
    create.add_argument("--event", default="", help="Event/hook name, e.g. post-edit or pre-commit")
    create.add_argument("--company", default="", help="GS company/product/offer")
    create.add_argument("--growth-outcome", default="", help="GS growth outcome")
    create.add_argument("--customer", default="", help="GS target customer/buyer")
    create.add_argument("--payer", default="", help="GS payer/buyer/budget owner")
    create.add_argument("--buying-trigger", default="", help="GS buying trigger / economic pain")
    create.add_argument("--horizon", default="", help="GS time horizon")
    create.add_argument("--research-allowed", action="store_true", help="GS public research allowed")
    create.add_argument("--published-status", default="draft", choices=["draft", "local", "validated", "published", "retired"], help="Loop record lifecycle state")
    create.add_argument("--related-loops", default="", help="Comma-separated related loop slugs or IDs")
    create.add_argument("--retirement-rule", default="", help="When this loop should retire")
    create.add_argument("--kill-condition", default="", help="When this loop should be killed")
    create.add_argument("--manual-trial", default="", help="One bounded manual trial before automation")

    validate = subs.add_parser("validate", help="Validate a loop run folder")
    validate.add_argument("path")

    summary = subs.add_parser("summary", help="Summarize a loop run folder")
    summary.add_argument("path")

    check_update = subs.add_parser("check-update", help="Read-only check for upstream plugin updates")
    check_update.add_argument("--remote", default="origin")
    check_update.add_argument("--branch", default="HEAD")

    subs.add_parser("selector", help="Print selector prompt")


def _handle_cli(args):
    cmd = getattr(args, "loop_command", None)
    if cmd in {None, "selector"}:
        print(tools.selector_text())
        return
    if cmd == "create":
        if not getattr(args, "track", None):
            print(tools.selector_text())
            return
        payload = {
            "track": args.track,
            "trigger_mode": args.trigger_mode,
            "risk_mode": args.risk_mode,
            "depth": args.depth,
            "slug": args.slug,
            "root_path": args.root_path,
            "artifact": args.artifact,
            "reader": args.reader,
            "outcome": args.outcome,
            "constraints": args.constraints,
            "check_command": args.check_command,
            "exit_when": args.exit_when,
            "step_1": args.step_1,
            "cadence": args.cadence,
            "event": args.event,
            "company": args.company,
            "growth_outcome": args.growth_outcome,
            "customer": args.customer,
            "payer": args.payer,
            "buying_trigger": args.buying_trigger,
            "horizon": args.horizon,
            "research_allowed": args.research_allowed if args.research_allowed else None,
            "published_status": args.published_status,
            "related_loops": args.related_loops,
            "retirement_rule": args.retirement_rule,
            "kill_condition": args.kill_condition,
            "manual_trial": args.manual_trial,
        }
        print(tools.create_scaffold(payload))
        return
    if cmd == "validate":
        print(tools.validate_run({"path": args.path}))
        return
    if cmd == "summary":
        print(tools.summarize_run({"path": args.path}))
        return
    if cmd == "check-update":
        print(tools.check_update({"remote": args.remote, "branch": args.branch}))
        return


def register(ctx):
    ctx.register_tool(
        name="loop_creator_scaffold",
        toolset="loop_creator",
        schema=schemas.LOOP_CREATOR_SCAFFOLD,
        handler=tools.create_scaffold,
        description="Create Loop Creator run scaffold",
        emoji="🧭",
    )
    ctx.register_tool(
        name="loop_creator_validate_run",
        toolset="loop_creator",
        schema=schemas.LOOP_CREATOR_VALIDATE_RUN,
        handler=tools.validate_run,
        description="Validate Loop Creator run package",
        emoji="✅",
    )
    ctx.register_tool(
        name="loop_creator_summarize_run",
        toolset="loop_creator",
        schema=schemas.LOOP_CREATOR_SUMMARIZE_RUN,
        handler=tools.summarize_run,
        description="Summarize Loop Creator run package",
        emoji="🧾",
    )
    ctx.register_tool(
        name="loop_creator_check_update",
        toolset="loop_creator",
        schema=schemas.LOOP_CREATOR_CHECK_UPDATE,
        handler=tools.check_update,
        description="Read-only check for Loop Creator plugin updates",
        emoji="🔎",
    )
    ctx.register_command("loop-creator", tools.handle_loop_creator, description="Create a standard/full/gs loop scaffold", args_hint="[standard|full|gs] [key=value...]")
    ctx.register_command("loop-validate", tools.handle_loop_validate, description="Validate a loop harness run", args_hint="<run-path>")
    ctx.register_command("loop-summary", tools.handle_loop_summary, description="Summarize a loop harness run", args_hint="<run-path>")
    ctx.register_command("loop-update-check", tools.handle_loop_update_check, description="Check whether loop-creator has upstream updates", args_hint="[remote=origin] [branch=HEAD]")
    ctx.register_hook("pre_gateway_dispatch", tools.pre_gateway_dispatch)
    ctx.register_cli_command("loop-creator", help="Create/validate/summarize Loop Creator runs", setup_fn=_setup_cli, handler_fn=_handle_cli)
