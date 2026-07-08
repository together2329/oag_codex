---
name: oag-ip-workflow
description: Use for concrete hardware IP requirements, RTL, testbench, simulation, coverage, signoff, common design-rule review, or evidence work when the user starts with the lowercase `oag` command or references a specific IP workspace/file/evidence artifact. Do not use for meta/manual discussion about OAG, Codex behavior, subagent policy, or workflow design unless the user explicitly asks to run OAG on an IP. Calls OAG before acting, records ROCEV-backed findings with explicit validation status, protects locked truth fields, writes decision receipts, and applies common design rules such as same-cycle priority, event/state commit consistency, verification methodology, CDC/RDC domain safety, PPA-aware RTL, and RTL language subset.
---

# OAG IP Workflow

Use this skill for hardware IP work where feature, requirement, obligation,
contract, evidence, and validation must stay explicit.

## Activation Boundaries

Full OAG mode requires the prompt to start with the lowercase `oag` command
prefix, for example `oag inspect <ip>` or `oag: run lock readiness`.

Without that command prefix, use only a lightweight OAG guard when the prompt
names a concrete IP workspace, file, or artifact whose edit/review could affect
locked truth, RTL, TB, simulation, coverage, evidence, gate review, or closure.
The guard may resolve the owning IP, check lock/write boundaries, and refuse
unsafe writes, but it must not expand into deep interview, lock, wavefront,
dispatch, or closure flow unless the user asks for that operation.

Do not activate this workflow for meta/manual discussion about OAG itself,
Codex rules, hooks, subagent orchestration, trigger behavior, or how the
system should be configured. Answer those as system-design or repository
maintenance questions unless the user explicitly asks to run OAG on an IP.

## Skill Router

Treat this skill as the umbrella workflow. Use the narrower OAG skills when a
task enters one of these lanes:

- `oag-deep-interview`: ambiguous IP/change requests that need Socratic
  requirement interview, topology confirmation, ambiguity scoring,
  one-question-per-round discipline, decision-matrix handoff, and closure
  restatement before lock.
- `oag-deep-semantic-intake`: compressed natural-language intent, source
  claims, hidden implications, ambiguity rows, and first decision candidates.
- `oag-decision-matrix`: lock-blocking product/design choices, profile-seeded
  decisions, recommended/default separation, and unresolved decision audits.
- `oag-lock-preview-frame`: pre-lock human review frames that render the
  draft scope as formal HTML with verbatim source panels, hashes, readiness
  issues, and no paraphrased replacement for authored truth.
- `oag-contract-projection`: requirement atoms, obligations, assume/guarantee
  contracts, behavior/cycle refs, and proof projection.
- `oag-authoring-packet`: post-lock `oag.compile`, role-specific `rtl__*.json`
  and `tb__*.json` packet checks, and native subagent packet handoff.
- `oag-wavefront`: dependency-aware parallel work planning, ownership locks,
  barrier tokens, read-only triage, disjoint write shards, and single
  integration owners.
- `oag-team-mode`: plan-only Team Lead plus Worker recommendations for complex
  or multi-role IP work. It reads Mission/Action and orchestration state but
  must not spawn workers, claim tasks, or create dispatches by itself.
- `oag-ip-versioning`: IP-local functional semantic versioning, golden baseline
  lineage, manifest/tag readiness, and patch/minor/major stewardship.
- `oag-evidence-closure`: scoreboard, coverage, validation, trace graph,
  freshness, gate, and `claim_complete` readiness.

Do not let this umbrella skill hide ownership. Intake and decisions are draft
workflow. Contract projection prepares implementation truth. Authoring packets
feed RTL/TB subagents. Wavefront scheduling opens only safe parallel work
boundaries. Evidence closure audits proof strength and decision freshness.
IP versioning governs whether an approved baseline lineage is safe to consume
or promote; it does not create design truth.

For nontrivial IP work, use `ontology/features.yaml` as the product-visible
scope layer before requirements. Use `ontology/ipxact_projection.yaml` for the
IP-XACT-style integration projection: VLNV, bus interfaces, ports, memory maps,
registers, address spaces, parameters, file sets, views, hierarchy,
configuration, generator chains, and vendor-extension links back to OAG IDs.
IP-XACT-style metadata is not the behavior oracle; OAG contracts and modeling
files remain the behavior/cycle authority.

For nontrivial runs, start from a run-control frame before opening new work:

```bash
python3 .codex/scripts/oag_run_frame.py --ip-dir <ip> --json
```

The run frame is the current-state snapshot for human and agent orchestration:
IP-local git status, scope lock state, active wavefront locks, compile
freshness, stale lifecycle evidence, pending gate frames, SSOT section health,
Mission/Action candidates, four next-action options, and the recommended next
action. Treat terminal scrollback as advisory only; durable JSON frames,
Action instances, receipts, decisions, and artifact hashes are the source of
truth.

The Mission/Action layer is the operation planner. It does not replace
requirements, obligations, contracts, wavefront locks, dispatches, receipts, or
ROCEV records; it makes the next operation explicit and auditable:

```bash
python3 .codex/scripts/oag_action_plan.py --ip-dir <ip> --json
python3 .codex/scripts/oag_mission_runtime.py show --ip-dir <ip> --mission-id active --json
python3 .codex/scripts/oag_mission_runtime.py evaluate --ip-dir <ip> --mission-id active --json
python3 .codex/scripts/oag_role_health.py --ip-dir <ip> --json
python3 .codex/scripts/oag_action_wavefront_draft.py --ip-dir <ip> --json
python3 .codex/scripts/oag_action_wavefront_draft.py --ip-dir <ip> --materialize-run-id <run_id> --json
python3 .codex/scripts/oag_team_plan.py --ip-dir <ip> --json
python3 .codex/scripts/oag_action_record.py start --ip-dir <ip> --candidate-id recommended --selected-reason "<why this action was chosen>" --json
python3 .codex/scripts/oag_action_record.py update --ip-dir <ip> --action-id latest --status accepted --summary "<what happened>" --json
python3 .codex/scripts/oag_operation_review_frame.py --ip-dir <ip> --json
python3 .codex/scripts/oag_mission_loop.py tick --ip-dir <ip> --json
python3 .codex/scripts/oag_mission_loop.py run --ip-dir <ip> --max-ticks 5 --json
```

Use `oag_action_record.py update` to attach dispatch ids, receipt paths,
wavefront task refs, changed paths, evidence paths, blockers, and review
decisions. Use `--git-checkpoint` when the action result should become an
IP-local git checkpoint, and `--auto-link-latest-dispatch` or
`--auto-link-active-wavefront` only when that linkage is intentional and
audited. Generated candidates under `ontology/generated/action_candidates.json`
`ontology/generated/action_graph.json`, and
`ontology/generated/action_wavefront_draft.json` are current-state
recommendations. The wavefront draft is not a claim and not a dispatch; it is a
reviewable task-shaped proposal with dependencies, owner roles, dispatch hints,
and `may_claim_complete=false`. `--materialize-run-id` converts that proposal
into a durable wavefront graph, but still does not claim tasks or create
dispatches. Mission instances under `knowledge/missions/` and Action instances
under `knowledge/actions/` are durable audit history.
Role health under `knowledge/operations/role_health.json` is derived state from
Action instances and active locks; stuck or degraded roles should route through
`ACT_ORCHESTRATION_RECOVERY` before opening more work for the affected role.

For human operation review, use the operation review frame. It renders the
current Mission, recommended action, four options, open items, Action graph,
draft wavefront tasks, role health, mission completion criteria, Action
history, and stuck/open actions without replacing the source JSON:

```bash
python3 .codex/scripts/oag_operation_review_frame.py --ip-dir <ip> --json
```

If a started or running Action instance exceeds the action-plan stuck timeout,
`oag_action_plan.py` emits an `ACT_ORCHESTRATION_RECOVERY` candidate. Resolve or
abort that Action record before opening conflicting dispatches.

When a run has active locks or a child appears stuck, use the orchestration
guard before opening replacement work:

```bash
python3 .codex/scripts/oag_orchestration_guard.py audit --ip-dir <ip> --json
python3 .codex/scripts/oag_orchestration_guard.py fallback-plan --ip-dir <ip> --json
```

Do not create a replacement dispatch while an ownership lock is active. If a
task must be abandoned, explicitly route it with `abort-task` to
`blocked`, `failed`, or `inconclusive`; late receipts from that aborted
dispatch are not valid handoffs. For stale gate-review locks, use
`fallback-plan` to quarantine late receipts and retry the gate as a fresh
`oag-custom-reviewer` dispatch instead of repeatedly spawning the dedicated
gate-reviewer role.

Use the SSOT section checker at planning, pre-dispatch, and closure boundaries:

```bash
python3 .codex/scripts/oag_ssot_section_check.py --ip-dir <ip> --stage planning --json
python3 .codex/scripts/oag_ssot_section_check.py --ip-dir <ip> --stage pre-dispatch --json
python3 .codex/scripts/oag_ssot_section_check.py --ip-dir <ip> --stage closure --json
```

It checks the required feature/source-claim/ambiguity/decision/requirement
atom/requirement/obligation/contract/modeling/verification/TB/IP-XACT-style
sections, and closure evidence/gate decision presence at the appropriate stage.

Use the version checker when an IP baseline or golden version is being promoted
or consumed:

```bash
python3 .codex/scripts/oag_ip_version_check.py --ip-dir <ip> --require-ip-git --json
```

For Windows portability, run:

```bash
python3 .codex/scripts/oag_windows_smoke.py --json
```

This checks that runtime hooks/scripts avoid `/bin/sh`, `sh.exe`, and
`shell=True`, that Windows hooks route through `.codex/bin/oag-python.cmd`
instead of PowerShell parsing, and that Git for Windows discovery remains
available for PowerShell-based IP-local checkpointing.

## Start

### New IP Intake Guard

If the user gives only a short IP request, such as "make packet rx ip",
"make uart", or "create dma ip", do not treat that as permission to decide the
architecture. Enter requirement interview mode.

Allowed first actions for a short IP request:

- read this skill and repo-local OAG guidance;
- check whether the requested IP already exists and keep it separate from other
  IP workspaces;
- create at most a draft scaffold/workspace when the IP is new and an OAG state
  area is needed to store interview notes;
- for an imported or partial legacy IP, do not scaffold over the source tree;
  preserve the existing RTL/document hierarchy and attach OAG state through a
  `.oag` overlay or external analysis workspace;
- run `oag.inspect`, `oag.compile`, and `oag.context` only to understand the
  draft workspace state;
- attempt bounded spec/source discovery;
- write `oag.draft` records with facts, assumptions, open questions, and
  proposed scope.
- capture load-bearing source intent in `req/source_claims.yaml` and unresolved
  questions in `req/ambiguity_register.yaml`; use `req/deep_semantic_intake/`
  for detailed interview notes and layer worksheets.
- derive candidate `ontology/requirement_atoms.yaml` entries for nontrivial
  requirements, keeping unknown trigger, condition, response, boundary,
  phenomena, assumption, timing, and proof-shape fields as draft ambiguity
  instead of architecture decisions.
- create or update `ontology/decision_matrix.yaml` rows for lock-blocking
  product choices, keeping unknown transport, feature scope, buffering,
  filtering, output, storage, interrupt/status, and error/drop policy as
  unresolved or blocked instead of architecture decisions.
- use `oag_deep_semantic_intake.py` for compressed natural-language intent and
  `oag_decision_matrix_generate.py` for profile-seeded decision rows when a
  protocol profile such as `protocol-packet-ip` applies.
- for deep requirement interviews, use `oag-deep-interview`; it owns Round 0 topology,
  document/spec/RTL-backed evidence intake, one-question option-backed rounds,
  clarity scoring, weakest-dimension targeting, decision-matrix handoff,
  evidence-cited brownfield questions, RTL-readiness audit, closure audit, and
  one-sentence scope restatement. For lock-critical rounds, use
  `oag_deep_interview_round.py` to rank candidate questions and validate the
  option set.

Forbidden until the user confirms scope or supplies a concrete spec:

- do not enrich or rewrite `req/locked_truth.md`;
- do not edit canonical requirement, obligation, contract, structure,
  decomposition, policy, waiver, or signoff ontology files beyond scaffold seed
  placeholders;
- do not create or modify RTL, TB, tests, filelists, or signoff evidence;
- do not spawn RTL/TB/sim implementation agents;
- do not choose protocol architecture defaults such as transport binding,
  single-packet versus multi-packet support, buffering depth, filtering policy,
  output interface, or error/drop behavior as locked truth.

For protocol IPs, ask or draft open questions for at least: spec version,
transport boundary, input/output interfaces, supported feature scope, buffering
and backpressure, filtering/addressing, and error/drop/status policy. Store
unconfirmed answers only as draft knowledge.

### Lock Preview Artifacts

Before asking the user to lock scope, show the user what would be locked. For
nontrivial IP work, prepare draft/proposed artifacts for source claims,
ambiguity rows, feature rows, lock-blocking decision rows, requirement atoms,
candidate obligations, candidate assume/guarantee contracts, verification
intent, and IP-XACT-like integration metadata gaps. Verification intent should
name proof objectives, scenarios, scoreboard refs, and coverage goals at the
level needed for RTL/TB authoring packets.

Render the preview as a formal HTML review frame before asking for lock:

```bash
python3 .codex/scripts/oag_lock_preview_frame.py --ip-dir <ip> --json
```

The frame is review UI, not source truth. It must preserve each source artifact
in verbatim panels with file paths and SHA-256 hashes. If the user changes any
answer after reading the frame, update draft/OAG source files and regenerate
the frame before lock.

These artifacts are a lock preview, not implementation permission. Until the
user confirms lock, keep candidate obligations and contracts as draft/proposed
data or under draft lifecycle state, and do not feed them to RTL/TB workers.
After user lock, run the semantic gates, refresh `oag.compile`, and use the
generated authoring packets as implementation inputs.

## Scope Lock

Each IP has one implementation permission switch:
`ontology/scope_lock.json`.

- `draft`: questions, summaries, draft requirements, and options only.
- `locked`: user has confirmed the scope; canonical ontology enrichment, RTL,
  TB, validation, gate review, and closure may proceed.

No lock, no RTL. No lock, no TB. No lock, no closure.

Check status before implementation or closure:

```bash
python3 .codex/scripts/oag_cli.py call --json '{"tool":"oag.lock_status","arguments":{"ip_dir":"<ip>"}}'
```

When the user explicitly says `lock`, `lock this`, `lock scope`, or `lock
requirements`, record the approval:

```bash
python3 .codex/scripts/oag_cli.py call --json '{
  "tool": "oag.lock",
  "arguments": {
    "ip_dir": "<ip>",
    "summary": "Human-confirmed scope summary.",
    "confirmed_scope": ["confirmed requirement or boundary"],
    "actor": {"kind": "human", "id": "user", "surface": "codex"}
  }
}'
```

If the user changes requirements after lock, save the new answer with
`oag.draft`; that returns the IP to draft state. Ask for a fresh lock before
continuing implementation. Use `oag.unlock` only when the user explicitly
withdraws approval.

After lock and before implementation or closure, run the OAG V2 semantic gate:

```bash
python3 .codex/scripts/oag_req_quality_check.py --ip-dir <ip> --json
python3 .codex/scripts/oag_requirement_atom_check.py --ip-dir <ip> --json
python3 .codex/scripts/oag_contract_strength_check.py --ip-dir <ip> --json
python3 .codex/scripts/oag_trace_graph_check.py --ip-dir <ip> --json
python3 .codex/scripts/oag_lock_readiness_check.py --ip-dir <ip> --json
python3 .codex/scripts/oag_verification_plan_check.py --ip-dir <ip> --json
```

Resolve failures before relying on obligations or contracts. These checks block
locked scopes that still have unresolved source ambiguity, weak requirement
shape, unresolved requirement-atom ambiguity, prose-only obligations, or
closure-grade contracts without explicit assume/guarantee. For locked TB work,
`ontology/verification_plan.yaml` must define the proof objectives before the
TB implementation agent satisfies them.
The lock-readiness check also blocks lock-required decision rows that are still
unresolved, proposed, or blocked. Passing it is implementation readiness, not
IP closure.

Before dispatching RTL or TB agents after lock, run:

```bash
python3 .codex/scripts/oag_cli.py call --json '{"tool":"oag.compile","arguments":{"ip_dir":"<ip>"}}'
python3 .codex/scripts/oag_authoring_packet_check.py --ip-dir <ip> --require-packets --json
```

The generated `ontology/generated/authoring_packets/rtl__*.json` and
`tb__*.json` files are the role-specific implementation and proof inputs.
RTL/TB agents should not reinterpret original prose once these packets exist.

File-scoped repair prompts still enter OAG. If the user asks to find, fix,
debug, test, or review a file reference such as `@ip_name/rtl/foo.sv`,
`@ip_name/tb/bar.sv`, or an absolute path under an IP workspace, first resolve
the owning IP root and run the same OAG context/lock/packet gates as if the user
had named the IP explicitly. Do not wait for the prompt to contain the literal
word `oag`. If multiple file references map to different IP roots, stop and
split the work by IP instead of guessing.

When RTL/TB dispatch creation fails only because the generated compile manifest
is missing or stale, refresh it with `oag.compile` and retry the packet gate
once. Treat schema, projection, lifecycle, decomposition, domain, or packet
content failures as real blockers; do not hide them behind repeated compile
loops.

When multiple RTL/TB/sim tasks should run in parallel, use wavefront scheduling
instead of unconstrained fan-out:

```bash
python3 .codex/scripts/oag_wavefront.py plan --ip-dir <ip> --run-id <run> --template .codex/oag/wavefront-templates/rtl_module_fanout.yaml --json
python3 .codex/scripts/oag_wavefront.py plan --ip-dir <ip> --run-id <run> --template .codex/oag/wavefront-templates/tb_common_then_scenario_fanout.yaml --json
python3 .codex/scripts/oag_wavefront.py ready --ip-dir <ip> --run-id <run> --json
python3 .codex/scripts/oag_wavefront.py claim --ip-dir <ip> --run-id <run> --task-id <task> --dispatch-id <dispatch_id> --json
```

Use role-structured RTL/TB wavefronts by default. RTL splits into
RTL_INTERFACE_SHELL, RTL_CONTROL_FSM, RTL_DATAPATH_STATE,
RTL_CLOCK_RESET_DOMAIN, and RTL_INTEGRATION_OWNER. TB splits into
TB_DRIVER_BFM, TB_MONITOR, TB_PREDICTOR_MODEL, TB_SCOREBOARD_SCHEMA,
TB_COVERAGE_MODEL, TB_ASSERTION_HOOKS, scenario shards, and TB_RUNNER_OWNER.
Only use a monolithic RTL/TB child for trivial one-file work or with a recorded
risk rationale.

Read-only triage can fan out aggressively. Write tasks require disjoint
`allowed_write_paths`. Shared artifacts such as filelists, run scripts,
aggregate results, coverage JSON, and closure packages require a single
integration owner. Simulation failures should be classified by read-only
triage before repair agents are opened.
When `ready` returns multiple dependency-ready tasks with non-conflicting
ownership, dispatch the whole ready wave as one native subagent batch. Serial
dispatch needs an explicit dependency, ownership, runtime-budget, or user-scope
blocker.
For write/integration wavefront tasks, create the dispatch before claiming and
pass its `dispatch_id` into the claim. Child receipt verification must happen
while the task is still `claimed`; only then may the parent record
`review_pending`, review it, and later record `handoff_pass`.

After user lock, main agent orchestrates; subagents implement and verify. The
main agent must not directly create or substantially edit RTL, TB, sim, lint,
coverage, formal, SDC, signoff, or implementation filelist artifacts. Those
writes require native OAG subagent dispatch + receipt. If native subagents are
unavailable, stop with BLOCKED unless the user records a human
`main_agent_subagent_waiver` decision receipt.

Keep parent/orchestrator authority separate from subagent implementation
authority. The parent creates or claims the dispatch, owns wavefront routing,
records validation decisions, controls barriers, and defers native child cleanup
until the OAG state transition is recorded. The child receives one
parent-provided dispatch and must stay inside explicit `allowed_write_paths`;
it must not create replacement dispatches, run `oag_decision_harness.py
record`, open barrier tokens, close or release wavefront tasks, call
`close_agent`, or claim final completion. `HANDOFF_PASS` from a worker is only
the assigned deliverable handoff, not IP closure, canonical simulation
evidence, DUT functional PASS, or barrier readiness.

For evidence-schema repair, use a two-surface prompt. Parent surface: audit
locks, create or claim one narrow repair dispatch, spawn exactly the native
implementation child required by the ready work, verify the receipt, record an
`evidence_validation` decision with supported verdict enums, and keep
`tb_uvm_dual_sim_evidence_ready` closed unless real canonical simulator
evidence exists. Child surface: read `scoreboard_rows.v1.yaml`, inspect the
failing rows and writer, repair only the allowed writer/output paths, preserve
`BLOCKED` or `INCONCLUSIVE` rows when no DUT observations exist, regenerate
blocked artifacts, run local checks, and write one receipt. Fix the generator
before hand-editing JSONL where safe. A blocked pre-sim `coverage.json` should
mean not observed/not sampled, not 0% sampled coverage; `results.xml` should
classify missing UVM or simulator setup as an environment blocker, not a DUT
functional failure.

After a child receipt, the parent must verify the exact dispatch/receipt pair
for the current task, not a stale schema-repair receipt from an earlier
dispatch. Treat `--schema-only` as a receipt-shape preflight only; `HANDOFF_PASS`
is safe only after the full dispatch verifier passes against the current
receipt and actual path delta. If full verification fails because the baseline
or external delta changed, route the task as `INCONCLUSIVE` with that blocker
while preserving successful schema, trace, or verification-plan checks. Then
rerun trace graph, verification-plan, `oag.check`, closure, and an
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

For a new IP, scaffold the ontology-first folder layout before creating RTL,
TB, or evidence artifacts:

```bash
python3 .codex/scripts/oag_scaffold_ip.py create <ip> --owner <owner>
```

The scaffold creates `req`, `ontology`, `knowledge`, `rtl`, `tb`, `sim`,
`lint`, `cov`, `formal`, `syn`, `sdc`, `list`, `doc`, and `signoff` with seed
Requirement -> Obligation -> Contract -> Evidence -> Validation files.
It also creates stage contracts, closure policy, protected-field policy, gate
registry, stage receipt schema, decision receipt schema, failure-ticket schema,
an append-only `knowledge/ledger.jsonl`, and a common
`ontology/design_rules.yaml` rulebook. It also creates
`ontology/structure.yaml` for the shared signal/register/interface namespace and
`ontology/decomposition.yaml` for module ownership and structure profile. It
also creates `ontology/modeling.yaml` for micro behavior/cycle oracle truth and
`ontology/domain_intent.yaml` for clock/reset-domain intent. It also creates
`ontology/tb_methodology.yaml` for framework-neutral verification methodology
intent, `req/source_claims.yaml` and `req/ambiguity_register.yaml` for deep
semantic intake, `ontology/features.yaml` for product-visible feature scope,
`ontology/requirement_atoms.yaml` for semantic decomposition before
obligations, and `ontology/decision_matrix.yaml` for decisions that must be
resolved before lock-ready implementation. It also creates
`ontology/ipxact_projection.yaml` for IP-XACT-style component/interface/register
map/file-set/hierarchy projection linked back to OAG feature, requirement,
obligation, and contract IDs. `oag.compile` also generates
role-specific authoring packets under `ontology/generated/authoring_packets/`.
For short IP intake, these scaffold files are placeholders for draft capture;
do not enrich locked truth or canonical ontology from assumptions.
The scaffold initializes an IP-local git repository and OAG-safe `.gitignore`
by default. Record compact IP-local checkpoints after meaningful stage
boundaries:

```bash
python3 .codex/scripts/oag_ip_git.py checkpoint --ip-dir <ip> --message "OAG <stage>: <meaningful summary>" --json
```

Checkpoints should capture scaffold state, interview drafts, decision matrix
updates, requirement atom/obligation/contract projection, scope lock, RTL/TB
handoff, evidence projection, validation/gate refresh, and baseline/version
updates. Do not checkpoint large transient dumps; the managed IP-local
`.gitignore` keeps waveforms, simulator build output, logs, and caches out of
git.

For legacy or partially implemented IP, scaffold is not required and should not
reshape the source tree. Use the existing RTL/doc/filelist hierarchy as
implementation evidence, select the `legacy_preserve` decomposition profile,
and keep OAG facts in a `.oag` overlay or separate analysis workspace. A
reviewer should compare the existing implementation against spec-derived
requirements/contracts and write:

```bash
python3 .codex/scripts/oag_implementation_review_check.py --ip-dir <ip> --legacy-no-scaffold --json
```

The resulting gap matrix ranks missing/partial contracts by priority and feeds
wavefront scheduling. Only when a gap action needs edits should dispatch target
the legacy files or wrapper files explicitly; there is no synthetic `rtl/`
layout requirement for imported IP.

Do not require a specific testbench implementation. Verilog, SystemVerilog,
UVM, Python, cocotb, or a simulator adapter are all valid if they emit the
standard evidence rows in `sim/scoreboard_events.jsonl`.
Do require verification methodology responsibilities when TB evidence is used
for closure: scenario intent, driver/BFM, monitor, independent predictor,
scoreboard, coverage collector when load-bearing, assertion/formal hooks when
useful, and OAG evidence writer. Random or constrained-random tests require
constraints and coverage goals before they can support closure. Failed tests do
not count toward closure coverage.

Before editing or claiming analysis, call OAG for the active IP:

```bash
python3 .codex/scripts/oag_cli.py call --json '{"tool":"oag.inspect","arguments":{"ip_dir":"<ip>","stage":"<stage>","intent":"<task>"}}'
python3 .codex/scripts/oag_cli.py call --json '{"tool":"oag.compile","arguments":{"ip_dir":"<ip>"}}'
python3 .codex/scripts/oag_cli.py call --json '{"tool":"oag.context","arguments":{"ip_dir":"<ip>","stage":"<stage>","intent":"<task>"}}'
```

Use `oag.inspect` for legacy IP folders with no knowledge ledger. Legacy
inspection is read-only: do not create scaffold directories unless the user is
creating a new IP or explicitly asks for an OAG overlay. Use `oag.compile` after
ontology edits. Use `oag.context` for prompt-ready ontology records. When Codex
hooks are enabled, `codex_context_inject.py` can inject this context
automatically on relevant UserPromptSubmit events. `codex_deep_interview_prompt_guard.py`
stays silent for normal work and injects a compact one-question/four-option
reminder only when the current prompt explicitly requests OAG deep interview mode.

For work that should keep moving across edit/test/stop boundaries, start a
durable run loop:

```bash
python3 .codex/scripts/oag_cli.py call --json '{"tool":"oag.run.start","arguments":{"ip_dir":"<ip>","stage":"<stage>","intent":"<task>","actor":{"kind":"ai","id":"codex","surface":"cli"}}}'
python3 .codex/scripts/oag_cli.py call --json '{"tool":"oag.run.next","arguments":{"ip_dir":"<ip>"}}'
python3 .codex/scripts/oag_mission_loop.py tick --ip-dir <ip> --json
python3 .codex/scripts/oag_mission_loop.py run --ip-dir <ip> --max-ticks 5 --json
python3 .codex/scripts/oag_mission_loop.py pause --ip-dir <ip> --reason "<why>" --json
python3 .codex/scripts/oag_mission_loop.py explain --ip-dir <ip> --json
```

`oag.run.start` derives the active obligation from the closure matrix and writes
`ontology/runs/<run_id>/run_state.json`, `next_action.json`, and
`checkpoint_history.jsonl`. `oag.run.next` always returns one action to take
next. `oag_mission_loop.py` is the bounded "keeps working" controller above the
Mission/Action layer: each tick audits orchestration hazards, refreshes Action
candidates, starts at most one Action record in record mode, and stops on human
questions, active locks, blocked candidates, or dispatch-required boundaries.
The run loop is a driver; it does not replace ROCEV records, wavefront locks,
dispatch receipts, or decision receipts.

When a user question is likely but local sources exist, the Mission/Action
layer should prefer `ACT_SELF_EXPLORE_OPTIONS` before asking. Run:

```bash
python3 .codex/scripts/oag_exploration_plan.py --ip-dir <ip> --json
```

This writes `knowledge/mission_loop/exploration_plan.json` with the current
ask-versus-explore decision, source targets, option axes, and a bounded research
prompt. Ask the user only after this local evidence pass leaves one residual
product-defining or lock-critical question.

After `oag.compile`, treat `ontology/generated/design_spec.json`,
`ontology/generated/authoring_packets/*.json`,
`ontology/generated/design_facts_graph.json`, and
`ontology/generated/domain_crossing_matrix.json` as read-only work inputs. The
design spec and authoring packets are compiled projections from authored
ontology. The design facts graph is extracted from current RTL with `pyslang`
when available, falling back to a conservative parser when needed. If a
projection is wrong, edit `ontology/requirements.yaml`,
`ontology/obligations.yaml`, `ontology/contracts.yaml`,
`ontology/structure.yaml`, `ontology/decomposition.yaml`, or
`ontology/policies.yaml`, then compile again. If extracted facts disagree with
decomposition, fix the RTL module names/files or the authored decomposition,
not the generated facts file.

For deep requirement interviews, do not wait for the user to say "save this" to
preserve draft knowledge. After each meaningful user answer or before a long
context transition, call `oag.draft` with the current facts, decisions,
assumptions, and open questions. Drafts are not locked truth; they are captured
under `req/interview_draft.md`, `ontology/drafts/`, and `knowledge/records/`.
Do not batch unrelated interview questions. If the user gives a broad answer,
refine it into decision, rationale, constraints, non-goals, and verified context
before promoting it from chat into durable draft knowledge.

## Subagents

Codex-facing OAG roles are individual `.codex/agents/oag-*.toml` custom agent
files. OAG metadata for those roles lives in `.codex/oag/agent-catalog.toml`.
The stable set is 14 core duties plus 3 custom dynamic duties:

- `oag-custom-researcher`: bounded research shard.
- `oag-custom-worker`: bounded implementation or repair shard.
- `oag-custom-reviewer`: bounded review shard.

Before using these roles, validate the catalog:

```bash
python3 .codex/scripts/oag_agent_catalog_check.py
```

Team prompts should use the lowercase `oag` command prefix when they want OAG
context and subagent workflow guidance. Terms such as `auto research`,
`subagent`, and `signoff`, uppercase OAG acronym mentions, or meta discussion
about OAG describe work but do not activate OAG mode by themselves. The
project config requests native subagents with
`[features].multi_agent = true` and `[features].child_agents_md = true`, while
forcing `[features.multi_agent_v2].enabled = false`. This matches the OMO Codex
runtime pattern: v1 is not directly enabled; v2 is re-disabled so Codex can
resolve to the v1 multi-agent path when native subagents are available. Team
members can run
`python3 .codex/scripts/oag_codex_config_doctor.py --include-omo-plugin-features --apply`
to patch their user Codex config, or let the SessionStart hook apply the same
guard at startup. Restart Codex or open a fresh trusted project session after a
config patch. Do not narrate speculative tool-namespace probes such as
"checking whether multi_agent_v1 is available." Missing `multi_agent_v1`
visibility in one agent surface is not proof that native subagents are
unavailable; Codex CLI/App can surface the same operation as an internal
`spawn_agent` collaboration event. Before reporting a native-subagent blocker,
first attempt a minimal explicit native spawn in the current surface and wait
for the child result. Do not decide availability from the visible callable tool
namespace alone; in Codex CLI/App traces, explicitly request the native
`spawn_agent` collaboration event even when no `multi_agent_v1` tool namespace
is visible. If the actual spawn attempt fails or the active runtime reports
spawning is unavailable, report the observed native-spawn blocker and ask the
user to restart/open a fresh trusted `ip_dev` session. Do not continue by
manually applying the child role unless the user explicitly waives the native
subagent requirement.

OAG subagents do not need UI automation MCPs for RTL/TB/lint/sim/gate work. If
a thread stalls at `Starting MCP servers` and `/mcp` shows optional
`computer-use`, use the lean OAG profile before opening a fresh trusted session:

```bash
python3 .codex/scripts/oag_codex_config_doctor.py \
  --include-omo-plugin-features \
  --lean-subagent-runtime \
  --apply
```

This disables `computer-use@openai-bundled` for the OAG-heavy session profile.
It is not a native-subagent availability test, and MCP startup must not become a
dispatch, receipt, lock, or wavefront progress gate.

Subagents are native Codex collaboration workers, not Python runners. Use
self-contained spawn assignments like this when the v1 tool is directly
exposed:

```text
multi_agent_v1.spawn_agent({
  "message": "TASK: act as the OAG legacy/reference IP analyzer. DELIVERABLE: source paths, extracted behavior, inferred requirements, gaps, leakage risks, and evidence needs. SCOPE: <reference paths>. VERIFY: cite exact files/lines or return INCONCLUSIVE. This is an executable assignment, not a context handoff.",
  "agent_type": "oag-legacy-ip-analyzer",
  "fork_context": false
})
```

In Codex CLI/App traces, the same native operation can appear as a `spawn_agent`
collaboration event, followed by a `wait` event and a child thread id. Treat
that as native. Treat Python/shell worker processes or manual role-play as
non-native and do not use them for "use subagent" requests.

For implementation splits:

```text
multi_agent_v1.spawn_agent({
  "message": "TASK: act as the OAG PPA-aware RTL implementation agent. DELIVERABLE: the smallest RTL change that implements assigned contracts plus rtl_dialect, changed paths, implemented_contracts, behavior_refs_implemented, cycle_rule_refs_implemented, ppa_notes, checks_run, blockers, and ROCEV links. SCOPE: rtl/<module>.sv only. DISPATCH: include dispatch_id, dispatch_path, allowed write paths, allowed tool side effects, and receipt path from oag_dispatch.py create. VERIFY: compile, run `python3 .codex/scripts/oag_ppa_check.py --ip-dir <ip> --json` when RTL files are available, run optional oag_pyslang_lint.py syntax lint when available, or return the exact blocker. Use OAG SV-lite: Verilog-2001 plus logic and static generate by default; function/task helper constructs are forbidden in RTL. Write a non-empty receipt with may_claim_complete=false and end with OAG_EVIDENCE_RECORDED: <relative-path>. Do not claim final completion.",
  "agent_type": "oag-rtl-implementation-agent",
  "fork_context": false
})
```

Use native waiting/mailbox behavior for child results; timeout means no new
update, not failure. Use native child steering for targeted follow-up. Integrate
or route completed/inconclusive lane receipts before new dispatch; defer native
child cleanup outside the critical path.
For long RTL/TB work, keep an active child through at least three native wait
cycles before routing it as no-progress. After the first silent wait, send at
most one targeted status/heartbeat request, then continue waiting; do not mark
`INCONCLUSIVE`/`BLOCKED` while there is fresh `WORKING:`, heartbeat,
owned-path, receipt, or blocker evidence.
For long write-capable RTL/TB children, include an explicit heartbeat contract
in the spawn prompt: `WORKING: <task> - <phase>` within the first wait cycle and
at major phase changes, or an owned draft file, receipt, or `BLOCKED:` reason.
For wavefront-backed children, include the matching machine-readable heartbeat
command:
`python3 .codex/scripts/oag_wavefront.py heartbeat --ip-dir <ip> --run-id <run> --task-id <task> --message "<phase>" --json`.
`oag_orchestration_guard.py audit` uses `heartbeat_at`, fresh receipts, and
claim-newer owned-path mtimes as progress evidence.
Large TB scenario shards are runtime-budget constrained by default; open one or
two scenario children first, then open the next shard after heartbeat or
owned-path evidence proves throughput. If a claimed child has no heartbeat,
owned file, or receipt after a bounded status request, route that dispatch to
`INCONCLUSIVE`/`BLOCKED` before any replacement and treat late receipts as
invalid handoffs.
Treat `agent_type` as a routing hint and paste role requirements into the child
message. See `.codex/oag/subagent-workflows.md` for more prompt shapes. Custom
subagents are execution actors only. They must stay inside the prompted shard,
preserve ROCEV traceability, and produce evidence paths. They cannot claim final
completion, approve protected ontology edits, or replace `oag.check`,
`oag.decide`, evidence validation, or gate review.

For partial implementations, use implementation-review evidence before opening
repair waves:

```bash
python3 .codex/scripts/oag_implementation_review_check.py --ip-dir <ip> --json
```

The report is normally
`knowledge/gap_matrix/implementation_review.json` with
`evidence_kind=implementation_review`. It classifies each contract as
`implemented`, `partial`, `missing`, `unverifiable`, or `not_applicable`, ranks
open gaps by P0/P1/P2/P3, and declares dependencies. Dispatch
`plan.next_wave.actions` first; actions in the same wave may run in parallel
only when dependency blockers are empty and target artifacts are disjoint.

Requirement detail work before lock stays main-owned, but use read-heavy
subagents when they help: spec extraction, reference RTL comparison, ambiguity
lists, or candidate obligation/contract review. Their output is draft evidence
until the user locks scope.

When assigning a write-capable subagent for a successful handoff, create a
dispatch record before native spawn:

```bash
python3 .codex/scripts/oag_dispatch.py create \
  --ip-dir <ip> \
  --agent-type <oag-write-agent> \
  --stage <stage> \
  --allowed-write-path <ip>/<owned-path> \
  --allowed-write-path <ip>/knowledge/subagents/<receipt>.json \
  --allowed-tool-side-effect <ip>/ontology/generated/ \
  --receipt-path <ip>/knowledge/subagents/<receipt>.json \
  --json
```

State the resulting `dispatch_id`, `dispatch_path`, allowed write paths, allowed
tool side effects, and receipt path in the child message. `oag.compile` is
allowed only when assigned; it may refresh `<ip>/ontology/generated/*` as
generated tool output. The child must not manually edit generated ontology
files, must not claim ownership of those outputs, and must report them
separately from owned changed paths. If a native OAG child starts but discovers
before write work that required dispatch, scope lock, authoring packet, runtime,
or tool context is missing, it may write
`schema_version=oag_subagent_diagnostic_receipt.v1` with `BLOCKED`,
`INCONCLUSIVE`, or `FAIL`, a `blocker_class`, non-empty `blockers`, empty
`changed_paths`, empty `generated_side_effects`, empty `evidence_outputs`,
`diagnostic_only=true`, `covers_writes=false`, `dispatch_verified=false`,
`implementation_evidence=false`, and `may_claim_complete=false`; diagnostic
receipts must not include `dispatch_id`, `dispatch_path`, or `receipt_path`.
They preserve the blocker but do not cover implementation writes. After child
completion, verify dispatch-backed handoffs before integration:

```bash
python3 .codex/scripts/oag_dispatch.py verify \
  --dispatch <ip>/knowledge/dispatches/<dispatch>.json \
  --receipt <ip>/knowledge/subagents/<receipt>.json \
  --json
```

The verifier compares the child receipt and actual
`git status --short -uall -- <ip>` delta against the dispatch baseline. Reject or explain any path outside
the child scope.
Dispatch records are immutable after creation. Do not edit
`allowed_write_paths`, `allowed_tool_side_effects`, baseline fields, receipt
path, wavefront fields, or ownership mode to make a failed verifier pass. If
the scope or baseline was wrong, mark the worker receipt
`INCONCLUSIVE`/`BLOCKED`, route cleanup or reconciliation separately, and create
a new dispatch from the clean baseline. Nested same-name generated artifacts
such as `<ip>/<ip>/ontology/generated` are cwd contamination, not valid tool
side effects; clean or rebaseline them through a separate route.
Use schema preflight before full path verification when repairing receipt
shape:

```bash
python3 .codex/scripts/oag_dispatch.py verify \
  --dispatch <ip>/knowledge/dispatches/<dispatch>.json \
  --receipt <ip>/knowledge/subagents/<receipt>.json \
  --schema-only \
  --json
```

Subagent receipts should use `HANDOFF_PASS`, `STATIC_HANDOFF_PASS`, or
`RTL_HANDOFF_PASS` for a bounded worker result. Do not use `PASS`, `COMPLETE`,
`DONE`, `SIGNOFF`, `RELEASED`, or `CLOSED` to describe the IP.

When hooks are enabled, `SubagentStart` injects the child-work contract and
records that an OAG child started. It must not spawn subagents or replace native
Codex orchestration. `SubagentStop` verifies write-capable child receipts.
`Stop` runs `oag_main_write_gate.py` so locked implementation or verification
artifact changes without a covering native subagent receipt block parent stop.

When checking instruction files, avoid unbounded parent-directory scans such as
`find .. -name AGENTS.md`. Use repo-local bounded search such as
`rg --files -g 'AGENTS.md' -g '!**/.git/**'` or explicit expected paths.

## During Work

When a meaningful stage boundary is reached, append one record:

```bash
python3 .codex/scripts/oag_cli.py call --json '{
  "tool": "oag.record",
  "arguments": {
    "ip_dir": "<ip>",
    "stage": "sim",
    "type": "finding",
    "claim": "scoreboard reset rows closed",
    "summary": "Observed reset rows matched expected state.",
    "actor": {"kind": "ai", "id": "codex", "surface": "cli"},
    "rocev": {
      "requirement": {"id": "REQ_RESET", "source": "req/locked_truth.md"},
      "obligation": {"id": "OBL_RESET_STATE", "text": "reset state is observable and stable"},
      "contract": {"id": "CONTRACT_SIM_SCOREBOARD", "method": "scoreboard", "pass_condition": "mismatch count is zero"},
      "evidence": {"files": ["sim/results.xml", "sim/scoreboard_events.jsonl"], "tests": [], "commit": ""},
      "validation": {"status": "closed", "verdict": "pass", "rationale": "simulation and scoreboard evidence are clean"}
    }
  }
}'
```

When an OAG run is active, use `oag.run.record` to record evidence against the
current run target and refresh the next action:

```bash
python3 .codex/scripts/oag_cli.py call --json '{"tool":"oag.run.record","arguments":{"ip_dir":"<ip>","run_id":"<run_id>","summary":"evidence inspected and validation recorded"}}'
```

Closed records require `rocev.validation.status` to be explicit. Evidence files
are SHA-256 fingerprinted by `oag.record`; if an evidence file changes later,
`oag.check` treats the record as stale until a fresh validation is recorded.

For interview draft capture:

```bash
python3 .codex/scripts/oag_cli.py call --json '{
  "tool": "oag.draft",
  "arguments": {
    "ip_dir": "<ip>",
    "stage": "req",
    "title": "requirement interview round",
    "summary": "What was learned in this round.",
    "facts": ["confirmed fact"],
    "decisions": ["explicitly chosen default"],
    "assumptions": ["temporary assumption"],
    "open_questions": ["remaining question"]
  }
}'
```

`oag.record`, `oag.draft`, and `oag.ticket` append hash-chained events to
`knowledge/ledger.jsonl`. Do not hand-edit this ledger. If `oag.check` reports
ledger tampering, protected field changes, or a monotonic closure violation,
stop and report the blocker.

When a stage produces evidence that may be used for signoff, write a
`stage_run_receipt.v1` JSON file under `ontology/evidence/stage_runs/` with
input/output SHA-256 fingerprints.

When designing RTL structure, choose the decomposition profile instead of
hard-coding "all one file" or "always split":

- `small_leaf_single_file`: tiny leaf IPs may keep one editable module with a
  rationale.
- `greenfield_modular`: new nontrivial IPs should split behavior into modules
  with explicit obligation/contract ownership and interface boundaries. Each
  current-IP module should map to a unique RTL file by default; shared files
  require explicit `shared_file_rationale`.
- `legacy_preserve`: imported legacy IPs keep existing hierarchy while OAG maps
  requirements, contracts, gap actions, and evidence onto that hierarchy; no
  scaffolded `rtl/` layout is required.
- `wrapper_adapter`: a legacy/child core remains protected while wrapper or
  adapter modules own new integration obligations.

Every obligation and contract should have an owning module in
`ontology/decomposition.yaml`. Module authoring should begin from the generated
packet for that module when it exists.
`ontology/generated/design_facts_graph.json` is the current implementation fact
view: modules, ports, parameters, registers, memories, instances, source file
hashes, extractor backend, and git HEAD when available. Use it to review large
IP hierarchy/connectivity without treating it as locked truth.

Do not change protected truth or policy fields silently. Protected paths are
declared in `ontology/protection.yaml` and include locked requirements,
obligations, contracts, structure/decomposition policy, and closure policy.
Semantic edits require a human-approved decision record.

When work exposes a common semantic hazard, activate a design-rule instance in
`ontology/design_rules.yaml` instead of leaving it as chat prose. Use this for
same-cycle priority conflicts, event/state commit consistency, and
contract-to-proof coverage. For packet/message designs with multiple active
contexts, use `interleaved_context_coverage` when packet-level interleaving must
be proven, for example `A.SOM -> B.SOM -> A.EOM -> B.EOM`. Keep the RTL
language subset rule active as the coding-policy baseline. Active instances must
point back to the relevant requirement, obligation, contract, and evidence as
the IP matures.

When a coverage point becomes load-bearing evidence, add a
`fault_model_coverage` instance instead of relying on hit count alone. The
instance should connect `coverage_refs` to requirement-relevant `fault_models`
and killed `mutation_results` with an evidence file such as
`mutation/relevant_tc/relevant_mutation_summary.json`. If mutation is not
applicable, set `mutation_not_required: true` and include a rationale.

For signoff-grade testbench architecture, add a
`verification_role_decomposition` instance. This imports UVM concepts without
requiring UVM syntax or SystemVerilog classes: `sequence` owns stimulus intent,
`driver` owns DUT input protocol driving, `monitor` owns DUT-facing observation,
`reference_model` owns expected prediction, `scoreboard` owns compare,
`coverage` owns coverage refs, `env` owns wiring/config/run control, and `test`
owns scenario/seed selection. Closed instances must keep expected_source,
observed_source, and compare_source as separate roles.

For general TB work, use `ontology/tb_methodology.yaml` and the documents under
`.codex/oag/verification-methodology-principles.md`,
`.codex/oag/verification-strategy-policy.md`,
`.codex/oag/tb-methodology-policy.md`,
`.codex/oag/tb-architecture-patterns.md`,
`.codex/oag/coverage-closure-policy.md`, and
`.codex/oag/assertion-formal-policy.md`. Verification strategy belongs in
`ontology/verification_plan.yaml` and should be authored or reviewed by
`oag-verification-strategy-agent` after lock. The TB implementation agent should
consume that plan and choose the smallest sufficient methodology:
directed/table-driven micro-TB for simple IPs, transaction/random/coverage/
assertion-assisted TB for moderate IPs, and reusable agents/reference
models/coverage-driven closure/formal candidates for complex IPs. Framework
presence alone is not evidence.

For signoff-grade domain claims, activate the SSOT-aligned rule kind instead of
leaving the claim as review prose:

- `cdc_crossing_coverage`: clock/reset-domain crossings from
  `clock_reset_domains`, `cdc_requirements`, or `rdc_requirements`.
- `protocol_compliance`: AXI/APB/streaming/valid-ready protocol assertions,
  monitors, VIP, or protocol scoreboard evidence.
- `timing_closure`: target frequency or target clocks, SDC constraints derived
  from those clocks and CDC policy, plus STA/sta-post setup and hold evidence.
- `functional_coverage_closure`: coverage goals versus observed coverage refs
  from `coverage_functional`, `coverage_ssot`, scoreboard rows, or coverage JSON.
- `reset_xprop_coverage`: reset sequencing, async assert/sync deassert, reset
  domain behavior, and X-prop robustness.

Closed instances must link requirement, obligation, contract, and evidence
files. Coverage-bearing instances must cite `coverage_refs` that appear in
scoreboard rows or coverage JSON. For timing, use target clocks or
`target_frequency_mhz` to derive `create_clock`; use CDC/RDC facts to derive
async clock groups or CDC exceptions; default input/output delay is 50% of clock
period unless the IP overrides it. DFT and power are not OAG v1 default gates.

CDC/RDC is a domain-safety contract. Use `ontology/domain_intent.yaml` to record
clock domains, reset domains, async inputs, crossing taxonomy, reset
deassertion policy, and approved mitigation. Development checks may use
`.codex/scripts/oag_domain_crossing_check.py` plus RTL structure notes and
functional scenarios. Release-grade CDC/RDC closure requires static, formal,
tool-grade, or explicitly approved equivalent evidence. Passing simulation alone
does not close CDC/RDC.

When a failure needs routed repair, create one failure ticket:

```bash
python3 .codex/scripts/oag_cli.py call --json '{
  "tool": "oag.ticket",
  "arguments": {
    "ip_dir": "<ip>",
    "stage": "sim",
    "reason": "scoreboard mismatch",
    "failing_contract": {"id": "CONTRACT_SIM_SCOREBOARD"},
    "expected": {},
    "observed": {},
    "evidence": {"files": ["sim/scoreboard_events.jsonl"]},
    "editable_files": ["rtl/<ip>.sv"],
    "required_evidence_after_patch": ["sim/results.xml", "sim/scoreboard_events.jsonl"]
  }
}'
```

## Visualize

When the user asks to understand the ontology, dependency shape, evidence
coverage, or gaps, generate a graph viewer:

```bash
python3 .codex/scripts/oag_graph.py build \
  --ip-dir <ip> \
  --stage <stage> \
  --intent "<task>" \
  --json-out <ip>/ontology/generated/oag_graph.json \
  --html-out <ip>/ontology/generated/oag_graph.html
```

Open the generated HTML directly in a browser. It is self-contained and supports
search, type/status filters, node lists, and node detail inspection.

## Finish

Before claiming completion:

```bash
python3 .codex/scripts/oag_cli.py call --json '{"tool":"oag.compile","arguments":{"ip_dir":"<ip>"}}'
python3 .codex/scripts/oag_cli.py call --json '{"tool":"oag.check","arguments":{"ip_dir":"<ip>"}}'
python3 .codex/scripts/oag_closure_check.py --ip-dir <ip>
python3 .codex/scripts/oag_cli.py call --json '{"tool":"oag.decide","arguments":{"ip_dir":"<ip>","action":"claim_complete","stage":"<stage>","intent":"<task>","record_decision":true,"approval":{"approved":true,"reason":"Human or owner-approved completion reason."},"actor":{"kind":"ai","id":"codex","surface":"cli"}}}'
```

For an active run, prefer:

```bash
python3 .codex/scripts/oag_cli.py call --json '{"tool":"oag.run.checkpoint","arguments":{"ip_dir":"<ip>","run_id":"<run_id>","stage":"<stage>","intent":"<task>","approval":{"approved":true,"reason":"Human or owner-approved run completion reason."},"actor":{"kind":"ai","id":"codex","surface":"cli"}}}'
```

If a stop hook is available, call `oag.stop_check`. If it returns
`should_continue: true`, continue with the returned prompt block instead of
claiming completion. The prompt block is dynamic: it includes the current loop
policy, ready/blocked wavefront tasks, dispatch candidates, active locks, and
open closure edges. Each open obligation-to-contract edge should name owner,
required evidence, approval policy, and criteria so the next action is not
inferred from prose alone. If checkpoint repeats the same blocker three times,
the run status becomes `needs_human`.

If `oag.decide` returns `allowed: false`, report the blocker instead of saying
the IP is complete. If it returns `allowed: true`, the decision receipt under
`ontology/validations/` is the durable completion decision. Completion actions
are blocked unless `record_decision` is true and the completion request carries
an explicit approval reason through `approval.reason`, `approval_reason`, or a
human actor with a non-empty reason. Do not close from tests, summaries, or
inferred intent alone.

`oag_closure_check.py` is the release-grade package gate: it requires a passing
`oag.check`, no `oag.inspect` artifact gaps, a passing
`oag_validation_report.v1` from `oag-evidence-validator`, a PASS
`oag_gate_decision.v1` from `oag-gate-reviewer`, checked artifact hashes for
current closure artifacts, and no custom subagent final closure claim. If RTL,
lint, simulation, scoreboard, coverage, validation, or generated evidence
changes after gate PASS, the gate decision is stale and must be re-run.
Canonical run summaries that are overwritten by reruns, such as
`sim/uvm_status.json`, must also be preserved under an immutable run directory
such as `sim/runs/<timestamp>_<scenario>/uvm_status.json` before they support
closure or repair receipts.

For `action=signoff`, OAG requires `ontology/policies.yaml` to use
`closure_profile: signoff`, a compiled truth graph, a closed closure matrix,
fresh evidence hashes, fresh stage receipts, clean protected fields, a valid
append-only ledger, monotonic closure, an independent `oag.review` reviewer
receipt, and a decision receipt. The policy transition itself is protected;
record a human decision when moving into signoff.
Do not model single-worker vs orchestrator as separate ontology modes; record the
actual runner in actor/execution metadata.
Over time, keep OAG-managed implementation and evidence git-backed: RTL, TB,
filelists, SDC, docs, generated facts, and signoff artifacts should be tied to
commit IDs or SHA-256 fingerprints in records and stage receipts.

If the runtime exposes context usage or compaction pressure and it is high
(about 70% or more), save an `oag.draft` before continuing an interview. Do not
rely on context compaction to preserve requirement decisions.
When Codex hooks are enabled, `codex_draft_pressure.py` injects this reminder but
does not invent facts; the agent must summarize confirmed facts into `oag.draft`.

## Rule

Do not collapse ROCEV into "tests passed." A compile pass, lint pass,
simulation pass, scoreboard evidence, coverage, waveform, formal proof, and
signoff close different obligations.

For scoreboard evidence, standardize the row semantics, not the TB language.
Use `scoreboard_rows.v1`: `goal_id`, `scenario_id`, `cycle`, `stimulus`,
`expected`, `observed`, `observed_source`, `passed`, `mismatch`, and
`coverage_refs`. `observed_source.kind` must name a DUT observation source such
as `dut_signal`, `monitor`, `waveform`, `transaction`, or `assertion`; it must
not be an FL/CL/model source.

For coverage evidence, standardize the closure rule, not the tool. Coverage
refs used for closure must resolve to contract-linked goals or evidence, and
coverage from failed tests or failed scoreboard rows must not contribute to
closure. Random stimulus without constraints and coverage goals is exploration,
not closure evidence.

For RTL semantics, use the common design rulebook instead of IP-specific prose.
OAG expects rules for event/state commit consistency, same-cycle priority
declaration, scoreboard evidence schema, contract-to-proof coverage,
module/file ownership boundary, the RTL language subset, and optional
signoff-grade CDC/protocol/timing/functional-coverage/reset-X-prop domain
closures. Timing closure requires target frequency/clocks before SDC/STA can be
claimed. Generated RTL is implementation, not truth: RTL agents may choose
internal structure, but must not invent behavior, timing, reset values, address
maps, priorities, or protocol semantics. PPA is architectural intent expressed
in RTL structure; it must preserve locked behavior while considering critical
paths, unnecessary switching, mux/register/memory growth, and synthesis-friendly
structure. The default RTL subset is OAG SV-lite: Verilog-2001 baseline plus
`logic` and static `generate`/`genvar`/`generate for`; `always_ff`,
`always_comb`, `always_latch`, `function`, `task`, and procedural `for`,
`while`, `repeat`, or `forever` loops outside generate blocks are forbidden by
default. Use
`.codex/scripts/oag_ppa_check.py` for lightweight generated-RTL PPA/dialect
screening when RTL files are available. Use
`.codex/scripts/oag_domain_crossing_check.py` for lightweight development
screening of domain intent and obvious unsafe crossings. OAG extracts
lightweight RTL facts through `design_facts_graph.json` and domain-crossing
intent through `domain_crossing_matrix.json`; these do not replace lint,
elaboration, static CDC/RDC, formal, protocol VIP, synthesis, or signoff tools.
It checks that declared hazards, crossings, and language policies are tied to
ROCEV objects and that
formal/assertion contracts name proof evidence.

For closure semantics, OAG expects seven platform gates:

- Protected fields: locked truth and signoff policy changes require a
  human-approved decision record.
- Append-only evidence ledger: event records are hash chained in
  `knowledge/ledger.jsonl`.
- Monotonic closure: once an object is closed or passed, an AI record cannot
  silently weaken it back to draft/open/stale; use a decision or a refuted
  record instead.
- Explicit validation: evidence never auto-closes a record; closed records must
  set `rocev.validation.status`.
- Closure matrix: every obligation must map to a contract and a closed
  validation record.
- Evidence freshness: closed records store SHA-256 hashes for evidence files.
- Independent reviewer: signoff/promote requires a passing `oag.review` receipt
  from a different actor when the profile is signoff.
- Decision receipt: completion decisions are written to `ontology/validations/`
  and hash-chained into the ledger.

For the tool schema and object vocabulary, read
`references/oag-tool-call-contract.md`.
