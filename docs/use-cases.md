# Loop Creator Use Cases

Loop Creator is useful when AI work needs more than output volume. Use it when the real problem is proving that an AI-produced artifact is correct, safe, aligned, and worth shipping.

## 1. AX transition after the first excitement

Early AI adoption often optimizes for accounts, training, prompt volume, and token usage. The second phase exposes the real bottleneck: output quality, verification cost, and workflow mismatch.

Use Loop Creator when:

- teams are producing more artifacts but trusting fewer of them
- managers ask “how do we know this is right?”
- review time grows faster than production speed
- AI outputs move across teams without enough context

What it creates:

- `state/goal-contract.md` for the real objective and hard-fails
- `eval/` for deterministic and judgment-based checks
- `state/evidence-ledger.json` for observed proof
- `state/session-handoff.md` for restartable context

## 2. Agent workflow and personal operating systems

A persona, memory, skill, and MCP toolchain can create a domain agent. But without an external verification layer, the agent may generate plausible work while accumulating hidden drift.

Use Loop Creator when:

- a personal or team agent is expected to make repeated decisions
- the agent needs to preserve taste, constraints, and prior judgment
- multiple agents or humans hand work off to each other
- output should become queryable future context, not chat history residue

What it creates:

- a durable state spine
- explicit human judgment gates
- trace-grounded completion claims
- failure taxonomy for future improvement

## 3. Strategy, GTM, and growth artifacts

Growth work fails when a memo sounds convincing but does not create revenue learning. GS Loop exists for artifacts whose core claim is revenue, ICP, offer, channel, funnel, or roadmap movement.

Use Loop Creator when:

- a strategy needs to prove where revenue learning will happen
- an offer or campaign needs buyer-facing validation criteria
- a roadmap needs evidence beyond internal preference
- a team needs to separate taste, evidence, and risk

What it creates:

- GS-specific harness structure
- growth outcome and buyer/payer framing
- evidence standards and score caps
- next mutation instead of vague “iterate more” advice

## 4. Code, systems, and operational changes

For code and operations, the dangerous failure is not only a bug. It is shipping code or config nobody understands because AI produced it and review only checked surface plausibility.

Use Loop Creator when:

- changes affect runtime, credentials, data, or user-facing behavior
- validation needs binary checks and qualitative review
- repeated failures should become policy updates
- completion claims require real command output

What it creates:

- check command and exit condition surfaces
- anti-gaming rules
- approval and review receipts
- runner-neutral loop metadata without pretending execution happened

## 5. Documents, proposals, and learning artifacts

For high-stakes writing, the problem is not just wording. The artifact must preserve intent, constraints, audience model, rejection criteria, and evidence.

Use Loop Creator when:

- a proposal must persuade a specific reader
- a course or guide must prevent AI-slop patterns
- a document needs an explicit quality bar and hard-fails
- revisions should accumulate learning instead of overwriting context

What it creates:

- reader/evaluator model
- hard-fails and acceptance criteria
- per-loop trace
- final user-facing summary

## Decision rule

Do not use Loop Creator for every task. Use it when the cost of being wrong, confused, or untraceable is higher than the cost of creating the loop package.
