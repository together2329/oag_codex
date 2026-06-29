# OAG Deep Interview Scoring And Output

Load this reference only during a real OAG deep requirement interview or when
auditing a completed interview draft.

## Clarity Score Shape

Score each active topology item independently:

```json
{
  "component_id": "packet-filter",
  "scores": {
    "goal": {"score": 0.8, "gap": "Exact accept criteria still open"},
    "constraints": {"score": 0.6, "gap": "Broadcast behavior undecided"},
    "criteria": {"score": 0.7, "gap": "Scoreboard rows not concrete"},
    "context": {"score": 0.9, "gap": ""},
    "rtl_readiness": {"score": 0.5, "gap": "Cycle behavior and reset state are not yet implementable"}
  },
  "weakest_dimension": "constraints"
}
```

Use the minimum or coverage-weighted weakest component score for the global
dimension. Do not let one well-described component mask a sibling component
that has no acceptance criteria.

## Ambiguity Formula

For a new/draft IP:

```text
ambiguity = 1 - (goal*0.35 + constraints*0.25 + criteria*0.25 + context*0.15)
```

For a brownfield change:

```text
ambiguity = 1 - (goal*0.30 + constraints*0.20 + criteria*0.25 + context*0.25)
```

Recommended threshold is `0.10`; use `0.05` when lock risk is high.

## Document And RTL Inputs

When the user provides a document, spec excerpt, RTL file, or existing IP tree,
run the interview as evidence-backed brownfield intake:

- extract source claims from documents/specs before asking questions;
- extract RTL facts from modules, ports, parameters, state machines, registers,
  resets, handshakes, datapath widths, and observable outputs;
- compare document intent against RTL behavior and mark mismatches as
  ambiguity rows;
- do not ask the user for facts visible in the artifacts;
- ask the user about intent, policy choices, contradictions, missing
  boundaries, and behavior that cannot be safely inferred;
- cite file paths, symbols, sections, or source claims in `why_now`.

The interview remains one-question-per-round. The artifacts narrow the question
set; they do not remove the need for user decisions when implementation intent
is genuinely ambiguous.

## Round Option Set Shape

Each round should carry a compact option set so the user can answer without
inventing phrasing from scratch. A round has exactly one primary question: the
highest-impact ambiguity for the current component/dimension. The options are
candidate answers to that question, not a menu of different questions.

```json
{
  "round": 3,
  "component_id": "packet-filter",
  "target_dimension": "constraints",
  "recommendation": {
    "option_id": "A",
    "rationale": "It keeps v0 small while preserving a visible future path."
  },
  "options": [
    {
      "id": "A",
      "label": "Accept exact-match filtering",
      "recommended": true,
      "tradeoff": "Smallest RTL/TB scope; wildcard behavior remains out of scope.",
      "decision_effect": "proposed"
    },
    {
      "id": "B",
      "label": "Support exact-match plus wildcard",
      "recommended": false,
      "tradeoff": "More flexible but increases parser, storage, and coverage scope.",
      "decision_effect": "unresolved"
    },
    {
      "id": "C",
      "label": "Defer filtering",
      "recommended": false,
      "tradeoff": "Simplifies v0 but records integration risk.",
      "decision_effect": "waiver_or_deferral"
    },
    {
      "id": "D",
      "label": "Other / refine",
      "recommended": false,
      "tradeoff": "User supplies exact behavior.",
      "decision_effect": "free_text"
    }
  ]
}
```

Recommendation policy:

- exactly one option should be marked recommended unless the facts are
  genuinely insufficient;
- the recommended option is a proposed answer, never locked truth;
- `Other / refine` or equivalent free-text escape must always be present;
- every rendered round should explicitly say that if A-D do not fit, the user
  may type a custom answer directly;
- each option must answer the same primary question; do not mix protocol,
  firmware, verification, and integration prompts in one option set;
- if a Codex surface lacks popup question UI, render the same option set as a
  chat block and wait for one selection or free-text refinement;
- if an option changes implementation, verification, firmware, or integration
  semantics, map it to an ambiguity row or decision-matrix row;
- do not improve clarity scores from an option until the user selects it or a
  concrete source/spec confirms it.

Question selection policy:

- pick the weakest clarity dimension for the active topology component;
- when dimensions tie, ask the question that blocks lock readiness or later
  implementation dispatch most directly;
- cite the brownfield path/source that makes the question necessary when
  available;
- defer lower-impact follow-ups to later rounds rather than bundling them.

## Importance Ranking

The weakest dimension is the starting point, not the whole decision. Rank
candidate next questions with a transparent lock-impact score before asking.
This imports the Gajae-style discipline into OAG: ask the question that removes
the current bottleneck, explain why it is the bottleneck, and do not ask the
user for facts the repo or spec can answer.

Recommended candidate shape:

```json
{
  "schema_version": "oag_deep_interview_candidates.v1",
  "candidates": [
    {
      "id": "C_PERF_BOUNDARY",
      "component": "performance-contract",
      "dimension": "constraints",
      "question": "Should latency be a hard requirement, a target, or explicitly out of v0 closure?",
      "clarity": 0.25,
      "lock_blocker": 3,
      "ssot_required_gap": 3,
      "downstream_fanout": 3,
      "irreversibility": 2,
      "proof_gap": 3,
      "contradiction_risk": 1,
      "user_value": 2,
      "brownfield_risk": 1,
      "upstream_dependency": 2,
      "researchable_fact": 0,
      "why": "Hard-vs-target latency changes buffering, acceptance criteria, and closure evidence."
    }
  ]
}
```

Run the deterministic ranker for complex or lock-blocking interviews:

```bash
python3 .codex/scripts/oag_deep_interview_round.py rank --json-file <candidates.json>
```

Scoring factors use a 0-3 scale:

| Factor | Meaning |
| --- | --- |
| `lock_blocker` | The answer is required before lock or implementation dispatch. |
| `ssot_required_gap` | A mandatory source-of-truth section is missing: feature, function, performance, interface, register/CSR, parameter/configuration, file-set/hierarchy, error/IRQ, lifecycle, IP-XACT-style projection, or proof. |
| `downstream_fanout` | Number and importance of artifacts that would change. |
| `irreversibility` | Cost of changing later after RTL/TB/evidence exists. |
| `ambiguity_gap` or `clarity` | Current clarity weakness. If `clarity` is present, the ranker derives `ambiguity_gap = 3 * (1 - clarity)`. |
| `proof_gap` | Missing or weak closure method. |
| `contradiction_risk` | Risk that current draft facts conflict. |
| `user_value` | Product-visible value impact. |
| `brownfield_risk` | Risk of violating existing files, interfaces, states, or assumptions. |
| `upstream_dependency` | Whether later questions depend on this answer. |
| `researchable_fact` | Subtracted from the score; high values mean read repo/spec before asking. |

Tie-breakers are: highest lock blocker, highest SSOT required gap, highest
downstream fanout, highest upstream dependency, lowest researchable fact, then
input order. The selected candidate becomes the next one-question round; the
other candidates remain in the ambiguity register or option history.

For complex or lock-blocking rounds, validate the round JSON before asking:

```bash
python3 .codex/scripts/oag_deep_interview_round.py validate --json-file <round.json>
```

The validator enforces the Gajae-style core shape inside OAG: one primary
question, roughly four candidate answers, exactly one recommendation, a
free-text escape, and warnings when implementation-affecting options are not
linked to the decision matrix.

## Ambiguity-Raising Triggers

Treat these as score-lowering triggers, not as separate penalty terms:

- direct contradiction of an established draft fact;
- mutually inconsistent requirements;
- evasive or low-quality answer to the targeted gap;
- scope expansion: new component, interface, integration, feature, proof
  surface, or externally visible behavior.

Record trigger metadata in the draft:

```json
{
  "trigger": "scope_expansion",
  "affected_component": "apb-status",
  "affected_dimension": "constraints",
  "prior_score": 0.8,
  "new_score": 0.55,
  "evidence": "User added sticky error counters in round 4"
}
```

## Hardware-IP Question Styles

| Dimension | Question pattern |
| --- | --- |
| Goal | "What exact behavior happens when `<condition>` occurs?" |
| Constraints | "Which boundary is fixed: `<A>`, `<B>`, or explicitly unsupported?" |
| Success criteria | "What scoreboard/assertion/coverage row would prove this?" |
| Context | "I found `<path/symbol>`. Should the new behavior extend it or create a new boundary?" |
| RTL readiness | "Can an RTL agent implement this from trigger/condition/response/timing/interface facts, or which detail is still missing?" |
| Ontology stress | "What is the core entity here, and which named objects are supporting views?" |

## Option Patterns By Dimension

| Dimension | Option A | Option B | Option C | Option D |
| --- | --- | --- | --- | --- |
| Topology | Looks right (Recommended when complete) | Add/remove/merge | Defer component | Other / explain |
| Goal | Minimal required behavior | Broader behavior | Explicitly unsupported | Other / refine |
| Constraints | Narrow v0 boundary | Broader boundary | Waive/defer boundary | Other / refine |
| Success criteria | Scoreboard-first proof | Assertion/coverage proof | Review-only with risk | Other proof |
| Context | Extend existing path | Create new boundary | Defer until source review | Other mapping |
| RTL readiness | Ready for RTL contract | Need cycle/interface detail | Defer implementation detail | Custom RTL-facing detail |

## RTL Implementation Readiness

Before recommending lock-readiness review, require enough detail for an RTL/TB
agent to act without inventing product behavior. A draft is RTL-ready only when
each active behavior has:

- trigger and condition;
- response and externally visible effect;
- timing or cycle rule, or an explicit statement that timing is not constrained;
- input/output interface semantics, including valid/ready, backpressure,
  ordering, widths, and packet/beat boundaries when applicable;
- reset/default behavior;
- state ownership and same-cycle priority;
- error/drop/recovery policy;
- firmware-visible register/CSR side effects when present;
- acceptance criteria tied to scoreboard, assertion, coverage, formal, or
  review evidence.

If any item is missing, continue the deep interview using `rtl_readiness` as the
target dimension. Do not pass the scope to RTL/TB dispatch with a hidden
assumption.

## Final Draft Scope Template

```markdown
# OAG Deep Interview Draft: <ip/topic>

## Metadata
- Type: greenfield | brownfield
- Threshold: <value>
- Final ambiguity: <value>
- Recommendation: continue interview | ready for lock-readiness review | blocked

## One-Sentence Scope
<scope restatement approved or awaiting approval>

## Topology
| Component | Status | Description | Coverage or Deferral |
| --- | --- | --- | --- |

## Established Facts
- <fact> (source: round/source claim/path)

## Input Evidence
- Documents/specs: <paths or sections reviewed>
- RTL/source files: <paths or symbols reviewed>
- Doc/RTL mismatches: <none or named ambiguity rows>

## Decisions
| Decision | Status | Rationale | Blocks lock |
| --- | --- | --- | --- |

## Option History
| Round | Target | Recommended | Selected | Effect |
| --- | --- | --- | --- | --- |

## Ambiguities
| Ambiguity | Component | Dimension | Required owner/action |
| --- | --- | --- | --- |

## Acceptance Criteria / Proof Shape
- <scoreboard/assertion/coverage/review evidence>

## RTL Readiness
| Component | Trigger/condition | Response/timing | Interface/state/reset | Proof | Status |
| --- | --- | --- | --- | --- | --- |

## Brownfield Evidence
- `<path>`: <why it matters>

## Interview Transcript Summary
- Round <n>: <question> -> <confirmed answer>
```
