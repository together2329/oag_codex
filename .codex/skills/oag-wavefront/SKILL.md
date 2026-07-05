---
name: oag-wavefront
description: Use when planning or executing OAG parallel subagent work with dependency barriers, ownership locks, read-only triage, disjoint write shards, or single integration owners instead of unconstrained fan-out.
---

# OAG Wavefront

Use this skill when OAG work should be parallelized without breaking ontology
truth, file ownership, or evidence boundaries.

## Principle

Parallelism is not "spawn many agents". Parallelism is opening the current
ready wavefront of tasks whose dependencies, ownership, and evidence boundaries
are satisfied.

## Workflow

1. Compile/check the IP ontology and authoring packets first.
2. Plan a wavefront graph from existing contracts, packets, and evidence plan.
3. Check ready tasks.
4. For write-capable tasks, create dispatch records before claiming.
5. Claim only dependency-satisfied tasks, passing `--dispatch-id` for
   write/integration claims.
6. Spawn the child and let its stop hook verify the receipt while the task is
   still `claimed`.
7. Record worker receipts as `review_pending`.
8. Review the handoff with `oag-custom-reviewer` or a narrower reviewer role.
9. Record `handoff_pass` and barrier outputs only after an approved
   `oag_wavefront_decision.v1` record.
10. Let a single integration owner write shared run artifacts.
11. Use read-only triage before repair when simulation fails.
12. For implementation gaps, consume `implementation_review` evidence and run
    highest-priority dependency-ready gaps first.
13. Treat each obligation-to-contract closure edge as a todo-like item with
    owner, criteria, required evidence, approval policy, and approved reason.
    Stop/run prompts should expose the open edge set so parent orchestration can
    choose all open items, one item, a scoped module, or a bounded batch.
14. Integrate, reject, or route completed child receipts before opening another
    fan-out batch; defer native child cleanup outside the critical path.
15. Let parent/gate decide closure.

RTL/TB implementation should use role-structured templates by default. For RTL,
start from `rtl_module_fanout.yaml`: context, interface shell, control FSM,
datapath/state, clock/reset, then one integration owner. For TB, start from
`tb_common_then_scenario_fanout.yaml`: context, driver/BFM, monitor,
predictor, scoreboard, coverage, assertion hooks, scenario shards, then one
runner owner. A monolithic RTL/TB child needs a recorded triviality or risk
rationale.

Child runtime latency is not implementation failure. If a write-capable child
has not produced artifacts yet, steer it for status or let a timeout policy
route `INCONCLUSIVE`/`BLOCKED`; do not close the child and have the parent edit
the child's RTL, TB, simulation, coverage, filelist, or signoff-owned files.
Parent implementation after lock requires a human waiver decision and must be
visible to the main-write gate.

Long write-capable RTL/TB children need an explicit heartbeat contract in the
spawn prompt: the child should emit `WORKING: <task> - <phase>` within the first
wait cycle and at major phase changes, or produce an owned draft file, receipt,
or `BLOCKED:` reason. A child that stays silent and produces no owned-path
evidence after a bounded status request is a wavefront state problem, not a
reason for parent implementation.
For wavefront-backed children, also include the machine-readable heartbeat
command from the dispatch prompt:
`python3 .codex/scripts/oag_wavefront.py heartbeat --ip-dir <ip> --run-id <run> --task-id <task> --message "<phase>" --json`.
`oag_orchestration_guard.py audit` uses that `heartbeat_at`, a fresh receipt, or
claim-newer owned-path mtimes as progress evidence.

Treat large TB scenario shards as runtime-budget constrained by default. Even
when three or more scenario tasks are dependency-ready and path-disjoint, open
only one or two long write-capable scenario children until the first heartbeat,
owned file, or receipt proves runtime throughput. Record the unspawned ready
tasks and the runtime-budget reason; this is not serialization for convenience.

Use bounded handoff for stalled children. After the configured wait budget,
request a minimal receipt with the current status, changed paths, commands, and
blockers. If the child does not respond, record the wavefront task as
`INCONCLUSIVE`, `BLOCKED`, or `failed` according to available evidence, then
create a new dispatch from the current baseline. Park or clean up the stale
child only after that OAG state transition, and never as part of a parallel
status/dispatch/receipt-review batch.
Do not keep an ownership lock open while starting an untracked replacement.
Do not widen an old dispatch to absorb the replacement's paths or artifacts.
When a task is recorded as `blocked`, `failed`, or `inconclusive`, treat the
old dispatch as aborted. Late receipts from that dispatch are not valid
handoffs; verify must reject them and the replacement must use a fresh dispatch
from the current baseline.

## Commands

Create a graph from a generic template:

```bash
python3 .codex/scripts/oag_wavefront.py plan \
  --ip-dir <ip> \
  --run-id <run_id> \
  --template .codex/oag/wavefront-templates/tb_common_then_scenario_fanout.yaml \
  --json
```

Create a graph from current Mission/Action candidates when the operating plan
has already selected the next ready work split:

```bash
python3 .codex/scripts/oag_action_wavefront_draft.py \
  --ip-dir <ip> \
  --materialize-run-id <run_id> \
  --json
```

This writes an intermediate generated template and a wavefront graph. It still
does not claim tasks, create dispatch records, or approve handoffs.

List ready tasks:

```bash
python3 .codex/scripts/oag_wavefront.py ready --ip-dir <ip> --run-id <run_id> --json
```

Claim a task:

```bash
python3 .codex/scripts/oag_wavefront.py claim \
  --ip-dir <ip> \
  --run-id <run_id> \
  --task-id <task_id> \
  --dispatch-id <dispatch_id> \
  --json
```

For write/integration tasks, create the dispatch record first and pass its
`dispatch_id` into `claim`. Claiming writable wavefront tasks without a
dispatch id is invalid because ownership locks must bind to the child dispatch.

Record bounded worker status after the worker receipt:

```bash
python3 .codex/scripts/oag_wavefront.py record \
  --ip-dir <ip> \
  --run-id <run_id> \
  --task-id <task_id> \
  --status review_pending \
  --receipt <ip>/knowledge/subagents/<receipt>.json \
  --json
```

Create a reviewer decision:

```bash
python3 .codex/scripts/oag_decision_harness.py record \
  --ip-dir <ip> \
  --run-id <run_id> \
  --task-id <task_id> \
  --decision-type rtl_conformance \
  --verdict approved \
  --summary "Reviewer-approved handoff rationale." \
  --checked-against ontology/contracts.yaml#CONTRACT_ID \
  --preserved "assigned contract guarantees" \
  --barrier-output <token> \
  --json
```

Record handoff only after review approval:

```bash
python3 .codex/scripts/oag_wavefront.py record \
  --ip-dir <ip> \
  --run-id <run_id> \
  --task-id <task_id> \
  --status handoff_pass \
  --decision <ip>/knowledge/decisions/<decision>.json \
  --barrier-output <token> \
  --json
```

Verify graph invariants:

```bash
python3 .codex/scripts/oag_wavefront.py verify --ip-dir <ip> --run-id <run_id> --json
```

Plan from implementation-review gaps when present:

```bash
python3 .codex/scripts/oag_implementation_review_check.py --ip-dir <ip> --json
```

For imported or partial legacy IPs without an OAG scaffold, use:

```bash
python3 .codex/scripts/oag_implementation_review_check.py --ip-dir <ip> --legacy-no-scaffold --json
```

Use `plan.next_wave.actions` as the next spawn batch. It is sorted by
P0/P1/P2/P3 priority and excludes actions whose dependencies are not satisfied
or whose target artifacts overlap within the batch.

## Rules

- Read-only extraction and failure triage may fan out aggressively.
- Write tasks require disjoint paths.
- If two or more dependency-ready tasks have non-conflicting ownership, spawn
  the whole ready wave as one native subagent batch; serial dispatch needs an
  explicit dependency, ownership, runtime-budget, or user-scope blocker.
- For large write-capable TB scenario shards, runtime budget is presumed
  constrained until early heartbeat or owned-path evidence proves otherwise;
  default to one or two concurrent scenario children and keep the rest visible
  as ready-but-unspawned.
- Shared artifacts require one integration owner.
- Scenario TB tasks must wait for driver, monitor, predictor, scoreboard,
  coverage, and assertion barriers.
- RTL/TB waves should be role-structured before they are parallelized.
- Worker tasks must not claim completion or signoff.
- Worker receipts do not unlock downstream work; they move tasks to
  `review_pending`.
- No approved reviewer decision, no `handoff_pass`.
- No completion claim without an explicit approval reason on the final OAG
  decision receipt.
- Child-thread closedness is not a progress gate. No new fan-out batch while
  prior ready-wave receipts remain unintegrated, unrejected, or unrouted; native
  cleanup may be deferred.
- Do not record `handoff_pass` before the child receipt has passed the stop
  hook or has been routed as a bounded `INCONCLUSIVE`/`BLOCKED`/`FAIL` receipt.
- Do not start a replacement dispatch under an active lock. If a claimed child
  has no heartbeat, owned file, or receipt after a bounded status request, route
  the existing dispatch to `INCONCLUSIVE`/`BLOCKED` first; late receipts from
  that dispatch are invalid handoffs.
- Do not widen a dispatch or baseline after verifier failure. Create a new
  dispatch from a clean baseline instead.
