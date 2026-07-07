# OAG Codex Subagent Workflows

Codex subagents are native Codex collaboration workers. Do not run a Python
script, shell wrapper, or manual role-play substitute to spawn them. The main
agent uses a prompt/directive to ask Codex to start native subagents, waits for
their results, integrates the result, then records durable OAG evidence through
the normal ROCEV flow.

Project-scoped custom agent definitions live in `.codex/agents/*.toml`. OAG
metadata for those roles lives in `.codex/oag/agent-catalog.toml`.

Native subagent assignments should include the posture from
`.codex/oag/agent-common-preamble.md`: preserve design truth, use the smallest
sufficient proof, do not infer expected behavior from RTL, and leave weak
closure claims open with precise blockers.

For team use, ask for OAG mode explicitly with the lowercase `oag` command
prefix. Terms like `auto research`, `subagent`, and `signoff`, uppercase OAG
acronym mentions, or meta discussion about OAG describe work but do not
activate OAG mode by themselves. Project config requests native subagent
support through `[features].multi_agent = true` and
`[features].child_agents_md = true`, and forces
`[features.multi_agent_v2].enabled = false`. This mirrors the OMO Codex runtime
pattern: v1 is not directly enabled; v2 is re-disabled so Codex can resolve to
the v1 multi-agent path when native subagents are available. Use
`python3 .codex/scripts/oag_codex_config_doctor.py --include-omo-plugin-features --apply` to
patch user-level Codex config for team members, or rely on the SessionStart hook
to do the same at startup. The active Codex runtime still has to expose the
native subagent facility after restart or a fresh trusted project session. Do
not narrate speculative tool-namespace probes. Missing `multi_agent_v1` in one
agent surface is not proof that native subagents are unavailable; Codex CLI/App
may surface the same operation as an internal `spawn_agent` collaboration event.
Before reporting a native-subagent blocker, first attempt a minimal explicit
native spawn in the current surface and wait for the child result. Do not decide
availability from the visible callable tool namespace alone; in Codex CLI/App
traces, explicitly request the native `spawn_agent` collaboration event even
when no `multi_agent_v1` tool namespace is visible. If the actual spawn attempt
fails or the active runtime reports spawning is unavailable, report the observed
native-spawn blocker and ask the user to restart/open a fresh trusted `ip_dev`
session. Do not continue by pretending a child agent ran, and do not manually
apply a child role as a substitute unless the user explicitly waives the native
subagent requirement.

## Lean OAG Runtime

Codex may start global MCP/plugin servers before a parent or child thread is
usable. OAG subagents do not need UI automation MCPs such as
`computer-use@openai-bundled` for RTL/TB/lint/sim/gate work. If a subagent or
fresh thread stalls at `Starting MCP servers` and `/mcp` shows `computer-use`,
switch that OAG-heavy workspace to the lean profile:

```bash
python3 .codex/scripts/oag_codex_config_doctor.py \
  --include-omo-plugin-features \
  --lean-subagent-runtime \
  --apply
```

Then open a fresh trusted session. This disables optional `computer-use`
startup for the session profile; it does not prove native subagents are
unavailable. Do not wait on MCP startup or native child closedness before
routing OAG dispatch, receipt, lock, and wavefront state.

## Native Trigger

The native spawn may appear as a Codex native tool call when the current surface
exposes it:

```text
multi_agent_v1.spawn_agent({
  "message": "TASK: act as <role>. DELIVERABLE: ... SCOPE: ... VERIFY: ...",
  "agent_type": "<oag-agent-name>",
  "fork_context": false
})
```

In Codex CLI/App traces the same native path can appear as a collaboration event
such as `spawn_agent`, followed by a `wait` event and a child thread id. Both
are native Codex subagents. A Python process that role-plays the instructions is
not.

## Exec-Resume Auto Research

For unattended or pane-independent auto research, use the wrapper:

```bash
python3 .codex/scripts/oag_exec_auto_research.py \
  --ip-dir <ip> \
  --session-id <exact-codex-session-id> \
  --objective "<bounded research objective>" \
  --yolo \
  --bypass-hook-trust
```

The wrapper invokes `codex exec` or `codex exec resume`, captures JSONL events,
and writes a manifest under `.codex/runs/auto_research/`. Prefer an exact
session id over `--last`; `--last` can select the wrong pane or older thread.
Do not count an auto-research run as native subagent-backed unless the manifest
observes a `spawn_agent` collaboration event. The wrapper is orchestration
evidence; it does not replace OAG records, dispatch receipts, validator reports,
or gate review. Read-only wrapper runs should use a built-in explorer-style
subagent. Use OAG custom/write-capable roles only after creating an OAG dispatch
record and passing the dispatch id, path, allowed writes, side effects, and
receipt path into the child assignment.

Use `agent_type` as a routing hint, not as proof that a TOML role, model,
reasoning effort, or service tier was selected. Always paste the role
requirements into `message` so the child has a self-contained executable
assignment.

Use `fork_context: false` unless the child truly needs full parent history. Full
history can make the child continue stale parent context instead of the assigned
task.

Use native waiting/mailbox behavior for child results. A wait timeout means "no
new update arrived"; it is not proof that the child failed. For long work,
require the child to send:

```text
WORKING: <task> - <current phase>
BLOCKED: <reason>
```

For RTL/TB authoring, use a patience protocol instead of a single wait. The
parent must not abandon an active child after one quiet wait cycle. Continue
waiting or send one targeted follow-up while the child is still running. Mark a
lane inconclusive only when the child completed without the deliverable, emitted
`BLOCKED:`, is no longer running, or remained silent across multiple wait cycles
and the parent records the reason. TB generation should be split into bounded
children: driver/BFM, monitor, predictor, scoreboard/schema, coverage,
assertion hooks, scenario groups, and runner integration. This keeps each child
short enough to finish while still letting large TB work proceed without the
parent prematurely closing the lane.

Every long write-capable RTL/TB child prompt must include an early evidence
contract: emit `WORKING: <task> - <phase>` within the first wait cycle and at
major phase changes, or create an owned draft file, receipt, or `BLOCKED:`
reason. If a claimed child stays silent and produces no owned-path evidence
after one bounded status request, route the existing dispatch to
`INCONCLUSIVE`/`BLOCKED` before opening replacement work. Late receipts from
that abandoned dispatch are not valid handoffs.
For wavefront-backed work, pair `WORKING:` with:

```bash
python3 .codex/scripts/oag_wavefront.py heartbeat \
  --ip-dir <ip> --run-id <run> --task-id <task> --message "<phase>" --json
```

This gives `oag_orchestration_guard.py audit` a durable progress signal instead
of relying on mailbox text alone.

Use native child steering only for targeted follow-up. Integrate, reject, or
route the completed/inconclusive lane first; native child cleanup is deferred
runtime hygiene, not a progress gate.
Do not mark a dependent step complete while an active child owns evidence for
that step.
When a wavefront-ready set contains two or more dependency-ready tasks with
non-conflicting ownership, spawn the whole ready wave as one native subagent
batch. Do not serialize ready tasks merely because the parent is easier to
drive one at a time. Serial dispatch is allowed only when a dependency, active
ownership lock, runtime budget, or user-stated scope limit blocks the batch; the
parent must record that reason and keep the unspawned ready tasks visible.
Normative shorthand: spawn the whole ready wave as one native subagent batch.
For large write-capable TB scenario shards, presume runtime budget is
constrained until throughput is proven. Open one or two scenario children first,
require early heartbeat or owned-path evidence, and leave the remaining
dependency-ready scenario tasks visible as ready-but-unspawned.
Before opening a new parallel batch, ensure every prior ready-wave child receipt
has been integrated, rejected, or routed. Keep only currently working children
on the critical path; cleanup of completed native child threads may be deferred
as a standalone bounded runtime hygiene step.

Use subagents when the work is naturally parallel and bounded:

- Read-heavy extraction: multiple specs, reference RTL trees, logs, waveform
  slices, or VIP patterns.
- Independent implementation shards: different files or modules with no shared
  edit surface.
- Independent review shards: evidence freshness, coverage gaps, protocol
  checks, or gate review.

Avoid subagents when a single edit surface needs tight sequential reasoning.
Write-heavy subagents must be assigned non-overlapping files or modules.
For larger fan-out, use `python3 .codex/scripts/oag_wavefront.py` first. The
wavefront graph records dependency barriers, ownership locks, and the single
integration owner for shared artifacts. A task that has unmet dependencies or a
conflicting ownership lock must not be dispatched.
When a gap matrix exists, run
`python3 .codex/scripts/oag_implementation_review_check.py --ip-dir <ip> --json`
and dispatch the returned `plan.next_wave.actions` first. For imported or
partial legacy IPs that do not have an OAG scaffold, add
`--legacy-no-scaffold`; the existing source hierarchy is the implementation
artifact under review. Actions in the same next wave can be parallelized when
their target artifacts are disjoint.

After user lock, main agent orchestrates; subagents implement and verify. Locked
RTL, TB, sim, lint, coverage, formal, SDC, signoff, and implementation filelist
writes require native OAG subagent dispatch + receipt. If native subagents are
unavailable, stop with BLOCKED unless the user records a human
`main_agent_subagent_waiver` decision receipt. Requirement detail work before
lock may stay with main, but read-heavy spec/reference/obligation research
should use subagents when useful and remains draft evidence until lock.

Keep parent-only and subagent-only authority separate. The parent creates
dispatches, claims or routes wavefront tasks, records `evidence_validation` or
other decisions, opens or withholds barrier tokens, and handles native child
cleanup outside the critical path. A write-capable subagent implements only the
parent-provided dispatch inside explicit `allowed_write_paths`, uses listed
tool side effects only for generated/wavefront bookkeeping, and writes one
receipt. The child must not create replacement dispatches, run
`oag_decision_harness.py record`, open `tb_uvm_dual_sim_evidence_ready`, release
or close wavefront tasks, or convert its handoff into a closure claim.

For evidence-schema repair, split the prompt into two surfaces. Parent prompt:
audit locks, create or claim one narrow repair dispatch, spawn the native child,
verify the receipt, record the evidence-validation decision, and keep the
dual-sim evidence barrier closed unless real canonical simulator evidence
exists. Child prompt: read `ontology/evidence/scoreboard_rows.v1.yaml`, compare
the failing rows and writer, repair only the writer/output in allowed paths,
preserve `BLOCKED`/`INCONCLUSIVE` semantics, regenerate blocked artifacts, and
write the receipt. `HANDOFF_PASS` from the child means only that the schema
repair deliverable is complete; it does not imply DUT functional PASS,
canonical simulation evidence, IP closure, or barrier readiness.

Blocked evidence must still be traceable. Do not hand-edit only the current
JSONL when the generator can be safely fixed; repair the writer first and then
regenerate artifacts. `results.xml` should distinguish simulator/UVM setup
blockers from DUT functional failures. `coverage.json` for a blocked pre-sim
run should report blocked, not observed, or not sampled rather than a misleading
0% sampled-coverage result.

After a child receipt, the parent must verify the exact dispatch/receipt pair
for the current task, not a stale schema-repair receipt from an earlier
dispatch. Use `--schema-only` only as a receipt-shape preflight; `HANDOFF_PASS`
is safe only after the full dispatch verifier passes against the current
receipt and actual path delta. If full verification fails because the baseline
or external delta changed, route the task as `INCONCLUSIVE` with that blocker
while preserving any successful schema, trace, or verification-plan checks.
Then rerun trace graph, verification-plan, `oag.check`, closure, and an
`evidence_validation` decision before opening any barrier. If canonical DUT
simulation is still blocked, keep dual-sim evidence barriers closed.

Coverage and observation artifacts should be explicit when simulation never
ran. Prefer `status=BLOCKED`, `coverage_observed=false`,
`coverage_sampled=false`, `closure_coverage_counted=false`, and a blocker
reason such as `missing_uvm_library` when the repo schema or existing writer
convention supports those fields. Do not add ad hoc fields that break the
local coverage schema. If `observed_source.kind=monitor` is required for schema
compatibility, use only `scoreboard_rows.v1`-allowed fields and make the
no-DUT-execution condition explicit through allowed metadata, blocker,
mismatch, observed object, or `evidence_notes`; do not imply that a real DUT
monitor observed a failing value.
Full or non-smoke runner paths must not silently fall back to the smoke subset
after `verification_plan.yaml` parse failure; they should emit blocked or
inconclusive runner-configuration evidence instead. Full/non-smoke receipts or
evidence notes should record scenario provenance such as `scenario_count`,
`scenario_source=ontology/verification_plan.yaml`, `plan_parse_success=true`,
and `smoke_fallback_used=false` when the receipt schema or local convention
allows those fields.

When reporting `oag.check`, do not collapse the result into overall PASS unless
the tool actually passes. If the scoreboard repair succeeded but closure,
freshness, or domain metadata issues remain, say that `oag.check` ran and no
scoreboard schema issue remains, while the remaining non-scoreboard issues
still block closure.
The parent or single integration owner should record IP-local git checkpoints
with `python3 .codex/scripts/oag_ip_git.py checkpoint --ip-dir <ip> --message
"OAG <stage>: <summary>" --json` after meaningful stage boundaries. Subagents
should not independently create commits unless their dispatch explicitly owns
that integration action. This keeps IP-local git history aligned with OAG
handoffs while avoiding large transient artifacts through the managed
`.gitignore`.

Before spawning a write-capable subagent, the main agent must create a dispatch
record and paste its fields into the child task:

For implementation, validation, coverage, mutation, evidence-validator,
gate-review, or closure subagents, the IP scope must already be locked:

```bash
python3 .codex/scripts/oag_cli.py call --json '{"tool":"oag.lock_status","arguments":{"ip_dir":"<ip>"}}'
```

If `ontology/scope_lock.json` is missing or `state=draft`, do not spawn the
child. Ask the user to confirm scope and run `oag.lock` first. No lock, no
RTL/TB/closure.

Before RTL or TB dispatch, compile the authored ontology and verify
role-specific packet projection:

```bash
python3 .codex/scripts/oag_cli.py call --json '{"tool":"oag.compile","arguments":{"ip_dir":"<ip>"}}'
python3 .codex/scripts/oag_authoring_packet_check.py --ip-dir <ip> --require-packets --json
```

RTL agents should consume `ontology/generated/authoring_packets/rtl__*.json`.
TB agents should consume `ontology/generated/authoring_packets/tb__*.json`.
If the packets are weak or missing refs, repair authored requirements,
contracts, modeling, or verification plan and compile again. Do not hand-edit
generated packets.

```bash
python3 .codex/scripts/oag_dispatch.py create \
  --ip-dir <ip> \
  --agent-type <oag-write-agent> \
  --stage <stage> \
  --allowed-write-path <ip>/rtl/<file>.sv \
  --allowed-write-path <ip>/knowledge/subagents/<receipt>.json \
  --allowed-tool-side-effect <ip>/ontology/generated/ \
  --receipt-path <ip>/knowledge/subagents/<receipt>.json \
  --json
```

The dispatch is the child work permit. The spawn message must include
`dispatch_id`, `dispatch_path`, allowed write paths, allowed tool side effects,
and receipt path. After child completion, run the bounded status/path audit
through `python3 .codex/scripts/oag_dispatch.py verify --dispatch <dispatch>
--receipt <receipt> --json`. It compares the child receipt and actual
`git status --short -uall -- <ip>` delta against the dispatch baseline. Any
path outside the child scope must be identified as pre-existing, rejected, or
explicitly routed to a new task before integration.

When the child belongs to a wavefront write or integration task, create the
dispatch before `oag_wavefront.py claim`, then claim with
`--dispatch-id <dispatch_id>`. Dispatch records that include wavefront metadata
automatically allow that run's wavefront bookkeeping paths as tool side
effects; workers still must not claim ownership of those paths. Do not record
`handoff_pass` while the child is still trying to stop. The required order is:

```text
dispatch create
-> wavefront claim --dispatch-id <dispatch_id>
-> native child spawn
-> child writes receipt and stop hook verifies while task is still claimed
-> wavefront record review_pending
-> reviewer decision
-> wavefront record handoff_pass
-> defer native child cleanup outside the critical path
```

The realistic stop boundary is receipt validity, not forced integration
success. In a parallel wave, another worker can legitimately change files under
the same IP after a dispatch baseline is captured. If `verify` fails only with
`ACTUAL_PATH_OUT_OF_SCOPE`, the child must not mutate the dispatch baseline,
widen its own allowed paths, or absorb those files into its receipt. It should
write `BLOCKED`, `INCONCLUSIVE`, or `FAIL` with blockers naming the external
delta and end with `OAG_EVIDENCE_RECORDED`. The `SubagentStop` hook may accept
that bounded blocked receipt so the parent can route or reconcile integration.
Successful handoff statuses still require a verifier pass.
The same bounded stop rule applies to parent-created wavefront lifecycle
mismatches such as `WAVEFRONT_TASK_UNCLAIMED` or
`WAVEFRONT_CLAIM_DISPATCH_MISMATCH`: child agents may record
`INCONCLUSIVE`/`BLOCKED`/`FAIL` with explicit blockers, but they must not edit
wavefront bookkeeping or widen their dispatch to hide the mismatch.
Dispatch IDs include a short nonce after the timestamp so same-second fan-out
does not rely on sleeps for uniqueness.
When a dispatch belongs to a wavefront task, include `--wavefront-run-id`,
`--task-id`, and `--ownership-mode`. The child receipt should echo
`wavefront_run_id`, `task_id`, and `ownership_mode` so parent-side verification
can connect the handoff to the wavefront task graph. Barrier tokens stay in the
wavefront task graph and are recorded with `oag_wavefront.py record`.

At parent Stop, `python3 .codex/scripts/oag_main_write_gate.py` checks the
locked IP's git delta. Locked implementation/verification artifacts without a
covering native OAG subagent receipt block stop.

`oag.compile` is a special verification tool side effect. A subagent may run it
only when the assignment says so. It may refresh
`<ip>/ontology/generated/*` as generated tool output; the child must not
manually edit generated ontology files, must not claim ownership of those
outputs, and must report generated side effects separately from owned changed
paths.

## Prompt Shape

```text
Use Codex subagents for this OAG task.

Spawn these agents with fork_context=false:
- agent_type=oag-legacy-ip-analyzer
  message starts:
  TASK: act as the OAG legacy/reference IP analyzer.
  DELIVERABLE: source paths, extracted behavior, inferred requirements, gaps,
  leakage risks, and evidence needs.
  SCOPE: <paths>. Preserve the existing source hierarchy; do not scaffold,
  move, or normalize legacy RTL into a new layout.
  VERIFY: cite exact files/lines or state INCONCLUSIVE.
- agent_type=oag-requirement-contract-agent
  message starts:
  TASK: act as the OAG requirement-contract agent.
  DELIVERABLE: Requirement -> Obligation -> Contract candidates with IDs,
  assumptions, missing facts, and expected evidence.
  SCOPE: <spec paths>.
  VERIFY: every candidate cites source material or is marked TBD.
- agent_type=oag-ip-contract-agent
  message starts:
  TASK: act as the OAG IP contract agent.
  DELIVERABLE: observable evidence contracts, owner routing, and proof artifacts.
  SCOPE: <active IP>.
  VERIFY: every contract names observable, pass condition, evidence path, and owner.

Wait for all agents. Do not claim completion from subagent summaries. The main
agent must validate outputs, update OAG records, run checks, and call OAG decide
before any closure claim.
```

## RTL/TB Split Prompt

```text
Use Codex subagents and wait for all results.

Plan a role-structured RTL/TB wavefront before spawning write-capable children.
Use .codex/oag/wavefront-templates/rtl_module_fanout.yaml for RTL and
.codex/oag/wavefront-templates/tb_common_then_scenario_fanout.yaml for TB
unless the task is trivial enough to record a monolithic-lane rationale.

Spawn RTL lanes only after RTL_PACKET_CONTEXT has reviewed rtl__*.json:
- agent_type=oag-rtl-implementation-agent for RTL_INTERFACE_SHELL only:
  ports, register shell, integration-facing interface declarations.
- agent_type=oag-rtl-implementation-agent for RTL_CONTROL_FSM only:
  sequencing, state transitions, event/commit ordering, backpressure control.
- agent_type=oag-rtl-implementation-agent for RTL_DATAPATH_STATE only:
  data transforms, storage, counters, FIFOs, payload state, and PPA notes.
- agent_type=oag-rtl-implementation-agent for RTL_CLOCK_RESET_DOMAIN only:
  reset behavior, clock/reset domain intent, CDC/RDC adapter hooks.
- agent_type=oag-rtl-lint-static-agent as RTL_INTEGRATION_OWNER only after
  the role lanes hand off; it owns top wiring, filelists, lint manifest, and
  integration review, including optional pyslang syntax lint via
  oag_pyslang_lint.py. Do not let multiple children edit the same top/filelist.
- agent_type=oag-verification-strategy-agent for ontology/verification_plan.yaml
  and strategy evidence only.

Spawn TB lanes only after TB_PACKET_CONTEXT has reviewed tb__*.json,
ontology/verification_plan.yaml, and ontology/tb_methodology.yaml:
- agent_type=oag-tb-implementation-agent for TB_DRIVER_BFM only:
  DUT input driving and transaction/API shape.
- agent_type=oag-tb-implementation-agent for TB_MONITOR only:
  DUT-facing observed-source capture, transaction decoding, and timestamps.
- agent_type=oag-tb-implementation-agent for TB_PREDICTOR_MODEL only:
  independent expected behavior from contracts, never from RTL/DUT output.
- agent_type=oag-tb-implementation-agent for TB_SCOREBOARD_SCHEMA only:
  scoreboard_rows.v1 schema, compare keys, mismatch reporting, row writer.
- agent_type=oag-tb-implementation-agent for TB_COVERAGE_MODEL only:
  coverage refs and coverage JSON, after scoreboard schema is frozen.
- agent_type=oag-tb-implementation-agent for TB_ASSERTION_HOOKS only:
  local assertion/formal hooks named by the verification plan.
- agent_type=oag-tb-implementation-agent for scenario shards only after the
  driver, monitor, predictor, scoreboard, coverage, and assertion barriers are
  present.
- agent_type=oag-sim-execution-agent as TB_RUNNER_OWNER only after scenario
  shards hand off; it owns run scripts, result aggregation, scoreboard event
  files, coverage JSON, and scenario mapping.

The RTL implementation agent must implement assigned behavior/cycle refs, stay
within OAG SV-lite by default, avoid RTL `function`/`task` helper constructs,
identify likely critical paths, high-toggle state/datapath, and area-risk
structures before nontrivial RTL edits, run or assign
`python3 .codex/scripts/oag_ppa_check.py --ip-dir <ip> --json` when applicable,
read `ontology/domain_intent.yaml` when crossings, async inputs, clocks, or resets are in scope, use approved
CDC/RDC patterns only, run or assign `oag_domain_crossing_check.py` when
applicable, and report `rtl_dialect`,
`implemented_contracts`, `behavior_refs_implemented`,
`cycle_rule_refs_implemented`, `ppa_notes`, `domain_crossing_notes`,
`changed_paths`, `checks_run`, and `may_claim_complete=false`.

The verification strategy agent must act as the proof planner, not the TB
writer. It should read locked requirements, obligations, contracts,
behavior_model, cycle_rules, domain_intent, and evidence_plan, then write or
review `ontology/verification_plan.yaml` with verification objectives,
proof_methods, scenarios, coverage_goals, assertion/formal candidates,
fault-model hooks, residual_risks, and open strategy blockers. It must not
implement RTL/TB.

The TB implementation agent must act as a verification methodology implementer,
not the owner of the proof strategy. It should read
`ontology/verification_plan.yaml` and `ontology/tb_methodology.yaml` when
present, classify each target, choose directed/table-driven, transaction-based,
constrained-random, assertion-assisted, formal-candidate, or PSS-style scenario
planning depth as appropriate, and report `tb_methodology_notes` with
methodology_profile, framework, architecture roles, stimulus_strategy,
coverage_strategy, assertion_hooks, formal_candidates, and open blockers. TB
writer must not define the proof strategy it is trying to satisfy. It may test
functional consequences of CDC/RDC rules, such as synchronizer latency or reset
sequencing, but must not claim CDC/RDC, low-power, safety, or AMS closure from
ordinary simulation alone. Failed rows must not count toward closure coverage.

Each subagent must report changed paths, evidence commands, blockers, and ROCEV
links. Write-capable evidence-producing subagents must write a non-empty receipt
under `<ip>/knowledge/subagents/` and end with final line:
`OAG_EVIDENCE_RECORDED: <relative-path>`. JSON receipts must follow
`.codex/schemas/oag_subagent_receipt.schema.json` and include `dispatch_id`,
`dispatch_path`, `changed_paths`, and `generated_side_effects`.

Use `HANDOFF_PASS`, `STATIC_HANDOFF_PASS`, or `RTL_HANDOFF_PASS` for a bounded
worker receipt that passed its assigned handoff. Do not use status language that
implies IP closure, verification closure, release, signoff, or final completion.
No subagent may claim final completion.
```

## Gate Prompt

```text
Use Codex subagents for independent review.

Spawn:
- oag-evidence-validator to check records, hashes, scoreboard rows, coverage
  refs, and stale evidence from disk.
- oag-gate-reviewer to independently approve or reject the final claim after
  validator output is available. Gate review must inspect `oag.check`,
  `oag.inspect`, the validation report, and every current closure artifact. Its
  decision must include `checked_artifacts` and `checked_artifact_hashes`.

Wait for both. The main agent reports APPROVE/REJECT with artifact paths and
does not override a blocker. If any closure artifact is added or changed after a
gate PASS, the gate decision is stale and must be re-run.
```

## Start/Stop Hooks

`hooks.json` registers a `SubagentStart` hook for OAG child threads and a
`SubagentStop` hook for evidence-producing OAG agents, including implementation,
validation, and gate-review agents. These hooks do not execute or spawn
subagents; Codex native orchestration does that. The start hook injects the
child-work contract and records a start event. The stop hook blocks a stopped
evidence-producing child that lacks a valid
`OAG_EVIDENCE_RECORDED: <relative-path>` receipt, dispatch link, schema-valid
JSON payload, and path-scope verification. This mirrors the oh-my-openagent
executor-verifier pattern while keeping final closure in OAG `check`/`decide`.
