# OAG Codex Subagent Workflows

Codex subagents are native Codex `multi_agent_v1` workers. Do not run a Python
script to spawn them. The main agent uses a prompt/directive to ask Codex to call
`multi_agent_v1.spawn_agent`, waits for mailbox signals with
`multi_agent_v1.wait_agent`, integrates the result, then records durable OAG
evidence through the normal ROCEV flow.

Project-scoped custom agent definitions live in `.codex/agents/*.toml`. OAG
metadata for those roles lives in `.codex/oag/agent-catalog.toml`.

## Native Trigger

The actual spawn is a Codex native tool call:

```text
multi_agent_v1.spawn_agent({
  "message": "TASK: act as <role>. DELIVERABLE: ... SCOPE: ... VERIFY: ...",
  "agent_type": "<oag-agent-name>",
  "fork_context": false
})
```

Use `agent_type` as a routing hint, not as proof that a TOML role, model,
reasoning effort, or service tier was selected. Always paste the role
requirements into `message` so the child has a self-contained executable
assignment.

Use `fork_context: false` unless the child truly needs full parent history. Full
history can make the child continue stale parent context instead of the assigned
task.

Use `multi_agent_v1.wait_agent` for mailbox signals only. A wait timeout means
"no new update arrived"; it is not proof that the child failed. For long work,
require the child to send:

```text
WORKING: <task> - <current phase>
BLOCKED: <reason>
```

Use `multi_agent_v1.send_input` only for targeted follow-up, and
`multi_agent_v1.close_agent` after integrating a completed or inconclusive lane.
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
links. Evidence-producing subagents must write a non-empty receipt under
<ip>/knowledge/subagents/ or .codex/oag/subagent-receipts/ and end with final
line: OAG_EVIDENCE_RECORDED: <relative-path>

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

`hooks.json` registers a `SubagentStop` hook for evidence-producing OAG agents.
It does not execute subagents. It only blocks a stopped child that lacks a valid
`OAG_EVIDENCE_RECORDED: <relative-path>` receipt. This mirrors the
oh-my-openagent executor-verifier pattern while keeping final closure in OAG
`check`/`decide`.
