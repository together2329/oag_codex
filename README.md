# IP Dev Agent OAG Architecture

This OAG pack supports ontology-first hardware IP development. OAG keeps design
truth, generated work inputs, parallel execution, and closure evidence separated
so agents can implement and verify IP without silently changing requirements.

The short version:

```text
User / Spec
  -> Intake / Draft
  -> Ontology Truth
  -> Projection / Compile
  -> Readiness / Schema / Quality Gates
  -> Run / Orchestration
  -> Wavefront
  -> Dispatch / Receipt
  -> Evidence / Closure / Decision
```

The upper layers define what is true and ready. The lower layers decide how to
execute work safely and whether the result can be claimed closed.

## Architecture Layers

| Layer | Role | Typical artifacts | Required when |
| --- | --- | --- | --- |
| 1. Intake / Draft | Capture user intent, source notes, unknowns, and candidate decisions without promoting them to locked truth. | `req/source_claims.yaml`, `req/ambiguity_register.yaml`, `ontology/decision_matrix.yaml`, `oag.draft` records | Required for new or ambiguous IP scope. Can be short when locked truth already exists. |
| 2. Ontology Truth | Own the single source of truth for requirements, contracts, structure, verification intent, and policy. | `ontology/requirements.yaml`, `requirement_atoms.yaml`, `obligations.yaml`, `contracts.yaml`, `structure.yaml`, `decomposition.yaml`, `modeling.yaml`, `domain_intent.yaml`, `verification_plan.yaml`, `design_rules.yaml`, `policies.yaml`, `scope_lock.json` | Required for any OAG-managed implementation, validation, or closure. |
| 3. Projection / Compile | Convert authored ontology into read-only work inputs and extracted implementation facts. | `ontology/generated/design_spec.json`, `design_truth_graph.json`, `authoring_packets/rtl__*.json`, `authoring_packets/tb__*.json`, `design_facts_graph.json` | Required before RTL/TB handoff or when generated views are stale. |
| 4. Readiness / Schema / Quality Gates | Check that ontology and generated packets are structurally valid and implementation-ready. | `oag_req_quality_check.py`, `oag_requirement_atom_check.py`, `oag_contract_strength_check.py`, `oag_lock_readiness_check.py`, `oag_verification_plan_check.py`, `oag_authoring_packet_check.py` | Required after scope lock and before relying on obligations, contracts, packets, or closure evidence. |
| 5. Run / Orchestration | Track the active obligation and the next action across edit, test, stop, and resume boundaries. | `oag.run.start`, `oag.run.next`, `oag.run.record`, `oag.run.checkpoint`, stop hooks | Useful for long or multi-step work. Optional for a small one-shot read-only check. |
| 6. Wavefront | Open only the dependency-ready parallel task set without breaking file ownership or evidence boundaries. | wavefront task graph, ready tasks, claims, barrier outputs, ownership locks, single integration owner | Required only for parallel work or multi-agent fan-out. Not needed for serial work. |
| 7. Dispatch / Receipt | Give write-capable native subagents bounded authority and verify their changed paths and receipts. | `oag_dispatch.py create`, allowed write paths, receipt path, `oag_dispatch.py verify` | Required for post-lock RTL, TB, sim, lint, coverage, formal, SDC, signoff, or implementation filelist writes by subagents. |
| 8. Evidence / Closure / Decision | Record proof, validate freshness and traceability, and decide whether completion/signoff is allowed. | `knowledge/ledger.jsonl`, `scoreboard_rows.v1`, stage receipts, validation report, gate decision, `oag.check`, `oag_closure_check.py`, `oag.decide` | Required for any completion, release, or signoff claim. |

## How The Layers Connect

1. Intake captures facts, assumptions, unresolved questions, and lock-blocking
   decisions. These records are draft knowledge, not implementation permission.
2. Ontology Truth promotes confirmed scope into requirements, atoms,
   obligations, contracts, structure, decomposition, modeling, domain intent,
   verification strategy, and policies.
3. Projection / Compile derives read-only work packets from ontology. RTL/TB
   workers consume the packets instead of reinterpreting the original prose.
4. Readiness gates validate schemas and semantics before implementation or
   verification relies on the ontology.
5. Run / Orchestration picks the current obligation and next action. It drives
   progress but does not replace ontology truth or evidence records.
6. Wavefront takes existing contracts, packets, and evidence plans and opens
   only dependency-satisfied tasks. It schedules work; it does not create truth.
7. Dispatch / Receipt bounds each write-capable worker to explicit paths and
   checks that the worker output matches the dispatch.
8. Evidence / Closure / Decision records ROCEV evidence, checks freshness and
   closure invariants, and writes the final decision receipt.

In responsibility form:

```text
Ontology = what is true
Projection = truth converted to worker inputs
Gate = whether truth and packets are usable
Run = what to do next
Wavefront = which tasks can run in parallel
Dispatch = who may write which paths
Evidence = what actually happened
Decision = whether the claim is allowed
```

## Which Layers Are Mandatory?

Not every layer must be fully active for every command. The required set
depends on the risk and workflow shape.

For a draft interview:

```text
Intake -> Ontology draft placeholders -> optional context/checks
```

For locked serial implementation:

```text
Ontology Truth -> Projection -> Readiness Gates -> Dispatch/Receipt -> Evidence -> Decision
```

For locked parallel implementation:

```text
Ontology Truth -> Projection -> Readiness Gates -> Run -> Wavefront -> Dispatch/Receipt -> Evidence -> Decision
```

For closure or signoff:

```text
Ontology Truth -> Projection -> Readiness Gates -> Evidence / Closure / Decision
```

Core layers for OAG-managed IP are:

- Ontology Truth
- Projection / Compile
- Readiness / Schema / Quality Gates
- Evidence / Closure / Decision

Conditional layers are:

- Intake / Draft: required when scope is new, compressed, or ambiguous.
- Run / Orchestration: useful when work spans multiple actions or stop/resume
  boundaries.
- Wavefront: required when work is parallelized.
- Dispatch / Receipt: required when post-lock write-capable subagents modify
  implementation or evidence artifacts.

## Non-Negotiable Boundaries

- Wavefront must not create or modify ontology truth. It only schedules ready
  work over existing truth, packets, dependencies, and ownership rules.
- Dispatch must not widen scope silently. It grants bounded write authority and
  verifies receipts against the dispatch baseline.
- Generated ontology outputs are read-only work inputs. If a generated packet
  is wrong, fix authored ontology and compile again.
- Evidence does not define new requirements. It proves or fails existing
  obligations and contracts.
- Tests passing is not completion. Completion requires explicit validation,
  fresh evidence, closure checks, and a recorded decision.
- After scope lock, RTL/TB/verification writes require native subagent dispatch
  and receipt unless there is an explicit human waiver.

## Common Commands

```bash
# Check scope lock status.
python3 .codex/scripts/oag_cli.py call --json '{"tool":"oag.lock_status","arguments":{"ip_dir":"<ip>"}}'

# Compile ontology projections.
python3 .codex/scripts/oag_cli.py call --json '{"tool":"oag.compile","arguments":{"ip_dir":"<ip>"}}'

# Run post-lock readiness gates.
python3 .codex/scripts/oag_req_quality_check.py --ip-dir <ip> --json
python3 .codex/scripts/oag_requirement_atom_check.py --ip-dir <ip> --json
python3 .codex/scripts/oag_contract_strength_check.py --ip-dir <ip> --json
python3 .codex/scripts/oag_lock_readiness_check.py --ip-dir <ip> --json
python3 .codex/scripts/oag_verification_plan_check.py --ip-dir <ip> --json
python3 .codex/scripts/oag_authoring_packet_check.py --ip-dir <ip> --require-packets --json

# Plan and claim dependency-safe parallel work.
python3 .codex/scripts/oag_wavefront.py plan --ip-dir <ip> --run-id <run> --template .codex/oag/wavefront-templates/tb_common_then_scenario_fanout.yaml --json
python3 .codex/scripts/oag_wavefront.py ready --ip-dir <ip> --run-id <run> --json
python3 .codex/scripts/oag_wavefront.py claim --ip-dir <ip> --run-id <run> --task-id <task> --json

# Check closure readiness.
python3 .codex/scripts/oag_cli.py call --json '{"tool":"oag.check","arguments":{"ip_dir":"<ip>"}}'
python3 .codex/scripts/oag_closure_check.py --ip-dir <ip>
```
