# .codex OAG Pack

This file governs maintenance of the OAG pack under `.codex/`. The repository
root intentionally does not carry `AGENTS.md`; runtime OAG behavior is activated
by the exact `oag` keyword through `.codex/oag/oag-mode-directive.md` and the
UserPromptSubmit hook.

Primary assets:

- `oag/oag-mode-directive.md`
- `skills/oag-ip-workflow/SKILL.md`
- `rules/oag-rocev.rules.md`
- `agents/oag-*.toml`
- `oag/agent-catalog.toml`
- `oag/ip-dev-agent.md`
- `oag/subagent-workflows.md`
- `hooks/oag_pre_work.py`
- `hooks/oag_interview_draft.py`
- `hooks/oag_stop_check.py`
- `hooks/oag_hook_utils.py`
- `hooks/codex_context_inject.py`
- `hooks/codex_draft_pressure.py`
- `hooks/codex_native_subagent_guard.py`
- `hooks/codex_stop_gate.py`
- `hooks/codex_subagent_oag_start.py`
- `hooks/codex_subagent_oag_gate.py`
- `hooks.json`
- `scripts/oag_cli.py`
- `scripts/oag_mcp_server.py`
- `scripts/oag_scaffold_ip.py`
- `scripts/oag_graph.py`
- `scripts/oag_portable_db.py`
- `scripts/oag_okf.py`
- `scripts/oag_eval.py`
- `scripts/oag_agent_catalog_check.py`
- `scripts/oag_codex_config_doctor.py`
- `scripts/oag_closure_check.py`
- `scripts/oag_dispatch.py`
- `scripts/oag_validate_json.py`
- `scripts/oag_pack_release_check.py`
- `schemas/*.schema.json`
- `mcp.json`
- `config.toml`

Use OAG as the common interface for Requirement -> Obligation -> Contract ->
Evidence -> Validation IP work.

Use `.codex/agents/*.toml` as Codex custom agent definitions. Each TOML file
must be a standalone Codex agent file with `name`, `description`, and
`developer_instructions`. OAG metadata for those agents lives outside that
loader path in `.codex/oag/agent-catalog.toml`.

The OAG role catalog defines 13 core duties plus 3 custom dynamic duties. The
role TOMLs are prompts and guardrails; durable state is still the IP ontology,
ledger, records, receipts, and evidence artifacts.

Critical OAG reasoning lanes must use `model_reasoning_effort = "xhigh"`:
requirement/contract, legacy/reference analysis, IP contract derivation, RTL
implementation, TB implementation, evidence validation, and gate review.
Procedural lanes such as lint/static checks, sim execution, coverage, and custom
worker shards may stay lower for throughput.

Before using a subagent role, run:

```bash
python3 .codex/scripts/oag_agent_catalog_check.py
```

Project config must keep `[features].multi_agent = true`,
`[features].child_agents_md = true`, `[features].hooks = true`, and
`[agents].max_depth = 1`. It must also keep
`[features.multi_agent_v2].enabled = false` with the v2 tuning table. This
follows the OMO Codex runtime pattern: v1 is not directly forced; v2 is
force-disabled so Codex falls back to the v1 multi-agent path when native
subagents are available. Use
`python3 .codex/scripts/oag_codex_config_doctor.py --include-omo-plugin-features --apply` to
patch a team member's user config, then restart Codex or open a fresh trusted
project session. Do not treat missing tool-namespace visibility in one agent
surface as proof that native subagents are unavailable; Codex CLI/App may
surface the native collaboration path as an internal `spawn_agent` event. If a
real native spawn cannot be started after an explicit subagent request, report
`BLOCKED: native Codex subagent unavailable in this surface` and stop or ask the
user to restart/open a fresh trusted `ip_dev` session. Do not replace the child
agent with Python, shell scripts, or manual role-play unless the user explicitly
waives the native-subagent requirement.

Use the exact `oag` keyword for OAG mode in team workflows. Hooks should not
inject OAG mode merely because a prompt mentions generic RTL, testing,
subagent, auto-research, or signoff terms unless an IP directory is explicit.

Codex subagents are native Codex collaboration workers, not Python-triggered
workers. Ask Codex to spawn named custom agents from `.codex/agents/*.toml`
using the native subagent facility (`multi_agent_v1.spawn_agent` where exposed,
or the equivalent Codex CLI/App `spawn_agent` collaboration event), give each
one a bounded self-contained `TASK/DELIVERABLE/SCOPE/VERIFY` message, wait for
summaries, and then let the main agent validate and record ROCEV evidence.
`agent_type` is a routing hint, so role requirements must also be pasted into
the message. Prompt patterns live in
`.codex/oag/subagent-workflows.md`. Evidence-producing OAG subagents are checked
by the `SubagentStop` hook only when they are write-capable, and must end with
`OAG_EVIDENCE_RECORDED: <relative-path>`. Subagents may never claim final
completion; final closure requires OAG check/decide and the gate reviewer role.
The `SubagentStart` hook injects the OAG child-work contract and records a
start event; it must not spawn subagents or replace native Codex orchestration.
Before spawning a write-capable child, create a dispatch record with
`python3 .codex/scripts/oag_dispatch.py create`. Put the resulting
`dispatch_id`, `dispatch_path`, allowed write paths, allowed tool side effects,
and receipt path in the spawn prompt. The child receipt must include those
dispatch fields plus `changed_paths` and `generated_side_effects`. The
`SubagentStop` hook calls `python3 .codex/scripts/oag_dispatch.py verify` and
blocks receipts that fail schema validation, dispatch matching, or path scope
checks. Use `python3 .codex/scripts/oag_validate_json.py` for direct schema
validation when debugging records.
For release-grade closure packages, `.codex/scripts/oag_closure_check.py` must pass
with both an `oag_validation_report.v1` from `oag-evidence-validator` and an
`oag_gate_decision.v1` PASS from `oag-gate-reviewer`.

Before releasing this pack to a team, run:

```bash
python3 .codex/scripts/oag_codex_config_doctor.py --include-omo-plugin-features
python3 .codex/scripts/oag_pack_release_check.py
python3 .codex/scripts/smoke_test.py
python3 .codex/scripts/oag_eval.py --json
```

Use the OAG run loop when a task should continue across edits, tests, stops, or
agent surfaces. `oag.run.start` writes `ontology/runs/<run_id>/run_state.json`,
`oag.run.next` returns exactly one next action, `oag.run.record` records
ROCEV-backed evidence, `oag.run.checkpoint` performs verified completion, and
`oag.stop_check` can re-inject the next action while the run is incomplete.
Use `oag.metrics` after meaningful improvement boundaries to persist numeric
progress snapshots under `ontology/metrics/`. The counts are derived from each
IP's own ontology and evidence graph; do not treat progress as a fixed list of
slots shared by every IP.
Use `oag.handoff` when progress needs to be explained or continued by another
agent/user. It writes `handoff/readiness_handoff.json` and history entries that
derive `development_ready`, `signoff_ready`, blockers, and ranked next actions
from current OAG metrics plus auto-research reports; development closure must
not be presented as signoff readiness.
The Codex Stop hook in `hooks/codex_stop_gate.py` adapts this to the Codex hook
contract: incomplete active runs print `{"decision":"block","reason":"..."}` and
complete/no-run cases stay silent.
The Codex context hook in `hooks/codex_context_inject.py` adapts
`oag.context` to `UserPromptSubmit`: identical context is deduped by content
hash under `.codex/.cache/`. The PostCompact hook stays silent for Codex's
stateless output contract and records a recovery marker that the next
UserPromptSubmit consumes to force one context re-injection.
Run `python3 .codex/scripts/oag_eval.py` for scenario-level evaluation of the
run-loop, context injection dedup/recovery, draft pressure, reviewer
independence, fault-model coverage, verification role decomposition, and hook
behavior. Local aliases are available as `make eval`, `make smoke`, and
`make test`.

Do not fix the testbench implementation style. Verilog, SystemVerilog, UVM,
Python, cocotb, or simulator adapters are valid when they produce
`scoreboard_rows.v1` evidence with DUT-facing `observed_source`.

Use `oag.compile` after ontology edits. The compiled
`ontology/generated/design_truth_graph.json` is derived; do not hand-edit it.
Use `closure_profile` for strictness (`draft`, `development`, `signoff`), and
record execution style as actor/execution metadata rather than separate ontology
modes.

Use `oag.draft` during deep requirement interviews. Save draft facts,
decisions, assumptions, and open questions after meaningful user answers and
before context pressure/compaction risk. Drafts are durable interview memory, not
locked truth.

Keep protected-field policy and ledger artifacts active. `ontology/protection.yaml`
declares locked truth and policy fields that require human-approved decisions
for semantic edits. `knowledge/ledger.jsonl` is append-only and hash chained;
never hand-edit it.

Keep reusable RTL semantic checks in `ontology/design_rules.yaml`. OAG expects
common rules for same-cycle priority, event/state commit consistency,
scoreboard evidence schema, contract-to-proof coverage, module file boundary,
and RTL language subset. It also supports signoff-grade fault-model coverage for
load-bearing coverage claims. The default subset allows `logic` and Verilog
`generate`, while procedural `for`/`while` loops outside generate blocks are
forbidden. Active instances must link to ROCEV objects and proof evidence as
they mature.
When a coverage point is load-bearing evidence, connect `coverage_refs` to
requirement-relevant `fault_models` and killed `mutation_results`; use
`mutation_not_required` only with a rationale.
For signoff-grade TB structure, use `verification_role_decomposition` to model
UVM-style roles independent of framework choice: sequence, driver, monitor,
reference_model, scoreboard, coverage, env, and test.
For signoff-grade domain closure, use SSOT-aligned rule instances:
`cdc_crossing_coverage`, `protocol_compliance`, `timing_closure`,
`functional_coverage_closure`, and `reset_xprop_coverage`. These mirror the
portable SSOT concepts for clock/reset domains, CDC/RDC requirements, interface
protocols, timing/STA expectations, coverage goals, and reset/X-prop robustness.
Closed instances must carry ROCEV links and real evidence files;
coverage-related instances must cite coverage refs observed in scoreboard or
coverage JSON. Timing instances must declare target frequency or target clocks,
and their SDC should be derived from target clocks plus CDC async clock
groups/exceptions; default input/output delay is 50% of clock period unless
explicitly overridden. DFT and power are intentionally not seeded as OAG v1
gates.

Keep structure and implementation shape in ontology, not in prose. The authored
source files are `ontology/structure.yaml` and `ontology/decomposition.yaml`;
`oag.compile` generates `ontology/generated/design_spec.json` and
`ontology/generated/authoring_packets/*.json` as read-only projections for
workers. `oag.compile` also generates
`ontology/generated/design_facts_graph.json` from current RTL using `pyslang`
when available, with a conservative parser fallback. Treat it as extracted
implementation fact/provenance, not authored truth: mismatches tell you to fix
RTL or `ontology/decomposition.yaml`, never to hand-edit generated facts. Use
the decomposition `profile.mode` to preserve flexibility:
`small_leaf_single_file`, `greenfield_modular`, `legacy_preserve`, or
`wrapper_adapter`. Do not force legacy IPs into new hierarchy, and do not let
greenfield nontrivial IPs hide all behavior in one unowned top module. For
`greenfield_modular`, each current-IP module should map to a unique RTL file by
default; shared files require explicit `shared_file_rationale`.

For routed failures, write `failure_ticket.v1` through `oag.ticket`. For
signoff-grade evidence, write fresh `stage_run_receipt.v1` files under
`ontology/evidence/stage_runs/`.

Before closure, `oag.check` must report explicit validation status for closed
records, a closed obligation-to-contract-to-validation matrix, fresh evidence
file hashes, clean protected fields, a valid append-only ledger, and monotonic
closure. Do not weaken a closed/passed object back to draft/open/stale without
an approved decision; use a `refuted` record for newly discovered defects.
Completion decisions must be written as `oag_decision_receipt.v1` files under
`ontology/validations/`; completion actions are blocked unless
`record_decision` is true.
For signoff/promote, a reviewer receipt must be passing and independent; an
`allowed` receipt with `independent: false` is not sufficient.
Use git as the durable version baseline for OAG-managed implementation and
evidence over time: records, stage receipts, and facts graph provenance should
carry commit IDs or file hashes for RTL, TB, filelists, SDC, docs, generated
facts, and signoff artifacts.
Use `.codex/scripts/oag_portable_db.py` to move durable OAG DB state between agent
surfaces or workspaces. The portable DB archive is platform-neutral: it carries
IP `req/`, `ontology/`, `knowledge/`, compact evidence artifacts, optional
source directories, optional common rules/adapters, a manifest, file SHA-256
fingerprints, and git provenance. Treat import/export as a bridge between
Codex, Cursor, CI, and future OAG UIs; do not copy chat transcripts as the
source of continuity.
Use `.codex/scripts/oag_okf.py` for Open Knowledge Format views. OKF exports are
generated markdown/frontmatter concepts for sharing, review, search, and other
agents. They are not locked truth and do not replace OAG checks. OKF imports
must enter as draft knowledge first, then be promoted through human-approved OAG
gates if they should affect requirements or signoff. OKF import must preserve
existing authored OAG concepts and Locked Truth: it may append draft knowledge,
but it must not rewrite canonical requirement or ontology source files.
Use `python3 .codex/scripts/oag_okf.py export --profile obsidian` or `make okf-export-obsidian`
for Obsidian vault output. The Obsidian profile is still a generated view; it
adds wiki links, aliases, graph-friendly frontmatter, and an `OAG Knowledge.base`
file without changing canonical OAG concepts.

To create a new IP, scaffold the ontology-first structure before RTL/TB work:

```bash
python3 .codex/scripts/oag_scaffold_ip.py create <ip> --owner <owner>
```

To visualize an IP as a filterable ontology graph:

```bash
python3 .codex/scripts/oag_graph.py build \
  --ip-dir <ip> \
  --stage <stage> \
  --intent "<task>" \
  --html-out <ip>/ontology/generated/oag_graph.html
```
