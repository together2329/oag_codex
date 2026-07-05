# Minimal-Mission Architecture Exploration Plan

This document is the implementation plan for turning OAG from a
"bounded loop that stops at every human decision" into a system that can take
one minimal Mission, explore the architecture space with evidence, and come
back to the user with a single consolidated review instead of a stream of
questions.

It is a design plan, not locked product truth. Concrete behavior must still be
implemented through OAG schemas, checks, scripts, hooks, and IP-local evidence.

Related design memos:

- `.codex/oag/self-exploring-ip-agent-plan.md` (vision, autonomy ladder)
- `.codex/oag/mission-action-model.md` (Mission/Action object model)
- `.codex/oag/decision-matrix-policy.md` (decision lifecycle)
- `.codex/oag/bounded-loop-hook-integration-plan.md` (loop/hook integration)

## One-Line Vision

Give the system a minimal Mission plus one human-approved Mission Charter, let
it classify every open decision by autonomy class, explore architecture
candidates with quantitative evidence, provisionally decide what the charter
allows, batch the rest into one checkpoint review, and only then ask the human
to lock.

```text
minimal mission
  -> charter round (human, once, <=5 questions)
    -> autonomous DSE loop (no mid-run questions)
         candidate generation -> tier-1 estimation -> tier-2 micro-bench
         -> prune -> provisional decisions with evidence
    -> consolidated checkpoint (human, once)
    -> scope lock (human, unchanged)
      -> existing implementation missions (unchanged)
```

## Problem Statement

Three gaps prevent minimal-mission operation today.

### Gap 1: No per-decision autonomy policy

`ontology/decision_matrix.yaml` rows only carry `lock_required: bool`. A fact
the agent can cite from the spec, a FIFO depth that should be a parameter, an
architecture tradeoff that measurement can settle, and an irreversible product
decision are all funneled into the same `needs_user` stop:

- `HUMAN_ACTION_TYPES` in `oag_mission_loop.py` and
  `oag_exploration_plan.py` treats every `ACT_RESOLVE_DECISION` as human work.
- `classify_candidate()` (`oag_mission_loop.py`) returns `needs_user` with no
  way to distinguish decision kinds.
- `check_decisions()` (`oag_lock_readiness_check.py`) requires `decided` or
  `waived` and has no notion of an agent-made, evidence-backed decision.

### Gap 2: Architecture candidates are not first-class objects

`oag_exploration_plan.py` defines five option axes (`OPTION_AXES`) and a
research prompt, but exploration output is prose. There is no
`architecture_candidate` object, no schema, no scoreboard, and no way for a
later tick to consume the result of exploration mechanically.
`oag_architecture_options.py` and its schema exist only as planned filenames
in `self-exploring-ip-agent-plan.md`.

### Gap 3: No quantitative comparison harness

`oag_ppa_check.py` is a dialect/style lint, not PPA measurement. Nothing can
say "candidate A costs 18% more area proxy but saves 2 cycles of latency", so
"explore the best architecture" cannot terminate in a defensible selection.

## Design Principles

1. Preserve every existing fail-closed invariant. Scope lock stays human.
   Product-defining decisions stay human. Post-lock writes still require
   dispatch and receipts. `no lock, no RTL` stays true for product RTL.
2. Move human interaction, do not remove it. From "one stop per decision"
   to "one charter up front plus one consolidated checkpoint".
3. Every autonomous decision must be typed, charter-authorized,
   evidence-backed, receipt-recorded, and revertible via IP-local git.
4. Prototype artifacts are evidence, never product. They live under
   `knowledge/arch_exploration/` and never under `rtl/` or `tb/`.
5. All additions are additive and backward compatible. An IP without a
   charter behaves exactly like today.
6. Windows portability rules apply to all new scripts: argv subprocess lists,
   no `shell=True`, no `/bin/sh` or `sh.exe` dependence.

## Target End-To-End Flow

```text
1. User: "make me a <X> IP" + (optionally) spec docs
2. MISSION_INTAKE_TO_RTL_READY starts (unchanged auto-selection)
3. ACT_CHARTER_INTERVIEW: one human form round
   -> ontology/mission_charter.yaml (approved, protected)
4. Mission Loop runs unattended:
   a. self-explore / semantic intake (existing)
   b. decision rows get decision_class assignments
   c. fact rows        -> auto-decided with citations
      parameterizable  -> promoted to parameters
      arch tradeoffs   -> routed to DSE actions
      product-defining -> queued for checkpoint
   d. ACT_ARCH_CANDIDATE_GENERATE -> candidates + tier-1 scores
   e. ACT_ARCH_BENCH_RUN          -> tier-2 measurements (top-N only)
   f. ACT_ARCH_SELECT_AND_DECIDE  -> provisional decisions + receipts,
                                     or top-2 kept for checkpoint
5. ACT_CHECKPOINT_REVIEW: one consolidated human review
   (charter panel + candidate scoreboard + provisional decisions
    + batched residual questions), rendered via extended lock preview frame
6. Human answers residual questions, optionally overrides provisional
   decisions, then locks scope (existing oag.lock, human actor)
7. Existing MISSION_RTL_READY_TO_IMPLEMENTED and later missions run unchanged
```

## Phase 1: Decision Classes and Charter-Scoped Auto-Decide

Goal: make the autonomy ladder from `self-exploring-ip-agent-plan.md`
machine-enforced at the decision-matrix level.

### 1.1 Decision matrix schema extension (additive)

Extend `.codex/schemas/oag_decision_matrix.schema.json` (schema stays
`oag_decision_matrix.v1`; new optional fields):

```yaml
decisions:
  - id: D010_QUEUE_ARCHITECTURE
    question: "Single dual-clock FIFO or per-channel queues?"
    status: decided
    lock_required: true
    owner: agent
    # NEW fields below
    decision_class: architecture_tradeoff
    # fact | parameterizable | architecture_tradeoff | product_defining
    decided_by:
      kind: agent_with_charter        # human | spec | agent_with_charter
      id: oag_mission_loop
      charter_ref: ontology/mission_charter.yaml#AUT_ARCH_TRADEOFF
    provisional: true                  # true until human checkpoint/lock review
    evidence_refs:
      - knowledge/arch_exploration/RUN_.../bench_results.json
      - knowledge/arch_exploration/RUN_.../architecture_scoreboard.json
    decision: per_channel_queues
    rationale: "Wins latency axis at +6% area proxy; charter weights latency 0.4."
```

Classification rules:

- `decision_class` is assigned by intake/interview/profile seeding.
- Missing `decision_class` defaults to `product_defining` (fail-closed;
  unclassified rows behave exactly like today).
- Profiles (`.codex/oag/profiles/*.yaml`) may seed `decision_class` per row.

Class semantics:

| Class | Auto-decide allowed | Required backing |
| --- | --- | --- |
| `fact` | yes (always, charter not needed) | citation refs into spec/RTL/doc |
| `parameterizable` | yes (convert to parameter, not truth) | parameter row + representative-value verify note |
| `architecture_tradeoff` | only with charter grant | quantitative evidence refs + margin rule |
| `product_defining` | never | human answer at checkpoint or immediately |

### 1.2 Lock readiness gate change

`oag_lock_readiness_check.py` `check_decisions()`:

- Accept `status: decided` with `decided_by.kind: agent_with_charter` only if
  all hold:
  - `ontology/mission_charter.yaml` exists, is approved, and grants that
    `decision_class`;
  - `decision_class` is not `product_defining`;
  - `evidence_refs` is non-empty and every ref resolves to an existing file;
  - a decision receipt exists under `knowledge/decisions/`.
- Otherwise the row fails exactly as today.
- `provisional: true` rows do not block lock readiness, but the lock preview
  must display them in a distinct "agent-decided, review before lock" section.

### 1.3 Exploration decision extension

`oag_exploration_plan.py` `infer_decision()` gains one outcome:

```text
existing: idle | self_explore | ask_user | proceed_action
new:      auto_decide
```

`auto_decide` is returned when the recommended candidate is
`ACT_RESOLVE_DECISION`, the target decision row's class is charter-granted,
and either evidence already exists or a DSE action can produce it. The payload
carries `decision_class`, `charter_grant_id`, and the evidence plan.

### 1.4 Mission loop classification change

`oag_mission_loop.py` `classify_candidate()` becomes charter-aware. New
signature takes the loaded charter (or empty dict):

```text
if action_type in HUMAN_ACTION_TYPES:
    row_class = target decision row's decision_class (default product_defining)
    if row_class == fact and citations available          -> "auto_decide"
    if row_class == parameterizable                        -> "auto_decide"
    if row_class == architecture_tradeoff and charter grants
                                                           -> "route_dse"
    if charter question_batching == checkpoint             -> "defer_question"
    else                                                   -> "needs_user"  (today)
```

New tick decisions: `auto_decide`, `route_dse`, `defer_question`. Each still
records an Action instance; nothing becomes invisible.

### 1.5 New helper script

`.codex/scripts/oag_decision_autoresolve.py`:

```bash
python3 .codex/scripts/oag_decision_autoresolve.py \
  --ip-dir <ip> --decision-id D010_QUEUE_ARCHITECTURE \
  --decision "per_channel_queues" \
  --class architecture_tradeoff \
  --evidence knowledge/arch_exploration/RUN_X/bench_results.json \
  --charter-grant AUT_ARCH_TRADEOFF \
  --json
```

Behavior: validates class/charter/evidence, writes the decision row update,
writes a decision receipt under `knowledge/decisions/`, appends a ledger
event, and refreshes the action plan. Refuses `product_defining` rows
unconditionally. Refuses when charter is missing or does not grant the class.

### 1.6 Phase 1 deliverables

```text
modified: .codex/schemas/oag_decision_matrix.schema.json
modified: .codex/scripts/oag_lock_readiness_check.py
modified: .codex/scripts/oag_exploration_plan.py
modified: .codex/scripts/oag_mission_loop.py
new:      .codex/scripts/oag_decision_autoresolve.py
new:      .codex/oag/decision-autonomy-policy.md
new:      .codex/rules/oag-decision-autonomy.rules.md (+ rule-index entries)
```

## Phase 2: Mission Charter

Goal: compress human intent input into one approved, protected artifact that
authorizes bounded autonomy.

### 2.1 Charter artifact

Location: `ontology/mission_charter.yaml` (authored truth, human-approved).
Add its autonomy-grant and objective fields to `ontology/protection.yaml` so
semantic edits require human-approved decisions.

```yaml
schema_version: oag_mission_charter.v1
ip: packet_rx
status: approved            # draft | approved | revoked
approved_by:
  kind: human
  id: user
  at: "2026-07-04T00:00:00Z"

objective: "Best-effort packet RX IP for AXI-Stream ingest, RTL-ready."
target_mission: MISSION_INTAKE_TO_RTL_READY

constraints:
  interfaces_fixed:
    - "input: AXI4-Stream 64b"
  clock_target_mhz: 500
  max_area_proxy_cells: null      # null = unconstrained
  forbidden:
    - "no external memory controller dependency"

objective_weights:                 # used by architecture scoring
  throughput: 0.30
  latency: 0.25
  area_proxy: 0.20
  power_proxy: 0.05
  verification_cost: 0.20

autonomy_grants:
  - id: AUT_FACT
    decision_class: fact
    granted: true
  - id: AUT_PARAM
    decision_class: parameterizable
    granted: true
  - id: AUT_ARCH_TRADEOFF
    decision_class: architecture_tradeoff
    granted: true
    conditions:
      require_tier2_evidence: true
      min_win_margin_pct: 10       # else keep top-2 for checkpoint
  - id: AUT_PRODUCT_DEFINING
    decision_class: product_defining
    granted: false                 # schema forbids true here

question_policy:
  batching: checkpoint             # immediate | checkpoint
  max_deferred_questions: 8        # exceeding forces early checkpoint

budgets:
  max_ticks: 40
  max_candidates_tier1: 8
  max_candidates_tier2: 3
  max_bench_wall_clock_sec: 1800
```

Schema notes:

- `.codex/schemas/oag_mission_charter.schema.json` hard-forbids
  `decision_class: product_defining` with `granted: true`.
- `status != approved` means the charter is inert; everything behaves like
  today.

### 2.2 Charter round

New action type `ACT_CHARTER_INTERVIEW` (phase: intake, owner:
`human_via_main`). Unlike deep-interview rounds, this is a single form, not
one-question-per-round: at most 5 grouped prompts (objective confirmation,
fixed constraints, objective weights, autonomy grants, budgets/question
policy), each with a recommended default so the user can accept in one reply.

New script `.codex/scripts/oag_mission_charter.py`:

```bash
python3 .codex/scripts/oag_mission_charter.py propose --ip-dir <ip> --json
python3 .codex/scripts/oag_mission_charter.py approve --ip-dir <ip> --actor-kind human --json
python3 .codex/scripts/oag_mission_charter.py show    --ip-dir <ip> --json
python3 .codex/scripts/oag_mission_charter.py revoke  --ip-dir <ip> --reason "<why>" --json
```

`propose` seeds a draft charter from the profile, intake report, and mission
template. `approve` requires `actor.kind=human` (same posture as `oag.lock`).
Approval writes a decision receipt and a ledger event.

### 2.3 Planner integration

- `oag_action_plan.py` emits `ACT_CHARTER_INTERVIEW` as a P0 candidate when
  the mission needs autonomy (any open lock-required decision) and no approved
  charter exists. It sits after `ACT_SELF_EXPLORE_OPTIONS` and before
  `ACT_ASK_DEEP_INTERVIEW_QUESTION` in `mission_templates.yaml`
  `action_priority`.
- Charter is optional. If the user declines, the candidate is marked waived
  and the system runs exactly as today.

### 2.4 Phase 2 deliverables

```text
new:      .codex/schemas/oag_mission_charter.schema.json
new:      .codex/scripts/oag_mission_charter.py
new:      .codex/oag/mission-charter-policy.md
modified: .codex/oag/operation_action_types.yaml   (ACT_CHARTER_INTERVIEW)
modified: .codex/oag/mission_templates.yaml        (action_priority insert)
modified: .codex/scripts/oag_action_plan.py        (candidate generation)
modified: ontology/protection.yaml template in oag_scaffold_ip.py
```

## Phase 3: Architecture Candidates and Tier-1 Static Estimation

Goal: make architecture alternatives first-class, comparable objects.

### 3.1 Candidate object

`.codex/schemas/oag_architecture_candidates.schema.json`:

```yaml
schema_version: oag_architecture_candidates.v1
ip: packet_rx
run_id: ARCH_RUN_20260704T000000Z
source_fingerprint: <sha256 of decision matrix + claims + charter>
candidates:
  - id: CAND_001
    label: "Single dual-clock FIFO, shared parser"
    decision_assignments:            # the vector that defines the candidate
      D010_QUEUE_ARCHITECTURE: dual_clock_fifo
      D011_PARSER_SHARING: shared
    parameter_draft:
      FIFO_DEPTH: 64
      DATA_W: 64
    structure_sketch:                # draft, not authored structure.yaml
      modules: [rx_top, rx_fifo, rx_parser]
    axes_notes:                      # maps to OPTION_AXES ids
      AXIS_ARCHITECTURE_PARTITION: "..."
      AXIS_VERIFICATION_EVIDENCE: "..."
    tier1_scores:
      throughput: {value: 1.0, unit: pkt_per_cycle_norm, model: "..."}
      latency:    {value: 6,   unit: cycles, model: "..."}
      area_proxy: {value: 5200, unit: est_bits_state, model: "..."}
      verification_cost: {value: 0.4, unit: norm, model: "oracle-complexity-v1"}
    status: alive                    # alive | pruned | benched | selected
    pruned_reason: ""
```

Storage: `knowledge/arch_exploration/<run_id>/candidates.json` (derived,
regenerable; never hand-edited).

### 3.2 Generation and estimation script

`.codex/scripts/oag_architecture_options.py`:

```bash
python3 .codex/scripts/oag_architecture_options.py generate --ip-dir <ip> --json
python3 .codex/scripts/oag_architecture_options.py estimate --ip-dir <ip> --run-id <id> --json
python3 .codex/scripts/oag_architecture_options.py score    --ip-dir <ip> --run-id <id> --json
```

- `generate`: enumerate candidates from the cartesian product of open
  `architecture_tradeoff` decision rows' options (from decision matrix
  `recommended`/interview options), bounded by
  `charter.budgets.max_candidates_tier1`. Prune combinations violating
  charter `constraints` immediately.
- `estimate`: run registered tier-1 analytical estimators. Initial estimator
  set (deterministic, milliseconds, pure Python):
  - throughput: interface width x clock vs required line rate;
  - latency: pipeline stage count from structure sketch;
  - buffering: burst/backpressure math from claims -> required depth;
  - area proxy: total bits of architectural state + port count heuristic;
  - verification cost: oracle complexity heuristic (state spaces to model,
    ordering guarantees to check, CDC crossings implied).
- `score`: apply `charter.objective_weights` after hard-constraint filtering;
  compute the Pareto front; write
  `knowledge/arch_exploration/<run_id>/architecture_scoreboard.json`
  (`oag_architecture_scoreboard.v1`) with per-axis values, weighted totals,
  Pareto membership, and the win margin between rank-1 and rank-2.

### 3.3 New action types

```text
ACT_ARCH_CANDIDATE_GENERATE  phase: architecture  owner: main/tool  safe
ACT_ARCH_SELECT_AND_DECIDE   phase: architecture  owner: main (charter authority)
```

`ACT_ARCH_SELECT_AND_DECIDE` selection rule:

- rank-1 win margin >= `charter.min_win_margin_pct` and evidence tier
  satisfies charter conditions -> call `oag_decision_autoresolve.py` per
  decision assignment (provisional decided rows + receipts);
- otherwise keep top-2 candidates `alive` and push one comparison question
  (with measured data attached) into the checkpoint queue.

### 3.4 Phase 3 deliverables

```text
new: .codex/schemas/oag_architecture_candidates.schema.json
new: .codex/schemas/oag_architecture_scoreboard.schema.json
new: .codex/scripts/oag_architecture_options.py
new: .codex/oag/architecture-option-policy.md
modified: .codex/oag/operation_action_types.yaml
modified: .codex/scripts/oag_action_plan.py (emit DSE candidates when
          architecture_tradeoff rows are open and charter grants exist)
modified: .codex/scripts/oag_action_model_check.py (catalog validation)
```

## Phase 4: Tier-2 Micro-Prototype Bench

Goal: give the top candidates real measured proxies so selection is defensible.

### 4.1 Bench harness

`.codex/scripts/oag_arch_bench.py`:

```bash
python3 .codex/scripts/oag_arch_bench.py run \
  --ip-dir <ip> --run-id <id> --candidate CAND_001 \
  --adapters yosys,verilator --json
python3 .codex/scripts/oag_arch_bench.py status --ip-dir <ip> --run-id <id> --json
```

Pipeline per candidate:

1. Skeleton RTL generation into
   `knowledge/arch_exploration/<run_id>/<cand_id>/rtl/`. Skeletons implement
   only the architecture-defining structure (queues, pipelines, arbiters,
   port shapes) with stub payload logic. Generation quality matters, so the
   default path dispatches a bounded `oag-rtl-implementation-agent` subagent
   with an explicit prototype dispatch (allowed paths limited to the
   exploration directory, `may_claim_complete=false`); a pure-Python template
   fallback exists for simple candidates.
2. `yosys` adapter: `synth` + `stat` for cell/FF counts (area proxy), optional
   `abc -D <period>` pass/fail at the charter clock target (timing proxy).
3. `verilator` adapter: compile skeleton + generic traffic generator, measure
   cycles/packet, stall cycles under backpressure, latency distribution on a
   representative stimulus profile derived from source claims.
4. Results written as
   `knowledge/arch_exploration/<run_id>/<cand_id>/bench_result.json`
   (`oag_arch_bench_result.v1`): tool versions, source hashes, metrics,
   wall-clock, status.

Tool availability policy: adapters probe for `yosys`/`verilator` on PATH.
Missing tools degrade the run to `status: bench_unavailable` per adapter; the
scoreboard then marks affected axes as tier-1-only, and the auto-decide margin
rule in the charter decides whether tier-1-only evidence is sufficient
(`require_tier2_evidence`). Subprocesses run as argv lists with explicit
timeouts from `charter.budgets`.

### 4.2 Guardrails

- Prototype writes are confined to `knowledge/arch_exploration/`; the bench
  script validates every emitted path against that root (no escapes).
- Prototype RTL is never referenced by `rtl_filelist`, authoring packets, or
  the compile step. `oag_protected_receipt_audit.py` gains a check that no
  product artifact references exploration paths.
- Bench results are evidence objects: hashed, receipt-linked, and cited by
  `evidence_refs` in auto-resolved decision rows.
- Selected-candidate skeletons may inform the authored
  `ontology/structure.yaml` and `ontology/decomposition.yaml`, but post-lock
  product RTL is always re-implemented through the normal authoring-packet
  and dispatch path, never copied wholesale from the prototype.

### 4.3 New action type

```text
ACT_ARCH_BENCH_RUN  phase: architecture  owner: dispatch (RTL skeleton)
                    or main/tool (adapter execution)  writes: knowledge only
```

### 4.4 Phase 4 deliverables

```text
new: .codex/scripts/oag_arch_bench.py
new: .codex/schemas/oag_arch_bench_result.schema.json
new: .codex/oag/arch-bench-policy.md
modified: .codex/oag/operation_action_types.yaml
modified: .codex/scripts/oag_protected_receipt_audit.py
modified: .codex/scripts/oag_windows_smoke.py (cover new subprocess calls)
```

## Phase 5: Checkpoint Batching and Consolidated Review

Goal: replace "stop per question" with "keep working, present once".

### 5.1 Pending question queue

New state file `knowledge/mission_loop/pending_questions.json`
(`oag_pending_questions.v1`):

```yaml
schema_version: oag_pending_questions.v1
ip: packet_rx
questions:
  - id: PQ_001
    source_candidate_id: ACT_CAND_..._ACT_RESOLVE_DECISION_D003
    decision_id: D003_BYTE_ORDERING
    decision_class: product_defining
    deferred_at: "..."
    question: "..."
    options: [...]                  # standard 4-option + custom shape
    attached_evidence: []           # e.g. bench comparisons for tradeoffs
status: accumulating                # accumulating | checkpoint_ready | flushed
```

### 5.2 Mission loop changes

`oag_mission_loop.py`:

- New tick decision `defer_question`: enqueue into pending questions, mark the
  candidate deferred, and re-plan. Requires `oag_action_plan.build_plan()` to
  support an exclusion list (`--exclude-candidates`) so the next-ranked
  non-deferred candidate surfaces.
- `run_loop()` break set changes: `defer_question` does not break;
  `checkpoint_ready` (new) does. `needs_user` still breaks (it now only occurs
  with `question_policy.batching: immediate` or no charter).
- Checkpoint trigger conditions (any):
  - no runnable non-human candidate remains;
  - `len(pending_questions) >= charter.max_deferred_questions`;
  - any charter budget exhausted (`max_ticks`, bench wall clock);
  - DSE finished with a non-dominant top candidate (comparison question).
- Speculative dual-branch rule: when exactly one deferred `product_defining`
  decision blocks candidate generation, `generate` may fork candidates for
  each of its options (bounded by tier-1 budget) so the checkpoint presents
  measured consequences per option instead of an abstract question.

### 5.3 Consolidated review surface

New action type `ACT_CHECKPOINT_REVIEW` (owner: `human_via_main`). Rendering
extends the existing formal-review machinery rather than inventing a new one:

- `oag_lock_preview_frame.py` gains panels: approved charter (verbatim),
  architecture scoreboard table with tier-1/tier-2 evidence links, provisional
  agent decisions (distinct section, per-row evidence + receipts + revert
  hint), and the batched question list in priority order.
- The chat-side presentation batches questions as one structured form (the
  deep-interview one-question rule applies to interactive rounds, not to the
  checkpoint form; document this exception in
  `.codex/oag/mission-charter-policy.md` and the deep-interview prompt guard
  stays silent for checkpoint forms).
- Human outcomes per item: answer, accept provisional decision, override
  provisional decision (flips row back to human-decided), or send back to
  exploration. Answers flow through the existing
  `oag_deep_interview_round.py handoff` path so decision-matrix writes,
  receipts, and plan refresh stay uniform.

### 5.4 Phase 5 deliverables

```text
new:      .codex/schemas/oag_pending_questions.schema.json
modified: .codex/scripts/oag_mission_loop.py
modified: .codex/scripts/oag_action_plan.py     (candidate exclusion)
modified: .codex/scripts/oag_lock_preview_frame.py
modified: .codex/oag/operation_action_types.yaml (ACT_CHECKPOINT_REVIEW)
modified: .codex/hooks/codex_deep_interview_prompt_guard.py (checkpoint form
          exemption)
```

## Mission Template and Catalog Changes (Summary)

`mission_templates.yaml` `MISSION_INTAKE_TO_RTL_READY`:

```text
action_priority (new order, additions marked +):
  ACT_RESOLVE_ORCHESTRATION_HAZARD
  ACT_ORCHESTRATION_RECOVERY
  ACT_RESOLVE_PENDING_GATE
  ACT_SELF_EXPLORE_OPTIONS
+ ACT_CHARTER_INTERVIEW
  ACT_CAPTURE_SOURCE_CLAIM
+ ACT_ARCH_CANDIDATE_GENERATE
+ ACT_ARCH_BENCH_RUN
+ ACT_ARCH_SELECT_AND_DECIDE
  ACT_ASK_DEEP_INTERVIEW_QUESTION
  ACT_RESOLVE_DECISION
+ ACT_CHECKPOINT_REVIEW
  ACT_REPAIR_SSOT_SECTION
  ... (rest unchanged)

target_state additions:
  mission_charter: approved_or_waived
  architecture_exploration: complete_or_waived
```

`operation_action_types.yaml` additions: `ACT_CHARTER_INTERVIEW`,
`ACT_ARCH_CANDIDATE_GENERATE`, `ACT_ARCH_BENCH_RUN`,
`ACT_ARCH_SELECT_AND_DECIDE`, `ACT_CHECKPOINT_REVIEW`, each with phase, owner
role, consumes/produces, preconditions, and fallback policy, validated by
`oag_action_model_check.py`.

No new mission template is required; `default_mission()` stays unchanged.

## Test Plan

Unit/scenario tests (extend `oag_eval.py` scenarios and `smoke_test.py`):

Phase 1:

- `product_defining` rows are never auto-decided, even with a charter.
- Missing `decision_class` behaves as `product_defining`.
- No charter (or `status != approved`) reproduces today's behavior bit-for-bit
  on existing eval scenarios.
- Lock readiness rejects agent-decided rows with missing/dangling
  `evidence_refs` or missing receipts.
- `oag_decision_autoresolve.py` writes row + receipt + ledger atomically and
  refuses ungranted classes.

Phase 2:

- Charter schema rejects `product_defining: granted true`.
- `approve` requires human actor; `revoke` disables all auto-decide paths on
  the next tick.
- Charter fields are protected: semantic edits without human decision receipts
  fail protection checks.

Phase 3:

- Candidate generation respects budgets and constraint pruning.
- Tier-1 estimators are deterministic for a fixed fingerprint.
- Scoreboard win-margin math and Pareto membership have fixed-vector tests.
- `ACT_ARCH_SELECT_AND_DECIDE` auto-decides only above the margin threshold;
  below it, exactly one comparison question lands in the queue.

Phase 4:

- Bench path guard rejects any emitted path outside
  `knowledge/arch_exploration/`.
- Missing yosys/verilator degrades to `bench_unavailable` without failing the
  mission loop; `require_tier2_evidence: true` then blocks auto-decide.
- Product artifacts referencing exploration paths fail the protected receipt
  audit.
- `oag_windows_smoke.py` passes (no `shell=True`, argv subprocess lists).

Phase 5:

- `defer_question` does not break `run_loop()`; `checkpoint_ready` does.
- Queue overflow and budget exhaustion both force checkpoint.
- Checkpoint answers route through `handoff` and clear the queue
  (`status: flushed`).
- Override at checkpoint flips `decided_by` to human and drops `provisional`.

End-to-end acceptance scenario (dry-run with stub estimators/adapters):

```text
scaffold IP -> approve charter -> mission loop run --max-ticks 40
expect: zero needs_user stops, >=1 auto-decided fact row,
        >=1 parameterized row, arch candidates generated and scored,
        checkpoint_ready with consolidated frame rendered,
        all provisional decisions carrying class+charter+evidence+receipt
```

## Risks and Mitigations

| Risk | Mitigation |
| --- | --- |
| Proxy metrics mislead (yosys cells != real area; skeleton != real timing) | Use proxies for ranking only, never absolute claims; record tool versions and margins; charter margin threshold gates auto-decide; below margin -> human comparison question with data |
| Prototype RTL leaks into product | Path confinement in bench script; protected receipt audit check; product RTL always re-authored via packets/dispatch |
| Charter over-grants autonomy | Schema forbids product-defining grants; default-deny for absent grants; charter approval is human; charter fields protected |
| Question starvation / user surprise at checkpoint size | `max_deferred_questions` cap; budget-exhaustion checkpoint; checkpoint frame ranks questions by lock impact |
| Candidate-space explosion | Tier-1 budget (default 8), tier-2 budget (default 3), constraint pruning before estimation, Pareto pruning before bench |
| Skeleton generation stalls (subagent hang) | Existing orchestration guard + role health cover dispatched skeleton work; template fallback for simple candidates |
| Backward-compatibility regression | Charter-absent path must pass the entire existing eval suite unchanged; all schema changes additive |

## Explicitly Out of Scope

- Real signoff PPA (synthesis/STA/power signoff) — proxies only.
- Auto scope lock. `oag.lock` remains human-only.
- Unattended post-lock implementation changes — existing missions,
  dispatch, receipts, and gates are unchanged.
- Multi-IP fleet orchestration and cross-IP resource scheduling.
- Web research during DSE (local sources only; `oag_exec_auto_research.py`
  integration can be a later addition).

## Rollout Order and Dependencies

```text
Phase 1  Decision classes + auto-decide      (no deps; largest stop-count win)
Phase 2  Mission charter                     (depends on 1 for grant checks)
Phase 3  Candidates + tier-1 + scoreboard    (depends on 2 for weights/budgets)
Phase 5  Checkpoint batching + review frame  (depends on 1,2; independent of 3/4;
                                              can be pulled before 3 for UX win)
Phase 4  Tier-2 bench harness                (depends on 3; heaviest build)
```

Each phase lands with its tests, passes
`python3 .codex/scripts/oag_pack_release_check.py`,
`python3 .codex/scripts/smoke_test.py`,
`python3 .codex/scripts/oag_eval.py --json`, and
`python3 .codex/scripts/oag_windows_smoke.py --json`, and updates the
`.codex/AGENTS.md` asset list plus `rules/oag-rule-index.yaml` for any new
policy/rule/checker triple.

## Acceptance Criteria

The plan is done when:

- a minimal mission plus one approved charter runs the intake mission to
  `checkpoint_ready` with zero mid-run `needs_user` stops when local sources
  exist;
- every agent-made decision row carries `decision_class`, charter grant ref,
  resolving `evidence_refs`, a decision receipt, and `provisional: true`;
- architecture selection cites a scoreboard with tier-1 (and where available
  tier-2) measurements, and non-dominant outcomes surface as one measured
  comparison question instead of silent defaults;
- the consolidated checkpoint frame shows charter, scoreboard, provisional
  decisions, and batched questions with verbatim source preservation;
- scope lock, product-defining decisions, post-lock dispatch/receipt gates,
  and the full existing eval suite are unchanged and passing.
