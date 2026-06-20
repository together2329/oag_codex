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
- no `oag.inspect` artifact gaps
- `.codex/scripts/oag_closure_check.py` for release-grade closure packages
- `oag.decide` with `record_decision=true`
- gate-review evidence with `checked_artifact_hashes` when the closure profile
  or release package requires it

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

Before canonical ontology enrichment, RTL, TB, validation, gate review, or
closure, check the scope lock:

```bash
python3 .codex/scripts/oag_cli.py call --json '{"tool":"oag.lock_status","arguments":{"ip_dir":"<ip>"}}'
```

If `state=draft`, stop at interview/draft work. Ask the user to confirm scope.
Only when the user says `lock`, `lock this`, `lock scope`, or `lock
requirements`, call `oag.lock` with `actor.kind=human` and a concise
`confirmed_scope`. New requirement drafts after a lock make the scope draft
again. No lock, no RTL. No lock, no TB. No lock, no closure.

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

Write-capable subagent assignments must start with a dispatch record:

```bash
python3 .codex/scripts/oag_dispatch.py create \
  --ip-dir <ip> \
  --agent-type <oag-write-agent> \
  --stage <stage> \
  --allowed-write-path <ip>/<owned-path> \
  --allowed-write-path <ip>/knowledge/subagents/ \
  --allowed-tool-side-effect <ip>/ontology/generated/ \
  --receipt-path <ip>/knowledge/subagents/<receipt>.json \
  --json
```

Paste `dispatch_id`, `dispatch_path`, allowed write paths, allowed tool side
effects, and receipt path into the native child spawn prompt. `oag.compile` may
be assigned as a verification step; when assigned, it may refresh
`<ip>/ontology/generated/*` as generated tool output. Do not manually edit
generated ontology files or claim ownership of generated outputs. Report
generated side effects separately from owned changed paths.

After a child reports, run a bounded path audit such as
`python3 .codex/scripts/oag_dispatch.py verify --dispatch <dispatch> --receipt
<receipt> --json`; it compares the receipt and actual
`git status --short -uall -- <ip>` delta with the dispatch baseline. Reject,
route, or explicitly explain any out-of-scope path before integration.

Worker receipts should use `HANDOFF_PASS`, `STATIC_HANDOFF_PASS`, or
`RTL_HANDOFF_PASS` for bounded handoffs. Do not use `PASS`, `COMPLETE`, `DONE`,
`SIGNOFF`, `RELEASED`, or `CLOSED` to describe the IP.

## Stop Rules

- A short IP request is requirement-interview input, not product authorization.
  For prompts like "I need mctp rx ip", create at most a draft workspace and
  `oag.draft` notes; do not edit locked truth, canonical ontology, RTL, TB,
  tests, filelists, or signoff evidence until scope is confirmed.
- `ontology/scope_lock.json` must be `locked` before implementation,
  validation, gate review, or closure. `draft` means interview only.
- Custom subagent output is never sufficient for final closure.
- Missing validator or gate-review reports block release-grade closure.
- Evidence added or changed after gate PASS makes the gate decision stale; run
  evidence validation and gate review again before `oag.decide`.
- Protected ontology, locked truth, waivers, enterprise promotion, and signoff
  policy transitions require explicit decision receipts.
- Interview drafts are durable draft knowledge, not locked truth.
- Never claim completion from tests, summaries, or inferred intent alone.
