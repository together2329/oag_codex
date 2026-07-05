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
it classify every open decision by autonomy class, keep reversible values open
as parameters and generated variants, settle measured tradeoffs by benchmark,
batch only irreversible or externally visible decisions into one checkpoint
review, clean up the exploration residue, and only then ask the human to lock.

```text
minimal mission
  -> charter round (human, once, <=5 grouped prompts)
    -> autonomous DSE loop (no mid-run questions)
         classify decisions -> parameterize / generate-option / measure
         -> candidate + sweep generation -> tier-1 estimation
         -> tier-2 micro-bench (worktree-isolated when non-trivial)
         -> prune -> provisional defaults with evidence
    -> consolidated checkpoint (human, once)
    -> promote selected candidate, clean up exploration residue
    -> scope lock (human, unchanged)
      -> existing implementation missions (unchanged)
```

## Operating Philosophy

Six rules govern every mechanism in this plan:

```text
1. Ask less.
2. Parameterize reversible values.
3. Preserve structural alternatives as generate options during exploration.
4. Settle measured tradeoffs by benchmark, not by asking.
5. Checkpoint only irreversible or externally visible decisions.
6. Clean up before scope lock.
```

Normative statement (goes into the policy doc verbatim):

> The agent must not ask the human for every unknown design value. If a
> decision can be safely represented as a parameter, synthesis-time option, or
> generated implementation variant, the agent should encode it as such, attach
> evidence and bounds, and continue the autonomous exploration loop. Only
> decisions that change external contracts, software-visible behavior,
> irreversible architecture boundaries, safety/security semantics, clock/reset
> architecture, CDC/RDC boundaries, or verification signoff criteria must be
> escalated to the consolidated checkpoint.

The old flow turned every unknown into a human stop:

```text
value unknown -> agent stops -> user answers -> continue
```

The target flow keeps the loop moving:

```text
value unknown
  -> represent as parameter / generate option
  -> pick a safe default from evidence (sweep, bench, citation)
  -> record decision + receipt + rollback path
  -> show it at the checkpoint, not as a blocking question
```

OAG must not become a question generator. Most internal design values are
explorable design variables, not questions a human must answer immediately.
Exploration keeps many doors open; evidence picks defaults; cleanup closes the
doors that were never product intent before lock.

## Problem Statement

Three gaps prevent minimal-mission operation today.

### Gap 1: No per-decision autonomy policy

`ontology/decision_matrix.yaml` rows only carry `lock_required: bool`. A fact
the agent can cite from the spec, a FIFO depth that should be a swept
parameter, an architecture tradeoff that measurement can settle, and an
irreversible external-contract decision are all funneled into the same
`needs_user` stop:

- `HUMAN_ACTION_TYPES` in `oag_mission_loop.py` and
  `oag_exploration_plan.py` treats every `ACT_RESOLVE_DECISION` as human work.
- `classify_candidate()` (`oag_mission_loop.py`) returns `needs_user` with no
  way to distinguish decision kinds.
- `check_decisions()` (`oag_lock_readiness_check.py`) requires `decided` or
  `waived` and has no notion of an agent-made, evidence-backed decision.

`lock_required: true` alone cannot tell the runtime what the agent is allowed
to do with the row.

### Gap 2: Architecture candidates are not first-class objects

`oag_exploration_plan.py` defines five option axes (`OPTION_AXES`) and a
research prompt, but exploration output is prose. There is no
`architecture_candidate` object, no schema, no scoreboard, no parameter sweep
record, and no way for a later tick to consume the result of exploration
mechanically. `oag_architecture_options.py` and its schema exist only as
planned filenames in `self-exploring-ip-agent-plan.md`.

### Gap 3: No quantitative comparison harness

`oag_ppa_check.py` is a dialect/style lint, not PPA measurement. Nothing can
say "candidate A costs 18% more area proxy but saves 2 cycles of latency" or
"depth 8 already saturates throughput for this workload", so "explore the best
architecture" cannot terminate in a defensible selection.

## Design Principles

1. Preserve every existing fail-closed invariant. Scope lock stays human.
   External-contract decisions stay human. Post-lock writes still require
   dispatch and receipts. `no lock, no RTL` stays true for product RTL:
   pre-lock exploration artifacts never live under `rtl/` or `tb/`.
2. Move human interaction, do not remove it. From "one stop per decision"
   to "one charter up front plus one consolidated checkpoint".
3. Internal reversible choice -> agent may decide provisionally.
   External irreversible contract -> human checkpoint required.
   This is the load-bearing invariant of the whole plan.
4. An agent statement without evidence is not a decision. Every autonomous
   decision must carry: candidate set, measurement command or citation,
   metrics, comparison, selection rule, artifact paths, receipt, and a
   rollback path. "8 looks good" is never a decision.
5. Exploration is wide, truth is narrow. During exploration, parameters and
   generated variants may proliferate; before lock, a mandatory cleanup pass
   collapses non-product parameters, deletes unselected variants, and keeps
   only options that are also verification targets.
6. All additions are additive and backward compatible. An IP without a
   charter behaves exactly like today.
7. Windows portability rules apply to all new scripts: argv subprocess lists,
   no `shell=True`, no `/bin/sh` or `sh.exe` dependence. `git worktree` runs
   through the same argv `git.exe` discovery as `oag_ip_git.py`.

## Target End-To-End Flow

```text
1. User: "make me a <X> IP" + (optionally) spec docs
2. MISSION_INTAKE_TO_RTL_READY starts (unchanged auto-selection)
3. ACT_CHARTER_INTERVIEW: one human form round
   -> ontology/mission_charter.yaml (approved, protected)
4. Mission Loop runs unattended:
   a. self-explore / semantic intake (existing)
   b. decision rows get autonomy_class + resolution_strategy assignments
   c. fact rows                -> auto-decided with citations
      reversible_internal rows -> parameter / generate option, default from
                                  evidence
      measured_tradeoff rows   -> routed to DSE sweep/bench actions
      external_contract rows   -> queued for checkpoint
   d. ACT_ARCH_CANDIDATE_GENERATE -> candidates + parameter sweeps
                                     + tier-1 scores
   e. ACT_ARCH_BENCH_RUN          -> tier-2 measurements (top-N only,
                                     worktree-isolated when non-trivial)
   f. ACT_ARCH_SELECT_AND_DECIDE  -> provisional defaults + receipts,
                                     or top-2 kept for checkpoint
5. ACT_CHECKPOINT_REVIEW: one consolidated human review
   (charter panel + candidate scoreboard + sweep curves + provisional
    decisions + batched irreversible questions), rendered via extended
    lock preview frame
6. Human answers residual questions, accepts or overrides provisional
   decisions, approves the selected candidate
7. ACT_EXPLORATION_CLEANUP: promote selected candidate into authored truth,
   collapse exploration parameters, delete unselected variants, prune
   worktrees; cleanup check must pass
8. Lock preview regenerated from cleaned truth -> scope lock
   (existing oag.lock, human actor)
9. Existing MISSION_RTL_READY_TO_IMPLEMENTED and later missions run unchanged
```

## Phase 1: Decision Autonomy Model and Charter-Scoped Auto-Decide

Goal: make the autonomy ladder from `self-exploring-ip-agent-plan.md`
machine-enforced at the decision-matrix level.

### 1.1 Orthogonal decision model

The model deliberately separates four orthogonal dimensions instead of one
flat enum. "Provisional" is a flag, not a class; "locked" is the existing
lifecycle plus scope lock, not a class. Mixing nature, strategy, and state in
one field would make the runtime unable to answer "what may the agent do with
this row" without special cases.

```text
autonomy_class       what kind of decision this is (nature)
resolution_strategy  how it gets resolved (mechanism)
representation       where the answer lives (truth / parameter / generate option)
status + flags       lifecycle (existing) + provisional flag
```

Extend `.codex/schemas/oag_decision_matrix.schema.json` (schema stays
`oag_decision_matrix.v1`; new optional fields):

```yaml
decisions:
  - id: D021_CMD_FIFO_DEPTH
    question: "Command FIFO depth?"
    status: decided
    lock_required: true
    owner: agent
    # NEW fields below
    autonomy_class: measured_tradeoff
    # fact | reversible_internal | measured_tradeoff | external_contract
    resolution_strategy: parameterized_default
    # cite_sources | parameterize | generate_option | measure_and_select
    # | parameterized_default | defer_to_checkpoint | ask_immediately
    representation: parameter        # truth | parameter | generate_option
    candidate_values: [2, 4, 8, 16, 32]
    selected_value: 8
    selection_rule: smallest_satisfying_with_margin
    external_contract_impact: none   # none | indirect | direct
    rollback_cost: low               # low | medium | high
    evidence_required:
      - tier2_microbench
    decided_by:
      kind: agent_with_charter       # human | spec | agent_with_charter
      id: oag_mission_loop
      charter_ref: ontology/mission_charter.yaml#AUT_MEASURED_TRADEOFF
    provisional: true                # true until checkpoint/lock review
    evidence_refs:
      - knowledge/arch_exploration/RUN_.../sweeps/CMD_FIFO_DEPTH.json
    decision: "CMD_FIFO_DEPTH parameter, default 8"
    rationale: "Throughput saturates at depth 8 under worst-case burst
      workload; 16/32 add area with no measured gain."
```

### 1.2 Class semantics

| `autonomy_class` | Meaning | Typical strategies | Auto allowed | Escalation |
| --- | --- | --- | --- | --- |
| `fact` | Answer exists in spec/RTL/doc | `cite_sources` | always (charter not needed) | never |
| `reversible_internal` | Internal value or structure, cheap to change later | `parameterize`, `generate_option`, `parameterized_default` | with charter grant | only when external impact is detected |
| `measured_tradeoff` | Benchmark/evidence can settle it | `measure_and_select`, `parameterized_default` | charter grant + required evidence + win margin | below margin -> measured comparison question at checkpoint |
| `external_contract` | Changes what integrators, software, or signoff can observe | `defer_to_checkpoint`, `ask_immediately` | never | always human |

Classification rules:

- `autonomy_class` is assigned by intake/interview/profile seeding.
- Missing `autonomy_class` defaults to `external_contract` (fail-closed;
  unclassified rows behave exactly like today).
- `external_contract_impact: direct` forces checkpoint escalation regardless
  of class or grant. An internal value becomes external the moment it affects
  externally observable behavior.
- Profiles (`.codex/oag/profiles/*.yaml`) may seed `autonomy_class` and
  `resolution_strategy` per row.

### 1.3 Checkpoint escalation list

These always escalate to the checkpoint (or an immediate question when
`question_policy.batching: immediate`); no charter can grant them:

- external protocol semantics;
- software-visible register map and field behavior;
- interrupt behavior;
- reset / clock architecture;
- CDC / RDC boundaries;
- security / privilege / isolation policy;
- externally visible queue or buffer capacity;
- integration contracts (ports, bus bindings, memory maps, parameter
  contracts published through IP-XACT projection);
- verification signoff criteria.

These may be decided by the agent without checkpoint (given charter grant and
evidence), as long as external impact stays `none`:

- internal FIFO / skid buffer depths;
- internal pipeline stage counts;
- arbitration defaults;
- non-visible outstanding counts;
- internal optimization options.

External-impact detection heuristic (mechanical, used by checks): a value is
`direct` when it feeds port widths, register map fields, interrupt semantics,
documented capacities, IP-XACT projection entries, or clock/reset/CDC
structure; `indirect` when it changes timing-observable behavior on external
interfaces (for example, backpressure onset point); otherwise `none`.
`indirect` requires the checkpoint to display the decision prominently but
does not force a blocking question.

Buffering values get an explicit normative statement (goes into the policy doc
verbatim):

> FIFO depths, queue sizes, skid buffers, outstanding counts, and similar
> buffering parameters are measured tradeoff decisions. The agent should sweep
> a bounded candidate set, run representative workloads, select the smallest
> value that satisfies the mission performance target with margin, and keep
> the chosen value as a parameterized default. The decision is escalated only
> when the value changes software-visible capacity, externally observable
> protocol behavior, or an integration contract.

The point of `smallest_satisfying_with_margin`: the goal is never "largest
depth" or "absolute best number". If depth 8, 16, and 32 measure the same
throughput and 8 already saturates, 8 is the better default.

### 1.4 Lock readiness gate change

`oag_lock_readiness_check.py` `check_decisions()`:

- Accept `status: decided` with `decided_by.kind: agent_with_charter` only if
  all hold:
  - `ontology/mission_charter.yaml` exists, is approved, and grants that
    `autonomy_class`;
  - `autonomy_class` is not `external_contract`;
  - `external_contract_impact` is not `direct`;
  - every entry in `evidence_required` is satisfied by a resolving entry in
    `evidence_refs`, and every ref resolves to an existing file;
  - a decision receipt exists under `knowledge/decisions/`.
- Otherwise the row fails exactly as today.
- `provisional: true` rows do not block lock readiness, but the checkpoint and
  lock preview must display them in a distinct "agent-decided, review before
  lock" section.

### 1.5 Exploration decision extension

`oag_exploration_plan.py` `infer_decision()` gains outcomes:

```text
existing: idle | self_explore | ask_user | proceed_action
new:      auto_decide | route_dse
```

- `auto_decide`: recommended candidate is `ACT_RESOLVE_DECISION`, the target
  row's class is charter-granted, and evidence already exists (citation for
  `fact`, sweep/bench results for tradeoffs).
- `route_dse`: class is granted but required evidence does not exist yet; the
  payload carries the sweep/bench plan that would produce it.

### 1.6 Mission loop classification change

`oag_mission_loop.py` `classify_candidate()` becomes charter-aware. New
signature takes the loaded charter (or empty dict):

```text
if action_type in HUMAN_ACTION_TYPES:
    row = target decision row
    cls = row.autonomy_class (default external_contract)
    if row.external_contract_impact == direct       -> defer/ask (human path)
    if cls == fact and citations available          -> "auto_decide"
    if cls == reversible_internal and granted       -> "auto_decide"
                                                        (parameter/option rep)
    if cls == measured_tradeoff and granted:
        evidence satisfied                          -> "auto_decide"
        else                                        -> "route_dse"
    if charter question_policy.batching == checkpoint -> "defer_question"
    else                                              -> "needs_user"  (today)
```

New tick decisions: `auto_decide`, `route_dse`, `defer_question`. Each still
records an Action instance; nothing becomes invisible.

### 1.7 New helper script

`.codex/scripts/oag_decision_autoresolve.py`:

```bash
python3 .codex/scripts/oag_decision_autoresolve.py \
  --ip-dir <ip> --decision-id D021_CMD_FIFO_DEPTH \
  --decision "CMD_FIFO_DEPTH parameter, default 8" \
  --autonomy-class measured_tradeoff \
  --resolution-strategy parameterized_default \
  --representation parameter \
  --selected-value 8 \
  --evidence knowledge/arch_exploration/RUN_X/sweeps/CMD_FIFO_DEPTH.json \
  --charter-grant AUT_MEASURED_TRADEOFF \
  --json
```

Behavior: validates class/charter/evidence/external-impact, writes the
decision row update, writes a decision receipt under `knowledge/decisions/`
(receipt must contain candidate set, measurement command, metrics, comparison,
selection rule, artifact paths, and rollback path), appends a ledger event,
and refreshes the action plan. Refuses `external_contract` rows and
`external_contract_impact: direct` rows unconditionally. Refuses when the
charter is missing, revoked, or does not grant the class. Refuses when any
`evidence_required` entry has no resolving artifact.

### 1.8 Phase 1 deliverables

```text
modified: .codex/schemas/oag_decision_matrix.schema.json
modified: .codex/scripts/oag_lock_readiness_check.py
modified: .codex/scripts/oag_exploration_plan.py
modified: .codex/scripts/oag_mission_loop.py
new:      .codex/scripts/oag_decision_autoresolve.py
new:      .codex/schemas/oag_decision_receipt_dse.schema.json (receipt shape)
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
    autonomy_class: fact
    granted: true
  - id: AUT_REVERSIBLE_INTERNAL
    autonomy_class: reversible_internal
    granted: true
  - id: AUT_MEASURED_TRADEOFF
    autonomy_class: measured_tradeoff
    granted: true
    conditions:
      require_tier2_evidence: true
      min_win_margin_pct: 10       # else keep top-2 for checkpoint
  - id: AUT_EXTERNAL_CONTRACT
    autonomy_class: external_contract
    granted: false                 # schema forbids true here

question_policy:
  batching: checkpoint             # immediate | checkpoint
  max_deferred_questions: 8        # exceeding forces early checkpoint

budgets:
  max_ticks: 40
  max_candidates_tier1: 8
  max_candidates_tier2: 3
  max_sweep_points_per_parameter: 6
  max_worktrees: 4
  max_bench_wall_clock_sec: 1800
```

Schema notes:

- `.codex/schemas/oag_mission_charter.schema.json` hard-forbids
  `autonomy_class: external_contract` with `granted: true`.
- `status != approved` means the charter is inert; everything behaves like
  today. `revoked` disables all auto-decide and DSE routing on the next tick.

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

## Phase 3: Architecture Candidates, Parameter Sweeps, and Tier-1 Estimation

Goal: make architecture alternatives and swept parameters first-class,
comparable objects.

### 3.1 Candidate object

A candidate is defined by three vectors: structural decision assignments,
generate-option selections, and a parameter point. Structural variants that
can share one skeleton become generate options of the same skeleton; variants
that cannot become separate candidates.

`.codex/schemas/oag_architecture_candidates.schema.json`:

```yaml
schema_version: oag_architecture_candidates.v1
ip: packet_rx
run_id: ARCH_RUN_20260704T000000Z
source_fingerprint: <sha256 of decision matrix + claims + charter>
candidates:
  - id: CAND_001
    label: "Dual-clock FIFO, shared parser, fast path on"
    decision_assignments:            # structural decision vector
      D010_QUEUE_ARCHITECTURE: dual_clock_fifo
      D011_PARSER_SHARING: shared
    generate_options:                # synthesis-time variant selections
      ENABLE_FAST_PATH: 1
    parameter_point:                 # one point of the sweep space
      CMD_FIFO_DEPTH: 8
      DATA_W: 64
    sweep_refs:                      # sweep curves this point came from
      - sweeps/CMD_FIFO_DEPTH.json
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
    isolation: directory             # directory | worktree (assigned in tier 2)
    status: alive                    # alive | pruned | benched | selected
    pruned_reason: ""
```

Storage: `knowledge/arch_exploration/<run_id>/candidates.json` (derived,
regenerable; never hand-edited).

### 3.2 Parameter sweep record

Swept parameters (`resolution_strategy: parameterized_default`) get a durable
sweep artifact per parameter:

```yaml
schema_version: oag_parameter_sweep.v1
parameter: CMD_FIFO_DEPTH
decision_ref: D021_CMD_FIFO_DEPTH
candidate_values: [2, 4, 8, 16, 32]
workloads: [worst_case_burst, sustained_line_rate, backpressure_50pct]
points:
  - value: 8
    metrics: {throughput_norm: 0.99, stall_cycles: 12, area_proxy: 512}
selection_rule: smallest_satisfying_with_margin
selected_value: 8
margin_note: "0.99 vs target 0.95; depth 16 measured 0.99 (no gain)."
```

Storage: `knowledge/arch_exploration/<run_id>/sweeps/<parameter>.json`. The
sweep artifact is the `evidence_refs` target for the auto-resolved decision
row, and the checkpoint renders it as a saturation curve.

### 3.3 Generation and estimation script

`.codex/scripts/oag_architecture_options.py`:

```bash
python3 .codex/scripts/oag_architecture_options.py generate --ip-dir <ip> --json
python3 .codex/scripts/oag_architecture_options.py estimate --ip-dir <ip> --run-id <id> --json
python3 .codex/scripts/oag_architecture_options.py score    --ip-dir <ip> --run-id <id> --json
```

- `generate`: enumerate candidates from open `measured_tradeoff` and
  `reversible_internal` structural rows (options from decision matrix
  `recommended`/interview options), fold sweepable parameters into per-
  candidate sweep plans, bounded by `charter.budgets.max_candidates_tier1`
  and `max_sweep_points_per_parameter`. Prune combinations violating charter
  `constraints` immediately.
- `estimate`: run registered tier-1 analytical estimators. Initial estimator
  set (deterministic, milliseconds, pure Python):
  - throughput: interface width x clock vs required line rate;
  - latency: pipeline stage count from structure sketch;
  - buffering: burst/backpressure math from claims -> required depth range
    (narrows the sweep before any bench runs);
  - area proxy: total bits of architectural state + port count heuristic;
  - verification cost: oracle complexity heuristic (state spaces to model,
    ordering guarantees to check, CDC crossings implied, plus a penalty per
    retained generate option since each retained option multiplies the
    verification matrix).
- `score`: apply `charter.objective_weights` after hard-constraint filtering;
  compute the Pareto front; write
  `knowledge/arch_exploration/<run_id>/architecture_scoreboard.json`
  (`oag_architecture_scoreboard.v1`) with per-axis values, weighted totals,
  Pareto membership, and the win margin between rank-1 and rank-2.

### 3.4 New action types

```text
ACT_ARCH_CANDIDATE_GENERATE  phase: architecture  owner: main/tool  safe
ACT_ARCH_SELECT_AND_DECIDE   phase: architecture  owner: main (charter authority)
```

`ACT_ARCH_SELECT_AND_DECIDE` selection rule:

- rank-1 win margin >= `charter.min_win_margin_pct` and evidence tier
  satisfies charter conditions -> call `oag_decision_autoresolve.py` per
  decision assignment and per swept parameter (provisional decided rows +
  receipts);
- otherwise keep top-2 candidates `alive` and push one comparison question
  (with measured data attached) into the checkpoint queue.

### 3.5 Phase 3 deliverables

```text
new: .codex/schemas/oag_architecture_candidates.schema.json
new: .codex/schemas/oag_architecture_scoreboard.schema.json
new: .codex/schemas/oag_parameter_sweep.schema.json
new: .codex/scripts/oag_architecture_options.py
new: .codex/oag/architecture-option-policy.md
modified: .codex/oag/operation_action_types.yaml
modified: .codex/scripts/oag_action_plan.py (emit DSE candidates when granted
          tradeoff rows are open)
modified: .codex/scripts/oag_action_model_check.py (catalog validation)
```

## Phase 4: Tier-2 Micro-Prototype Bench with Worktree Isolation

Goal: give the top candidates real measured proxies so selection is
defensible, without candidates contaminating each other or the main tree.

### 4.1 Isolation tiers

Normative statement (goes into the policy doc verbatim):

> Architecture candidates should be isolated using git worktrees whenever they
> require non-trivial RTL, configuration, or testbench changes. Each candidate
> worktree must produce a candidate receipt, evidence artifacts, benchmark
> results, and a diff summary. Rejected worktrees may be discarded; the
> selected candidate may be promoted or merged after checkpoint approval.

Two tiers, chosen per candidate and recorded in the candidate's `isolation`
field:

- **Tier A: directory isolation.** Skeleton-only candidates and pure
  parameter/define sweeps over one shared skeleton. Artifacts live under
  `knowledge/arch_exploration/<run_id>/<cand_id>/`. Cheap, default.
- **Tier B: worktree isolation.** Candidates that must touch shared files
  (filelists, TB config, common includes) or run full lint/sim flows. Each
  candidate gets an IP-local git worktree and branch:

```text
<ip>/.oag_worktrees/<cand_id>/          (git-ignored root)
branch: oag/dse/<mission_id>/<cand_id>
```

Worktree lifecycle per candidate:

```text
create worktree + branch
  -> generate/modify candidate RTL, config, bench TB
  -> run lint / sim / bench adapters inside the worktree
  -> write report.json + candidate receipt + diff summary
  -> copy receipts, reports, and metrics back to
     knowledge/arch_exploration/<run_id>/<cand_id>/ in the main tree
  -> prune worktree; delete or tag the branch
```

The main tree only ever collects results. Candidate changes never mix,
rejected candidates are dropped by pruning the worktree, and the checkpoint
comparison table is built from copied-back reports plus branch diff summaries.

New helper `.codex/scripts/oag_dse_worktree.py`:

```bash
python3 .codex/scripts/oag_dse_worktree.py create --ip-dir <ip> --run-id <id> --candidate CAND_001 --json
python3 .codex/scripts/oag_dse_worktree.py list   --ip-dir <ip> --json
python3 .codex/scripts/oag_dse_worktree.py prune  --ip-dir <ip> --candidate CAND_001 --json
python3 .codex/scripts/oag_dse_worktree.py prune-all --ip-dir <ip> --run-id <id> --json
```

Guard rules: worktree roots must stay under `<ip>/.oag_worktrees/`; the root
is added to the managed IP-local `.gitignore`; `create` is refused beyond
`charter.budgets.max_worktrees`; stale worktrees (no heartbeat/receipt beyond
the stale threshold) are surfaced as orchestration hazards by the existing
`oag_orchestration_guard.py` so the planner emits recovery before new DSE
work.

### 4.2 Generated variants inside skeletons

Structural alternatives that can coexist in one skeleton should be encoded as
generate options rather than duplicated skeletons:

```systemverilog
parameter bit ENABLE_FAST_PATH = 1'b1;
generate
  if (ENABLE_FAST_PATH) begin : g_fast_path
    // low-latency implementation
  end else begin : g_simple_path
    // smaller / simpler implementation
  end
endgenerate
```

This keeps sweeps cheap (one codebase, many build configs), maps cleanly onto
the candidate `generate_options` vector, and fits the existing RTL dialect
policy (Verilog `generate` is allowed).

Scope rules for generate options:

- Pre-lock, generate options live only in exploration skeletons (Tier A
  directories or Tier B worktrees). Product RTL does not exist pre-lock, so
  the `no lock, no RTL` invariant is untouched.
- Exploration regions may carry human-readable provisional markers:

```systemverilog
// OAG-BEGIN-PROVISIONAL: fast_path_exploration
// decision_id: D030_FAST_PATH_POLICY
// candidate_id: CAND_001
// evidence: knowledge/arch_exploration/RUN_X/CAND_001/report.json
...
// OAG-END-PROVISIONAL: fast_path_exploration
```

  Markers are navigation aids only. The durable link between RTL regions and
  decisions is the typed candidate object and receipt, never the comment; the
  cleanup check treats any marker remaining in authored/product paths as a
  lock blocker.
- A generate option survives into authored truth only as an explicit product
  configuration: a decision row with `representation: generate_option`, an
  entry in the parameter/configuration model, and matching verification plan
  configurations. Unverified options must not survive cleanup.

### 4.3 Bench harness

`.codex/scripts/oag_arch_bench.py`:

```bash
python3 .codex/scripts/oag_arch_bench.py run \
  --ip-dir <ip> --run-id <id> --candidate CAND_001 \
  --adapters yosys,verilator --json
python3 .codex/scripts/oag_arch_bench.py sweep \
  --ip-dir <ip> --run-id <id> --parameter CMD_FIFO_DEPTH \
  --values 2,4,8,16,32 --workloads worst_case_burst,backpressure_50pct --json
python3 .codex/scripts/oag_arch_bench.py status --ip-dir <ip> --run-id <id> --json
```

Pipeline per candidate:

1. Skeleton RTL generation into the candidate's isolation root (Tier A
   directory or Tier B worktree). Skeletons implement only the
   architecture-defining structure (queues, pipelines, arbiters, port shapes,
   generate-option variants) with stub payload logic. The default path
   dispatches a bounded `oag-rtl-implementation-agent` subagent with an
   explicit prototype dispatch (allowed paths limited to the isolation root,
   `may_claim_complete=false`); a pure-Python template fallback exists for
   simple candidates.
2. `yosys` adapter: `synth` + `stat` for cell/FF counts (area proxy), optional
   `abc -D <period>` pass/fail at the charter clock target (timing proxy).
3. `verilator` adapter: compile skeleton + generic traffic generator, measure
   cycles/packet, stall cycles under backpressure, latency distribution on a
   representative stimulus profile derived from source claims.
4. `sweep` mode reuses one skeleton across parameter/define values and writes
   the `oag_parameter_sweep.v1` artifact.
5. Results written as
   `knowledge/arch_exploration/<run_id>/<cand_id>/bench_result.json`
   (`oag_arch_bench_result.v1`): tool versions, source hashes, metrics,
   wall-clock, status, isolation kind, worktree branch (if any).

Tool availability policy: adapters probe for `yosys`/`verilator` on PATH.
Missing tools degrade the run to `status: bench_unavailable` per adapter; the
scoreboard then marks affected axes as tier-1-only, and the charter condition
(`require_tier2_evidence`) decides whether tier-1-only evidence may still
auto-decide. Subprocesses run as argv lists with explicit timeouts from
`charter.budgets`.

### 4.4 Guardrails

- Prototype writes are confined to `knowledge/arch_exploration/` (Tier A) or
  `.oag_worktrees/<cand_id>/` (Tier B); the bench script validates every
  emitted path against the candidate's isolation root (no escapes).
- Prototype RTL is never referenced by `rtl_filelist`, authoring packets, or
  the compile step. `oag_protected_receipt_audit.py` gains a check that no
  product artifact references exploration or worktree paths.
- Bench results are evidence objects: hashed, receipt-linked, and cited by
  `evidence_refs` in auto-resolved decision rows.
- Candidate receipts are mandatory per benched candidate and must contain:
  candidate set context, benchmark commands, metrics, comparison, selection
  rule, artifact paths, diff summary (Tier B), and rollback path.
- Selected-candidate skeletons may inform the authored
  `ontology/structure.yaml` and `ontology/decomposition.yaml`, but post-lock
  product RTL is always re-implemented through the normal authoring-packet
  and dispatch path, never copied wholesale from the prototype.

### 4.5 New action type

```text
ACT_ARCH_BENCH_RUN  phase: architecture  owner: dispatch (RTL skeleton)
                    or main/tool (adapter execution)
                    writes: knowledge + .oag_worktrees only
```

### 4.6 Phase 4 deliverables

```text
new: .codex/scripts/oag_arch_bench.py
new: .codex/scripts/oag_dse_worktree.py
new: .codex/schemas/oag_arch_bench_result.schema.json
new: .codex/schemas/oag_candidate_receipt.schema.json
new: .codex/oag/arch-bench-policy.md
modified: .codex/oag/operation_action_types.yaml
modified: .codex/scripts/oag_protected_receipt_audit.py
modified: .codex/scripts/oag_orchestration_guard.py (stale worktree hazard)
modified: .codex/scripts/oag_ip_git.py (managed .gitignore adds .oag_worktrees/)
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
    autonomy_class: external_contract
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
- `run_loop()` break set changes: `defer_question`, `auto_decide`, and
  `route_dse` do not break; `checkpoint_ready` (new) does. `needs_user` still
  breaks (it now only occurs with `question_policy.batching: immediate` or no
  charter).
- Checkpoint trigger conditions (any):
  - no runnable non-human candidate remains;
  - `len(pending_questions) >= charter.max_deferred_questions`;
  - any charter budget exhausted (`max_ticks`, worktrees, bench wall clock);
  - DSE finished with a non-dominant top candidate (comparison question).
- Speculative dual-branch rule: when exactly one deferred `external_contract`
  decision blocks candidate generation, `generate` may fork candidates for
  each of its options (bounded by tier-1 budget) so the checkpoint presents
  measured consequences per option instead of an abstract question.

### 5.3 Consolidated review surface

New action type `ACT_CHECKPOINT_REVIEW` (owner: `human_via_main`). Rendering
extends the existing formal-review machinery rather than inventing a new one:

- `oag_lock_preview_frame.py` gains panels: approved charter (verbatim),
  architecture scoreboard table with tier-1/tier-2 evidence links, parameter
  sweep curves with the selection rule applied, provisional agent decisions
  (distinct section, per-row evidence + receipts + rollback hint), retained
  generate options with their verification plan mapping, and the batched
  question list in priority order.
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

## Phase 6: Pre-Lock Exploration Cleanup

Goal: enforce "explore wide, lock narrow". Exploration is allowed to leave
many parameters, options, worktrees, and provisional regions open; scope lock
is not.

### 6.1 Cleanup action

New action type `ACT_EXPLORATION_CLEANUP` (phase: architecture/review, owner:
main/tool, or dispatch when RTL-shaped artifacts must be edited). It runs
after checkpoint approval and before the final lock preview regeneration.

Cleanup tasks:

- Promote the selected candidate: fold its structure sketch, decision
  assignments, and selected parameter defaults into authored
  `ontology/structure.yaml`, `ontology/decomposition.yaml`, and the
  parameter/configuration model.
- Collapse parameters: keep a parameter public only when it is a real product
  configuration value with a recorded rationale in the decision matrix;
  collapse exploration-only parameters to constants/localparams.
- Resolve generate options: delete unselected option paths; a retained option
  must have a decision row (`representation: generate_option`), a
  configuration model entry, and verification plan configurations covering
  every retained value. Options nobody will verify must not survive.
- Remove all `OAG-*-PROVISIONAL` markers from anything that feeds authored
  truth or later product work.
- Prune all DSE worktrees and branches (`oag_dse_worktree.py prune-all`);
  keep receipts, reports, sweeps, and the scoreboard in
  `knowledge/arch_exploration/` as durable evidence.
- Archive pruned/rejected candidates in the candidates file with
  `pruned_reason` so the audit trail survives even though the artifacts are
  gone.

### 6.2 Cleanup check

New script `.codex/scripts/oag_exploration_cleanup_check.py --ip-dir <ip> --json`,
wired into `oag_lock_readiness_check.py` as an additional gate. Blockers:

- more than one candidate still `alive` without a checkpoint decision;
- provisional markers present in authored/product paths;
- public parameters without a product rationale in the decision matrix;
- retained generate options without matching verification plan configurations;
- existing DSE worktrees or `oag/dse/*` branches;
- decision rows still `provisional: true` after checkpoint flush (checkpoint
  acceptance drops the flag; overrides flip `decided_by` to human).

Passing the cleanup check is a precondition for regenerating the final lock
preview; the preview then shows cleaned truth plus preserved evidence links.

### 6.3 Phase 6 deliverables

```text
new:      .codex/scripts/oag_exploration_cleanup_check.py
new:      .codex/oag/exploration-cleanup-policy.md
modified: .codex/scripts/oag_lock_readiness_check.py (cleanup gate)
modified: .codex/oag/operation_action_types.yaml (ACT_EXPLORATION_CLEANUP)
modified: .codex/oag/mission_templates.yaml (priority insert before
          ACT_RENDER_LOCK_PREVIEW)
```

## Phase 7: Decision-to-Implementation Traceability

Goal: guarantee that what exploration decided is what implementation builds.
Phases 1-6 make the system decide well; Phase 7 makes it provable that the
decisions were honored.

### 7.1 Why this phase must exist

Walk one decision through the system as it stands after Phase 6.

A sweep measures FIFO depths 4/8/16, selects 8 as the smallest value that
satisfies the mission target, and writes a receipt with the candidate set,
metrics, selection rule, and rollback path. The human approves it at the
consolidated checkpoint. The scope locks. So far every step is gated,
receipted, and auditable.

Now the post-lock RTL agent writes `parameter int CMD_FIFO_DEPTH = 4`.

Nothing fires. The authoring packet check passes, because packets reference
contracts and behavior rules, not decisions. The contract strength check
passes, because no contract mentions the depth unless an agent happened to
project it into one. The trace graph check passes, because decision rows are
not nodes in the trace graph. Lint passes; the scoreboard passes; closure
passes. The system spent its entire evidence budget proving the decision was
made correctly and has no mechanism that proves the decision was built.

This is not a hypothetical. The chain today has two well-governed segments
with an ungoverned seam between them:

```text
[exploration -> decision truth]   gated (charter, receipts, cleanup, lock)
[decision -> contract/structure]  agent prose discipline only   <- the seam
[contract -> RTL -> evidence]     gated (packets, dispatch, proofs, closure)
```

The seam is exactly where this plan concentrates its value, and autonomy
makes it wider, not narrower. Before this plan, a human made each decision
and then reviewed the RTL that implemented it; the human was the
traceability. After this plan, decisions are made in batch, reviewed in
batch, and nobody re-reads every RTL parameter against the decision matrix.
The better Phases 1-6 succeed at removing per-decision human attention, the
fewer accidental opportunities remain to catch a silent divergence. A
measured, receipted, approved decision that is not verifiably built is
indistinguishable, one year later, from a guess.

The seam also has one already-observed hard failure: the autoresolve writer
records `knowledge/arch_exploration/...` evidence refs on decision rows,
while the cleanup check forbids that path in any authored ontology file. The
pipeline as shipped cannot pass its own lock gate after auto-deciding; the
exploration-to-lock transition currently requires an undocumented manual
rewrite of evidence refs. Every mechanism below is an extension of an
existing OAG pattern (schema field + check script + rule index entry), not a
new subsystem.

### 7.2 Evidence promotion at the lock boundary

Add a promotion step to `ACT_EXPLORATION_CLEANUP`: copy the selected
candidate's evidence (sweep artifacts, bench results, scoreboard rows) from
`knowledge/arch_exploration/<run>/` into a durable promoted area
(`knowledge/views/promoted/arch/<run>/`), rewrite the decision rows'
`evidence_refs` to the promoted paths, and keep the original exploration
lineage inside the decision receipt. The cleanup check stays strict — no
authored file may reference `knowledge/arch_exploration` — but the flow can
now pass it legitimately instead of by hand-editing truth.

### 7.3 Selected-candidate promotion into authored truth (tooled, not prose)

Phase 6 lists "fold the selected candidate's structure sketch and parameter
defaults into authored truth" as a cleanup task, but gives the agent no tool
and the gates no way to verify it happened. Add a
`promote` subcommand to `oag_architecture_options.py` that, given the
selected candidate: marks the winner `selected` and every loser `pruned`
with a `pruned_reason` in the candidates file; emits a module-boundary
draft for `ontology/structure.yaml` from `structure_sketch.modules`; and
emits/updates parameter decision rows from `parameter_draft`. The output is
a draft the agent reviews and commits, plus a promotion receipt — the same
propose-then-confirm shape as every other OAG writer.

### 7.4 Authoring packets must carry the decisions they implement

Extend `oag_rtl_authoring_packet.schema.json` (and the TB packet) with
`decision_refs_to_honor`. The packet compiler must include every locked
decision row whose `affects` or module scope intersects the packet target;
`oag_authoring_packet_check.py` fails a packet that omits one. The RTL
implementation agent then cannot receive work without the decided values in
front of it — honoring decisions stops depending on whether a subagent
happened to read the decision matrix.

### 7.5 Decision-to-RTL consistency gate

New check `oag_decision_rtl_consistency_check.py --ip-dir <ip> --json`,
wired into lock-preview regeneration, implementation review, and closure:

- for every locked decision with `representation: parameter`, parse the RTL
  (pyslang) and verify the declared parameter default matches the decided
  value;
- for every retained `representation: generate_option` decision, verify the
  corresponding generate/config construct exists in the RTL and its
  verification plan configuration is still present;
- report drift as blockers with both values and both sources, so a
  legitimate change is forced back through a decision update instead of a
  silent edit.

This turns "the implementation honors the decisions" from a review-culture
assumption into a machine-checked invariant — the same promotion every other
OAG claim has already received.

### 7.6 Phase 7 deliverables

```text
new:      .codex/scripts/oag_decision_rtl_consistency_check.py
new:      .codex/oag/decision-implementation-traceability-policy.md
modified: .codex/scripts/oag_architecture_options.py (promote subcommand)
modified: .codex/scripts/oag_exploration_cleanup_check.py (promoted-evidence
          aware; still forbids raw arch_exploration refs in authored truth)
modified: .codex/schemas/oag_rtl_authoring_packet.schema.json and
          oag_tb_authoring_packet.schema.json (decision_refs_to_honor)
modified: .codex/scripts/oag_authoring_packet_check.py (decision ref gate)
modified: .codex/scripts/oag_lock_readiness_check.py /
          oag_implementation_review_check.py (consistency gate wiring)
modified: .codex/rules/oag-rule-index.yaml (new RULE-AUTO/TRACE entries)
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
+ ACT_EXPLORATION_CLEANUP
  ACT_REPAIR_SSOT_SECTION
  ...
  ACT_RENDER_LOCK_PREVIEW
  ACT_LOCK_SCOPE
  ... (rest unchanged)

target_state additions:
  mission_charter: approved_or_waived
  architecture_exploration: complete_or_waived
  exploration_cleanup: pass_or_not_applicable
```

`operation_action_types.yaml` additions: `ACT_CHARTER_INTERVIEW`,
`ACT_ARCH_CANDIDATE_GENERATE`, `ACT_ARCH_BENCH_RUN`,
`ACT_ARCH_SELECT_AND_DECIDE`, `ACT_CHECKPOINT_REVIEW`,
`ACT_EXPLORATION_CLEANUP`, each with phase, owner role, consumes/produces,
preconditions, and fallback policy, validated by `oag_action_model_check.py`.

No new mission template is required; `default_mission()` stays unchanged.

## Test Plan

Unit/scenario tests (extend `oag_eval.py` scenarios and `smoke_test.py`):

Phase 1:

- `external_contract` rows are never auto-decided, even with a charter.
- `external_contract_impact: direct` forces the human path regardless of
  class and grant.
- Missing `autonomy_class` behaves as `external_contract`.
- No charter (or `status != approved`) reproduces today's behavior bit-for-bit
  on existing eval scenarios.
- Lock readiness rejects agent-decided rows with missing/dangling
  `evidence_refs`, unsatisfied `evidence_required`, or missing receipts.
- `oag_decision_autoresolve.py` writes row + receipt + ledger atomically,
  refuses ungranted classes, and refuses receipts missing candidate set,
  metrics, selection rule, or rollback path.

Phase 2:

- Charter schema rejects `external_contract: granted true`.
- `approve` requires human actor; `revoke` disables all auto-decide and DSE
  routing on the next tick.
- Charter fields are protected: semantic edits without human decision receipts
  fail protection checks.

Phase 3:

- Candidate generation respects budgets (tier-1 count, sweep points) and
  constraint pruning.
- Tier-1 estimators are deterministic for a fixed fingerprint.
- Scoreboard win-margin math and Pareto membership have fixed-vector tests.
- Sweep selection picks the smallest satisfying value with margin on a fixed
  saturation-curve vector (8 beats 16/32 when the curve is flat past 8).
- `ACT_ARCH_SELECT_AND_DECIDE` auto-decides only above the margin threshold;
  below it, exactly one comparison question lands in the queue.

Phase 4:

- Bench path guard rejects any emitted path outside the candidate's isolation
  root.
- Worktree helper refuses roots outside `.oag_worktrees/`, refuses creation
  beyond `max_worktrees`, and `prune` removes both worktree and branch while
  receipts and reports persist in the main tree.
- Stale worktrees surface as orchestration hazards.
- Missing yosys/verilator degrades to `bench_unavailable` without failing the
  mission loop; `require_tier2_evidence: true` then blocks auto-decide.
- Product artifacts referencing exploration or worktree paths fail the
  protected receipt audit.
- `oag_windows_smoke.py` passes (no `shell=True`, argv subprocess lists,
  worktree commands through git.exe discovery).

Phase 5:

- `defer_question`, `auto_decide`, and `route_dse` do not break `run_loop()`;
  `checkpoint_ready` does.
- Queue overflow and budget exhaustion both force checkpoint.
- Checkpoint answers route through `handoff` and clear the queue
  (`status: flushed`).
- Accept drops `provisional`; override flips `decided_by` to human.

Phase 6:

- Cleanup check blocks lock while provisional markers remain in authored
  paths.
- Cleanup check blocks lock while a retained generate option lacks
  verification plan configurations.
- Cleanup check blocks lock while DSE worktrees or `oag/dse/*` branches exist.
- Public parameter without product rationale fails; collapsed constant passes.
- After cleanup, the lock preview regenerates from cleaned truth and preserved
  evidence links resolve.

Phase 7:

- Evidence promotion rewrites decision `evidence_refs` to promoted paths;
  the cleanup check passes afterward without hand-editing authored truth,
  and the receipt retains the original exploration lineage.
- `promote` marks exactly one winner `selected`, every loser `pruned` with a
  reason, and emits structure/parameter drafts matching the winner's
  `structure_sketch` and `parameter_draft`.
- A packet whose target intersects a locked decision's scope fails the
  packet check when `decision_refs_to_honor` omits that decision.
- Consistency gate: RTL parameter default differing from the decided value
  is a blocker naming both values and both sources; matching RTL passes; a
  retained generate option with no matching RTL construct is a blocker.
- Decision drift cannot be fixed by editing the decision row without a new
  human or charter-granted decision receipt (protection check).

End-to-end acceptance scenario (dry-run with stub estimators/adapters):

```text
scaffold IP -> approve charter -> mission loop run --max-ticks 40
expect: zero needs_user stops, >=1 auto-decided fact row,
        >=1 swept parameter with saturation-based default,
        arch candidates generated and scored, checkpoint_ready with
        consolidated frame rendered, cleanup check failing before cleanup
        and passing after, all provisional decisions carrying
        class+strategy+charter+evidence+receipt
```

## Risks and Mitigations

| Risk | Mitigation |
| --- | --- |
| Proxy metrics mislead (yosys cells != real area; skeleton != real timing) | Use proxies for ranking only, never absolute claims; record tool versions and margins; charter margin threshold gates auto-decide; below margin -> human comparison question with data |
| Parameter knob sprawl in final RTL | Cleanup collapse rule: public parameter requires product rationale; exploration-only parameters become constants; cleanup check blocks lock |
| Generate-option verification matrix explosion | Default is collapse-at-cleanup; retained options must map to verification plan configurations; tier-1 verification-cost estimator penalizes retained options during scoring |
| Prototype RTL leaks into product | Isolation-root confinement in bench script; protected receipt audit check; product RTL always re-authored via packets/dispatch |
| Stale or leaked worktrees | Git-ignored `.oag_worktrees/` root; budget cap; prune-all in cleanup; stale-worktree hazard in orchestration guard; cleanup check blocks lock on leftovers |
| Charter over-grants autonomy | Schema forbids external-contract grants; default-deny for absent grants; `external_contract_impact: direct` overrides any grant; charter approval is human; charter fields protected |
| Question starvation / user surprise at checkpoint size | `max_deferred_questions` cap; budget-exhaustion checkpoint; checkpoint frame ranks questions by lock impact |
| Candidate-space explosion | Tier-1 budget (default 8), tier-2 budget (default 3), sweep-point budget, constraint pruning before estimation, Pareto pruning before bench |
| Skeleton generation stalls (subagent hang) | Existing orchestration guard + role health cover dispatched skeleton work; template fallback for simple candidates |
| Silent decision drift (approved decision not honored by post-lock RTL) | Phase 7: packets carry `decision_refs_to_honor`; decision-to-RTL consistency gate blocks lock preview, implementation review, and closure on mismatch |
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
Phase 1  Decision autonomy model + auto-decide (no deps; largest stop-count win)
Phase 2  Mission charter                       (depends on 1 for grant checks)
Phase 3  Candidates + sweeps + tier-1 + score  (depends on 2 for weights/budgets)
Phase 5  Checkpoint batching + review frame    (depends on 1,2; independent of
                                                3/4; can be pulled before 3 for
                                                the UX win)
Phase 6  Pre-lock exploration cleanup          (depends on 3; must land before
                                                the first real post-DSE lock)
Phase 4  Tier-2 bench + worktree isolation     (depends on 3; heaviest build)
Phase 7  Decision-to-implementation trace      (depends on 6; must land before
                                                the first post-DSE implementation
                                                mission is trusted — without it,
                                                auto-decided values are measured,
                                                approved, and then unverifiable
                                                in the built RTL)
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
- every agent-made decision row carries `autonomy_class`,
  `resolution_strategy`, charter grant ref, resolving `evidence_refs`, a
  decision receipt with candidate set / metrics / selection rule / rollback
  path, and `provisional: true` until checkpoint review;
- buffering-class values are settled by bounded sweeps that select the
  smallest value satisfying the mission target with margin, kept as
  parameterized defaults;
- architecture selection cites a scoreboard with tier-1 (and where available
  tier-2) measurements, non-trivial candidates are isolated in git worktrees
  with receipts and diff summaries, and non-dominant outcomes surface as one
  measured comparison question instead of silent defaults;
- the consolidated checkpoint frame shows charter, scoreboard, sweep curves,
  provisional decisions, retained options with verification mapping, and
  batched questions with verbatim source preservation;
- the cleanup check proves that no provisional markers, unselected variants,
  rationale-less public parameters, or leftover worktrees survive into the
  locked scope;
- every locked decision is verifiably built: promoted evidence resolves from
  the decision rows, authoring packets carry the decisions they implement,
  and the decision-to-RTL consistency gate confirms parameter defaults and
  retained generate options in the shipped RTL match the decided values;
- scope lock, external-contract decisions, post-lock dispatch/receipt gates,
  and the full existing eval suite are unchanged and passing.
