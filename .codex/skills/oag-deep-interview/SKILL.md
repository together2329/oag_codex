---
name: oag-deep-interview
description: Use when a hardware IP request, change request, spec document, or existing RTL must be interviewed into requirements before lock or implementation. Runs a Socratic OAG requirement interview with topology confirmation, one-question-per-round discipline, recommendation-backed option sets, ambiguity scoring, weakest-dimension targeting, document/RTL evidence citations, RTL-readiness audit, closure audit, and draft persistence through OAG artifacts before any RTL, TB, validation, or gate work.
---

# OAG Deep Interview

Use this skill to turn a vague IP request, a spec/document bundle, or existing
RTL into draft OAG scope that is ready for lock-readiness review and RTL/TB
authoring-packet preparation. It is a requirements workflow, not an
implementation workflow.

## Operating Rules

- Ask one question per round: choose the highest-impact ambiguity at that
  moment and ask only that. Do not batch unrelated protocol, storage, IRQ,
  firmware, and verification decisions.
- Present roughly four options with every user-facing round. Put the
  recommended option first, mark it `(Recommended)`, explain its tradeoff, and
  always allow free-text correction. The options answer the one question; they
  must not smuggle in extra questions.
- For lock-critical or approval-style rounds, emit a durable gate frame before
  asking the user when useful:

```bash
python3 .codex/scripts/oag_gate_frame.py create --ip-dir <ip> --stage deep-interview --kind question \
  --prompt "<single question>" \
  --option "A|<recommended label>|<tradeoff>" \
  --option "B|<label>|<tradeoff>" \
  --option "C|<label>|<tradeoff>" \
  --option "D|Other / custom|User supplies exact correction." \
  --json
```

  The gate JSON is the durable prompt state; chat rendering is only the
  fallback UI when no popup/question surface exists.
- Prefer a native question UI when the Codex surface provides one. If no popup
  or `ask`-style control is available, render the same single-question option
  block as normal chat and wait for one selection or free-text refinement.
- Preserve user language for user-facing questions and summaries.
- Do focused repo/spec reading before asking about factual brownfield details.
  Cite the file, symbol, source claim, or pattern that triggered the question.
- When the user provides documents, specifications, or RTL, treat them as
  evidence inputs. Extract facts, contradictions, and implementation surfaces
  first; ask the user only about unresolved choices, conflicts, missing
  boundaries, or intent that cannot be derived from the material.
- Route product/design choices to the user. Do not convert plausible defaults
  into locked truth.
- Persist meaningful answers with `oag.draft` before context pressure, handoff,
  or scope-lock discussion.
- Do not edit locked truth, canonical ontology, RTL, TB, sim, cov, signoff, or
  gate artifacts during the interview.

## Phase 0: Setup

1. Check OAG state if an IP workspace exists:

```bash
python3 .codex/scripts/oag_cli.py call oag.lock_status --file <lock_status_args.json>
```

2. If the workspace is missing and the user only gave a short IP request, create
   at most a draft scaffold or ask where to store draft state.
3. Run deep semantic intake for compressed source text when useful:

```bash
python3 .codex/scripts/oag_deep_semantic_intake.py --ip-dir <ip> --topic "<topic>" --prompt "<user text>" --profile <profile> --json
```

4. Set the interview threshold. Default to `0.10` ambiguity. Use `0.05` for
   lock-critical or safety-critical scope, or a user-specified stricter value.
5. For lock-critical interviews, use the deterministic round helper to build or
   validate the next option set before asking:

```bash
python3 .codex/scripts/oag_deep_interview_round.py template \
  --round <n> \
  --component "<component>" \
  --dimension <topology|goal|constraints|criteria|context|rtl_readiness|closure> \
  --ambiguity <score> \
  --why-now "<why this is the weakest target>" \
  --question "<one targeted question>"
```

Validate or render an edited round payload:

```bash
python3 .codex/scripts/oag_deep_interview_round.py validate --json-file <round.json>
python3 .codex/scripts/oag_deep_interview_round.py render --json-file <round.json>
```

Rank candidate next questions when several gaps look important:

```bash
python3 .codex/scripts/oag_deep_interview_round.py rank --json-file <candidates.json>
```

## Phase 1: Round 0 Topology

Before scoring, confirm the shape of the request. Enumerate top-level outcomes
that can succeed or fail independently:

- protocol boundary and supported spec profile;
- feature list, non-goals, and product-visible value boundaries;
- input, output, buffering, and backpressure surfaces;
- packet/session/reassembly or ordering components;
- storage/commit and firmware-visible APB/CSR surfaces;
- interrupt/status/error/drop-policy surfaces;
- verification proof surfaces.
- RTL implementation surfaces: clock/reset, handshakes, state transitions,
  datapath widths, parameterization, ordering, error recovery, and observable
  outputs.

Ask one topology question. The options are answers to that one topology
confirmation question, not follow-up questions:

```text
Round 0 | Topology confirmation | Ambiguity: not scored

I read this as these top-level IP components:
1. <component>: <one sentence>
2. ...

Should any component be added, removed, merged, split, or explicitly deferred?

Options:
1. Looks right (Recommended) - Use the listed components as draft topology.
2. Add/remove/merge components - Revise topology before scoring starts.
3. Defer one or more components - Keep deferrals visible with reasons.
4. Not sure / explain tradeoff - Ask for a short clarification before deciding.
```

If the user supplied documents or RTL, include source-backed topology:

- document/spec claims that define intended behavior;
- RTL modules, ports, parameters, state machines, and register/CSR surfaces;
- mismatches between written intent and implemented behavior;
- unknown intent that cannot be safely inferred from the artifacts.

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
- RTL-readiness clarity: could an RTL agent implement from this without asking
  another product/spec question? Are trigger, condition, response, timing,
  interface handshake, reset/default behavior, state update priority, error
  handling, parameter limits, and observable outputs concrete?

Use weighted ambiguity:

- new/draft IP: `1 - (goal*0.35 + constraints*0.25 + criteria*0.25 + context*0.15)`
- brownfield change: `1 - (goal*0.30 + constraints*0.20 + criteria*0.25 + context*0.25)`

Target the active component and dimension with the weakest score next. When
multiple components tie, rotate across components so a detailed component does
not hide ambiguous siblings. The next round should always ask the single
question that most reduces lock-blocking uncertainty right now.

### Importance Ranking Protocol

Use Gajae-style weakest-dimension targeting, then rank the candidate questions
by lock impact. The highest-impact question is the one that best reduces a
blocking uncertainty across these factors:

- lock blocker: whether the answer is required before scope lock or
  implementation dispatch;
- SSOT required gap: whether a mandatory source-of-truth field, IP-XACT-like
  section, feature row, interface/register/parameter/file-set projection,
  interface contract, requirement atom, proof row, or lifecycle field is
  missing;
- functional feature impact: whether the answer changes product-visible
  behavior or feature scope;
- performance impact: whether the answer changes latency, throughput, storage,
  timing, frequency, or PPA-sensitive constraints;
- downstream fanout: how many RTL, TB, firmware, integration, or evidence
  artifacts would change;
- irreversibility: how costly it is to change later;
- ambiguity gap: how weak the current clarity score is;
- proof gap: whether the closure method is unknown or weak;
- contradiction risk: whether current facts may conflict;
- user value: whether the answer changes the product-visible value;
- brownfield risk: whether existing code/spec assumptions could be violated;
- upstream dependency: whether later questions depend on this answer;
- researchable fact: subtract this. If repo/spec reading can answer it, read
  first instead of asking the user.
- RTL readiness gap: treat this as a lock blocker when the missing answer would
  leave an RTL/TB agent guessing about cycle behavior, interface semantics,
  state ownership, or proof expectations.

Tie-break in this order: lock blocker, SSOT required gap, downstream fanout,
upstream dependency, lower researchable-fact score, then input order. For
complex interviews, express candidate questions as JSON and run
`oag_deep_interview_round.py rank`; ask only the selected top candidate.

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

### Option Set Protocol

Every user-facing round must include an option set, not just a prose question.
Keep the round to one question, but make answering easy. The four choices are
candidate answers to that one question:

```text
Round N | Component: <component> | Targeting: <dimension> | Ambiguity: <score>
Why now: <one sentence>
Recommendation: <Option A> because <short rationale>.

Question: <single targeted question>

Options:
A. <label> (Recommended) - <effect/tradeoff if selected>
B. <conservative or narrower answer> - <effect/tradeoff>
C. <explicit defer/waive/out-of-scope answer> - <effect/tradeoff>
D. Other / refine - User supplies the exact answer or correction.

If none of A-D fits, type a custom answer directly.
```

Option labels should be concrete enough to select without reinterpreting the
question. Recommendations are draft guidance only; they become decisions only
after explicit user/spec confirmation. If an option affects RTL, TB,
firmware-visible behavior, integration assumptions, or proof obligations, link
it to `ontology/decision_matrix.yaml`.

Do not list multiple prompts such as "A. answer protocol, B. answer IRQ, C.
answer storage". That violates the interview rhythm. Instead, pick the weakest
dimension, ask the one most important question, and make A/B/C/D the plausible
answers to that question.

When the next round is complex or lock-blocking, draft the round as JSON and run
`oag_deep_interview_round.py validate` before showing it. If validation fails,
fix the option set instead of asking the user a bundled question.

Use these option families by default:

- topology: looks right, edit topology, defer scope, ask for clarification;
- goal: recommended behavior, narrower behavior, explicitly unsupported,
  refine in user's words;
- constraints: recommended boundary, stricter boundary, defer/waive boundary,
  supply another boundary;
- success criteria: scoreboard-first proof, assertion/coverage proof,
  review-only/waived proof with risk, supply another proof;
- brownfield context: extend existing path, create new boundary, defer until
  source/spec review, supply another mapping.
- RTL readiness: ready for RTL contract, need cycle/interface detail, defer
  implementation detail, supply custom RTL-facing detail.

For detailed scoring and output templates, read
`references/scoring-and-output.md` when conducting a real interview.

## Phase 3: Answer Handling

For long free-text answers, refine before scoring:

- Decision: what the user decided.
- Rationale: why.
- Constraints: user-stated boundaries.
- Non-goals: explicitly excluded scope.
- Verified context: facts backed by repo/spec evidence.
- RTL-facing detail: concrete trigger, condition, response, timing, interface,
  reset/default, state update, error/drop, and proof implications.

Ask the user to confirm the refined interpretation if it changes meaning or
contains multiple decisions. Then persist with `oag.draft`.

Use a refinement option set when free text contains multiple decisions:

```text
Recommendation: Send structured interpretation as-is.

Options:
A. Send as-is (Recommended) - Use the structured interpretation for scoring.
B. Add a constraint - User supplies the missing boundary.
C. Mark something out of scope - User supplies the excluded behavior.
D. Rewrite / other - User replaces the interpretation.
```

For brownfield facts, prefer evidence-backed confirmation:

```text
I found <symbol/path/pattern>. Should this feature extend that path, or is the
intent to create a new boundary?
```

## Phase 4: Draft Persistence

After each meaningful answer or before a long transition, call `oag.draft`:

```bash
python3 .codex/scripts/oag_cli.py call oag.draft --file <draft_args.json>
```

Use the draft to update or propose:

- `req/interview_draft.md`;
- `req/source_claims.yaml`;
- `req/ambiguity_register.yaml`;
- `ontology/decision_matrix.yaml`;
- candidate `ontology/requirement_atoms.yaml` entries, with unknown trigger,
  condition, response, timing, boundary, and proof-shape fields left as draft
  ambiguity.

When the user selects an option, persist the selection as a handoff before
scoring or moving to lock:

```bash
python3 .codex/scripts/oag_deep_interview_round.py handoff \
  --ip-dir <ip> \
  --json-file <round.json> \
  --selected-option A \
  --write-decision-matrix \
  --write-source-claim \
  --refresh-action-plan \
  --render-operation-frame
```

Use `--confirmed` only when the user or a cited source explicitly confirmed the
answer. Without `--confirmed`, generated decision rows remain proposed and
source claims remain draft. Use `--refresh-action-plan` and
`--render-operation-frame` when the answer changes the current operating state:
the handoff will regenerate Mission/Action candidates and a formal operation
frame so the next question/action is selected from the updated SSOT.

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
- RTL readiness is concrete enough that an RTL/TB implementation agent can
  produce code and tests from authoring packets without inventing product
  behavior.

Use this RTL-readiness checklist before closure:

- trigger and condition are explicit;
- response and externally visible outputs are explicit;
- timing/cycle rule is explicit or intentionally unconstrained;
- input/output handshake, backpressure, and ordering are explicit;
- reset/default and state ownership are explicit;
- error/drop/recovery behavior is explicit;
- register/CSR side effects are explicit when firmware-visible;
- proof shape identifies scoreboard/assertion/coverage expectations;
- open assumptions are either resolved, decision-matrix rows, or named
  deferrals.

Then restate the intended scope in one sentence and ask the user to approve or
correct it. For nontrivial IP work, generate the formal pre-lock HTML frame
before asking for final approval so the user can inspect the authored source
artifacts verbatim:

```bash
python3 .codex/scripts/oag_lock_preview_frame.py --ip-dir <ip> --json
```

Treat the HTML as a review envelope only. If the user changes wording or scope
after reading it, update the draft/OAG source files and regenerate the frame.
Only after explicit approval should normal OAG lock flow begin.

Use this final restatement option set:

```text
Recommendation: Approve for lock-readiness review if the sentence is complete.

Options:
A. Approve for lock-readiness review (Recommended) - Run readiness gates next.
B. Adjust wording - User supplies exact wording correction.
C. Missing scope - Return to the weakest affected topology item.
D. Custom / continue interview - User supplies exact correction, or ask another
targeted round before lock discussion.
```

## Output

End the interview with a draft scope package:

- confirmed topology and deferrals;
- established facts and source claims;
- open ambiguity rows;
- lock-blocking decision matrix status;
- option history with selected choices, recommendations, and free-text
  refinements;
- acceptance criteria and proof-shape notes;
- RTL-readiness checklist status;
- one-sentence scope restatement;
- recommendation: continue interview, ready for lock-readiness review, or
  blocked on named user decisions.
