OAG MODE ENABLED!

# OAG Mode Directive

You are operating IP Dev Agent through OAG, the Ontology Agent Gateway.
Use this mode only because the user prompt explicitly included the `oag`
keyword. Do not treat ordinary RTL, testbench, research, subagent, or signoff
wording as automatic mode activation.

## Completion Standard

Every meaningful IP claim must flow through:

```text
Requirement -> Obligation -> Contract -> Evidence -> Validation -> Decision
```

Tests green is not final completion. Final closure requires:

- `oag.compile`
- `oag.check`
- `.codex/scripts/oag_closure_check.py` for release-grade closure packages
- `oag.decide` with `record_decision=true`
- gate-review evidence when the closure profile or release package requires it

If evidence is missing, stale, unverifiable, or outside allowed paths, report
the blocker instead of claiming completion.

## Bootstrap

Before meaningful IP work, identify `ip_dir`, `stage`, and `intent`, then load
OAG context from disk:

```bash
python3 .codex/scripts/oag_cli.py call --json '{"tool":"oag.inspect","arguments":{"ip_dir":"<ip>","stage":"<stage>","intent":"<task>"}}'
python3 .codex/scripts/oag_cli.py call --json '{"tool":"oag.compile","arguments":{"ip_dir":"<ip>"}}'
python3 .codex/scripts/oag_cli.py call --json '{"tool":"oag.context","arguments":{"ip_dir":"<ip>","stage":"<stage>","intent":"<task>"}}'
```

For work that should continue across turns, use the OAG run loop:

```bash
python3 .codex/scripts/oag_cli.py call --json '{"tool":"oag.run.start","arguments":{"ip_dir":"<ip>","stage":"<stage>","intent":"<task>"}}'
python3 .codex/scripts/oag_cli.py call --json '{"tool":"oag.run.next","arguments":{"ip_dir":"<ip>"}}'
```

## Execution Loop

Use this loop for implementation, verification, and ontology changes:

```text
CONTEXT -> PIN/RED -> BUILD -> EVIDENCE -> VALIDATE -> DECIDE
```

- CONTEXT: read current OAG records, active run state, contracts, and evidence.
- PIN/RED: capture the gap, failing behavior, stale evidence, or missing proof
  before changing behavior where practical.
- BUILD: make the smallest RTL, TB, ontology, hook, script, or evidence change
  that addresses the pinned gap.
- EVIDENCE: produce concrete artifacts such as scoreboard rows, sim logs, VCD
  review notes, lint/formal/coverage reports, hashes, or decision receipts.
- VALIDATE: record findings through `oag.record` or `oag.run.record`; ensure
  validation status and evidence freshness are explicit.
- DECIDE: use OAG closure gates; do not decide from chat memory alone.

## Native Codex Subagents

Use native Codex `multi_agent_v1.spawn_agent` when work is parallel and bounded.
Do not run a Python script to spawn subagents.

Every spawn assignment must be self-contained and start with `TASK:`. Include
`DELIVERABLE`, `SCOPE`, and `VERIFY`. Use `fork_context=false` unless the child
truly needs full parent history.

Example shape:

```text
multi_agent_v1.spawn_agent({
  "message": "TASK: act as <OAG role>. DELIVERABLE: ... SCOPE: ... VERIFY: ...",
  "agent_type": "<oag-agent-name>",
  "fork_context": false
})
```

Treat `agent_type` as a routing hint, not proof that a TOML role, model,
reasoning effort, or service tier was selected. Put the role requirements inside
the child message.

Use `multi_agent_v1.wait_agent` for mailbox signals only. A timeout means no
new mailbox update arrived; it is not proof of failure. Use
`multi_agent_v1.send_input` for targeted follow-up and
`multi_agent_v1.close_agent` after integrating a completed or inconclusive lane.

Evidence-producing write-capable OAG subagents must write a non-empty receipt
and end with:

```text
OAG_EVIDENCE_RECORDED: <relative-path>
```

Active child agents that own evidence block parent closure until their output is
integrated, validated, or explicitly rejected.

## Stop Rules

- Custom subagent output is never sufficient for final closure.
- Missing validator or gate-review reports block release-grade closure.
- Protected ontology, locked truth, waivers, enterprise promotion, and signoff
  policy transitions require explicit decision receipts.
- Interview drafts are durable draft knowledge, not locked truth.
- Never claim completion from tests, summaries, or inferred intent alone.
