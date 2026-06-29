# OAG Deep Semantic Intake Policy

Deep semantic intake preserves the user's compressed intent before OAG turns it
into requirements, obligations, contracts, RTL, TB, or evidence.

## Purpose

User phrases such as "AXI WDATA carries the protocol frame" or "make packet RX" are
valuable source intent, but they are not implementation contracts. Intake
captures the phrase, extracts hidden design implications, and records
ambiguities before an agent fills the gaps with plausible defaults.

## Canonical Artifacts

Each IP should carry:

```text
req/deep_semantic_intake/
req/source_claims.yaml
req/ambiguity_register.yaml
```

`source_claims.yaml` stores source-level claims and normalized meaning.
`ambiguity_register.yaml` stores unresolved questions that may block lock.
Detailed Markdown notes under `req/deep_semantic_intake/` preserve interview
rounds, spec notes, and layer worksheets.

## Intake Responsibilities

For each load-bearing user/spec statement, capture:

- source quote or summary;
- source location or conversation round;
- normalized meaning;
- hidden implementation implications;
- affected design layers;
- candidate requirement refs;
- decision refs and ambiguity refs.

For protocol IPs, decompose at least boundary, protocol profile, ordering or
reassembly, buffering/backpressure, storage/commit, firmware visibility,
interrupt/status, error/drop policy, and verification scenario implications.

## Draft Versus Lock

Draft intake may contain unresolved ambiguity. Lock-ready intake must resolve or
waive lock-required ambiguities before implementation dispatch.

Deep intake does not slow implementation down. It turns natural-language intent
into implementation-grade design truth so RTL and TB agents can work from the
same source without reading each other.

## Deep Interview Readiness

When a compressed prompt requires a conversation, OAG intake follows a bounded
deep-interview discipline:

- first confirm topology: top-level components, protocol boundaries, firmware
  surfaces, and verification surfaces;
- ask one question per round and aim it at the weakest unresolved clarity
  dimension instead of collecting a broad wishlist;
- keep clarity dimensions explicit: goal, constraints, success criteria, and
  protocol/context fit for brownfield work;
- use repository/spec evidence for factual confirmations and cite the source
  before asking the user to decide;
- treat contradictions, evasive answers, or scope expansion as ambiguity that
  can rise, not as automatic progress;
- before scope lock, run a closure audit and ask the user to approve a
  one-sentence restatement of the intended IP scope.

The interview may produce drafts, source claims, ambiguity rows, and decision
candidates. It must not produce locked truth, RTL, TB, or closure evidence until
the user confirms scope and OAG lock readiness gates pass.
