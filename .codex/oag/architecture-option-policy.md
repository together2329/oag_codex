# Architecture Option Policy

Architecture exploration is derived evidence, not product truth.

- Inputs are approved `ontology/mission_charter.yaml` objective weights and open
  `architecture_tradeoff` rows from `ontology/decision_matrix.yaml`.
- Generated candidates and scoreboards live only under
  `knowledge/arch_exploration/<run_id>/`.
- Tier-1 metrics are deterministic ranking proxies. They may justify a
  provisional architecture decision only when the decision remains
  charter-authorized, evidence-linked, and reviewable.
- Product-defining decisions remain human-only. Architecture exploration must
  never lock scope, rewrite authored ontology truth, or write prototype RTL/TB
  into product directories.
- A missing, revoked, or invalid charter fails closed. A budget cap limits
  candidate enumeration before scoring.
- Retained generate options carry extra Tier-1 `verification_cost` because they
  add generated-configuration lifecycle and proof obligations. A retained
  generate option must remain linked to a decision row, a configuration model
  entry, and a verification-plan configuration mapping before downstream cleanup
  or implementation may consume it.
- Parameter sweeps use `oag_parameter_sweep.v1` and the deterministic
  `smallest_satisfying_with_margin` rule: sort numeric candidate values
  ascending and select the first value whose metric satisfies the target plus
  the declared margin. Sweep artifacts must preserve evidence references and
  emit issue codes for missing lifecycle links or unmatched
  `OAG-BEGIN-PROVISIONAL` / `OAG-END-PROVISIONAL` markers.
