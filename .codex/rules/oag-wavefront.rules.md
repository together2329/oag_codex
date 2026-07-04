# OAG Wavefront Rules

## RULE-WAVE-001

Wavefront tasks must not create or change locked design truth. They may only
consume existing ontology, authoring packets, and evidence plans.

## RULE-WAVE-002

Write-capable wavefront tasks require disjoint `allowed_write_paths` or a single
declared `integration_owner`.

## RULE-WAVE-003

Tasks with unmet `depends_on` or missing `barrier_inputs` must not be claimed.

## RULE-WAVE-004

Shared artifacts such as run scripts, filelists, aggregate results, coverage,
and closure packages must have a single integration owner.

## RULE-WAVE-005

Failing simulation should enter read-only triage before scoped repair agents are
opened.

## RULE-WAVE-006

Worker receipts must keep `may_claim_complete=false`; closure remains gate-owned.

## RULE-WAVE-007

When two or more dependency-ready tasks have non-conflicting ownership, parent
orchestration should dispatch the whole ready wave as a native subagent batch.
Serial dispatch requires an explicit dependency, ownership, runtime-budget, or
user-scope blocker.

## RULE-WAVE-008

RTL/TB implementation waves should be role-structured. RTL lanes split
interface shell, control, datapath/state, clock/reset, and one integration
owner. TB lanes split driver/BFM, monitor, predictor, scoreboard, coverage,
assertion hooks, scenario shards, and one runner owner. A monolithic RTL or TB
child requires a recorded triviality or risk rationale.
