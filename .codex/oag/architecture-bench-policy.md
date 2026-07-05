# OAG Architecture Bench Policy

Tier-2 architecture benches are exploration artifacts only. They may compare
candidate implementation shapes, adapter availability, and lightweight synthesis
or lint probes, but they do not create product RTL, testbench, or signoff
evidence.

Bench inputs and outputs must stay under:

```text
knowledge/arch_exploration/<run_id>/<candidate>/
```

The bench harness must reject absolute paths, `..`, and multi-segment
`run_id` or candidate identifiers. Generated prototype RTL, logs, and
`bench_result.json` are candidate-local knowledge artifacts. They must not be
written into product `rtl/`, `tb/`, `sim/`, `lint/`, `evidence/`, `gate/`,
`scoreboard/`, or `reports/` directories.

Missing optional adapters such as Yosys or Verilator are not command failures.
The result should record `bench_unavailable` when no adapter is present, or
`pass_with_warnings` when a subset is missing and the available probes pass.
Available adapters that run and fail should produce a failing bench result.

`oag_arch_bench.py run` writes a candidate-local prototype skeleton, not product
RTL. The skeleton should reflect the candidate id and any available
`parameter_draft` / decision-assignment metadata so adapter probes are tied to a
specific candidate.

`oag_arch_bench.py sweep` writes `oag_parameter_sweep.v1` artifacts next to the
bench result. Sweeps must use the deterministic
`smallest_satisfying_with_margin` rule and preserve evidence refs to candidate
bench results when available.

Every Tier-2 bench or sweep artifact must declare:

```json
{
  "evidence_tier": "tier2_probe",
  "valid_for": ["exploration_comparison"],
  "not_valid_for": [
    "scope_lock",
    "product_rtl_claim",
    "timing_claim",
    "area_claim",
    "performance_claim",
    "external_contract_claim",
    "product_defining_claim"
  ]
}
```

This metadata is normative. Tier-2 skeleton and sweep artifacts are
non-authoritative exploration aids. They cannot by themselves satisfy
scope-lock readiness, product-defining decisions, direct external-contract
claims, timing closure, area closure, performance closure, or signoff evidence.
Lock readiness must fail a lock-required decision whose evidence set contains
only Tier-2 probe/sweep artifacts.

Protected product artifacts must not reference architecture exploration paths.
If product artifacts need a design decision, promote the decision through the
normal OAG requirement, obligation, contract, evidence, validation, and decision
flow instead of linking to exploratory bench material.
