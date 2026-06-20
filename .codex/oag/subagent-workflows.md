# OAG Codex Subagent Workflows

Codex subagents are native Codex collaboration workers. Do not run a Python
script, shell wrapper, or manual role-play substitute to spawn them. The main
agent uses a prompt/directive to ask Codex to start native subagents, waits for
their results, integrates the result, then records durable OAG evidence through
the normal ROCEV flow.

Project-scoped custom agent definitions live in `.codex/agents/*.toml`. OAG
metadata for those roles lives in `.codex/oag/agent-catalog.toml`.

For team use, ask for OAG mode explicitly with the exact `oag` keyword. Terms
like `auto research`, `subagent`, and `signoff` describe work, but do not
activate OAG mode by themselves. Project config requests native subagent
support through `[features].multi_agent = true` and
`[features].child_agents_md = true`, and forces
`[features.multi_agent_v2].enabled = false`. This mirrors the OMO Codex runtime
pattern: v1 is not directly enabled; v2 is re-disabled so Codex can resolve to
the v1 multi-agent path when native subagents are available. Use
`scripts/oag_codex_config_doctor.py --include-omo-plugin-features --apply` to
patch user-level Codex config for team members, or rely on the SessionStart hook
to do the same at startup. The active Codex runtime still has to expose the
native subagent facility after restart or a fresh trusted project session. Do
not narrate speculative tool-namespace probes. Missing `multi_agent_v1` in one
agent surface is not proof that native subagents are unavailable; Codex CLI/App
may surface the same operation as an internal `spawn_agent` collaboration event.
If an explicit native spawn cannot be started, report
`BLOCKED: native Codex subagent unavailable in this surface` and stop or ask the
user to restart/open a fresh trusted `ip_dev` session. Do not continue by
pretending a child agent ran, and do not manually apply a child role as a
substitute unless the user explicitly waives the native-subagent requirement.

## Native Trigger

The native spawn may appear as a Codex native tool call when the current surface
exposes it:

```text
multi_agent_v1.spawn_agent({
  "message": "TASK: act as <role>. DELIVERABLE: ... SCOPE: ... VERIFY: ...",
  "agent_type": "<oag-agent-name>",
  "fork_context": false
})
```

In Codex CLI/App traces the same native path can appear as a collaboration event
such as `spawn_agent`, followed by a `wait` event and a child thread id. Both
are native Codex subagents. A Python process that role-plays the instructions is
not.

Use `agent_type` as a routing hint, not as proof that a TOML role, model,
reasoning effort, or service tier was selected. Always paste the role
requirements into `message` so the child has a self-contained executable
assignment.

Use `fork_context: false` unless the child truly needs full parent history. Full
history can make the child continue stale parent context instead of the assigned
task.

Use native waiting/mailbox behavior for child results. A wait timeout means "no
new update arrived"; it is not proof that the child failed. For long work,
require the child to send:

```text
WORKING: <task> - <current phase>
BLOCKED: <reason>
```

Use native child steering only for targeted follow-up, and close child threads
after integrating a completed or inconclusive lane.
Do not mark a dependent step complete while an active child owns evidence for
that step.

Use subagents when the work is naturally parallel and bounded:

- Read-heavy extraction: multiple specs, reference RTL trees, logs, waveform
  slices, or VIP patterns.
- Independent implementation shards: different files or modules with no shared
  edit surface.
- Independent review shards: evidence freshness, coverage gaps, protocol
  checks, or gate review.

Avoid subagents when a single edit surface needs tight sequential reasoning.
Write-heavy subagents must be assigned non-overlapping files or modules.

## Prompt Shape

```text
Use Codex subagents for this OAG task.

Spawn these agents with fork_context=false:
- agent_type=oag-legacy-ip-analyzer
  message starts:
  TASK: act as the OAG legacy/reference IP analyzer.
  DELIVERABLE: source paths, extracted behavior, inferred requirements, gaps,
  leakage risks, and evidence needs.
  SCOPE: <paths>.
  VERIFY: cite exact files/lines or state INCONCLUSIVE.
- agent_type=oag-requirement-contract-agent
  message starts:
  TASK: act as the OAG requirement-contract agent.
  DELIVERABLE: Requirement -> Obligation -> Contract candidates with IDs,
  assumptions, missing facts, and expected evidence.
  SCOPE: <spec paths>.
  VERIFY: every candidate cites source material or is marked TBD.
- agent_type=oag-ip-contract-agent
  message starts:
  TASK: act as the OAG IP contract agent.
  DELIVERABLE: observable evidence contracts, owner routing, and proof artifacts.
  SCOPE: <active IP>.
  VERIFY: every contract names observable, pass condition, evidence path, and owner.

Wait for all agents. Do not claim completion from subagent summaries. The main
agent must validate outputs, update OAG records, run checks, and call OAG decide
before any closure claim.
```

## RTL/TB Split Prompt

```text
Use Codex subagents and wait for all results.

Spawn:
- agent_type=oag-rtl-implementation-agent for rtl/<module>.sv only.
- agent_type=oag-tb-implementation-agent for tb/<test_or_monitor> only.
- agent_type=oag-rtl-lint-static-agent as read-only reviewer for filelist,
  compile, lint, and static risks after the write agents report.

Each subagent must report changed paths, evidence commands, blockers, and ROCEV
links. Write-capable evidence-producing subagents must write a non-empty receipt under
<ip>/knowledge/subagents/ or .codex/oag/subagent-receipts/ and end with final
line: OAG_EVIDENCE_RECORDED: <relative-path>. JSON receipts must follow
`.codex/schemas/oag_subagent_receipt.schema.json`.

No subagent may claim final completion.
```

## Gate Prompt

```text
Use Codex subagents for independent review.

Spawn:
- oag-evidence-validator to check records, hashes, scoreboard rows, coverage
  refs, and stale evidence from disk.
- oag-gate-reviewer to independently approve or reject the final claim after
  validator output is available.

Wait for both. The main agent reports APPROVE/REJECT with artifact paths and
does not override a blocker.
```

## Stop Hook

`hooks.json` registers a `SubagentStop` hook for write-capable
evidence-producing OAG agents. It does not execute subagents. It only blocks a
stopped write-capable child that lacks a valid `OAG_EVIDENCE_RECORDED:
<relative-path>` receipt. This mirrors the
oh-my-openagent executor-verifier pattern while keeping final closure in OAG
`check`/`decide`.
