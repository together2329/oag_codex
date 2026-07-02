# OAG Mission and Action Object Model

This document records the Mission/Action layer for OAG. It does not
replace the current OAG operation stack. It gives the existing run frame,
decision matrix, gap matrix, wavefront, dispatch, receipt, validation, and gate
artifacts a shared object vocabulary so the system can explain and trace why an
operation was opened.

## Purpose

OAG already has an operation layer:

```text
open item / failed check / gap
  -> next-action recommendation
    -> wavefront task
      -> dispatch
        -> ownership lock
          -> subagent work
            -> receipt
              -> review decision
                -> evidence validation
                  -> gate decision
```

The missing piece is not execution. The missing piece is a first-class model for
the meaning of each operation:

- what kind of action it is;
- which ontology objects it targets;
- why it is currently recommended;
- what preconditions open or block it;
- which role may execute it;
- which files or artifacts it may change;
- what evidence it must produce;
- how to recover if it times out, fails, or emits a late receipt.

The Mission/Action layer makes those answers explicit.

## Non-Goals

This layer must not:

- replace ROCEV truth objects;
- replace `oag.check`, lock readiness checks, or closure checks;
- replace wavefront dependency and ownership locking;
- make RTL/TB writes possible before scope lock;
- let the main agent bypass native subagent dispatch after lock;
- treat generated action candidates as authored design truth.

It is a planning, explanation, and traceability layer above the existing OAG
execution machinery.

## Object Families

OAG should distinguish four object families.

```text
Design objects:
  IP, feature, interface, register, field, memory map, parameter, module,
  port, signal, state, clock domain, reset domain.

Truth objects:
  source claim, ambiguity, decision, requirement atom, requirement,
  obligation, contract, behavior rule, cycle rule, design rule.

Evidence objects:
  verification objective, scenario, scoreboard event, coverage goal,
  assertion, formal proof, lint report, sim result, validation record,
  artifact hash, gate decision.

Operation objects:
  mission, open item, action type, action candidate, action instance,
  wavefront task, dispatch, ownership lock, receipt, review decision,
  retry, abort, fallback.
```

ROCEV covers the truth and evidence families. Wavefront and dispatch cover much
of the operation family. Mission and Action objects make the operating intent,
selection rationale, and recovery path explicit.

## Core Concepts

### Mission Type

A reusable goal template.

Examples:

- `MISSION_INTAKE_TO_RTL_READY`
- `MISSION_RTL_READY_TO_IMPLEMENTED`
- `MISSION_IMPLEMENTED_TO_VALIDATED`
- `MISSION_VALIDATED_TO_GATE_PASS`
- `MISSION_LEGACY_IP_GAP_REPAIR`

A mission type defines:

- target state;
- forbidden actions before target;
- action priority order;
- user-question policy;
- review and escalation policy.

### Mission Instance

A mission type applied to one IP workspace.

Example:

```yaml
schema_version: oag_mission_instance.v1
id: MISSION_RUN_20260630T001500Z_MISSION_INTAKE_TO_RTL_READY
template_id: MISSION_INTAKE_TO_RTL_READY
status: active
current_open_items:
  - id: OPEN_0001_UNRESOLVED_LOCK_DECISION
current_recommended_action:
  id: ACT_CAND_P0_ACT_ASK_DEEP_INTERVIEW_QUESTION_001
action_instance_refs: []
```

Mission instances are durable if they guide real work. They should live under
IP state:

```text
<ip>/knowledge/missions/<mission_instance_id>.json
<ip>/knowledge/missions/_index.json
```

### Action Type

A reusable operation kind. This is the catalog entry.

Examples:

- `ACT_CAPTURE_SOURCE_CLAIM`
- `ACT_ASK_DEEP_INTERVIEW_QUESTION`
- `ACT_RESOLVE_DECISION`
- `ACT_PROJECT_REQUIREMENT_ATOMS`
- `ACT_PROJECT_OBLIGATIONS`
- `ACT_PROJECT_CONTRACTS`
- `ACT_RENDER_LOCK_PREVIEW`
- `ACT_LOCK_SCOPE`
- `ACT_COMPILE_AUTHORING_PACKETS`
- `ACT_ARCHITECTURE_PROJECTION`
- `ACT_RTL_IMPLEMENTATION`
- `ACT_TB_IMPLEMENTATION`
- `ACT_LINT_STATIC_CHECK`
- `ACT_SIMULATION_RUN`
- `ACT_COVERAGE_REVIEW`
- `ACT_EVIDENCE_VALIDATION`
- `ACT_GATE_REVIEW`
- `ACT_ORCHESTRATION_RECOVERY`

Action types are mostly pack-level concepts. They should live in a common
catalog such as:

```text
.codex/oag/operation_action_types.yaml
```

IP workspaces may add overrides only when they have a real IP-specific action
policy.

### Open Item

A normalized finding that something is missing, weak, stale, blocked, or
failed.

Open items may come from:

- SSOT section checks;
- decision matrix checks;
- requirement atom checks;
- requirement quality checks;
- contract strength checks;
- trace graph checks;
- authoring packet checks;
- implementation review;
- lint/sim/formal failures;
- stale evidence checks;
- gate failures;
- orchestration guard findings.

Open items are not necessarily durable. They can be recalculated from check
results. Durable failures should still be recorded through OAG records,
tickets, receipts, or validation reports.

### Action Candidate

A generated candidate operation that could resolve one or more open items.

Action candidates are generated from the current IP state and should be treated
as derived data.

Suggested location:

```text
<ip>/ontology/generated/action_candidates.json
<ip>/ontology/generated/action_graph.json
```

Do not hand-edit this file. If a candidate is wrong, fix the authored ontology,
decision matrix, check logic, or action catalog, then regenerate candidates.

### Action Instance

A real execution of a selected candidate.

Action instances are durable history. They answer:

- which candidate was selected;
- who selected it;
- why it was selected;
- which wavefront task or dispatch executed it;
- which receipt and review decision accepted or rejected it;
- which evidence or validation records resulted.

Suggested location:

```text
<ip>/knowledge/actions/<action_instance_id>.json
<ip>/knowledge/actions/_index.json
```

## Action Lifecycle

```text
Action Type
  -> generated Action Candidate
    -> selected Action Instance
      -> optional Wavefront Task
        -> optional Dispatch
          -> Receipt
            -> Review Decision
              -> Evidence / Validation / Gate
```

Not every action needs wavefront or dispatch. A read-only SSOT check may be a
local action. Post-lock RTL/TB/sim/lint/formal/signoff artifact writes must use
native subagent dispatch and receipt.

## Implemented CLI

Action types are created once in the pack catalog.

Generate current Mission/Action recommendations:

```bash
python3 .codex/scripts/oag_action_plan.py --ip-dir <ip> --json
```

This writes:

- `<ip>/ontology/generated/action_candidates.json`
- `<ip>/ontology/generated/action_graph.json`
- `<ip>/knowledge/missions/<mission_instance_id>.json`

Inspect or create Mission instances:

```bash
python3 .codex/scripts/oag_mission_runtime.py show --ip-dir <ip> --mission-id active --json
python3 .codex/scripts/oag_mission_runtime.py list --ip-dir <ip> --json
python3 .codex/scripts/oag_mission_runtime.py evaluate --ip-dir <ip> --mission-id active --json
```

`evaluate` checks completion criteria for the active mission without replacing
closure policy. It verifies common operational criteria such as no active
wavefront locks, no pending gates, no unresolved P0/P1 open items, and no open
Action instances, then adds mission-specific checks such as scope lock,
compile-manifest freshness, accepted implementation actions, evidence
validation, or gate-decision freshness.

Record the selected operation:

```bash
python3 .codex/scripts/oag_action_record.py start --ip-dir <ip> --candidate-id recommended --selected-reason "<why>" --json
python3 .codex/scripts/oag_action_record.py update --ip-dir <ip> --action-id latest --status accepted --summary "<result>" --json
```

For real implementation/evidence work, attach execution artifacts:

```bash
python3 .codex/scripts/oag_action_record.py update \
  --ip-dir <ip> \
  --action-id latest \
  --status accepted \
  --dispatch-id <dispatch-id> \
  --receipt-path <ip>/knowledge/subagents/<receipt>.json \
  --review-decision <ip>/knowledge/decisions/<decision>.json \
  --git-checkpoint \
  --checkpoint-message "OAG action checkpoint" \
  --json
```

Render the formal operating review page:

```bash
python3 .codex/scripts/oag_operation_review_frame.py --ip-dir <ip> --json
```

This writes:

```text
<ip>/knowledge/operation_frames/latest/index.html
<ip>/knowledge/operation_frames/latest/operation_frame.json
```

The page shows the current Mission, recommended action, four options, open
items, action graph, draft wavefront tasks, role health, mission-completion
criteria, action history, and stuck/open Action instances.

Generate a non-executing wavefront draft from ready Action candidates:

```bash
python3 .codex/scripts/oag_action_wavefront_draft.py --ip-dir <ip> --json
```

This writes:

```text
<ip>/ontology/generated/action_wavefront_draft.json
```

The draft is intentionally not a claim and not a dispatch. It converts ready
Action candidates into task-shaped records with dependencies, owner roles,
dispatch hints, and `may_claim_complete=false` so a human or orchestrator can
review the proposed work split before opening locks.

When the split is acceptable, materialize the same draft into an OAG wavefront
graph. This still does not claim tasks or create dispatches; it only creates
the durable run graph and seeded barriers:

```bash
python3 .codex/scripts/oag_action_wavefront_draft.py \
  --ip-dir <ip> \
  --materialize-run-id WF_<name> \
  --barrier <already_ready_token> \
  --json
```

This writes:

```text
<ip>/ontology/generated/action_wavefront_template_WF_<name>.json
<ip>/ontology/runs/WF_<name>/wavefront_task_graph.json
<ip>/ontology/runs/WF_<name>/ownership_locks.json
<ip>/ontology/runs/WF_<name>/barriers.json
```

Audit role health:

```bash
python3 .codex/scripts/oag_role_health.py --ip-dir <ip> --json
```

This writes:

```text
<ip>/knowledge/operations/role_health.json
```

Role health is derived from durable Action instances and active wavefront
locks. Stuck open work or repeated bad terminal outcomes become planning
hazards; `oag_action_plan.py` then emits an `ACT_ORCHESTRATION_RECOVERY`
candidate before additional work is opened for the affected role.

For stuck gate-review tasks, create a fallback plan before retrying:

```bash
python3 .codex/scripts/oag_orchestration_guard.py fallback-plan --ip-dir <ip> --json
```

The fallback plan records stale gate locks, late-receipt quarantine, and the
custom-reviewer retry policy. It does not auto-abort or auto-open a replacement
dispatch. The parent must first release the stale task with `abort-task`, then
create a fresh `oag-custom-reviewer` dispatch from the current baseline.

After a Deep Interview answer, persist the selection and refresh operation
state in one handoff:

```bash
python3 .codex/scripts/oag_deep_interview_round.py handoff \
  --ip-dir <ip> \
  --json-file <round.json> \
  --selected-option A \
  --write-decision-matrix \
  --write-source-claim \
  --refresh-action-plan \
  --render-operation-frame
```

This connects the one-question interview loop to Mission/Action planning
without making the answer locked truth unless `--confirmed` is also supplied.

Run the Windows portability smoke check before publishing the pack:

```bash
python3 .codex/scripts/oag_windows_smoke.py --json
```

It checks that runtime hooks and scripts do not depend on `/bin/sh`, `sh.exe`,
or `shell=True`, that argv-style command splitting rejects shell metacharacters,
and that Git for Windows discovery paths are present.

## When Actions Are Created

Action candidates are recalculated at OAG stage boundaries:

- after a deep interview answer;
- after source claim or ambiguity capture;
- after decision matrix updates;
- after requirement atom or contract projection;
- after lock preview generation;
- after scope lock;
- after `oag.compile`;
- after authoring packet checks;
- after implementation review;
- after RTL/TB handoff;
- after lint/sim/formal execution;
- after evidence validation;
- after gate review;
- after orchestration guard audit.

Action instances are created only when a candidate is actually selected for
execution.

## Why This Exists

The benefit is not another checklist. The benefit is operational traceability:

- the system can say which Mission is active now;
- each recommended next step has score factors, open-item links, and a command;
- selected actions become durable records instead of scrollback;
- dispatches, receipts, review decisions, evidence files, and git checkpoints
  attach to one Action instance;
- stuck actions can be detected and recovered before opening conflicting work;
- a reviewer can inspect the formal operation frame instead of reconstructing
  the story from terminal output.

This distinction matters:

```text
candidate = current possible work
instance  = historical work that actually happened
```

Candidates may be regenerated or disappear when the IP state changes. Instances
are audit history and must not be silently rewritten.

## Candidate Grouping Rules

Action candidates are not one-per-requirement. They are grouped by executable
work boundary.

Group open items into one candidate when these fields match:

- action type;
- owner role;
- writable artifact or write path;
- dependency layer;
- precondition status;
- proof method;
- review policy;
- root cause.

Split candidates when any of these differ:

- different owner role;
- different writable artifact;
- different phase;
- different dependency ordering;
- one needs a user decision while another can be automated;
- one is RTL and another is TB or evidence;
- different risk/severity;
- parallel execution is possible and useful.

Examples:

```text
Three requirements missing source refs
  -> one ACT_FIX_REQUIREMENT_QUALITY candidate.

One unresolved interface decision blocks five requirements
  -> one ACT_RESOLVE_DECISION candidate targeting the decision row.

One packet parsing module owns three contracts
  -> one ACT_RTL_IMPLEMENTATION candidate for that module.

Three contracts map to three disjoint modules
  -> three ACT_RTL_IMPLEMENTATION candidates, wavefront-parallel if ready.
```

## Candidate Shape

Suggested generated shape:

```yaml
schema_version: oag_action_candidates.v1
generated_at: "2026-06-30T00:00:00Z"
ip: packet_rx
candidates:
  - id: ACT_CAND_20260630_001
    action_type: ACT_RESOLVE_DECISION
    mission_refs:
      - MIS_RUN_20260630_001
    status: ready
    priority: P0
    recommended: true
    recommendation_reason: "Blocks RTL-ready mission and downstream interface, contract, RTL, and TB objects."
    target_objects:
      decisions:
        - DEC_INPUT_INTERFACE_KIND
      blocked_objects:
        - REQ_PACKET_INPUT
        - ATOM_PACKET_ACCEPT
        - CONTRACT_PACKET_ACCEPT
    open_items:
      - OPEN_DECISION_001
    preconditions:
      scope_lock_state: draft
      active_lock_conflict: false
    owner_role: human_via_deep_interview
    user_question_policy:
      one_question_per_round: true
      option_count: 4
      require_recommendation: true
      allow_custom_answer: true
    expected_effects:
      writes:
        - ontology/decision_matrix.yaml
        - req/source_claims.yaml
      records:
        - oag.draft
```

## Action Instance Shape

Suggested durable shape:

```yaml
schema_version: oag_action_instance.v1
id: ACT_RUN_20260630_001
action_type: ACT_RESOLVE_DECISION
candidate_ref: ACT_CAND_20260630_001
mission_instance_refs:
  - MIS_RUN_20260630_001
selected_by:
  kind: human
  id: user
  surface: codex
selected_reason: "Highest lock-blocking decision for RTL-ready mission."
status: accepted
started_at: "2026-06-30T00:00:00Z"
completed_at: "2026-06-30T00:05:00Z"
target_objects:
  decisions:
    - DEC_INPUT_INTERFACE_KIND
result:
  changed_paths:
    - ontology/decision_matrix.yaml
  records:
    - knowledge/records/IKL_...
  review_decision: ""
  dispatch_id: ""
  receipt_path: ""
```

For dispatched work:

```yaml
result:
  wavefront_run_id: WF_...
  wavefront_task_id: W2_RTL_PACKET_PARSER
  dispatch_id: DISPATCH_...
  receipt_path: knowledge/subagents/RTL_PACKET_PARSER.json
  review_decision: ontology/decisions/DEC_WAVEFRONT_...
```

## Recommended Action Type Catalog

The initial catalog should be small. Add new action types only when the existing
type cannot describe owner, preconditions, outputs, or review policy.

| Action Type | Phase | Typical Owner | Main Inputs | Main Outputs |
| --- | --- | --- | --- | --- |
| `ACT_CAPTURE_SOURCE_CLAIM` | intake | main / intake agent | user text, docs, RTL notes | source claims, ambiguity rows |
| `ACT_ASK_DEEP_INTERVIEW_QUESTION` | intake | main | ambiguity, decision row | user answer, decision update, draft record |
| `ACT_RESOLVE_DECISION` | intake/planning | human + main | decision matrix row | decided/waived row, rationale |
| `ACT_PROJECT_REQUIREMENT_ATOMS` | planning | requirement/contract agent | source claims, decisions | requirement atoms |
| `ACT_REVIEW_REQUIREMENTS` | review | custom reviewer | claims, atoms, requirements | findings, blockers, recommendations |
| `ACT_PROJECT_OBLIGATIONS` | planning | contract agent | requirements, atoms | obligations |
| `ACT_PROJECT_CONTRACTS` | planning | contract agent | obligations, behavior intent | assume/guarantee contracts |
| `ACT_ARCHITECTURE_PROJECTION` | architecture | contract/ontology agent | features, contracts, IP-XACT-style metadata | structure, decomposition, modeling |
| `ACT_RENDER_LOCK_PREVIEW` | review | main/tool | draft truth artifacts | HTML review frame |
| `ACT_LOCK_SCOPE` | lock | human + main | preview, checks, decisions | scope lock receipt |
| `ACT_COMPILE_AUTHORING_PACKETS` | compile | main/tool | authored ontology | generated packets |
| `ACT_RTL_IMPLEMENTATION` | implementation | RTL implementation agent | RTL authoring packet, contract, module boundary | RTL files, receipt |
| `ACT_TB_IMPLEMENTATION` | verification | TB implementation agent | TB authoring packet, scenarios, scoreboard refs | TB files, receipt |
| `ACT_LINT_STATIC_CHECK` | static validation | lint/static agent | RTL, design rules | lint report, findings |
| `ACT_SIMULATION_RUN` | dynamic validation | sim execution agent | RTL, TB, scenarios | results XML, scoreboard rows, coverage |
| `ACT_COVERAGE_REVIEW` | closure | coverage/evidence agent | coverage JSON, refs | coverage findings |
| `ACT_EVIDENCE_VALIDATION` | closure | evidence validator | evidence files, hashes, ROCEV links | validation report |
| `ACT_GATE_REVIEW` | gate | gate reviewer | closure matrix, validation report | gate decision |
| `ACT_ORCHESTRATION_RECOVERY` | orchestration | main / custom reviewer | active locks, late receipts | abort/fallback decision |

## Action Type Example

```yaml
schema_version: oag_operation_action_types.v1
action_types:
  - id: ACT_RTL_IMPLEMENTATION
    label: RTL Implementation
    phase: implementation
    owner_role: oag-rtl-implementation-agent
    consumes:
      - rtl_authoring_packet
      - contract
      - module_boundary
      - behavior_rule
      - cycle_rule
    preconditions:
      - scope_lock.state == locked
      - oag.compile == pass
      - oag_authoring_packet_check == pass
      - oag_contract_strength_check == pass
      - no_conflicting_wavefront_lock
    allowed_write_policy:
      source: dispatch
      required: true
    produces:
      - rtl_file_delta
      - subagent_receipt
      - lint_or_compile_evidence_when_available
    cannot_claim:
      - final_completion
      - signoff
      - closure
    fallback_policy:
      dispatch_verify_fail: route_inconclusive
      active_lock_conflict: block_until_released
```

## Mission Templates

### `MISSION_INTAKE_TO_RTL_READY`

Goal: turn ambiguous user/spec intent into locked, implementable OAG truth.

Target state:

- source claims present;
- lock-blocking ambiguities resolved or waived;
- lock-required decisions decided or waived;
- requirement atoms pass;
- requirement quality passes;
- obligations present;
- contracts are closure-grade enough for implementation;
- verification plan passes;
- lock preview frame is current;
- scope is locked;
- authoring packets pass.

Forbidden before target:

- RTL implementation;
- TB implementation;
- sim closure;
- gate completion.

Priority:

```text
orchestration hazard
  -> source claim gap
    -> highest-impact user question
      -> decision matrix update
        -> requirement atom hygiene
          -> obligation projection
            -> contract projection
              -> verification plan
                -> lock preview
                  -> human lock
                    -> compile authoring packets
```

### `MISSION_RTL_READY_TO_IMPLEMENTED`

Goal: implement locked contracts into RTL and TB artifacts.

Target state:

- RTL module handoffs accepted;
- TB handoffs accepted;
- lint/static checks run or blockers recorded;
- basic sim/compile run or blockers recorded;
- implementation receipts verified.

Priority:

```text
authoring packet freshness
  -> architecture/decomposition gaps
    -> RTL/TB wavefront tasks
      -> lint/static check
        -> basic sim run
          -> handoff review
```

### `MISSION_IMPLEMENTED_TO_VALIDATED`

Goal: convert implementation into contract-linked evidence.

Target state:

- sim results pass for required scenarios;
- scoreboard rows use `scoreboard_rows.v1`;
- coverage refs are registered and contract-linked;
- failed tests do not contribute to closure;
- validation records link requirements, obligations, contracts, evidence, and
  hashes.

Priority:

```text
sim execution
  -> failure triage
    -> repair wave
      -> regression rerun
        -> coverage review
          -> evidence validation
```

### `MISSION_VALIDATED_TO_GATE_PASS`

Goal: produce current closure and gate decision.

Target state:

- `oag.check` passes;
- `oag_closure_check.py` passes;
- validation report is current;
- gate decision is current and PASS, or the blocker is explicit.

Priority:

```text
stale evidence check
  -> validation refresh
    -> gate review frame
      -> gate decision
        -> completion decision
```

### `MISSION_LEGACY_IP_GAP_REPAIR`

Goal: preserve imported RTL/doc hierarchy while mapping gaps to OAG contracts
and repair actions.

Target state:

- legacy implementation facts captured;
- gap matrix ranks missing/partial contracts;
- repairs are dispatched only to explicit legacy/wrapper files;
- evidence closes repaired gaps without reshaping the source tree.

Priority:

```text
read-only extraction
  -> implementation review gap matrix
    -> P0/P1 repairs
      -> regression/evidence
        -> validation/gate
```

## Deep Interview Integration

Deep Interview questions become action candidates when they resolve
lock-blocking ambiguity or decision rows.

Question policy:

- ask one question per round;
- present about four options;
- mark one recommendation when defensible;
- always allow custom user input;
- cite the target ambiguity/decision;
- explain the downstream impact;
- write the answer to draft/decision artifacts before long context transitions.

Example:

```yaml
action_type: ACT_ASK_DEEP_INTERVIEW_QUESTION
target_objects:
  ambiguity: AMB_INPUT_BOUNDARY
  decision: DEC_INPUT_INTERFACE_KIND
recommendation_reason: "This decision blocks interface, contract, RTL module boundary, and TB driver selection."
options:
  - label: AXI4-Stream
    recommended: true
    effect: "DEC_INPUT_INTERFACE_KIND=axi4_stream"
  - label: AXI4 memory-mapped write
    effect: "DEC_INPUT_INTERFACE_KIND=axi4_mm_write"
  - label: APB register write
    effect: "DEC_INPUT_INTERFACE_KIND=apb_csr"
  - label: Minimal custom input
    effect: "user_supplied"
```

## Recommendation Scoring

The mission planner should rank candidates with explicit reasons. Suggested
factors:

- lock-blocking severity;
- downstream fanout;
- user-only knowledge requirement;
- reversibility cost;
- implementation risk;
- proof/evidence impact;
- active lock or orchestration hazard;
- stale evidence or gate staleness;
- mission target distance;
- whether preconditions are already satisfied.

Suggested rough priority:

```text
P0: blocks scope lock, implementation permission, or valid closure
P1: blocks major RTL/TB/evidence progress
P2: improves review quality or reduces risk
P3: cleanup, documentation, optional hardening
```

## Wavefront and Dispatch Integration

Wavefront remains the dependency and ownership scheduler. It should consume
selected action candidates, not raw prose.

```text
action_candidate
  -> wavefront task materialization
    -> dispatch create
      -> wavefront claim with dispatch id
        -> child receipt
          -> dispatch verify
            -> review_pending
              -> approved wavefront decision
                -> handoff_pass
```

Dispatch records should eventually include optional references:

```yaml
mission_instance_ref: MIS_RUN_20260630_001
action_candidate_ref: ACT_CAND_20260630_004
action_instance_ref: ACT_RUN_20260630_009
```

These references should be additive. Existing dispatch verification must not be
weakened.

## Stuck, Abort, Retry, and Fallback

Action type policy should define bounded recovery rules.

Example:

```yaml
action_type: ACT_GATE_REVIEW
timeout_policy:
  soft_timeout_sec: 600
  retry_limit: 1
abort_policy:
  terminal_statuses:
    - blocked
    - failed
    - inconclusive
late_receipt_policy:
  after_abort: invalid_handoff
fallback_policy:
  after_retry_stuck: ACT_ORCHESTRATION_RECOVERY
  custom_review_allowed: true
```

This avoids ad hoc retry loops. The parent can explain:

```text
Gate review action timed out, retry limit was consumed, late receipts are not
valid handoffs, and fallback custom review is now the recommended action.
```

## Review Frame Integration

Human review frames should show both possible and blocked actions.

Example table:

```text
Action                         Status     Reason
ACT_ASK_DEEP_INTERVIEW_QUESTION open       DEC_INPUT_INTERFACE_KIND blocks RTL-ready
ACT_RENDER_LOCK_PREVIEW         blocked    unresolved lock decision remains
ACT_RTL_IMPLEMENTATION          blocked    scope_lock is draft
ACT_CUSTOM_ACTION               open       user override
```

The frame should preserve source artifacts verbatim. Action summaries are
navigation and explanation, not replacement truth.

## Relationship to Palantir-Style Ontology

The conceptual mapping is:

```text
Object Type
  -> OAG requirement, contract, module, evidence, decision.

Link Type
  -> OAG source_ref, requirement_ref, obligation_ref, contract_ref, evidence_ref.

Action Type
  -> OAG deep interview, review, RTL implementation, TB implementation,
     lint, simulation, evidence validation, gate review.

Action Log
  -> OAG action instance, dispatch, receipt, decision, ledger event.

Operational objective
  -> OAG mission.
```

OAG should adopt the useful part: actions are first-class operational objects
with preconditions, permissions, side effects, and audit history. OAG should not
copy product-specific Palantir implementation details.

## MVP Implementation Plan

### Phase 1: Static Catalog

Add:

```text
.codex/oag/operation_action_types.yaml
.codex/oag/mission_templates.yaml
.codex/schemas/oag_operation_action_types.schema.json
.codex/schemas/oag_mission_templates.schema.json
.codex/scripts/oag_action_model_check.py
```

Validation:

- catalog IDs are unique;
- owner roles exist in `agent-catalog.toml` or are marked human/main/tool;
- phases are known;
- action types declare inputs, outputs, preconditions, and fallback policy where
  relevant.

### Phase 2: Candidate Generator

Add:

```text
.codex/scripts/oag_action_plan.py
```

It reads current state from existing checks and writes:

```text
<ip>/ontology/generated/action_candidates.json
```

It should initially support:

- scope not locked;
- unresolved lock-required decisions;
- requirement atom check failure;
- contract strength failure;
- stale compile manifest;
- authoring packet failure;
- active wavefront lock;
- stale evidence;
- gate decision stale.

### Phase 3: Run Frame Integration

Update `oag_run_frame.py` to include:

- recommended action candidate;
- up to four action choices;
- blocked actions and reasons;
- mission target state summary;
- custom action slot.

The old hardcoded next action logic can remain as fallback.

Current implementation also adds:

- `oag_action_wavefront_draft.py` for non-executing wavefront task drafts;
- `oag_role_health.py` for stuck/degraded role detection;
- `oag_mission_runtime.py evaluate` for mission-completion criteria;
- operation review frame sections for wavefront drafts, role health, and
  mission completion.

### Phase 4: Durable Action Instances

Add:

```text
.codex/scripts/oag_action_record.py
<ip>/knowledge/actions/
```

Record action instances when a candidate is selected. Link action instances to:

- wavefront run/task;
- dispatch id;
- receipt path;
- review decision;
- evidence/validation artifacts.

### Phase 5: Dispatch and Receipt References

Add optional refs to dispatch creation and receipt verification:

- `mission_instance_ref`;
- `action_candidate_ref`;
- `action_instance_ref`.

These should be additive and backward-compatible.

### Phase 6: Review Frame and Closure Integration

Update review/gate frames to show:

- action history;
- current open candidates;
- blocked actions;
- late receipt or retry state;
- why completion is or is not allowed.

## Acceptance Criteria

The feature is useful only if these questions become easy to answer:

- Why is this action recommended now?
- Which open item does it resolve?
- Which requirement, contract, module, or evidence object does it target?
- Who is allowed to execute it?
- What can it write?
- Which dispatch/receipt/review accepted it?
- What evidence changed because of it?
- If it failed, what fallback policy applied?

The MVP should pass if:

- action type and mission catalogs validate;
- an IP run frame can show action candidates;
- generated candidates are derived, not hand-authored truth;
- existing wavefront/dispatch behavior still works;
- no post-lock write path is opened without dispatch and receipt;
- failed or stuck actions can be explained through action instance history.
