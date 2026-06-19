# Example: AI-native Verification Tax

This example shows how a prompt-only AI task becomes a Loop Creator package.

The point is not that the example output is large. The point is that the work becomes reviewable, restartable, and auditable.

## Before

`before-prompt-only.md` is the common pattern: a broad prompt asks AI to improve a proposal. The result may be useful, but the goal, hard-fails, acceptance criteria, and evidence are not durable.

## After

`after-loop-package/` shows the minimum useful loop package:

- `state/goal-contract.md` defines the objective, hard-fails, and verification surface.
- `state/evidence-ledger.json` records observed evidence for completion claims.
- `state/failure-taxonomy.yaml` makes failure reusable instead of anecdotal.
- `eval/eval_spec.yaml` separates deterministic checks, judge checks, and safety checks.
- `runner/loop.yaml` describes a runner-neutral loop without claiming execution happened.
- `final/user-facing-summary.md` gives the human reviewer the current verdict and next action.

## What this demonstrates

| Prompt-only work | Loop package work |
|---|---|
| “Improve this” | objective + reader + hard-fails |
| “Looks better” | acceptance criteria + eval pack |
| “Done” | evidence-backed candidate completion |
| chat context | files that future agents can query |
| vague retry | failure taxonomy + next mutation |

Use this pattern when the review cost is high enough that a one-off prompt is cheaper now but more expensive later.
