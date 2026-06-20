# OAG ROCEV Rule Pack

Use these rules in Codex project instructions, AGENTS.md, or a future hook
configuration.

```text
Before IP work:
  if the IP is new, call oag.scaffold or run .codex/scripts/oag_scaffold_ip.py
  call oag.inspect
  call oag.compile after ontology edits
  call oag.context
  when Codex hooks are enabled, UserPromptSubmit may inject oag.context automatically
  for goal-driven work, call oag.run.start and then follow oag.run.next
  keep ontology/design_rules.yaml present with required common rule kinds
  keep ontology/structure.yaml and ontology/decomposition.yaml present
  keep ontology/protection.yaml and knowledge/ledger.jsonl present

During IP work:
  keep claims linked to requirement, obligation, contract, evidence, validation
  record findings with actor.kind and actor.id
  rely on oag.record, oag.draft, and oag.ticket to append ledger events
  if an OAG run is active, use oag.run.record at evidence boundaries
  keep ontology/runs/<run_id>/run_state.json as durable execution state, not source truth
  during deep requirement interviews, call oag.draft after each meaningful answer round
  if context usage/compaction pressure is high, call oag.draft before continuing
  when Codex hooks are enabled, high-pressure requirement prompts inject an oag.draft guard
  never treat an interview draft as locked truth without explicit human promotion
  never silently edit protected locked-truth or closure-policy fields
  do not require a specific TB language, framework, simulator, or generator
  require scoreboard_rows.v1 semantics when scoreboard evidence is submitted
  require observed_source to prove DUT-facing observation, not model output
  activate design-rule instances for same-cycle priority conflicts, event/state commit consistency, contract-to-proof coverage, interleaved-context coverage, fault-model coverage, verification role decomposition, CDC/RDC crossing coverage, protocol compliance, timing closure, functional coverage closure, reset/X-prop coverage, and RTL language subset policy
  for load-bearing coverage closure, link coverage_refs -> fault_models -> killed mutation_results, or record mutation_not_required with rationale
  for signoff-grade TB architecture, model UVM-style roles without requiring UVM: sequence, driver, monitor, reference_model, scoreboard, coverage, env, and test
  for signoff-grade domain closure, require concrete evidence refs for CDC/RDC, protocol, timing/STA, functional coverage, and reset/X-prop claims; timing/STA must declare target frequency or target clocks, derive SDC from target clocks plus CDC/RDC async groups/exceptions, and use 50% clock-period input/output delays by default; DFT and power are not OAG v1 default gates
  keep the RTL language subset rule active: logic and Verilog generate are allowed; procedural for/while loops outside generate blocks are forbidden
  model RTL structure through decomposition profiles, not blanket rules:
    small_leaf_single_file for tiny leaf IPs, greenfield_modular for new nontrivial IPs,
    legacy_preserve for imported existing hierarchy, wrapper_adapter for protected cores plus new integration wrappers
  for greenfield_modular, require each current_ip module to use a unique RTL file by default;
    shared files require explicit shared_file_rationale
  use ontology/generated/design_spec.json and ontology/generated/authoring_packets/*.json as generated read-only work inputs after oag.compile
  use ontology/generated/design_facts_graph.json as generated read-only current-RTL facts after oag.compile; fix RTL or authored decomposition when extracted modules drift from ontology, never hand-edit generated facts
  keep implementation and evidence versioned through git-aware records/receipts: RTL, TB, filelists, SDC, docs, generated facts, and signoff artifacts should carry commit IDs or SHA-256 fingerprints before closure
  after meaningful improvement boundaries, call oag.metrics so closure ratio, issue counts, evidence counts, stage receipts, ledger events, and blocked/partial next-action counts are recorded numerically
  call oag.handoff when progress needs to be carried forward; the handoff must derive development_ready, signoff_ready, ranked next actions, and blockers from OAG metrics and auto-research evidence
  never mark signoff_ready=true from development closure alone; signoff readiness requires signoff profile, no blockers, no partial actions, and independent review evidence
  do not hard-code a fixed number of obligations or signoff slots for progress; derive totals and percentages from the active IP ontology and evidence graph
  route failures through failure_ticket.v1 instead of raw log prose
  write stage_run_receipt.v1 for evidence intended for signoff
  when bounded formal/assertion evidence is submitted through signoff/formal_assertion_report.json,
    treat status=development_pass as partial development evidence unless a promoted formal contract,
    full signoff proof scope, independent review, and matching ROCEV evidence exist

Before closure:
  call oag.compile
  call oag.check
  call oag.decide action=claim_complete with record_decision=true
  if an OAG run is active, call oag.run.checkpoint before claiming completion
  if oag.stop_check returns should_continue=true, continue with its OAG NEXT ACTION
  if allowed=false, do not claim completion
  require explicit rocev.validation.status for closed records
  require every obligation to close through the obligation -> contract -> validation closure matrix
  require closed evidence file hashes to match current disk content
  require protected fields clean, append-only ledger valid, and monotonic closure intact
  require a decision receipt under ontology/validations for completion claims
  include improvement_metrics in check/context/decision evidence so progress can be compared between snapshots
  keep readiness handoff reports consistent with embedded improvement_metrics so next actions and blockers can be checked numerically
  for signoff, require closure_profile=signoff, human-approved policy transition, fresh stage receipts, and an independent reviewer receipt
  do not claim a formal/assertion contract without proof/assertion evidence refs
  do not weaken closed/passed objects back to draft/open/stale without an approved decision

When asked to understand the whole IP:
  call oag.inspect
  build an ontology graph with .codex/scripts/oag_graph.py
  use the graph to explain requirements, obligations, contracts, evidence, validations, actors, records, artifacts, and gaps

Promotion:
  AI may propose local knowledge and candidates
  human decision is required for enterprise promotion, waivers, and signoff
  human decision is required for protected semantic truth or policy changes
  discovered defects should become refuted records, not silent closure downgrades
  execution style (single worker, orchestrator, CI, human shell) is record metadata, not a separate ontology mode
```

Completion report shape:

```text
Requirement:
Obligation:
Contract:
Evidence:
Validation:
OAG Decision:
```
