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

Use native Codex subagents when work is parallel and bounded. Do not run a
Python script, shell wrapper, or manual role-play substitute to spawn
subagents.

Every spawn assignment must be self-contained and start with `TASK:`. Include
`DELIVERABLE`, `SCOPE`, and `VERIFY`. Use `fork_context=false` unless the child
truly needs full parent history.

When the current surface exposes the v1 tool directly, use this shape:

```text
multi_agent_v1.spawn_agent({
  "message": "TASK: act as <OAG role>. DELIVERABLE: ... SCOPE: ... VERIFY: ...",
  "agent_type": "<oag-agent-name>",
  "fork_context": false
})
```

In Codex CLI/App, the same native operation may appear as an internal
`spawn_agent` collaboration event followed by `wait` and a child thread id. That
is also native. Missing `multi_agent_v1` namespace visibility in one surface is
not a reason to manually impersonate a child agent.

Treat `agent_type` as a routing hint, not proof that a TOML role, model,
reasoning effort, or service tier was selected. Put the role requirements inside
the child message.

Use native waiting/mailbox behavior for child results. A timeout means no new
mailbox update arrived; it is not proof of failure. Use native child steering
for targeted follow-up and close child threads after integrating a completed or
inconclusive lane.

If an explicit native spawn cannot be started in the active surface, report
`BLOCKED: native Codex subagent unavailable in this surface` and ask for a fresh
trusted `ip_dev` Codex CLI/App session. Do not continue as a manual
requirement-contract, IP-contract, RTL, TB, or review "subagent" unless the user
explicitly waives the native-subagent requirement.

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
