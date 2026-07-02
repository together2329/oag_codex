# OAG Team Mode Policy

Team Mode exists to make multi-agent IP work auditable before it becomes
execution. It turns "keep working" intent into an explicit Team Lead and Worker
plan with bounded scope, review points, and stop conditions.

## Levels

- `default`: stay with the main agent. Use for small, single-scope, read-only,
  or clearly blocked work.
- `team_plan_optional`: show a team split because parallelism may help, but the
  main agent can still handle the next step.
- `team_plan_recommended`: use a Team Lead plus Worker plan before execution.
  The task has multiple roles, separable scopes, architecture optioning,
  independent-review value, or long-running research/regression.
- `blocked`: do not plan worker execution. Resolve active locks, pending gates,
  missing IP state, or unsafe final-claim hazards first.

Team Mode v1 is plan-only. It must not spawn workers, claim wavefront tasks, or
create dispatches by itself.

## Complexity Dimensions

Score the current state with these dimensions:

- action count: several ready or high-priority Mission/Action candidates.
- role split: candidates need more than one owner role.
- write scope split: RTL, TB, sim, evidence, review, or gate work can be
  isolated.
- architecture optioning: the task needs option research, parameterization, or a
  recommended design choice.
- independent review value: correctness depends on reviewer separation.
- long-running work: simulation, coverage, research, or regression should not
  block the Team Lead.
- blockers: active locks, pending gates, missing IP state, or unsafe completion
  claims override the score and produce `blocked`.

Recommendation thresholds:

- score `< 3`: `default`
- score `3..5`: `team_plan_optional`
- score `>= 6`: `team_plan_recommended`
- blockers present: `blocked`

## Role Contracts

Team Lead:

- owns user intent, one-question discipline, and recommendation framing.
- reads run state, Mission/Action candidates, and orchestration guard output.
- decides whether work should stay local or be prepared for dispatch.
- creates dispatches or wavefront claims only after explicit execution approval.
- reviews receipts and final evidence before reporting completion.

Worker:

- starts only from an approved dispatch or wavefront task.
- owns one bounded task and disjoint write scope.
- writes an explicit receipt with changed paths, commands, evidence, and
  blockers.
- never claims final closure, gate pass, signoff, or lock authority.

## Handoff Rules

Worker plans are drafts until dispatched. Shared artifacts require a single
integration owner. Late receipts from aborted tasks are not accepted as valid
handoffs. Active locks and pending gates must be resolved before replacement
work is opened.

Future Team Mode execution should integrate only through OAG wavefront and
dispatch records, with `may_claim_complete=false` on Worker tasks and a
separate reviewer or Team Lead decision before handoff.
