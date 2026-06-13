"""loop-creator plugin registration."""
from __future__ import annotations

from . import schemas, tools


def _setup_cli(subparser):
    subs = subparser.add_subparsers(dest="loop_command")

    create = subs.add_parser("create", help="Create a loop run scaffold")
    create.add_argument("track", nargs="?", choices=["standard", "full", "gs"], help="standard, full, or gs")
    create.add_argument("--depth", default="", help="GS depth: Quick, standard, or Full GS")
    create.add_argument("--slug", default="", help="Folder slug")
    create.add_argument("--root-path", default="", help="Parent folder for loop-runs")
    create.add_argument("--artifact", default="", help="Artifact path/text/TODO")
    create.add_argument("--reader", default="", help="Reader/evaluator")
    create.add_argument("--outcome", default="", help="Desired outcome")
    create.add_argument("--constraints", default="", help="Constraints/evidence limits")
    create.add_argument("--company", default="", help="GS company/product/offer")
    create.add_argument("--growth-outcome", default="", help="GS growth outcome")
    create.add_argument("--customer", default="", help="GS target customer/buyer")
    create.add_argument("--payer", default="", help="GS payer/buyer/budget owner")
    create.add_argument("--buying-trigger", default="", help="GS buying trigger / economic pain")
    create.add_argument("--horizon", default="", help="GS time horizon")
    create.add_argument("--research-allowed", action="store_true", help="GS public research allowed")

    validate = subs.add_parser("validate", help="Validate a loop run folder")
    validate.add_argument("path")

    summary = subs.add_parser("summary", help="Summarize a loop run folder")
    summary.add_argument("path")

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
            "depth": args.depth,
            "slug": args.slug,
            "root_path": args.root_path,
            "artifact": args.artifact,
            "reader": args.reader,
            "outcome": args.outcome,
            "constraints": args.constraints,
            "company": args.company,
            "growth_outcome": args.growth_outcome,
            "customer": args.customer,
            "payer": args.payer,
            "buying_trigger": args.buying_trigger,
            "horizon": args.horizon,
            "research_allowed": args.research_allowed if args.research_allowed else None,
        }
        print(tools.create_scaffold(payload))
        return
    if cmd == "validate":
        print(tools.validate_run({"path": args.path}))
        return
    if cmd == "summary":
        print(tools.summarize_run({"path": args.path}))
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
    ctx.register_command("loop-creator", tools.handle_loop_creator, description="Create a standard/full/gs loop scaffold", args_hint="[standard|full|gs] [key=value...]")
    ctx.register_command("loop-validate", tools.handle_loop_validate, description="Validate a loop harness run", args_hint="<run-path>")
    ctx.register_command("loop-summary", tools.handle_loop_summary, description="Summarize a loop harness run", args_hint="<run-path>")
    ctx.register_hook("pre_gateway_dispatch", tools.pre_gateway_dispatch)
    ctx.register_cli_command("loop-creator", help="Create/validate/summarize Loop Creator runs", setup_fn=_setup_cli, handler_fn=_handle_cli)
