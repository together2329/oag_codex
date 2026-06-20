# Ontology IP Agent

This project is a `.codex`-first OAG test pack. The plugin folder is optional;
the primary Codex-facing assets live under `.codex/`.

For hardware IP work:

1. Read `.codex/rules/oag-rocev.rules.md`.
2. Use `.codex/skills/oag-ip-workflow` when working on RTL, TB, simulation,
   coverage, signoff, or evidence review.
3. For a new IP, create the ontology-first scaffold before RTL/TB work:

```bash
python3 .codex/scripts/oag_scaffold_ip.py create <ip> --owner <owner>
```

4. Before editing an IP, run OAG inspect/compile/context:

```bash
python3 .codex/scripts/oag_cli.py call --json '{"tool":"oag.inspect","arguments":{"ip_dir":"<ip>","stage":"<stage>","intent":"<task>"}}'
python3 .codex/scripts/oag_cli.py call --json '{"tool":"oag.compile","arguments":{"ip_dir":"<ip>"}}'
python3 .codex/scripts/oag_cli.py call --json '{"tool":"oag.context","arguments":{"ip_dir":"<ip>","stage":"<stage>","intent":"<task>"}}'
```

For goal-driven IP work, start a durable OAG run and keep following the single
next action it derives from the closure matrix:

```bash
python3 .codex/scripts/oag_cli.py call --json '{"tool":"oag.run.start","arguments":{"ip_dir":"<ip>","stage":"<stage>","intent":"<task>"}}'
python3 .codex/scripts/oag_cli.py call --json '{"tool":"oag.run.next","arguments":{"ip_dir":"<ip>"}}'
```

Run state belongs under `ontology/runs/<run_id>/`; evidence still closes through
`oag.record`/`oag.run.record`, and decisions still close through
`oag.decide`/`oag.run.checkpoint`.
When `.codex/hooks.json` is enabled by Codex, the Stop hook calls
`hooks/codex_stop_gate.py` so an incomplete active run blocks stopping with the
next OAG action instead of relying on the agent to remember it.
The UserPromptSubmit hooks can also inject `oag.context` for inferred IP work
and add an `oag.draft` reminder when requirement-interview context pressure is
high. Context injection is content-hash deduped in `.codex/.cache/` so repeated
turns do not consume context with identical state; the PostCompact hook records
a recovery marker, and the next UserPromptSubmit consumes that marker to restore
OAG context after compaction.
To evaluate these gates as scenarios, run
`python3 .codex/scripts/oag_eval.py`; use `--json` for machine-readable reports.
Local aliases are available as `make eval`, `make smoke`, and `make test`.

During deep requirement interviews, save draft knowledge with `oag.draft` after
each meaningful user answer or before context pressure/compaction risk. Drafts
belong in `req/interview_draft.md`, `ontology/drafts/`, and
`knowledge/records/`; they are not locked truth until explicitly promoted by a
human.

Use protected-field and ledger gates as part of the ontology, not as prose.
`ontology/protection.yaml` declares locked truth and closure policy fields that
need human-approved decisions for semantic edits. `knowledge/ledger.jsonl` is
append-only and hash chained; do not hand-edit it.

5. Before claiming completion, run OAG compile/check/decide:

```bash
python3 .codex/scripts/oag_cli.py call --json '{"tool":"oag.compile","arguments":{"ip_dir":"<ip>"}}'
python3 .codex/scripts/oag_cli.py call --json '{"tool":"oag.check","arguments":{"ip_dir":"<ip>"}}'
python3 .codex/scripts/oag_cli.py call --json '{"tool":"oag.decide","arguments":{"ip_dir":"<ip>","action":"claim_complete","stage":"<stage>","intent":"<task>","record_decision":true}}'
```

If an OAG run is active, prefer checkpointing it:

```bash
python3 .codex/scripts/oag_cli.py call --json '{"tool":"oag.run.checkpoint","arguments":{"ip_dir":"<ip>","stage":"<stage>","intent":"<task>"}}'
```

If `oag.decide` returns `allowed: false`, report the blocker instead of saying
the IP is complete. If it returns `allowed: true`, keep the decision receipt
under `ontology/validations/` as the durable completion decision. Completion
actions are blocked unless `record_decision` is true.

Do not require a fixed TB implementation. The standard is the evidence row
schema (`scoreboard_rows.v1` with DUT-facing `observed_source`), not Verilog,
SystemVerilog, UVM, Python, cocotb, or any simulator choice.

Keep common semantic RTL rules in `ontology/design_rules.yaml`, not in chat
notes. Required rule kinds are event/state commit consistency, same-cycle
priority declaration, scoreboard evidence schema, contract-to-proof coverage,
module file boundary, and RTL language subset. The default language subset
allows `logic` and Verilog `generate` constructs, while procedural `for`/`while`
loops outside generate blocks are forbidden. Activate rule instances when an IP
has the hazard, and link them to the relevant requirement, obligation, contract,
and evidence.
For packet/message IPs with multiple active contexts, use an
`interleaved_context_coverage` rule instance when packet-level interleaving is a
load-bearing claim; closed instances require observed coverage refs.
For signoff-grade or otherwise load-bearing coverage claims, use a
`fault_model_coverage` rule instance to connect each coverage ref to the
requirement fault models it is meant to catch and to killed mutation evidence.
If mutation is not applicable, set `mutation_not_required: true` with an
explicit rationale instead of silently treating coverage hit as proof strength.
For signoff-grade verification architecture, use a
`verification_role_decomposition` rule instance to model UVM-style roles without
requiring UVM itself: sequence, driver, monitor, reference_model, scoreboard,
coverage, env, and test. Closed instances require role artifacts and independence
between expected_source, observed_source, and compare_source.
For signoff-grade DV/implementation closure, use SSOT-aligned domain rule
instances instead of prose waivers: `cdc_crossing_coverage` for
clock/reset-domain crossings, `protocol_compliance` for AXI/APB/streaming
interface rules, `timing_closure` for target frequency/clocks plus SDC/STA setup-hold evidence,
`functional_coverage_closure` for coverage goals versus observed coverage refs,
and `reset_xprop_coverage` for reset sequencing and X-propagation robustness.
Closed instances require linked ROCEV refs plus concrete evidence files; coverage
rule instances require observed coverage refs. Timing instances must name a
target frequency or target clocks; SDC should derive `create_clock`, CDC async
clock groups/exceptions, and default input/output delays of 50% of the clock
period unless the IP overrides them. DFT and power remain outside OAG v1 signoff
gates unless a project adds explicit local rules.

Treat authored ontology files as the authority and generated projections as
read-only views. `ontology/structure.yaml` owns the namespace for signals,
interfaces, registers, state, and derived signals. `ontology/decomposition.yaml`
owns module hierarchy, ownership, legacy-preservation policy, and which module
owns each obligation/contract. `oag.compile` derives
`ontology/generated/design_spec.json` and
`ontology/generated/authoring_packets/*.json`; it also derives
`ontology/generated/design_facts_graph.json` from current RTL using `pyslang`
when available, with a conservative parser fallback. Do not hand-edit generated
projection or facts files. Use `design_facts_graph.json` as implementation
evidence/provenance only: authored `structure.yaml`/`decomposition.yaml` remain
the source of design intent, while the facts graph proves what the RTL currently
contains and flags unmapped or missing modules. Use
`structure_profile`/decomposition modes instead of a hard
single-file or hard multi-file rule:

- `small_leaf_single_file`: one small editable leaf module is allowed with an
  explicit rationale.
- `greenfield_modular`: new nontrivial IPs should split behavior into owned
  modules with interface/contract boundaries. Each current-IP module should use
  a unique RTL file by default; shared files require explicit
  `shared_file_rationale`.
- `legacy_preserve`: existing IP hierarchy is preserved and mapped to extracted
  requirements before repair or verification.
- `wrapper_adapter`: legacy/child core remains protected while wrapper/adapter
  modules own new integration obligations.

For signoff, use `closure_profile: signoff` in `ontology/policies.yaml`, a
compiled `ontology/generated/design_truth_graph.json`, and fresh
`stage_run_receipt.v1` files. `oag.check` must also report clean protected
fields, a valid ledger hash chain, monotonic closure, a closed closure matrix,
explicit validation status for closed records, and fresh evidence hashes.
`oag.decide action=signoff` also requires a passing independent `oag.review`
receipt before the final decision receipt; reviewer receipts with
`independent: false` do not satisfy the gate even when their verdict is `pass`.
Do not weaken a closed/passed object back to draft/open/stale without an
approved decision; use a `refuted` record for newly discovered defects. Single
worker, orchestrator, CI, and human shell are execution metadata, not separate
ontology modes.
Long-term version management should be git-backed: RTL, TB, list files, SDC,
docs, generated facts, and signoff evidence should be tied to commit IDs and
file SHA-256 fingerprints in records/receipts instead of relying on transient
chat memory.
For cross-platform continuity, use `.codex/scripts/oag_portable_db.py` to
export/import portable OAG DB snapshots. The snapshot is the reusable state
bridge across Codex, Cursor, CI, and future OAG frontends; platform adapters
should remain thin and reconstruct context from the imported OAG DB rather than
from chat history.
Use `.codex/scripts/oag_okf.py` to generate Open Knowledge Format views from
OAG DB state. Treat OKF as a readable/shareable generated view; import external
OKF only as draft knowledge until it passes explicit OAG promotion gates.
OKF import must preserve existing authored OAG concepts and Locked Truth; it may
append draft knowledge, but it must not rewrite canonical requirement or
ontology source files.
Use `--profile obsidian` or `make okf-export-obsidian` only for generated
Obsidian vault views. That profile adds wiki links, aliases, graph-friendly
frontmatter, and an `OAG Knowledge.base` file, but OAG remains the canonical DB.
