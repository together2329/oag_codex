# Self-Exploring IP Agent Plan

This document records the design direction discussed for making OAG act less
like a one-shot coding assistant and more like a persistent, ontology-backed IP
development teammate.

It is a design memo, not locked product truth by itself. Concrete behavior must
still be implemented through OAG skills, schemas, checks, hooks, scripts, and
IP-local evidence.

## One-Line Vision

Build an ontology-backed, evidence-driven, AI-native IP development workflow
that keeps understanding the user's intent, fills safe gaps by research, asks
only the most important unresolved question, proposes architecture options, and
continues bounded Mission work until the IP reaches the next validated state.

Short version:

```text
User intent
  -> Deep Interview / semantic intake
  -> SSOT sections
  -> decision matrix
  -> requirements / obligations / contracts
  -> authoring packets
  -> wavefront actions
  -> RTL / TB / evidence
  -> validation / gate / versioned baseline
```

The desired feel is a hardware IP development "Jarvis", but with engineering
guardrails: explicit truth, explicit action records, explicit evidence, and no
silent invention of design behavior.

## What We Mean By AI-Native Knowledge Graph

This is not just a knowledge graph and not just chat memory.

OAG should maintain typed objects and relations:

- Product objects: feature, performance target, interface, register, memory
  map, parameter, module, clock domain, reset domain, file set, view, hierarchy.
- Truth objects: source claim, ambiguity, decision, requirement atom,
  requirement, obligation, contract, behavior rule, cycle rule, assumption.
- Evidence objects: scenario, scoreboard event, coverage goal, assertion,
  formal proof, lint report, simulation result, validation record, gate
  decision, artifact hash.
- Operation objects: mission, open item, action candidate, action instance,
  wavefront task, dispatch, ownership lock, receipt, review decision, retry,
  abort, fallback.

The ontology says what exists and how it is related. The AI-native layer decides
which relation matters now, what is missing, what can be researched safely, what
must be asked, and what action should run next.

## Why This Is Needed

The hard part in Spec-to-RTL is rarely writing the first RTL draft. The hard
part is knowing what should be true.

Without this layer, an agent tends to:

- convert vague prose directly into RTL;
- hide unresolved architecture decisions as defaults;
- ask too many questions at once;
- run implementation before requirement shape is strong enough;
- treat simulation pass as closure;
- lose why an action was opened;
- restart from terminal scrollback instead of durable state;
- get stuck when a subagent or MCP/tool hangs;
- create evidence that is not traceable to contracts.

The improved system should instead:

- separate intent, decision, truth, implementation, and evidence;
- keep every gap visible;
- pick the most important next question or action;
- make safe recommended defaults, but parameterize them when appropriate;
- use bounded autonomous work loops with stop conditions;
- keep a human-readable formal review surface before lock and gate.

## Lessons From Gajae-Code To Bring Over

Gajae-Code's useful shape is small and disciplined:

```text
deep-interview -> ralplan -> ultragoal
                         -> optional team
```

The OAG translation is:

```text
Deep Interview / semantic intake
  -> OAG planning / architecture review / decision matrix
    -> Mission / Action runtime
      -> optional wavefront team execution
```

Specific ideas to keep:

- Interview before guessing.
- Plan before mutation.
- Execute with durable evidence.
- Use team mode only when parallel execution materially helps.
- Keep planner, architect, and critic/reviewer roles read-only when they are
  supposed to reason rather than mutate.
- Persist stage artifacts and receipts instead of relying on pasted chat text.
- Use one-question-per-round discipline.
- Gather code/spec facts before asking the user about facts.
- Ask only for priorities, tradeoffs, irreversible choices, product decisions,
  or preferences that repository/spec inspection cannot resolve.
- Review plans for actionability, concrete verification, risk, alternatives,
  and file/artifact references before execution.

## Deep Interview Policy

Deep Interview is the front door for vague or high-impact IP work.

It should support:

- a short user request;
- a pasted spec document;
- an existing RTL/TB codebase;
- a brownfield bug or change request;
- a mix of documents and RTL.

Core rules:

- Ask one question at a time.
- Every round should offer about four concrete options with one recommended
  option and a free-text/custom answer path.
- Target the weakest dimension, not an arbitrary checklist.
- Explain why the selected question is the most important question now.
- Auto-research facts from docs/RTL/repo before asking the user.
- Cite source files, symbols, requirement paragraphs, or evidence rows for
  brownfield questions.
- Persist source claims, ambiguities, draft decisions, and interview state.
- Do not proceed to RTL/TB until lock-required ambiguity is resolved or waived.
- Before finalizing, restate the intended IP scope in one sentence and ask the
  user to confirm.

The interview should not ask "everything". It should ask the one question whose
answer most reduces lock risk and downstream rework.

## How To Choose The Most Important Question

The ranking should be computed from an explicit priority model, not from vibes.

Recommended priority order:

1. Lock blocker: unresolved answer blocks requirements, contracts, RTL, TB, or
   evidence.
2. Irreversibility: changing the answer later would rewrite interfaces,
   register maps, storage architecture, timing, or protocol boundaries.
3. Downstream fanout: the answer affects many obligations, contracts, modules,
   tests, scoreboards, or coverage goals.
4. Safety/security/correctness risk: wrong answer can create silent data loss,
   privilege exposure, unsafe reset/clock behavior, or unrecoverable state.
5. Functional feature priority: the answer defines user-visible capability or
   feature scope.
6. Performance/PPA impact: answer affects throughput, latency, buffering,
   timing paths, area, power, or clocking.
7. Interface/integration impact: answer affects bus binding, port shape,
   memory map, IP-XACT projection, file sets, or hierarchy.
8. Verification difficulty: answer changes oracle shape, random constraints,
   formal properties, coverage, or scoreboard observables.
9. Evidence gap: answer is needed to prove closure, not just implement code.
10. Cost of asking: ask the user only when local research and a safe default are
    insufficient.

Each candidate question can be scored:

```text
priority_score =
  lock_blocker * 100
+ irreversibility * 40
+ downstream_fanout * 30
+ safety_security * 25
+ functional_feature * 20
+ performance_ppa * 18
+ interface_impact * 18
+ verification_difficulty * 16
+ evidence_gap * 14
- local_research_confidence * 20
- safe_parameterizable_default * 10
```

The exact weights can evolve, but the principle should stay: ask the question
that most reduces irreversible uncertainty.

## Round Option Format

Every important question should be easy to answer.

Recommended round shape:

```text
Round N | Weakest dimension: <dimension> | Why now: <one sentence>

Question:
<one focused question>

Options:
1. <Recommended option> (Recommended)
   Impact: <tradeoff>
2. <Option B>
   Impact: <tradeoff>
3. <Option C>
   Impact: <tradeoff>
4. <Option D>
   Impact: <tradeoff>

Custom:
You can answer with another option or constraints in free text.
```

When a UI popup is available, this maps naturally to a single multiple-choice
prompt plus a free-text option. If the Codex surface does not expose a popup
tool in the current mode, the same shape should be printed as one concise chat
question.

## Autonomy Ladder

The agent should not ask the user for things it can safely determine.

```text
Level 0: Read local repo/spec/RTL and fill facts with citations.
Level 1: If a safe default exists and is reversible, choose it and record it.
Level 2: If a value can remain configurable, parameterize it instead of locking.
Level 3: If architecture tradeoffs remain, present 3-4 options and recommend.
Level 4: If answer is irreversible or product-defining, ask the user.
Level 5: If no answer is possible, block with exact missing evidence.
```

Research-then-ask rule:

```text
If repo/spec/RTL can answer it, do not ask.
If a good default is safe and parameterizable, pick it as proposed/default.
If the choice changes architecture, verification oracle, or user-visible scope,
ask one focused question.
```

## Parameterization Policy

Minimal decisions should be enough to create a v0 IP, but unknown future needs
should not be hard-coded as truth.

Use parameters or configuration for values that are:

- likely to change by integration target;
- not semantically essential to the requirement;
- performance/area tradeoffs;
- bounded implementation choices;
- easy to verify across representative values.

Examples of parameterizable decisions:

- data width;
- address width;
- FIFO depth;
- timeout cycles;
- number of contexts/channels;
- counter width;
- feature enable flags;
- pipeline stages;
- optional interrupt output;
- optional error counters.

Do not parameterize away real ambiguity. Protocol semantics, error policy,
ordering guarantee, security policy, reset behavior, and register access rules
still need explicit decisions or contracts.

## SSOT And Normalization

The system should use SSOT-style sections, not one giant YAML file.

Required source-of-truth sections for nontrivial IP work:

- feature scope;
- source claims;
- ambiguity register;
- decision matrix;
- requirement atoms;
- requirements;
- obligations;
- contracts;
- behavior model / cycle rules;
- structure and decomposition;
- interface specification;
- programmer's model;
- configuration/parameter model;
- verification objectives;
- TB methodology;
- evidence plan;
- IP-XACT-style integration projection;
- validation records;
- gate decision;
- version/baseline metadata.

Normalization principle:

```text
Raw user/spec/RTL text
  -> source claim
  -> normalized claim / atom
  -> schema check
  -> ambiguity or decision row if incomplete
  -> requirement / obligation / contract only after sufficient clarity
```

If a section does not match its schema, the system should not silently continue.
It should run a hygiene step: report the mismatch, repair only mechanical shape
when safe, and keep semantic gaps as ambiguity or decision rows.

## IP-XACT Role

IP-XACT is not the behavior oracle. It is the integration packaging view.

OAG should use IP-XACT-style metadata for:

- VLNV identity;
- component metadata;
- bus interfaces;
- ports;
- memory maps;
- registers and fields;
- address spaces;
- parameters;
- file sets;
- views;
- hierarchy/design;
- design configuration;
- generator chains;
- vendor-extension links back to OAG IDs.

OAG should not try to force all meaning into IP-XACT. These remain OAG truth or
external evidence objects:

- feature intent;
- requirement semantics;
- obligation owner;
- assume/guarantee contract;
- behavior/cycle oracle;
- evidence sufficiency;
- validation rationale;
- gate decision.

Practical rule:

```text
Interface / register / memory map / parameter / file / hierarchy
  -> IP-XACT-style projection

Feature / requirement / obligation / contract / evidence / validation
  -> OAG truth and evidence model

Links between them
  -> IDs or vendor-extension-style refs
```

## Lock Preview And Formal Review Surface

Before lock, the user should not have to read scattered YAML files.

The system should generate a formal HTML review frame that:

- preserves raw source artifacts verbatim;
- shows file paths and hashes;
- shows source claims;
- shows ambiguities and lock blockers;
- shows features and decisions;
- shows requirement atoms and requirements;
- shows candidate obligations and contracts;
- shows verification intent;
- shows IP-XACT-style integration metadata gaps;
- highlights what will become locked truth;
- avoids paraphrasing source text as if it were the source.

Review should happen while reading this frame. If the user changes any answer,
update the source files and regenerate the frame before lock.

## Skill Flow For IP Development

The recommended high-level skill flow:

```text
1. oag-deep-semantic-intake
   Capture source claims, hidden implications, ambiguity rows, and first
   decision candidates.

2. oag-deep-interview
   Ask one lock-reducing question at a time, with options and recommendation.

3. oag-decision-matrix
   Record lock-blocking choices and recommended/default separation.

4. oag-lock-preview-frame
   Render formal pre-lock HTML for human review.

5. oag-contract-projection
   Lower approved truth into requirement atoms, obligations, and contracts.

6. oag-authoring-packet
   Compile role-specific packets for RTL/TB/evidence agents.

7. oag-wavefront
   Plan dependency-aware parallel work with ownership locks.

8. RTL/TB/sim/formal/evidence workers
   Implement and verify only within bounded dispatch scope.

9. oag-evidence-closure
   Audit scoreboard, coverage, validation, freshness, and gate readiness.

10. oag-ip-versioning
    Commit/tag/version approved IP-local baselines.
```

The user-facing command should not need to name every skill. A Mission Runner
can select the next skill from the current state, but the state transition must
remain explainable.

## Mission Model

A Mission is a durable goal with a target state.

Examples:

- Intake this IP until RTL-ready.
- Convert locked requirements into implementation-ready contracts.
- Implement the locked IP.
- Bring evidence from stale to gate-ready.
- Repair orchestration failure and recover safe progress.

Mission contains:

- objective;
- target state;
- stop conditions;
- allowed action types;
- forbidden action types;
- active open items;
- current recommended action;
- completion criteria;
- user-question policy;
- evidence and review policy.

A Mission is created when:

- the user states a durable goal;
- an IP lifecycle stage begins;
- a run frame detects a coherent set of open items that share a target state;
- a previous Mission completes and a natural next lifecycle target opens;
- recovery is needed after a stuck action, stale evidence, or broken gate.

Mission should not be created for every small command. It should represent a
meaningful outcome, not a terminal action.

## Action Model

An Action is not the same thing as a requirement.

Actions are created from:

- open items;
- failed checks;
- stale evidence;
- unresolved decisions;
- missing SSOT sections;
- weak contracts;
- missing authoring packets;
- implementation gaps;
- lint/sim/formal failures;
- gate review blockers;
- orchestration health issues.

Action candidate count is determined by ownership and evidence boundaries, not
by the number of requirements.

Create separate Actions when:

- different roles own the work;
- write scopes differ;
- dependency barriers differ;
- evidence artifacts differ;
- one can finish without the other;
- failure recovery differs.

Merge into one Action when:

- the same role owns the same bounded write scope;
- the same check/evidence closes the same open item group;
- splitting would create artificial coordination overhead.

Lifecycle:

```text
open item
  -> action candidate
    -> selected action instance
      -> optional wavefront task
        -> dispatch / lock
          -> receipt
            -> review decision
              -> evidence / validation / gate
```

The key improvement is traceability: later we can answer not just "what
changed", but "why did we open this operation, who owned it, what evidence
closed it, and what decision accepted it".

## Mission Loop

Mission Loop is the autonomous engine.

```text
Observe
  -> Understand
    -> Plan
      -> Decide
        -> Act
          -> Record
            -> Evaluate
              -> Continue or stop
```

Expanded:

1. Observe current IP state: run frame, checks, locks, open items, git state,
   evidence freshness, role health.
2. Understand user intent and current Mission target.
3. Plan candidate Actions and rank them.
4. Decide whether to auto-act, ask one question, or stop.
5. Act through the right skill/script/subagent, with bounded ownership.
6. Record action instance, dispatch, receipt, changed paths, evidence, and
   decisions.
7. Evaluate closure/gates and role health.
8. Continue only if policy allows another safe step.

The loop should be bounded. It should never be an infinite "keep going" hook.

Stop rules:

- user question required;
- unresolved lock-required decision;
- active conflicting ownership lock;
- destructive/credentialed/external action needed;
- repeated same blocker;
- evidence failure that needs human interpretation;
- budget or max-step limit;
- role/tool hang detected;
- dirty state outside allowed scope;
- gate complete.

## Stop Hook Versus Mission Loop

Stop Hook is a guard. Mission Loop is the driver.

Stop Hook should:

- inspect latest action result;
- check receipt shape;
- verify allowed paths;
- verify no active lock is orphaned;
- detect stale or late receipts;
- decide whether a continuation is safe;
- surface the next recommended action.

Stop Hook should not:

- invent new design truth;
- bypass Mission policy;
- keep looping forever;
- spawn replacement work while a lock is active;
- treat late receipt from aborted dispatch as valid handoff.

Input prompt hooks should be lightweight. They can inject OAG run context when
the prompt is clearly OAG/IP-related, but should not run heavy checks or block
ordinary conversation every time.

## Conversation Mode And Mission Runner Mode

Two modes should coexist:

- Main Interaction Thread: the user's control room. It asks questions, explains
  choices, shows options, and receives approvals.
- Mission Runner Thread: a bounded autonomous worker that advances one active
  Mission and reports back through durable artifacts.

The current user-facing thread should remain conversational. It should not be
held hostage by a long-running worker. A separate Mission Runner can run one
tick or many bounded ticks toward the active Mission.

Preferred policy:

- one active Mission Runner per IP workspace;
- runner lock prevents concurrent mission loops;
- runner may use bounded wavefront/subagents internally;
- all user questions route back to the Main Interaction Thread;
- no hidden final completion claim without gate decision.

## Team Mode

The default user-facing team should be minimal: two people.

Baseline roles:

- Team Lead: owns the Mission, user intent, action selection, questions,
  decisions, wavefront boundaries, review, and final explanation.
- Team Member: executes one bounded lane at a time. The lane can be research,
  architecture, requirement/contract projection, RTL, TB, evidence, IP-XACT
  packaging, or review, but it is still one worker role with a bounded hat.

The Team Member may temporarily wear a specialist hat:

- Research hat: specs, docs, RTL reading, source claims.
- Architecture hat: options, tradeoffs, PPA, hierarchy, interfaces.
- Requirement/Contract hat: atoms, obligations, contracts, oracles.
- RTL hat: bounded implementation from authoring packet.
- Verification hat: independent oracle, tests, scoreboards, coverage.
- Evidence/Gate hat: validation, freshness, closure, gate decision.
- Integration hat: IP-XACT-style packaging, file sets, version/baseline.

Escalate beyond two people only when there is a real concurrency benefit:

- write scopes are disjoint;
- dependency barriers are clear;
- shared artifacts have one integration owner;
- the work would otherwise block on independent research, RTL, TB, or evidence
  lanes;
- the Team Lead can still review every receipt and decision.

Do not create a larger team just because it sounds impressive. For most IP
development, the best default is:

```text
Team Lead
  -> one Team Member with the right hat for the current Action
```

This keeps the system closer to a practical assistant: the user talks to one
lead, and the lead delegates only one bounded piece of work at a time unless
parallelism is clearly justified.

## Team Expansion Model

Expansion should preserve the two-person mental model. The user should still
feel like they are talking to one Team Lead, not managing a crowd of agents.
When more execution capacity is needed, the system expands the Team Member into
bounded Action lanes, each with one focus, one owner, one deliverable, and one
receipt.

The expansion rule is:

```text
default:
  Team Lead + one Team Member

when justified:
  Team Lead + multiple bounded Team Member lanes

never:
  vague permanent roles without action ownership
```

Borrow from the LazyCodex team mode, but adapt it to OAG:

- keep durable team state, not chat-memory-only state;
- generate a short guide for the team before work starts;
- require every member lane to have `focus`, `lens`, and `deliverable`;
- require heartbeat-style status for long-running lanes;
- use artifacts and receipts instead of long pasted transcripts;
- use isolated worktrees only when path conflicts or long-lived branches make
  isolation necessary;
- archive or close completed lanes so stale workers cannot write late outputs.

Recommended team state shape:

```yaml
schema_version: oag_team_state.v1
team_id: TEAM_<timestamp>_<slug>
mode: two_person_default
status: active

lead:
  kind: main_interaction_thread
  owns:
    - mission
    - user_intent
    - most_important_question
    - decision_selection
    - action_selection
    - wavefront_boundaries
    - receipt_review
    - final_explanation

members:
  - id: member_1
    name: current_action_worker
    focus: one concrete action or lane
    lens: area | ownership | perspective
    hat: research | architecture | requirement_contract | rtl | verification | evidence_gate | integration
    deliverable: receipt_or_artifact_path
    status: pending | active | reported | blocked | archived

artifacts_dir: knowledge/teams/<team_id>/artifacts
```

Expansion stages:

1. Stage 0: Team Lead only.
   Used for conversation, mission shaping, and deciding whether the problem is
   clear enough to act.

2. Stage 1: Two-person default.
   Team Lead selects one Action. Team Member executes that Action with the
   right hat. This is the normal mode.

3. Stage 2: Sequential hats.
   The same Team Member role performs multiple Actions one after another:
   research first, then architecture, then requirement/contract, then RTL/TB,
   then evidence. The state records each Action separately.

4. Stage 3: Parallel bounded lanes.
   Multiple Team Member lanes may run only when scopes are independent:
   read-only research can run beside planning, RTL and TB can split after
   authoring packets, and simulation/evidence can run under one integration
   owner.

5. Stage 4: Worktree isolation.
   Use isolated worktrees only when two lanes would otherwise conflict in the
   same files, or when a long-lived branch needs independent commits. Do not
   use worktrees as the default for every small task.

6. Stage 5: Temporary specialist reviewers.
   Add a reviewer, formal, CDC, timing, or security lane only as a temporary
   bounded reviewer. It must produce a receipt and then close.

Expansion triggers:

- two or more ready Actions have disjoint write paths;
- a read-only investigation can reduce ambiguity while another lane waits;
- RTL, TB, and evidence work have clear dependency barriers;
- shared artifacts can be assigned to one integration owner;
- an Action is long-running and would block the main interaction thread;
- the user explicitly asks for team mode or parallel work.

Expansion blockers:

- the Mission goal is still ambiguous;
- lock-required decisions are unresolved;
- lanes would write the same files without an integration owner;
- no receipt path or evidence path is defined;
- the Team Lead cannot review all outputs;
- a previous lane is stuck and still owns an active lock;
- connector or thread tools are unavailable and the work requires them.

Mapping to OAG:

```text
Team Lead
  -> Mission controller
  -> Action selector
  -> user-question owner
  -> integration reviewer

Team Member lane
  -> one OAG Action
  -> optional OAG dispatch
  -> optional wavefront task
  -> one receipt
  -> one bounded artifact set
```

This means Action objects are not created one-per-requirement by default. They
are created when a requirement, obligation, contract, decision, evidence gap,
or orchestration blocker needs a concrete operation. A single requirement may
produce zero Actions if already closed, one Action if a clear next step exists,
or several Actions if it decomposes into independent architecture, RTL, TB, and
evidence lanes.

The system should prefer the smallest useful Action:

```text
bad:
  Implement all open requirements.

good:
  Resolve the highest lock-blocking interface decision.

good:
  Project accepted feature rows into requirement atoms and obligations.

good:
  Implement one contract-owned RTL module from its authoring packet.

good:
  Run one evidence refresh after canonical scoreboard projection.
```

Team guide generation should be automatic. Before expanding beyond the
two-person default, generate a short guide that states:

- Mission objective;
- current lock and evidence state;
- allowed files and forbidden files;
- communication rule: `WORKING`, `BLOCKED`, `HANDOFF`;
- expected receipt path;
- completion criteria;
- cleanup/archive rule.

This is the practical bridge between "AI-native team" and OAG discipline. The
team can explore, but every exploration still lands as a typed Action,
dispatch, receipt, decision, or evidence artifact.

Tests to add for team expansion:

- reject a one-member "team" when it should just be a normal Action;
- reject duplicate member focus or duplicate write ownership;
- reject expansion while lock-required decisions remain unresolved;
- allow read-only fan-out without write paths;
- require one integration owner for shared artifacts;
- reject late receipts from aborted lanes;
- verify worktree paths cannot escape the IP workspace;
- verify completed lanes are archived or closed before final gate.

## How The Agent Should Present Architecture Options

When architecture is not obvious, the agent should propose options before
locking.

Option format:

```text
Decision: <architecture decision>

1. <Recommended option> (Recommended)
   Best when: ...
   Cost: ...
   Verification impact: ...
   Parameterization: ...

2. <Alternative>
   Best when: ...
   Cost: ...
   Verification impact: ...

3. <Alternative>
   ...

4. <Minimal/deferred option>
   ...

Custom:
User may provide another architecture or constraint.
```

The recommendation should be based on:

- user intent;
- spec constraints;
- integration target;
- RTL simplicity;
- verification clarity;
- PPA;
- future extensibility;
- cost of rework;
- evidence strength.

## How A User Should Use This In Practice

Natural prompts should be enough:

```text
이 문서랑 RTL 보고 Deep Interview 해줘.
```

Expected behavior:

- read documents and RTL first;
- extract source claims and ambiguity;
- ask one critical question with options;
- persist draft artifacts.

```text
이 IP를 RTL-ready까지 Mission으로 진행해줘.
```

Expected behavior:

- create or resume a Mission;
- run semantic intake, decision matrix, and lock preview;
- stop for lock-critical user decisions.

```text
현재 run frame 보고 다음 액션 추천해줘.
```

Expected behavior:

- show four next-action options;
- recommend one;
- explain why.

```text
Mission Runner 한 tick만 돌려.
```

Expected behavior:

- execute only one bounded action;
- record result;
- report next blocker or next recommended action.

```text
계속 돌리되, 질문 필요하면 멈춰.
```

Expected behavior:

- run bounded Mission Loop;
- stop on user-question, risk, lock, or gate condition.

## Windows And Git Requirements

The workflow must work on Windows PowerShell.

Rules:

- Do not depend on `/bin/sh`.
- Do not assume `sh.exe`.
- Avoid `shell=True`.
- Run subprocesses with argument lists.
- Find `git.exe` through `PATH` or common Git for Windows install paths.
- IP-local git should be initialized per IP workspace when versioning is
  enabled.
- `.gitignore` should exclude transient dumps, build outputs, obj dirs, caches,
  waveform dumps, simulation scratch, and huge logs.
- Commit only meaningful IP state changes with clear commit messages.
- Use IP-local commits as checkpoints for important Action/Mission boundaries.
- Do not force-add large generated/transient artifacts.

PowerShell can use Git normally when Git for Windows is installed. Git Bash is
not required for ordinary git operations if `git.exe` is available.

## MCP / Connector Policy

Connectors should not block normal OAG work.

Policy:

- Do not ship project-required MCP registration unless the project truly needs
  it.
- Nonessential MCP servers should be disabled or removed from project startup.
- If a connector such as `z-ai-mcp` stalls startup, remove it from the active
  project configuration rather than letting it block all work.
- Prefer lazy-loading tools when a specific task needs them.
- Keep OAG core checks runnable without optional external MCPs.

This avoids the failure mode where the agent cannot even start because an
unrelated connector is hanging.

## Current Implementation Level

Current OAG already has many pieces:

- ROCEV-style requirement/obligation/contract/evidence/validation flow.
- Deep Interview and semantic intake skills.
- Decision matrix policy.
- Lock preview frame concept.
- Contract projection.
- Authoring packet checks.
- Wavefront planning and ownership locks.
- Evidence closure checks.
- Mission/Action object model.
- Operation review frame.
- Role health and orchestration guard.
- Initial bounded Mission Loop controller:
  `.codex/scripts/oag_mission_loop.py`.
- Ask-versus-explore planner:
  `.codex/scripts/oag_exploration_plan.py`.
- Mission/Action catalog entry for `ACT_SELF_EXPLORE_OPTIONS`, ordered before
  deep-interview and decision questions.
- Windows smoke checks.
- IP-local versioning policy.

The first persistent Mission Loop controller now exists, and it can represent
the "do not ask yet; inspect local evidence first" step as a typed Action. The
remaining gap is deeper execution integration: safe tool execution, dispatch
creation, wavefront materialization, team-state generation, optional Codex
hook/thread wakeup integration, and automatic conversion from exploration notes
into updated decisions or one residual question.

## Implementation Plan

Needed additions:

```text
.codex/oag/mission-loop-policy.md
.codex/oag/intent-memory-policy.md
.codex/oag/architecture-option-policy.md
.codex/scripts/oag_mission_loop.py              # initial bounded controller exists
.codex/scripts/oag_exploration_plan.py          # ask-versus-explore planner exists
.codex/scripts/oag_intent_packet.py
.codex/scripts/oag_architecture_options.py
.codex/scripts/oag_question_rank.py
.codex/schemas/oag_exploration_plan.schema.json # exists
.codex/schemas/oag_mission_loop_state.schema.json
.codex/schemas/oag_mission_tick.schema.json
.codex/schemas/oag_intent_packet.schema.json
.codex/schemas/oag_architecture_options.schema.json
```

Suggested CLI shape:

```bash
python3 .codex/scripts/oag_mission_loop.py tick --ip-dir <ip> --json
python3 .codex/scripts/oag_mission_loop.py run --ip-dir <ip> --max-ticks 5 --json
python3 .codex/scripts/oag_mission_loop.py pause --ip-dir <ip> --reason "<why>" --json
python3 .codex/scripts/oag_mission_loop.py explain --ip-dir <ip> --json
```

Mission loop state should record:

- active mission id;
- runner lock owner;
- current step number;
- max steps;
- last run frame hash;
- last selected action;
- why it was selected;
- checks run;
- artifacts written;
- next recommended action;
- stop reason;
- user question if needed.

## Tests To Add

Minimum tests:

- Deep Interview asks one question per round.
- Question ranker chooses lock blocker over lower-impact curiosity.
- Option generator emits four options plus custom path and recommendation.
- Auto-research avoids asking for facts present in docs/RTL.
- Parameterization policy marks flexible choices as parameters, not locked
  truth.
- Mission Loop stops on user-question-required.
- Mission Loop stops on active conflicting lock.
- Mission Loop does not accept late receipt from aborted action.
- Mission Loop emits action record for every executed step.
- Mission Loop can run one tick and stop.
- Mission Loop can run bounded multi-step and stop cleanly.
- Windows smoke catches `/bin/sh`, `sh.exe`, and `shell=True`.
- Optional MCP startup failure does not block OAG core checks.
- IP-local git ignores transient artifacts and can checkpoint meaningful state.

## Why This Makes The System Better

With this layer, OAG becomes:

- more proactive, because it can find the next action itself;
- safer, because it knows when not to act;
- easier to supervise, because each action has a reason and receipt;
- more useful in architecture exploration, because it can propose options with
  tradeoffs;
- less annoying, because it asks one high-impact question instead of a survey;
- more portable, because Windows/git/tool assumptions are explicit;
- more reviewable, because formal frames preserve raw source and hashes;
- closer to a real team, because roles, actions, and evidence are typed.

The target is not full autonomy. The target is bounded agency: the system keeps
moving on reversible, evidence-backed work and stops exactly where human intent
or engineering risk matters.
