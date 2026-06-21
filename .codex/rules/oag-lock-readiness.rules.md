# OAG Lock Readiness Rules

These rules govern the transition from draft requirement work to post-lock
implementation.

## Hard Rules

1. `ontology/scope_lock.json` controls implementation permission, but `locked`
   is not sufficient by itself.
2. Post-lock implementation requires both:
   - `oag_requirement_atom_check.py --ip-dir <ip> --json`
   - `oag_lock_readiness_check.py --ip-dir <ip> --json`
3. Any `lock_required: true` decision with `status` other than `decided` or
   `waived` blocks implementation.
4. A `decided` row without `decision` is invalid.
5. A `waived` row without `waiver_reason` is invalid.
6. A proposed recommendation is draft guidance, not locked truth.
7. RTL, TB, simulation, lint, coverage, formal, SDC, filelist, validation, and
   gate work must not proceed from unresolved lock-blocking decisions.
8. Lock readiness is not closure. It authorizes bounded implementation
   dispatch; it does not prove behavior.

## Complex IP Guidance

For complex IPs, missing decisions should be explicit by layer. A packet or
protocol IP should not lock until key choices for boundary, protocol profile,
ordering/reassembly, storage/commit, firmware visibility, interrupt/status, and
verification scope are either decided or waived with risk.
