# Verification Tax and Loop Creator

AI increases production speed before it increases organizational confidence. The hidden cost is Verification Tax: the effort required to decide whether an AI-produced artifact is correct, safe, aligned, and worth using.

Loop Creator exists to reduce that tax by turning work into a verifiable loop package.

## The three debts

| Debt | Failure mode | Loop Creator countermeasure |
|---|---|---|
| Technical debt | AI changes code, config, or workflow without enough checks | check commands, exit criteria, review receipts, runner-neutral specs |
| Cognitive debt | people circulate AI output they cannot explain | goal contract, learning trace, handoff, quality document |
| Intent debt | the reason behind choices disappears | non-goals, rejected alternatives, risks, approval gates |

## From production to verification-system design

In AI-native work, the expert role shifts:

- from writing every artifact by hand
- to defining what good looks like
- to encoding that judgment into deterministic, explainable checks where possible
- to placing those checks between generation steps so drift is caught early
- to using LLM/human judges only for the residue that cannot yet be made deterministic
- to owning hard decisions that should not be automated away

Loop Creator supports that shift by separating the maker, the deterministic checker, the judge residue, the evidence, and the human judgment gate.

## Queryable, closed loop, self-improving

### Queryable

Loop packages leave machine-readable files: goals, acceptance criteria, evidence, failures, review receipts, and results. Future agents can inspect state instead of relying on chat memory.

### Closed loop

A loop is not “try again.” A useful loop has a predicate, evaluation surface, failure taxonomy, mutation, and evidence update.

### Self-improving

Failure types and eval results become the next harness input. Repeated failures become policy candidates, not hidden one-off notes.

## What Loop Creator does not claim

Loop Creator does not prove that an external runner executed a task. `runner/loop.yaml` is portable planning metadata. Real execution evidence still has to be recorded in the evidence ledger, eval result, command output, or review receipt.

Loop Creator does not remove human responsibility. It makes the responsibility visible: who approves, what evidence exists, what risk remains, and what mutation should happen next.

## Practical success signal

A good Loop Creator package lets a reviewer answer these questions quickly:

1. What was the goal?
2. What would count as failure?
3. Which human judgment was encoded into checks?
4. Which checks are deterministic and explainable?
5. Which parts still require LLM/human judge review, and why?
6. What actually happened?
7. What evidence supports the claim?
8. What should happen next?

If those answers are not recoverable, the team is paying Verification Tax manually.
