# Goal Contract

- goal_id: `ai-native-verification-tax-example`
- objective: Turn a vague AI-native consulting proposal into a buyer-reviewable artifact with explicit proof of credibility.
- artifact: `proposal.md`
- reader: B2B operator evaluating whether AI work can be trusted beyond output volume.
- completion_criteria:
  - buyer can identify the promised business outcome
  - reviewer can see how claims will be verified
  - artifact explains Verification Tax, cognitive debt, and intent debt without buzzword inflation
- hard_fails:
  - claims automation happened without evidence
  - hides remaining risk behind “AI-native” language
  - lacks a human approval or judgment boundary
- verification_surface:
  - deterministic: required sections exist
  - qualitative: rubric checks buyer clarity, evidence quality, and risk honesty
  - safety: no fake evidence or secret leakage
- lifecycle_state: `candidate`
- next_continuation_condition: Fill evidence after a real review or command output, then update eval/latest-result.json.
