# OAG Mission Charter Policy

`oag_mission_charter.v1` is an operation-level authorization record for bounded
agent autonomy. It does not replace requirements, decisions, scope locks,
dispatches, receipts, evidence, or closure gates.

Mission charters are inert until approved by a human actor. An absent charter,
a proposed charter, or a revoked charter must preserve the existing default:
agents may draft, inspect, and route work, but may not treat the charter as
permission to decide product-defining scope.

Approved charters may grant autonomy only for non-product-defining decision
classes:

- `fact`: mechanically checkable facts with local evidence.
- `parameterizable`: values promoted to explicit parameters instead of hidden
  design truth.
- `architecture_tradeoff`: bounded exploration or DSE routing where the human
  has approved the class of tradeoff.

`product_defining` grants are forbidden. They must be rejected by tooling or
fail schema validation. Product-defining decisions remain human-review items
even when a charter permits checkpoint-style question batching.

Approval requires `actor.kind: human`. AI-authored proposals are allowed, but
AI actors cannot approve a charter.
