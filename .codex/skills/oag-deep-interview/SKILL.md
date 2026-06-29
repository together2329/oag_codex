---
name: oag-deep-interview
description: Use when a hardware IP request or change request is ambiguous enough that requirements must be interviewed before lock or implementation. Runs a Socratic OAG requirement interview with topology confirmation, one-question-per-round discipline, ambiguity scoring, weakest-dimension targeting, brownfield evidence citations, closure audit, and draft persistence through OAG artifacts before any RTL, TB, validation, or gate work.
---

# OAG Deep Interview

Use this skill to turn a vague IP request into draft OAG scope that is ready for
lock-readiness review. It is a requirements workflow, not an implementation
workflow.

## Operating Rules

- Ask one question per round. Do not batch unrelated protocol, storage, IRQ,
  firmware, and verification decisions.
- Preserve user language for user-facing questions and summaries.
- Do focused repo/spec reading before asking about factual brownfield details.
  Cite the file, symbol, source claim, or pattern that triggered the question.
- Route product/design choices to the user. Do not convert plausible defaults
  into locked truth.
- Persist meaningful answers with `oag.draft` before context pressure, handoff,
  or scope-lock discussion.
- Do not edit locked truth, canonical ontology, RTL, TB, sim, cov, signoff, or
  gate artifacts during the interview.

## Phase 0: Setup

1. Check OAG state if an IP workspace exists:

```bash
python3 .codex/scripts/oag_cli.py call --json '{"tool":"oag.lock_status","arguments":{"ip_dir":"<ip>"}}'
```

2. If the workspace is missing and the user only gave a short IP request, create
   at most a draft scaffold or ask where to store draft state.
3. Run deep semantic intake for compressed source text when useful:

```bash
python3 .codex/scripts/oag_deep_semantic_intake.py --ip-dir <ip> --topic "<topic>" --prompt "<user text>" --profile <profile> --json
```

4. Set the interview threshold. Default to `0.10` ambiguity. Use `0.05` for
   lock-critical or safety-critical scope, or a user-specified stricter value.

## Phase 1: Round 0 Topology

Before scoring, confirm the shape of the request. Enumerate top-level outcomes
that can succeed or fail independently:

- protocol boundary and supported spec profile;
- input, output, buffering, and backpressure surfaces;
- packet/session/reassembly or ordering components;
- storage/commit and firmware-visible APB/CSR surfaces;
- interrupt/status/error/drop-policy surfaces;
- verification proof surfaces.

Ask one topology question:

```text
Round 0 | Topology confirmation | Ambiguity: not scored

I read this as these top-level IP components:
1. <component>: <one sentence>
2. ...

Should any component be added, removed, merged, split, or explicitly deferred?
```

Store confirmed topology and deferrals in draft notes. Deferred components stay
visible in the final draft scope with user-confirmed reasons.

## Phase 2: Scored Interview Loop

After every meaningful answer, score each active topology item across:

- Goal clarity: what exact behavior or outcome is required?
- Constraint clarity: what boundaries, non-goals, limits, and protocol choices
  are fixed?
- Success-criteria clarity: what tests, scoreboard rows, assertions, coverage,
  or review evidence would prove it?
- Protocol/context clarity: for brownfield work, how the request maps to
  existing files, interfaces, states, and assumptions.

Use weighted ambiguity:

- new/draft IP: `1 - (goal*0.35 + constraints*0.25 + criteria*0.25 + context*0.15)`
- brownfield change: `1 - (goal*0.30 + constraints*0.20 + criteria*0.25 + context*0.25)`

Target the active component and dimension with the weakest score next. When
multiple components tie, rotate across components so a detailed component does
not hide ambiguous siblings.

Ambiguity is bidirectional. Increase ambiguity when an answer:

- contradicts an established draft fact;
- introduces mutually inconsistent requirements;
- evades the targeted gap;
- expands scope with a new component, interface, integration, or proof surface.

Report progress briefly after each scored round:

```text
Round N complete.
Ambiguity: <old>% -> <new>%.
Weakest target: <component> / <dimension>.
Remaining gap: <one sentence>.
```

For detailed scoring and output templates, read
`references/scoring-and-output.md` when conducting a real interview.

## Phase 3: Answer Handling

For long free-text answers, refine before scoring:

- Decision: what the user decided.
- Rationale: why.
- Constraints: user-stated boundaries.
- Non-goals: explicitly excluded scope.
- Verified context: facts backed by repo/spec evidence.

Ask the user to confirm the refined interpretation if it changes meaning or
contains multiple decisions. Then persist with `oag.draft`.

For brownfield facts, prefer evidence-backed confirmation:

```text
I found <symbol/path/pattern>. Should this feature extend that path, or is the
intent to create a new boundary?
```

## Phase 4: Draft Persistence

After each meaningful answer or before a long transition, call `oag.draft`:

```bash
python3 .codex/scripts/oag_cli.py call --json '{
  "tool": "oag.draft",
  "arguments": {
    "ip_dir": "<ip>",
    "stage": "interview",
    "title": "requirement interview round",
    "summary": "<confirmed facts and decisions>",
    "assumptions": ["<still-draft assumption>"],
    "open_questions": ["<remaining question>"],
    "actor": {"kind": "ai", "id": "codex", "surface": "oag-deep-interview"}
  }
}'
```

Use the draft to update or propose:

- `req/interview_draft.md`;
- `req/source_claims.yaml`;
- `req/ambiguity_register.yaml`;
- `ontology/decision_matrix.yaml`;
- candidate `ontology/requirement_atoms.yaml` entries, with unknown trigger,
  condition, response, timing, boundary, and proof-shape fields left as draft
  ambiguity.

## Decision Matrix Handoff

Use `oag-decision-matrix` whenever an interview answer exposes a choice that
would change RTL, TB, firmware-visible behavior, integration assumptions, or
closure evidence. The interview asks and scores; the decision matrix owns the
lock-blocking row.

Typical handoff rows:

- supported protocol/spec profile;
- input/output interface shape;
- buffering depth, packet ordering, reassembly, or backpressure policy;
- filtering/addressing behavior;
- storage/commit semantics and payload readback contract;
- APB/CSR ownership, clear-on-read/write-one-clear behavior, counter behavior;
- IRQ/status level versus pulse behavior;
- malformed packet, error/drop, counter, and recovery policy;
- required proof surface: scoreboard, assertion, coverage, formal, or review.

Execution flow:

1. During Round 0, seed candidate rows for every topology item with
   implementation impact.
2. During each interview round, update the row status:
   `unresolved` for open questions, `proposed` for draft recommendations,
   `decided` only for explicit user/spec confirmation, and `waived` only with
   a waiver reason and risk.
3. Keep `lock_required: true` for implementation-affecting rows.
4. Before recommending scope lock, run:

```bash
python3 .codex/scripts/oag_lock_readiness_check.py --ip-dir <ip> --json
```

5. If lock readiness fails on unresolved/proposed rows, continue the interview
   by targeting the weakest decision row rather than moving to RTL/TB.

## Phase 5: Closure Before Lock

Do not recommend scope lock just because the score is below threshold. Run a
closure audit first:

- every active topology item has goal, constraint, and success-criteria
  coverage;
- no unresolved contradiction or scope expansion affects implementation;
- every lock-required decision matrix row is `decided` or explicitly `waived`;
- brownfield facts cite repo/spec evidence;
- verification proof surfaces are concrete enough to seed contracts and
  authoring packets.

Then restate the intended scope in one sentence and ask the user to approve or
correct it. Only after explicit approval should normal OAG lock flow begin.

## Output

End the interview with a draft scope package:

- confirmed topology and deferrals;
- established facts and source claims;
- open ambiguity rows;
- lock-blocking decision matrix status;
- acceptance criteria and proof-shape notes;
- one-sentence scope restatement;
- recommendation: continue interview, ready for lock-readiness review, or
  blocked on named user decisions.
