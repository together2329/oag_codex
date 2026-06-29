---
name: oag-deep-semantic-intake
description: Use when a compressed hardware IP request or spec note must be decomposed into source claims, hidden implications, ambiguity rows, and lock-blocking decision candidates before requirements, RTL, or TB work.
---

# OAG Deep Semantic Intake

Use this skill before requirement lock when user input is compressed, such as
"make packet rx ip" or "AXI WDATA has the full protocol frame".

## Rules

- Preserve the original phrase as a source claim.
- Extract hidden implications instead of turning them into locked truth.
- Emit ambiguity rows for missing interface, protocol, storage, IRQ, error, and
  verification decisions.
- Emit decision candidates with `status: unresolved` or `proposed`, never
  `decided`, unless the user explicitly confirms them.
- Do not edit `req/locked_truth.md`, canonical ontology, RTL, TB, or evidence
  as part of intake.

## Deep Interview Discipline

Use `oag-deep-interview` when intake becomes a requirement interview instead of
a single source-note capture. At minimum, preserve these handoff constraints:

- Ask one scope or ambiguity question at a time.
- Start with a Round 0 topology check before scoring or lock discussion.
- Track clarity for each active topology item and target the weakest clarity dimension next.
- Send implementation-affecting choices to `ontology/decision_matrix.yaml` via
  `oag-decision-matrix`; do not hide them in prose notes.
- For brownfield or imported IP work, answer factual questions from focused
  repo/spec evidence first and cite the file, symbol, or source claim that
  triggered the question. Route product/design decisions back to the user.
- Refine long free-text answers into decision, rationale, constraints,
  non-goals, and verified context before promoting them into `oag.draft`.
- Do not move from draft/interview to scope lock until a closure audit confirms
  all active topology items have goal, constraint, and success-criteria
  coverage, and the user approves a one-sentence restatement of the intended
  scope.

## Tool

Use:

```bash
python3 .codex/scripts/oag_deep_semantic_intake.py --ip-dir <ip> --topic "<topic>" --prompt "<user/source text>" --profile <profile> --json
```

For protocol packet IP requests, use `--profile protocol-packet-ip`.
