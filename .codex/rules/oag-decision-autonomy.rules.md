# OAG Decision Autonomy Rules

## RULE-AUTO-001: Product-defining decisions are human-only

Agents must not auto-decide product-visible scope, protocol, integration,
feature, or user-promise decisions. Missing or unknown `decision_class` values
are treated as `product_defining`.

Checker refs:

- `scripts/oag_decision_autoresolve.py`
- `scripts/oag_mission_loop.py`
- `scripts/oag_lock_readiness_check.py`

## RULE-AUTO-005: Autonomy class is orthogonal and fail-closed

Autonomy is controlled by `autonomy_class`, not by legacy `decision_class`.
Missing or unknown `autonomy_class` values are treated as `external_contract`.
Agents must not auto-decide `external_contract` rows.

Checker refs:

- `schemas/oag_decision_matrix.schema.json`
- `scripts/oag_decision_autoresolve.py`
- `scripts/oag_lock_readiness_check.py`

## RULE-AUTO-006: Direct external impact is checkpoint-only

Rows with `external_contract_impact: direct` must route to checkpoint/user
review regardless of charter grants, decision class, or evidence.

Checker refs:

- `scripts/oag_decision_autoresolve.py`
- `scripts/oag_lock_readiness_check.py`

## RULE-AUTO-007: Mission charters cannot grant external-contract autonomy

Mission charter grants may authorize only `fact`, `reversible_internal`, or
`measured_tradeoff` autonomy. `external_contract` autonomy is human-only.

Checker refs:

- `schemas/oag_mission_charter.schema.json`
- `scripts/oag_decision_autoresolve.py`

## RULE-AUTO-008: Measured decisions require structured receipts

Agent-made decisions must retain candidate set, bench command, metrics,
comparison, selection rule, artifact path, and rollback path fields in the
receipt. Empty fields must be explicit structured values.

Checker refs:

- `scripts/oag_decision_autoresolve.py`
- `scripts/oag_lock_readiness_check.py`

## RULE-AUTO-002: Fact autonomy requires local evidence

Agents may auto-decide `fact` rows only when the row cites at least one local
source path that exists in the IP workspace.

Checker refs:

- `scripts/oag_decision_autoresolve.py`
- `scripts/oag_exploration_plan.py`

## RULE-AUTO-003: Architecture tradeoff autonomy routes to DSE

Agents may route `architecture_tradeoff` rows to bounded architecture
exploration only when a human-approved mission charter grants that decision
class. The route is not a product decision and does not lock scope.

Checker refs:

- `scripts/oag_decision_autoresolve.py`
- `scripts/oag_mission_loop.py`
- `scripts/oag_lock_readiness_check.py`

## RULE-AUTO-004: Agent decisions require receipts

Agent-made decisions must retain evidence references and a decision receipt.
Readiness checks must fail missing receipts, dangling evidence, product-defining
agent decisions, and missing charter grants.

Checker refs:

- `scripts/oag_decision_autoresolve.py`
- `scripts/oag_lock_readiness_check.py`
