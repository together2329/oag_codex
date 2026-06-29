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
    "context": {"score": 0.9, "gap": ""}
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
| Ontology stress | "What is the core entity here, and which named objects are supporting views?" |

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

## Decisions
| Decision | Status | Rationale | Blocks lock |
| --- | --- | --- | --- |

## Ambiguities
| Ambiguity | Component | Dimension | Required owner/action |
| --- | --- | --- | --- |

## Acceptance Criteria / Proof Shape
- <scoreboard/assertion/coverage/review evidence>

## Brownfield Evidence
- `<path>`: <why it matters>

## Interview Transcript Summary
- Round <n>: <question> -> <confirmed answer>
```
