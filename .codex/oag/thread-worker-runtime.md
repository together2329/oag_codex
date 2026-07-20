# OAG Thread Worker Runtime

New OAG dispatches use a fresh Codex App Server worker thread by default. The
worker is a top-level thread, not a native subagent. Legacy native-subagent
dispatch remains available only through an explicit
`--execution-kind native_subagent` selection.

## Contract

- `oag_dispatch.py create` records `execution_actor.kind=worker_thread`.
- The actor uses `isolation=fresh_thread`, a bounded `resume_limit`, and
  `subagents_allowed=false`.
- `oag_thread_worker.py` starts one App Server thread with the multi-agent and
  child-agent features disabled, streams token usage, and records thread and
  turn IDs. Codex requires `agents.max_depth` to remain at least 1, so depth 0
  is not used as the isolation mechanism.
- At the warning threshold the runner sends `turn/steer` with a bounded finish
  instruction.
- At the hard token limit or wall-clock timeout the runner sends
  `turn/interrupt`.
- Any `collabAgentToolCall` event fails the run and prevents write coverage.
- `oag_thread_control.py status` combines the execution manifest's live state
  with a compact `thread/read` snapshot. A second App Server can read persisted
  task items, but the owning worker manifest remains authoritative while a turn
  is active.
- External steering is appended to the dispatch event log and is accepted only
  by the worker process that owns the active App Server connection. The worker
  validates the thread ID, expected turn ID, request ID, method, and input size
  before issuing `turn/steer`, then records an applied or rejected audit row.
  Status reports steering support only when the running manifest advertises the
  matching control protocol, so workers started by an older runtime cannot be
  steered accidentally.
- The App Server runs in an isolated process session. Runtime close captures
  and terminates its descendant process tree before reaping the server, so a
  timed-out solver or helper cannot remain orphaned and write into a resumed
  dispatch.
- The worker is told that parent orchestration is complete and must not reload
  OAG skills, workflow manuals, or broad repository context.
- The turn receives a literal receipt JSON skeleton. The model owns semantic
  fields such as `status`, blockers, checks, and evidence notes. The runtime
  owns dispatch identity, exact mirrored scope, thread identity, list shape,
  and the `dispatch_verified` transition.
- After a completed turn, the runtime normalizes only dispatch-owned structure,
  writes `dispatch_verified=false`, and runs full preverification. It changes
  the value to `true` only when preverification passes, then runs the ordinary
  verifier again. A failed final verification resets it to `false`.
- Scalar values in schema-defined receipt string-list fields are normalized to
  one-element arrays. This includes `tb_methodology_notes` blocker collections.
- A schema-defined receipt object rendered as uniquely labeled `key=value`
  strings is normalized only when every label maps to a declared property.
  Unknown or duplicate labels remain invalid. `tb_methodology_notes` accepts
  the legacy `architecture_roles` label as `architecture`.
- A verified `INCONCLUSIVE` receipt is structurally valid and preserves its
  blockers, but it does not provide passing artifact coverage at the parent
  Stop gate. The parent must repair the deliverable or record an explicit human
  waiver; the runtime never promotes `INCONCLUSIVE` to a passing handoff.
- Formal subprocesses must run from dispatch-owned build directories. As a
  final containment guard, the runtime removes a newly created repo-root
  `sm01.aig` only when that path was absent at worker start, and records its
  digest and size as a `worker_runtime_cleanup` event. A pre-existing file is
  never removed.
- A passing receipt must reference a completed execution manifest whose event
  log hash, dispatch ID, thread ID, budget status, resume count, and subagent
  count validate.

## Usage

```bash
python3 .codex/scripts/oag_dispatch.py create \
  --ip-dir <ip> \
  --agent-type <oag-role> \
  --stage <stage> \
  --allowed-write-path <path> \
  --receipt-path <ip>/knowledge/subagents/<receipt>.json \
  --warning-total-tokens <early-finish-threshold> \
  --json

python3 .codex/scripts/oag_thread_worker.py \
  --dispatch <ip>/knowledge/dispatches/<dispatch>.json \
  --task-file <bounded-task.md> \
  --effort medium \
  --json

python3 .codex/scripts/oag_thread_control.py status \
  --manifest <ip>/knowledge/executions/<dispatch>.thread.json \
  --json

python3 .codex/scripts/oag_thread_control.py steer \
  --manifest <ip>/knowledge/executions/<dispatch>.thread.json \
  --message "Concrete blocker correction only." \
  --json
```

Steering is exceptional, not periodic prompting. Use it only when task history
shows a concrete blocker, stale assumption, scope error, or incorrect proof
strategy. Status polling alone never writes to the worker event log.

For a failed or interrupted run with remaining token budget, the same command
may add `--resume`. The runner uses `thread/resume`, appends a new turn to the
existing event log, preserves cumulative token usage, and refuses attempts past
the dispatch `resume_limit`.

The raw App Server JSONL stream and durable execution manifest are stored with
mode `0600` under `<ip>/knowledge/executions/`. Both paths are explicit dispatch
side effects, and the manifest hash-links the event log. OAG correlation
telemetry receives the execution kind, dispatch ID, dispatch path, and manifest
path through the worker environment.

## Compatibility

Dispatches without `execution_actor` are interpreted as legacy
`native_subagent` records. Existing receipt schema and result field names stay
readable. New write-gate output also exposes `executor_receipts` so consumers
can migrate without losing old evidence.

## Bounded Reuse Pilot

Thread reuse is an evaluated optimization, not the default execution policy.
The 2026-07-19 pilot compared fresh threads with one reused thread across Sol,
Terra, and Luna at medium effort. The compact report is
`.codex/evals/reports/thread_reuse_pilot_20260719.json`.

- Short prompt-only tasks kept the same answers and reduced latency by 25.3%,
  but increased total tokens by 2.6%.
- An eight-turn prompt-only lane reduced latency by 47.6%, but increased total
  tokens by 3.4%.
- Sequential RTL repair lanes passed 12/12 independent simulations and reduced
  latency by 58.1%, total tokens by 44.6%, non-cached input by 66.8%, output by
  64.8%, and reasoning output by 73.9%.
- Hidden lint found a width warning in two reused RTL results that the matching
  fresh result avoided. A reused implementation lane therefore cannot review
  or sign off its own output.

The candidate policy is bounded mission-lane reuse:

- reuse only when IP, role, model, reasoning effort, scope-lock version, and
  owned artifact set remain compatible;
- use at most four related implementation/debug turns before rotation while
  further evidence is collected;
- keep dispatch, receipt, budget, and telemetry attribution per turn;
- rotate immediately on role, model, scope, ownership, or architectural change;
- require a fresh reviewer plus deterministic test, lint, or formal gate before
  promotion;
- keep fresh threads for unrelated prompt-only tasks because reuse did not save
  total tokens in that workload.

Production dispatch remains `fresh_thread` until lineage validation, per-turn
usage deltas, receipt verification, rotation, and fresh-review enforcement are
implemented and covered by regression tests.
