# Minimal-Mission Exploration Workstream — Implementation Handoff

Date: 2026-07-04 (KST)
Status: exploration pipeline implemented and live-verified; lock boundary
blocked by one design contradiction; Phase 7 specced; debt-control work
recommended before new gates.

This document is a self-contained handoff. An agent with no access to the
original conversation must be able to (a) understand what was decided and
why, (b) reproduce the verification results, and (c) execute the work orders
below in the stated priority order.

Authoritative companion documents:

- `.codex/oag/minimal-mission-architecture-exploration-plan.md` — the full
  design plan (Phases 1-7). Phase 7 (`## Phase 7: Decision-to-Implementation
  Traceability`, sections 7.1-7.6) is the newest addition and is the primary
  spec for work orders WO-2 through WO-5 below.
- `.codex/oag/decision-autonomy-policy.md`, `mission-charter-policy.md`,
  `architecture-option-policy.md`, `architecture-bench-policy.md`,
  `dse-worktree-policy.md` — implemented policy docs.
- `.codex/rules/oag-rule-index.yaml` — invariant/rule registry (seed for
  WO-6).

---

## 1. Conversation Record (chronological, decisions only)

1. **Mission framing.** The user wants the `.codex` OAG system to operate
   like "Jarvis": given a minimal mission, autonomously explore the
   architecture space and design hardware IP, asking humans as little as
   possible. Diagnosis at the time: the Mission Loop stopped at every human
   decision (`needs_user`) and had no quantitative architecture comparison.

2. **Plan document.** A detailed plan was written to
   `.codex/oag/minimal-mission-architecture-exploration-plan.md`.

3. **Operating philosophy (user-confirmed, normative).** Six rules govern
   everything: (1) Ask less. (2) Parameterize reversible values.
   (3) Preserve structural alternatives as generate options during
   exploration. (4) Settle measured tradeoffs by benchmark, not by asking.
   (5) Checkpoint only irreversible or externally visible decisions.
   (6) Clean up before scope lock. Key corollaries the user explicitly
   endorsed: FIFO depths / queue sizes are measured-tradeoff parameters
   (sweep, pick smallest satisfying with margin, keep as parameterized
   default); git worktrees are the DSE isolation mechanism; agent decisions
   without evidence receipts are not decisions; internal reversible choices
   may be decided provisionally by the agent, external irreversible
   contracts always go to a human checkpoint.

4. **First implementation review.** The user implemented Phases 1-6. Review
   found 3 blockers: (a) inverted comparison logic in
   `oag_parameter_sweep.py selects()`; (b) `oag_dse_worktree.py prune`
   deleting `knowledge/arch_exploration/` evidence; (c) missing subprocess
   timeouts in `oag_arch_bench.py` and `run_git()`. Plus majors:
   policy-vs-writer charter-grant inconsistency in
   `oag_decision_autoresolve.py`; incomplete charter schema (missing
   budgets/objective_weights/constraints under `additionalProperties:
   false`); partial Phase 3/4/6 implementations.

5. **Fix verification (all confirmed in code + new regression tests).**
   - `selects()` fixed: `max` → `metric >= target - margin`, `min` →
     `metric <= target + margin`. NOTE: margin is deliberately a
     *tolerance* (loosens the target), locked in by
     `test_oag_arch_exploration_blocker_regressions` in `smoke_test.py`.
     Do not "fix" this to a safety margin without a decision.
   - Prune now removes only worktrees and `oag/dse/*` branches; evidence
     survives (regression-tested).
   - Bench timeouts come from `charter.budgets.max_bench_wall_clock_sec`
     (`bench_timeout_sec()`); `TimeoutExpired` → status `timeout`,
     `BENCH_ADAPTER_TIMEOUT` issue, overall fail. `run_git()` uses
     `GIT_TIMEOUT_SEC`.
   - `resolve_candidate_policy()` now requires an approved charter grant
     for `parameterizable`, `reversible_internal`, and `measured_tradeoff`
     branches (consistent with the writer).
   - Charter schema now includes `budgets` (incl. `max_worktrees`,
     `max_bench_wall_clock_sec`), `objective_weights`, `constraints`.
   - `oag_arch_bench.py` gained a `sweep` subcommand writing
     `knowledge/arch_exploration/<run>/<cand>/parameter_sweep_<PARAM>.json`.
   - Hard constraints are enforced in tier-1 scoring
     (`constraint_issues_for_candidate`, `SCORE_HARD_CONSTRAINTS_EMPTY`,
     constraint-failing candidates sorted last).
   - Cleanup check gained `PUBLIC_PARAMETER_RATIONALE_MISSING`,
     `PROVISIONAL_DECISION_REMAINS`,
     `GENERATE_OPTION_VERIFICATION_MAPPING_UNKNOWN`,
     `GENERATE_OPTION_VERIFICATION_PLAN_MISSING`,
     `EXPLORATION_SELECTION_MISSING`, `EXPLORATION_CANDIDATE_UNPRUNED`.
   - Lock readiness `_agent_decision_issues` triggers on any
     `decided_by.kind` starting with `agent_` (the `provisional: false`
     bypass is closed). Receipts must contain: `candidate_set`,
     `bench_command`, `metrics`, `comparison`, `selection_rule`,
     `artifact_paths`, `rollback_path` (see `_receipt_structural_issues`).

6. **Live end-to-end verification** on a scratch IP (see §3 replay
   protocol). Everything from charter to lock-readiness worked except one
   structural deadlock (§2, defect D-1).

7. **Assessment: supplement vs innovate.** Supplements: evidence promotion
   at the lock boundary, config/gate mismatch, candidate-selection CLI,
   doc/registration leftovers. Innovations, in priority order:
   (1) evidence provenance — sweep metric points are currently
   agent-asserted CLI values with empty `evidence_refs`; fabricated numbers
   pass every gate; (2) bounded executor — `oag_loop_runner.py` `execute`
   mode is intentionally unimplemented, so every action round-trips through
   an LLM agent; (3) option-space generation — `architecture_tradeoff` rows
   with options/tier1_scores are currently authored by hand, so the system
   explores only human-enumerated spaces; (4) estimator calibration —
   tier-1 model is static (`tier1-deterministic-v1`), no learning from
   tier-2 measurements.

8. **Exploration-to-implementation connection analysis.** The chain has two
   governed segments and one ungoverned seam:
   `[exploration → decision truth]` gated; `[decision → contract/structure]`
   agent prose discipline only; `[contract → RTL → evidence]` gated. Three
   broken links: decision→requirement/contract projection is untooled;
   the selected candidate's `structure_sketch`/`parameter_draft` have no
   downstream consumer; no gate compares RTL parameter defaults or retained
   generate options against decided values. This became **Phase 7** in the
   plan doc (written persuasively at the user's request; see §7.1 there).

9. **Debt-control decision.** Measured: 86 scripts, 37 schemas, 50 policy
   docs, but only 15 rules in `oag-rule-index.yaml` referencing 13 unique
   scripts → 73 scripts trace to no registered invariant; ~60 duplicate
   definitions of `read_structured`/`issue`/`text` helpers across scripts.
   All three bug classes found in review were "one truth implemented in two
   places" failures. Agreed direction: consolidate shared helpers, promote
   the rule index to a bidirectional invariant registry with one meta
   check, then add new gates (Phase 7) at the reduced marginal cost.
   Explicit warning: the meta layer must stay one file + one check;
   `pack_release_check` breaking on a drifted config constant (defect D-2)
   is the cautionary example of meta-check overreach.

---

## 2. Open Defects (fix before or during Phase 7)

### D-1 (BLOCKER): evidence-ref deadlock at the lock boundary

`oag_decision_autoresolve.py` writes decision rows whose `evidence_refs`
point into `knowledge/arch_exploration/...`. The cleanup gate
(`oag_exploration_cleanup_check.py check_product_leaks`) fails ANY authored
ontology file containing the substring `knowledge/arch_exploration`
(`PRODUCT_ARCH_EXPLORATION_REFERENCE`), and `oag_lock_readiness_check.py`
embeds that gate. Meanwhile lock readiness also requires `evidence_refs` to
resolve to existing files. Consequence: after any auto-decide, the pipeline
cannot pass its own lock gate; there is no tool that promotes/rewrites the
refs. Reproduced live (§3 step 8). Resolution is WO-2 (plan §7.2).

### D-2 (GATE FAILURE): config vs release-check constant drift

`.codex/config.toml` sets
`[features.multi_agent_v2].max_concurrent_threads_per_session = 1000`, but
`oag_pack_release_check.py` (~L680) requires >= 10000
(`MULTI_AGENT_V2_LIMIT`). This makes `smoke_test.py` exit 1 — it is the
ONLY failing check in the entire suite. The 1000 value was changed by the
user/another session; intent unknown. Action: confirm the intended value
with the owner; then make config and check agree (and check whether
`smoke_test.py` embeds the same constant).

### D-3 (minor, all confirmed still present)

- `oag_pending_questions.py read_state()` silently resets the queue to
  default when `schema_version` mismatches or JSON is corrupt (L70-79).
  Should surface an issue instead of dropping queued questions.
- `oag_dse_worktree.py prune_all()` `--run-id` arg only validates the id
  (`clean_id`) and does nothing else — vestigial; remove or implement.
- Candidate selection (marking `selected`/`pruned` + `pruned_reason` in
  `knowledge/arch_exploration/<run>/candidates.json`) has no CLI; during
  E2E it required hand-editing JSON. Subsumed by WO-3 `promote`.
- `.codex/AGENTS.md` asset list does not mention any of the new scripts
  (`oag_mission_charter.py`, `oag_decision_autoresolve.py`,
  `oag_architecture_options.py`, `oag_arch_bench.py`,
  `oag_dse_worktree.py`, `oag_exploration_cleanup_check.py`,
  `oag_parameter_sweep.py`, `oag_pending_questions.py`).
- `.codex/oag/exploration-cleanup-policy.md` (named in plan Phase 6
  deliverables) does not exist.

---

## 3. Verified E2E Replay Protocol

All commands below were executed successfully on 2026-07-04 against a
scratch IP. Use this to re-verify after any change. Run from the repo root.

```bash
# 1. Scaffold
python3 .codex/scripts/oag_scaffold_ip.py create /tmp/oag_e2e/demo_ip --owner brian

# 2. Charter: propose as AI, approve must FAIL for AI and PASS for human
python3 .codex/scripts/oag_mission_charter.py propose --ip-dir /tmp/oag_e2e/demo_ip \
  --actor-kind ai --actor-id agent-1 --question-batching checkpoint \
  --grant parameterizable --grant architecture_tradeoff \
  --max-candidates-tier1 8 --max-sweep-points-per-parameter 5 \
  --max-bench-wall-clock-sec 60 --max-worktrees 2 \
  --objective-weight throughput=0.4 --objective-weight area_proxy=0.3 \
  --objective-weight verification_cost=0.3 --rationale "demo mission" --json
python3 .codex/scripts/oag_mission_charter.py approve --ip-dir /tmp/oag_e2e/demo_ip \
  --actor-kind ai --actor-id agent-1 --json    # expect fail: human required
python3 .codex/scripts/oag_mission_charter.py approve --ip-dir /tmp/oag_e2e/demo_ip \
  --actor-kind human --actor-id brian --json   # expect pass
```

3. Append decision rows to `ontology/decision_matrix.yaml` (YAML, appended
   under the existing `decisions:` list). Two `architecture_tradeoff` rows
   with `options` (each option: `id`, `label`, `modules`, `tier1_scores`
   with throughput/latency/area_proxy/power_proxy/verification_cost), one
   `parameterizable` row with `autonomy_class: measured_tradeoff`,
   `resolution_strategy: parameterized_default`, `representation:
   parameter`, `external_contract_impact: none`, `candidate_values`.
   (Exact rows used in the verified run: fast_path/simple_path datapath,
   reg_fifo/sram_fifo, CMD_FIFO_DEPTH in {4,8,16}.)

```bash
# 4. Tier-1 pipeline: expect 4 candidates, weighted totals, Pareto flags
python3 .codex/scripts/oag_architecture_options.py generate --ip-dir /tmp/oag_e2e/demo_ip --run-id run_demo --json
python3 .codex/scripts/oag_architecture_options.py estimate --ip-dir /tmp/oag_e2e/demo_ip --run-id run_demo --json
python3 .codex/scripts/oag_architecture_options.py score    --ip-dir /tmp/oag_e2e/demo_ip --run-id run_demo --json
# verified result: CAND_001 (fast_path+reg_fifo) weighted_total 0.577, rank 1

# 5. Sweep: expect selected value 8 = smallest satisfying target with margin
python3 .codex/scripts/oag_arch_bench.py sweep --ip-dir /tmp/oag_e2e/demo_ip \
  --run-id run_demo --candidate CAND_001 --parameter CMD_FIFO_DEPTH \
  --metric throughput --objective max --target 0.9 --margin 0.05 \
  --candidate-value 4 --candidate-value 8 --candidate-value 16 \
  --metric-point "4=0.7" --metric-point "8=0.92" --metric-point "16=0.95" --json

# 6. Auto-resolve (repeat for each agent decision; evidence ref must exist)
python3 .codex/scripts/oag_decision_autoresolve.py --ip-dir /tmp/oag_e2e/demo_ip \
  --decision-id DEC_CMD_FIFO_DEPTH --decision "CMD_FIFO_DEPTH parameter default 8" \
  --resolution-strategy parameterized_default --representation parameter \
  --external-contract-impact none \
  --evidence "knowledge/arch_exploration/run_demo/CAND_001/parameter_sweep_CMD_FIFO_DEPTH.json" \
  --candidate-values "4,8,16" --rationale "smallest depth satisfying target" --json
# verified: row becomes status=decided, decided_by.kind=agent_with_charter,
# provisional=true, receipt at knowledge/decisions/DEC_CMD_FIFO_DEPTH.json
# with all structural fields present.

# 7. Worktree isolation (needs at least one commit in IP-local git)
python3 .codex/scripts/oag_dse_worktree.py create --ip-dir /tmp/oag_e2e/demo_ip \
  --run-id run_demo --candidate CAND_001 --tier B --force --json
python3 .codex/scripts/oag_dse_worktree.py prune-all --ip-dir /tmp/oag_e2e/demo_ip --json
# verified: worktree .oag_worktrees/CAND_001 + branch oag/dse/mission/CAND_001
# created then removed; knowledge/arch_exploration evidence SURVIVES.

# 8. Gates
python3 .codex/scripts/oag_exploration_cleanup_check.py --ip-dir /tmp/oag_e2e/demo_ip --json
# before selection: EXPLORATION_SELECTION_MISSING + EXPLORATION_CANDIDATE_UNPRUNED x4.
# after marking CAND_001 selected / others pruned(+reason) in candidates.json:
# exactly one remaining failure = PRODUCT_ARCH_EXPLORATION_REFERENCE  <- defect D-1
python3 .codex/scripts/oag_lock_readiness_check.py --ip-dir /tmp/oag_e2e/demo_ip --json
# verified: 3 provisional_review_items, unresolved_lock_blockers=1 (seeded
# product decision), fails only on the cleanup issue above.

# 9. Mission loop
python3 .codex/scripts/oag_mission_loop.py run --ip-dir /tmp/oag_e2e/demo_ip --max-ticks 6 --json
# verified: starts ACT_SELF_EXPLORE_OPTIONS for the remaining product
# decision and stops with decision=action_started (bounded-agency design:
# the loop proposes, an agent executes).
```

Suite verification (all must pass; currently D-2 breaks smoke):

```bash
python3 .codex/scripts/smoke_test.py            # exit 1 today, only MULTI_AGENT_V2_LIMIT
python3 .codex/scripts/oag_eval.py              # PASS (verified)
python3 .codex/scripts/oag_windows_smoke.py --json   # pass (verified)
python3 .codex/scripts/oag_action_model_check.py     # PASS, 33 actions / 5 missions
```

---

## 4. Work Orders (priority order)

### WO-1: Resolve D-2 config drift (trivial, do first)

Align `.codex/config.toml` `max_concurrent_threads_per_session` with
`oag_pack_release_check.py`. Confirm intended value with the owner before
choosing the direction. Re-run smoke to confirm exit 0.

### WO-2: Evidence promotion at the lock boundary (fixes D-1; plan §7.2)

Extend the cleanup flow (`ACT_EXPLORATION_CLEANUP`): copy the selected
candidate's evidence from `knowledge/arch_exploration/<run>/` to
`knowledge/views/promoted/arch/<run>/`; rewrite decision rows'
`evidence_refs` to promoted paths; keep original exploration lineage inside
the decision receipt. Cleanup check stays strict on raw
`knowledge/arch_exploration` refs in authored files but must accept
promoted refs. Acceptance: E2E replay §3 passes cleanup + lock readiness
after promotion with zero hand-edits.

### WO-3: `promote` subcommand on `oag_architecture_options.py` (plan §7.3)

Given `--run-id` + `--candidate`: mark winner `selected`, losers `pruned`
with `pruned_reason`; emit module-boundary draft for
`ontology/structure.yaml` from the winner's `structure_sketch.modules`;
emit/update parameter decision rows from `parameter_draft`; write a
promotion receipt. Propose-then-confirm shape (drafts, not silent writes).
This also retires the manual JSON editing noted in D-3.

### WO-4: `decision_refs_to_honor` in authoring packets (plan §7.4)

Add the field to `oag_rtl_authoring_packet.schema.json` and the TB packet
schema; packet compiler includes every locked decision whose `affects` or
module scope intersects the packet target; `oag_authoring_packet_check.py`
fails packets that omit one.

### WO-5: Decision-to-RTL consistency gate (plan §7.5)

New `.codex/scripts/oag_decision_rtl_consistency_check.py`: for locked
`representation: parameter` decisions, parse RTL (pyslang) and compare the
declared parameter default with the decided value; for retained
`representation: generate_option` decisions, verify the generate/config
construct exists and its verification-plan configuration is present. Wire
into lock-preview regeneration, `oag_implementation_review_check.py`, and
closure. Drift reports must name both values and both sources.

### WO-6: Debt control (recommended BEFORE WO-3..5 to cut marginal cost)

1. **Shared helpers**: create one common module consolidating
   `read_structured`, `issue`, `text`, charter reading, and grant parsing
   (currently ~60 duplicate definitions across `.codex/scripts/`). The
   grant parser MUST have exactly one implementation (the Phase-1
   policy/writer divergence bug came from duplication).
2. **Invariant registry**: extend `.codex/rules/oag-rule-index.yaml` rows
   with `tested_by` (smoke/eval case names); add a meta check that
   enforces bidirectionally: every `oag_*_check.py` script appears in at
   least one rule's `checker_refs`, and every rule has at least one
   `tested_by`. Emit orphans as warnings first (73 scripts currently trace
   to no rule), then triage: register or delete.
3. Keep the meta layer to exactly one file + one check. Do not build more
   meta-machinery.

### WO-7: Innovation track (after WO-1..6; priority order fixed with user)

1. **Evidence provenance**: require each sweep `--metric-point` to carry a
   run-artifact ref (sim log, yosys stat output) + content hash;
   `selected.evidence_refs` must be non-empty; gates verify resolvability.
   Close the bench pipeline: per-candidate skeleton RTL → compile/sim in
   the candidate worktree → automatic metric extraction. Rationale: today
   an agent can fabricate `--metric-point 8=0.92` and every gate passes.
2. **Bounded executor**: implement `oag_loop_runner.py` `execute` mode for
   a whitelist of deterministic, read-only/tool commands (already present
   in candidate `command` fields); LLM agents handle only judgment actions.
3. **Option-space generation**: seed `architecture_tradeoff` rows +
   options + tier-1 estimates from profile catalogs
   (`.codex/oag/profiles/`) and deep-semantic-intake output instead of
   hand-authoring.
4. **Estimator calibration**: record (tier-1 estimate, tier-2 measurement)
   pairs in the scoreboard schema; calibrate tier-1 models over time.

---

## 5. Invariants That Must Not Regress

Fail-closed properties verified during this workstream; any change must
keep these true (most have smoke/eval coverage):

- Charter approval requires a human actor; AI approval fails.
- `product_defining` grants are refused at charter proposal.
- Missing/unknown `decision_class` or `autonomy_class` fails closed as
  `product_defining` / `external_contract`.
- `external_contract_impact: direct` forces the human path regardless of
  class or grant.
- Auto-decide without an approved charter grant fails
  (`CHARTER_GRANT_MISSING`) — in both the policy classifier and the writer.
- Agent-decided rows require resolving `evidence_refs`, structured receipt
  fields, and `provisional: true` until checkpoint review.
- Worktree prune never deletes `knowledge/arch_exploration/` evidence.
- Bench subprocesses always run with a timeout from charter budgets.
- Scope lock remains human-only; no charter grant can unlock it.
- Charter-absent behavior reproduces the pre-exploration system (eval
  suite unchanged).

## 6. Known Deliberate Semantics (do not "fix" without a decision)

- Sweep margin is a tolerance: `max` accepts `>= target - margin`, `min`
  accepts `<= target + margin`; selection picks the smallest candidate
  value that satisfies. Locked by regression test.
- Tier-1 metric aggregation: `latency`/`area_proxy`/`power_proxy`/
  `verification_cost` sum across module contributions; `throughput` takes
  the min (bottleneck semantics).
- The mission loop intentionally stops at `action_started` — it proposes,
  an executor (currently an LLM agent) acts. Autonomy expansion is WO-7.2,
  not a loop redesign.
- Exploration skeleton RTL is throwaway by design; production RTL is
  re-authored post-lock via packets/dispatch. Continuity comes from
  WO-3/WO-5, not from promoting prototype code.
