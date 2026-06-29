# OAG Feature and IP-XACT Projection Policy

OAG keeps product intent and integration metadata separate. A feature is the
user-visible capability being delivered. IP-XACT-style metadata is the
tool-readable packaging view for integration.

```text
Feature -> Requirement -> Requirement Atom -> Obligation -> Contract
        -> Evidence -> Validation -> Decision

Interface/Register/MemoryMap/Parameter/File/Hierarchy
        -> IP-XACT-style projection
        -> linked back to OAG IDs
```

## Feature Layer

Use `ontology/features.yaml` for product-visible feature scope. A feature row
should name:

- `id`
- `name`
- `summary`
- `status`
- `source_claim_refs`
- `decision_refs`
- `requirement_refs`
- `obligation_refs`
- `contract_refs`
- verification objective or scenario refs when known
- IP-XACT projection refs when the feature changes interfaces, registers,
  parameters, hierarchy, or file/package metadata

Features are not vague marketing labels. A load-bearing feature is a scope
handle that tells the user what value is being locked and tells OAG which
requirements, contracts, verification objectives, and integration metadata move
together.

## SSOT-Inspired Sections

For IP development, the useful source-of-truth sections are:

- identity and top module;
- feature list and non-goals;
- decomposition and submodules;
- interfaces, ports, clocks, resets, and protocol bindings;
- registers, memory maps, address spaces, and interrupts;
- parameters and configuration model;
- function model and cycle/timing model;
- clock/reset domains, CDC/RDC intent, dataflow, and state ownership;
- power, security, error handling, debug observability, DFT, synthesis, and
  integration notes when load-bearing;
- quality gates, verification objectives, scenarios, scoreboard rows, coverage
  goals, assertions/formal candidates, and residual risks.

OAG does not need one monolithic SSOT YAML. It uses authority files:

- product value: `ontology/features.yaml`
- requirements and atoms: `ontology/requirements.yaml`,
  `ontology/requirement_atoms.yaml`
- decisions: `ontology/decision_matrix.yaml`
- obligations and contracts: `ontology/obligations.yaml`,
  `ontology/contracts.yaml`
- behavior and cycle truth: `ontology/modeling.yaml`
- interface/register/module namespace: `ontology/structure.yaml`,
  `ontology/decomposition.yaml`
- verification intent: `ontology/verification_plan.yaml`,
  `ontology/tb_methodology.yaml`
- integration/package projection: `ontology/ipxact_projection.yaml`

## IP-XACT Role

IP-XACT is not the behavior oracle. It is the tool-readable package metadata for
what integration tools need to know:

- VLNV identity;
- component metadata;
- bus interfaces and port bindings;
- memory maps, address blocks, registers, fields, access policy, reset values;
- address spaces and target/initiator references;
- parameters and configurable element values;
- file sets for RTL, constraints, docs, scripts, models, and TB collateral;
- views, instantiations, design, design configuration, and generator chains;
- vendor extensions that link back to OAG feature, requirement, obligation,
  contract, evidence, validation, and decision IDs.

Use `ontology/ipxact_projection.yaml` as the OAG-side projection plan. A later
exporter may generate IEEE 1685 XML from this plan, but OAG closure must still
resolve to ROCEV artifacts.

## Lock Rule

Before user scope lock on nontrivial IP work, show a lock preview that includes:

- feature rows and non-goals;
- requirement atoms;
- candidate obligations;
- candidate assume/guarantee contracts;
- verification objectives and proof expectations;
- IP-XACT-like integration metadata gaps: interface, register, memory map,
  parameter, file set, hierarchy, generator, and vendor-extension links.

Unknown fields stay draft. Do not let a missing feature, interface/register
surface, or IP-XACT-like metadata gap become an implicit RTL/TB default.
