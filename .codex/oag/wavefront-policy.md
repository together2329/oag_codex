# OAG Wavefront Policy

OAG Wavefront is the dependency-aware parallel execution layer above ROCEV
truth. It decides which already-defined work shards may run in parallel; it
does not create requirements, contracts, locked truth, or closure decisions.

## Definition

Wavefront parallelism means opening only tasks whose dependency, ownership, and
evidence boundaries are currently satisfied.

```text
locked ontology truth
  -> authoring packets / evidence plan
    -> wavefront task graph
      -> dispatch
        -> ownership lock bound to dispatch_id
        -> subagent receipt
          -> review_pending
            -> reviewer decision
              -> handoff_pass
                -> evidence validation
                  -> gate decision
```

## Boundaries

- `read_only` tasks may fan out aggressively. They may write only reports,
  receipts, or wavefront events.
- `write` tasks may fan out only when their `allowed_write_paths` are disjoint
  from active writer locks.
- `integration` tasks own shared artifacts such as filelists, run scripts,
  aggregate results, coverage JSON, and generated closure summaries.
- `closure` tasks are not worker-owned. Closure remains parent/gate authority.

For write/integration tasks, the dispatch record must be created before the
wavefront task is claimed. The claim must include the dispatch id so ownership
locks bind the task to the child receipt that will later be verified.

## Required Conditions

A task is ready only when:

1. every `depends_on` task has reached `handoff_pass`, `closed`, or `waived`;
2. every `barrier_inputs` token exists in the run barrier set;
3. no active ownership lock conflicts with its write paths;
4. the task keeps `may_claim_complete=false`.

If two or more tasks are ready at the same time and their ownership boundaries
do not conflict, parent orchestration should dispatch them as one native
subagent batch. Serializing a ready wave requires an explicit blocker such as an
active dependency, an ownership conflict, a runtime budget, or a user-stated
scope limit. The unspawned ready tasks must remain visible in the run prompt and
`dispatch_command_candidates`.

Long write-capable TB scenario waves are runtime-budget constrained until
proven otherwise. Open one or two scenario children first and require a
`WORKING:` heartbeat, owned draft file, receipt, or `BLOCKED:` reason before
opening the next scenario shard. If a claimed child has no heartbeat, owned
file, or receipt after a bounded status request, route the existing dispatch to
`INCONCLUSIVE`/`BLOCKED` before replacement; do not clear the path by closing
native children.

For wavefront-backed children, `WORKING:` should be paired with machine-readable
progress evidence:

```bash
python3 .codex/scripts/oag_wavefront.py heartbeat \
  --ip-dir <ip> --run-id <run> --task-id <task> --message "<phase>" --json
```

`oag_orchestration_guard.py audit` treats `heartbeat_at`, a fresh receipt, or a
claim-newer owned-path mtime as progress evidence. If all three are missing
after the progress budget, the task is a routing problem, not a cleanup problem.

For gap-driven work, parent orchestration should consume the latest
`knowledge/gap_matrix/implementation_review.json` when present. Open
implementation findings are scheduled by highest priority first (`P0` before
`P1`, then `P2`, then `P3`). Tasks in the same priority band may run in
parallel only when their dependency fields are satisfied and their target
artifacts do not overlap.

`handoff_pass` is not a worker self-claim. A worker receipt moves a task to
`review_pending`. Only an approved `oag_wavefront_decision.v1` review record
may move `review_pending` to `handoff_pass` and unlock downstream barriers.
The child receipt must be verified while the task is still `claimed`, or routed
as bounded `INCONCLUSIVE`, `BLOCKED`, or `FAIL`. Parent orchestration must not
record `handoff_pass` before the child stop hook has accepted the receipt; doing
so releases wavefront ownership and makes the child-side dispatch verifier see
an unclaimed/mismatched task.

## Worker Language

Wavefront workers may say `HANDOFF_PASS`, `BLOCKED`, `FAIL`, or
`INCONCLUSIVE`. They must not say completion, signoff, release, or closure.
Parent orchestration records worker `HANDOFF_PASS` receipts as
`review_pending` until `oag-custom-reviewer` or a narrower reviewer approves
the handoff rationale.

After a child reaches `handoff_pass`, `blocked`, `failed`, or `inconclusive`,
the parent must integrate, reject, or route the receipt before opening another
fan-out batch. Native child cleanup is runtime hygiene, not an OAG evidence
gate; defer it outside status checks, dispatch planning, receipt review, and
RTL/TB critical-path work.
If runtime startup stalls on optional MCP servers such as `computer-use`, do not
serialize or block the wavefront on that plugin startup. Apply the lean OAG
session profile with `oag_codex_config_doctor.py --lean-subagent-runtime`,
restart into a fresh trusted session, and continue from durable dispatch,
ownership lock, receipt, and barrier state.

## Role-Structured RTL/TB Pattern

RTL and TB dispatch should be role-structured before it is parallel. A generic
single `RTL_MODULE_A` or monolithic `TB_IMPLEMENTATION` child is allowed only
for trivial one-file work or when the parent records why role splitting would
create more risk than it removes.

```text
Wave RTL-0: read-only authoring packet / role split context
Wave RTL-1: interface shell, control FSM, datapath/state, clock/reset lanes
Barrier: role handoff tokens from each lane
Wave RTL-2: single RTL integration owner for top, filelists, lint manifest

Wave TB-0: read-only authoring packet / methodology context
Wave TB-1: driver/BFM, monitor, predictor, scoreboard, assertion lanes
Wave TB-2: coverage model after scoreboard schema
Wave TB-3: scenario tests in parallel ready wave
Wave TB-4: single runner owner for scripts, results, scoreboard rows, coverage
Wave TB-5: read-only failure triage
```

TB scenarios must not open until driver, monitor, predictor, scoreboard,
coverage, and assertion hooks have produced their declared barriers. Predictor
and expected-source work must remain independent of DUT/RTL-observed behavior.
RTL integration must not be split across multiple children that edit the same
top module, filelist, lint output, or generated manifest.

## Ontology Coupling

Wavefront reads ontology truth and authoring packets, then writes runtime state
under `ontology/runs/<run_id>/` and receipts under `knowledge/`. It is runtime
state, not authored design truth.
