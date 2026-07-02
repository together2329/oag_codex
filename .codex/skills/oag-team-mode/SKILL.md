---
name: oag-team-mode
description: Use when an OAG hardware IP task should be planned as a bounded Team Lead plus Worker workflow, including explicit Team Mode requests, Mission Loop recommendations for team mode, multi-role IP work such as architecture/RTL/TB/evidence/review split, or when a user asks for team mode, team plan, worker task planning, or scalable AI-agent IP development without automatic uncontrolled subagent execution.
---

# OAG Team Mode

Use this skill to decide whether an OAG IP task should stay in single-agent
mode or be split into a small team workflow.

## Rule

Team Mode v1 is **plan-only**. Do not spawn workers, claim wavefront tasks,
create dispatches, or modify RTL/TB/evidence just because this skill triggered.

Run the read-only planner:

```bash
python3 .codex/scripts/oag_team_plan.py --ip-dir <ip> --json
```

The planner writes `knowledge/team_mode/team_plan.json` unless `--no-write` is
used. Treat the output as a proposal. It does not grant implementation
authority.

## Team Shape

Use two roles by default:

- Team Lead: the current main agent; owns context, user questions, planning,
  dispatch creation after approval, review decisions, and final reporting.
- Worker: a future bounded subagent; owns one narrow task only after a proper
  OAG dispatch or wavefront claim exists.

Do not let a Worker claim final completion, gate approval, signoff, lock
authority, or broad architecture ownership.

## When To Recommend Team Mode

Recommend Team Mode when the task has several independent roles, separable write
scopes, architecture options, research value, long-running regression, or a
clear independent-review benefit.

Do not recommend Team Mode for a tiny one-file edit, a read-only explanation, a
single checker run, or a task blocked by active locks or pending gates.

If active locks, pending workflow gates, missing IP state, or unsafe final claims
exist, stop at the Team Lead and surface the blocker. Do not open more workers.

## Execution Boundary

If the user explicitly approves execution after reviewing the team plan:

1. Use `oag-wavefront` or the existing OAG dispatch flow.
2. Give each Worker a disjoint write scope and receipt path.
3. Keep `may_claim_complete=false` for Worker tasks.
4. Put shared artifacts under a single integration owner.
5. Review Worker receipts before accepting handoff.

Ask the user at most one question when a decision is genuinely required. If the
main agent can safely research, infer, or parameterize the answer, do that first
and present the recommendation.
