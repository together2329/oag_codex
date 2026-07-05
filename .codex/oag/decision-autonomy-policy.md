# OAG Decision Autonomy Policy

Decision autonomy is a bounded Mission/Action aid. It may reduce unnecessary
interruptions, but it must not replace human product authority, scope lock, or
OAG evidence gates.

## Legacy Decision Classes

Every decision row may carry `decision_class`:

- `fact`: a repo-local, cited fact. Agents may auto-decide only when at least
  one cited local source exists.
- `parameterizable`: a choice that remains exposed as an integration parameter.
  Agents may auto-decide by preserving configurability instead of locking a
  product value.
- `architecture_tradeoff`: an implementation tradeoff that needs bounded DSE.
  Agents may route it to architecture exploration only when a human-approved
  mission charter grants that class.
- `product_defining`: a product-visible scope, protocol, integration, or user
  promise. Agents must never auto-decide it.

Missing, unknown, or malformed `decision_class` values fail closed as
`product_defining`.

## Orthogonal Autonomy Classes

Decision autonomy is controlled by `autonomy_class`, not by
`decision_class`. Existing `decision_class` values remain valid compatibility
metadata, but a missing or malformed `autonomy_class` fails closed as
`external_contract`.

- `fact`: repo-local cited fact; use `resolution_strategy: cite` and
  `representation: truth`.
- `reversible_internal`: an implementation-local choice that remains reversible
  through a parameter or generated option; use `parameterize`,
  `generate_option`, or `parameterized_default`.
- `measured_tradeoff`: an internal tradeoff selected by bounded evidence; use
  `measure_and_select` or `parameterized_default` with candidate values,
  metrics, comparison, and a selection rule.
- `external_contract`: product, integration, protocol, visible feature, or
  user-promise authority. Agents must not decide it.

Rows also carry:

- `resolution_strategy`: `cite`, `parameterize`, `generate_option`,
  `measure_and_select`, `parameterized_default`, `defer`, or `ask`.
- `representation`: `truth`, `parameter`, or `generate_option`.
- `external_contract_impact`: `none`, `indirect`, or `direct`.
- `rollback_cost`, `candidate_values`, `selection_rule`,
  `evidence_required`, and `provisional` as the audit context for reversible or
  measured decisions.

`external_contract_impact: direct` always forces the checkpoint/user path
regardless of grants. Mission charters must not grant `external_contract`
autonomy, and product-defining or direct-impact rows cannot be auto-decided.

## Autonomy Outcomes

The decision-autonomy policy emits one of these outcomes:

- `auto_decide`: allowed only for cited `fact` rows, charter-granted
  `reversible_internal` rows, and charter-granted `measured_tradeoff` rows with
  satisfying evidence.
- `route_dse`: allowed only for charter-granted `measured_tradeoff` rows whose
  required measurement evidence is not available yet.
- `defer_question`: allowed only for external-contract questions when a
  human-approved charter explicitly batches questions to a checkpoint. This is
  not a decision.
- `needs_user`: the fail-closed outcome.

`product_defining` and `external_contract` rows may be batched for checkpoint
review, but the decision itself remains human-only. OAG scope lock remains
human-only.

## Receipts And Readiness

Agent-made decision rows must stay auditable:

- `decision_class` records the legacy compatibility class.
- `autonomy_class` records the resolved autonomy class.
- `resolution_strategy`, `representation`, and `external_contract_impact`
  record the autonomy routing inputs.
- `decided_by.kind` records `agent_with_evidence` or `agent_with_charter`.
- `evidence_refs` cite existing local evidence when evidence is required.
- `decision_receipt_ref` points to a non-empty decision receipt.
- `provisional: true` keeps agent decisions reviewable before lock.
- The receipt keeps explicit structured fields for candidate set, bench
  command, metrics, comparison, selection rule, artifact paths, and rollback
  path. If a field is not supplied, the receipt still carries an empty
  structured value.

Lock readiness must fail any agent decision that attempts to decide a
product-defining, external-contract, or direct-impact row, lacks required
evidence, lacks its receipt, lacks the approved human charter grant needed for
reversible or measured autonomy, or has a receipt missing structured comparison
fields. A valid `agent_with_charter` provisional measured-tradeoff decision
appears in readiness output as a provisional review item so human lock review
can see it explicitly.
