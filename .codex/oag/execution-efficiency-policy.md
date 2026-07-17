# OAG Execution Efficiency Policy

OAG execution must be bounded, attributable, and re-plannable. Correctness and
evidence strength remain mandatory; this policy removes repeated context and
duplicate process work rather than weakening closure.

## Dispatch Contract

Every newly created native-subagent dispatch carries:

- a `simple` (5M), `medium` (10M), or `complex` (20M) total-token ceiling;
- an 80% warning threshold and `stop_and_replan` hard-limit action;
- at most one review attempt by default, with two allowed only by explicit CLI override;
- a `mechanical`, `balanced`, or `reasoning` model capability tier;
- `fork_turns=none` and an authoring-packet or explicit file/hash input contract.

The 25M ceiling is absolute. Work that cannot fit must be decomposed before a
new dispatch is created. A budget is an execution guard, not permission to omit
required checks.

## Review And Recovery

One writer and one independent reviewer are the default. A review-target
fingerprint is derived from the dispatch baseline after excluding orchestration
state, receipts, and reviewer-owned outputs. Re-reviewing an unchanged target
fingerprint is an efficiency failure. A rejected review may open one bounded
repair dispatch; further repair requires a parent re-plan with a new baseline.

Stop hooks remain fail-closed, but an unchanged blocker is printed in full only
once per session/workspace digest. Repeats carry a stable short issue ID and
counter. Python bytecode and cache directories are never implementation proof.

## Telemetry And Gates

Correlation events join Codex token/model telemetry to dispatch, task,
wavefront/mission, role, result, budget, context contract, content fingerprint,
and dispatch scope hash. `oag_otel_cost.py` reports token and configured-rate
cost by model, task, role, and mission.

Run the enforceable audit with:

```bash
python3 .codex/scripts/oag_execution_efficiency_check.py \
  --report .codex/.cache/otel/reports/current.json --json
```

Default project-run targets are root share at most 15%, process/review share at
most 25%, and largest single-agent share at most 5%. Ratio gates apply only to
runs with at least five accounting sessions. Budget and duplicate-review gates
always apply. Use `--advisory` only for historical baselines that predate the
dispatch budget contract.
