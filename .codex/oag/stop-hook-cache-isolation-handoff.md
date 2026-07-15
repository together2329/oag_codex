# Stop Hook Target and Cache Isolation Handoff

Status: implemented and validated on 2026-07-15

Priority: high; the defect can block an unrelated Codex session and instruct it
to create invalid OAG subagent evidence or a human waiver for the wrong IP.

Observed incident: 2026-07-15, while working in a sibling MCTP workspace that
shared this repository's reusable `.codex` pack.

## Implementation Result

The root defect is fixed. Context and Stop caches now use schema v2 records
bound to a hashed session key and canonical invocation workspace. The reusable
pack's physical location is used only to locate pack assets and the default
cache directory; it is no longer treated as the caller's workspace.

The implemented target authority order is:

1. explicit payload `ip_dir`;
2. `OAG_IP_DIR`;
3. identity-valid v2 context from the same session and workspace;
4. the invocation cwd itself when it is an OAG IP;
5. a unique `run_id` match inside the invocation workspace;
6. a single active workspace IP only when the payload has a positive OAG signal
   and a session identity;
7. no target.

The context cache records the exact invocation cwd for provenance and binds
authority to the stable workspace root. This intentionally supports a session
moving between directories inside one workspace without allowing another
workspace or session to inherit its target. Legacy v1 records and identity
mismatches are non-authoritative. When no session ID and no exact cache override
are supplied, the context hook does not create anonymous shared live state.

Implemented files:

- `.codex/hooks/oag_hook_utils.py`
- `.codex/hooks/codex_context_inject.py`
- `.codex/hooks/codex_stop_gate.py`
- `.codex/scripts/oag_hook_cache_isolation_test.py`
- `.codex/scripts/smoke_test.py`
- `.codex/scripts/oag_eval.py`
- `.codex/scripts/oag_answer_key_eval.py`
- `.codex/AGENTS.md`
- `.codex/oag/recovery-playbook.md`

All real-hook evaluator calls now use a cache directory under their own
temporary root. The focused regression keeps foreign fixtures alive while the
live-equivalent Stop call runs and covers evaluator/live separation, two
sessions in one workspace, same-session blocking, explicit target priority,
relative paths, environment priority, direct-IP cwd discovery, legacy v1
rejection, deduplication, and PostCompact recovery.

Validation results:

- focused cache-isolation regression: pass;
- full smoke suite: pass;
- OAG scenario evaluation: 48/48 pass;
- OAG answer-key evaluation: 10/10 pass;
- Windows portability smoke: pass;
- pack release check: pass;
- Python compilation and `git diff --check`: pass;
- live `.codex/.cache` byte comparison across evaluator runs: unchanged.

## Objective

Prevent OAG hook tests, evaluations, and unrelated Codex sessions from changing
the target selected by the live `Stop` hook. The final behavior must preserve
the locked-write protection for the IP owned by the current session while
eliminating cross-workspace and cross-session false positives.

This is a hook runtime isolation problem. It is not an MCTP RTL problem and it
must not be fixed by creating a waiver or a synthetic subagent receipt in an IP
that the current session does not own.

## Incident Summary

The MCTP session received this unrelated block:

```text
[OAG:demo_counter_cx1] locked implementation write requires native subagent evidence.
- MAIN_AGENT_WRITE_WITHOUT_SUBAGENT: .../oag-eval-.../context_injection_before_work/...
```

The referenced IP was an `oag_eval.py` temporary fixture, not the current MCTP
IP. Later `oag.stop_check` returned `no active OAG run`, the orchestration audit
passed, and the temporary directory disappeared.

Those observations are consistent. The visible block did not come from the
active-run continuation check. It came from the separate main-write gate after
the Stop hook selected an evaluation fixture through the shared context cache.

## Exact Failure Chain

1. `.codex/hooks.json` registers `hooks/codex_stop_gate.py` for every Codex
   `Stop` event.
2. The MCTP workspace uses a `.codex` symlink to this repository's physical
   `.codex` pack.
3. Hook modules resolve their physical script path. Consequently, linked
   workspaces use the same pack root and the same `.codex/.cache` directory.
4. `scripts/oag_eval.py::case_context_injection_before_work` creates a temporary
   `demo_counter_cx1`, deletes the shared `context_inject.json`, and invokes the
   real context hook against the temporary IP.
5. `hooks/codex_context_inject.py` has a hard-coded cache path and records that
   temporary IP as the global `last_target`.
6. A concurrent or immediately following live Stop event has no explicit
   `ip_dir`. `hooks/codex_stop_gate.py` finds no usable active-run target and
   falls back to `context_inject.json:last_target`.
7. `_recent_context_targets()` accepts any path that is still a directory. It
   does not check session ID, invocation cwd, workspace, cache age, active-run
   ownership, or whether the target came from an evaluator.
8. The temporary fixture contains deliberately locked/generated artifacts with
   no native subagent receipt. `oag_main_write_gate.check_ip()` correctly fails
   for that fixture.
9. The live MCTP Stop event therefore reports the fixture failure as if it
   belonged to the MCTP session.
10. `TemporaryDirectory.cleanup()` removes the evaluation tree. A later audit
    then sees no active run and `_recent_context_targets()` no longer accepts the
    now-missing path.

The defect is repeatable. `scripts/oag_answer_key_eval.py` also invokes the real
context and Stop hooks through `smoke_test` helpers without isolated hook cache
paths. The full smoke test has context-hook cases that delete and update the
same live cache as well.

## Code Evidence

The line numbers below are from the repository state at the time of this
handoff. Use symbols rather than line numbers when editing.

| Area | Current behavior | Reference |
| --- | --- | --- |
| Stop hook registration | Runs on every Stop event | `.codex/hooks.json:57-66` |
| Physical pack root | Derives `ROOT` and `PROJECT` from resolved hook file | `.codex/hooks/codex_stop_gate.py:36-38` |
| Global target scan | Scans under the physical pack project | `.codex/hooks/codex_stop_gate.py:127-161` |
| Context fallback | Reads global `context_inject.json:last_target` | `.codex/hooks/codex_stop_gate.py:176-195` |
| Fallback use | Uses recent context when active targets are empty | `.codex/hooks/codex_stop_gate.py:240` |
| Main-write block | Runs against every selected fallback target | `.codex/hooks/codex_stop_gate.py:241-266` |
| Misleading summary | Labels all block types as active OAG runs | `.codex/hooks/codex_stop_gate.py:268-273` |
| Hard-coded context cache | No environment or session isolation | `.codex/hooks/codex_context_inject.py:39` |
| Global last target | Stores one `last_target` for all callers | `.codex/hooks/codex_context_inject.py:153-168` |
| Eval cache mutation | Deletes live cache and invokes real hook | `.codex/scripts/oag_eval.py:1397-1408` |
| Eval environment | Inherits normal environment without cache overrides | `.codex/scripts/oag_eval.py:178-187` |
| Eval cleanup | Removes fixture after the hook can observe it | `.codex/scripts/oag_eval.py:2552-2553` |
| Answer-key hook calls | Uses non-isolated context and Stop helpers | `.codex/scripts/oag_answer_key_eval.py:54-83` |
| Context helper | Has no `extra_env` parameter | `.codex/scripts/smoke_test.py:1864-1874` |
| Stop helper | Supports an override, but callers normally omit it | `.codex/scripts/smoke_test.py:1819-1831` |

At incident time, `.codex/.cache/stop_gate.json` contained an exact
`oag-eval-.../context_injection_before_work/...::main-write-gate` entry. The
cache is ignored runtime state and must not be used as permanent test evidence,
but it confirms the failure chain.

## Root Causes

### RC1: Test and production state share one cache namespace

`codex_context_inject.py` always uses:

```text
<physical-pack-root>/.cache/context_inject.json
```

Evaluations run the production hook but do not provide a test-specific cache.
One evaluator even unlinks the production cache before its assertions.

### RC2: One global `last_target` is treated as authority

The cache is designed for context deduplication and PostCompact recovery, but
the Stop hook also uses its global `last_target` as authority to select the IP
for a locked-write policy decision. Deduplication state is weaker than ownership
state and must not be promoted into an authorization decision without matching
session and workspace identity.

### RC3: Pack location is confused with invocation workspace

`Path(__file__).resolve()` correctly locates the reusable OAG pack. It does not
identify the workspace from which Codex invoked the hook. With a shared or
symlinked `.codex`, `ROOT.parent` can be different from the current workspace.
Scanning every IP under that physical project can both miss the current sibling
workspace and select an IP owned by another session.

### RC4: Stop fallback is not session-scoped

The hook payload can carry `cwd` and `session_id`; the subagent hooks already use
those fields. The context and Stop hooks do not bind cached targets to them.

### RC5: Evaluation helpers are only partially isolatable

`codex_stop_gate.py` already supports `OAG_STOP_GATE_CACHE`, and the smoke helper
can pass extra environment to it. `codex_context_inject.py` has no equivalent,
and `smoke_test.context_hook()` cannot pass an environment override. As a
result, a caller cannot fully isolate the pair of hooks.

### RC6: The emitted message hides the source of the block

The outer text says `Active OAG run(s) still require closure` even when there is
no active run and only the main-write gate failed. This delayed diagnosis and
made the later `no active OAG run` result look contradictory.

## Required Safety Invariants

The implementation is complete only if all of these remain true:

1. An evaluation or smoke test cannot read, delete, or update a live session's
   context or Stop cache.
2. Session A cannot cause Session B to select A's IP through cached state, even
   when both sessions use the same physical `.codex` pack.
3. A symlinked `.codex` pack location is never assumed to be the invocation
   workspace.
4. A cached target may drive the main-write gate only when its session and
   workspace identity match the current Stop payload.
5. Explicit `ip_dir` and `run_id` in the hook payload retain highest priority.
6. `OAG_IP_DIR` and `OAG_RUN_ID` remain supported for manual/runtime integration.
7. The current session's locked-write violation still blocks Stop.
8. An unknown or ambiguous target does not cause a block for an unrelated IP.
9. PostCompact context recovery remains scoped to the same session/workspace.
10. Test cleanup is not relied on for correctness. Isolation must hold while an
    evaluation fixture still exists and while an evaluation is running.
11. Old global cache entries cannot become authoritative after the upgrade.
12. Hook output remains JSON-only on stdout and hooks retain their intended
    fail-open/fail-closed behavior.

## Recommended Design

### 1. Separate pack identity, workspace identity, and session identity

Introduce shared hook helpers, preferably in `hooks/oag_hook_utils.py`, for:

```text
pack_root       = resolved location of the reusable .codex pack
invocation_cwd  = canonical payload.cwd, with os.getcwd() only as a fallback
session_id      = payload.session_id when present
workspace_key   = hash(canonical invocation_cwd)
session_key     = hash(session_id + canonical invocation_cwd)
```

Do not expose a raw session ID in filenames. A stable SHA-256 prefix is enough.
Keep the canonical values inside cache metadata for validation and debugging.

Treat `session_id` as required before cached context can authorize a Stop target.
When it is absent, context injection may still deduplicate output, but the Stop
hook must use only explicit `ip_dir`, environment configuration, or an
unambiguous current-workspace target. A cwd-only global recent-target fallback
is not sufficient to distinguish two sessions in one workspace.

### 2. Add an isolated cache configuration contract

Support these environment variables:

```text
OAG_HOOK_CACHE_DIR          # base directory for all session-scoped hook state
OAG_CONTEXT_INJECT_CACHE   # exact-file override for focused tests/manual use
OAG_STOP_GATE_CACHE         # existing exact-file override; preserve it
```

Recommended precedence:

```text
specific exact-file override
  -> OAG_HOOK_CACHE_DIR plus hook/session-specific relative path
  -> default .codex/.cache plus hook/session-specific relative path
```

Recommended live layout:

```text
.codex/.cache/
  context_inject/<session_key>.json
  stop_gate/<session_key>.json
```

Per-session files avoid cross-session read/modify/write loss in addition to
target leakage. If the implementation instead keeps a single JSON map, it must
provide real inter-process locking and exact session/workspace matching. A
single unlocked map with atomic replace is not sufficient because simultaneous
writers can lose each other's entries.

### 3. Make context cache records identity-bearing

Use a new cache schema rather than silently extending the authority of the
legacy global record. A suggested shape is:

```json
{
  "schema_version": "oag_context_inject_cache.v2",
  "identity": {
    "session_key": "sha256-prefix",
    "session_id": "runtime-session-id",
    "cwd": "/canonical/invocation/workspace"
  },
  "entries": {},
  "last_target": {
    "ip_dir": "/canonical/ip/path",
    "session_key": "sha256-prefix",
    "cwd": "/canonical/invocation/workspace",
    "hook_event": "UserPromptSubmit",
    "updated_at": "RFC3339 timestamp"
  },
  "post_compact_recovery": {}
}
```

Before writing `last_target`, verify that the target is an OAG IP with
`is_ip_dir()`. Before consuming it in Stop, verify all of the following:

- the cache schema is the new identity-bearing version;
- `session_id` and canonical `cwd` match the current payload;
- the target still exists and passes `is_ip_dir()`;
- the target is consistent with the current workspace or an explicit target
  previously selected in the same session;
- the record was not produced under an isolated evaluator cache namespace when
  the current hook is using the live namespace.

A time-to-live may be used for garbage collection, but not as the main security
or ownership boundary. A wrong target that is one second old is still wrong.

### 4. Replace global Stop target selection with an authority order

Recommended target resolution order:

1. `payload.ip_dir`, optionally paired with `payload.run_id`.
2. `OAG_IP_DIR`, optionally paired with `OAG_RUN_ID`.
3. A session-scoped context target with exact `session_id` and `cwd` match.
4. An unambiguous OAG IP represented by the invocation cwd itself.
5. An unambiguous current-workspace scan, only when the current payload contains
   a positive OAG work signal and the result is owned by the current session.
6. No target.

Do not scan every active run under the physical pack project and apply all of
them to every Stop event. That makes unrelated simultaneous sessions mutually
blocking. If compatibility requires an active-run scan, constrain it to the
invocation workspace and require exactly one matching target plus session-bound
context. Document any weaker compatibility fallback explicitly.

The main-write gate must use the same authoritative targets as the active-run
check. It must not independently revive a weaker global `last_target` when the
authoritative list is empty.

### 5. Make workspace discovery symlink-safe

Refactor `scan_ip_dirs()` and related helpers to accept an explicit root rather
than always scanning `ROOT.parent`:

```python
scan_ip_dirs(root: Path) -> list[Path]
active_run_ips(root: Path) -> list[Path]
target_ip_dirs(payload, workspace_root=...) -> list[Path]
```

The helper must recognize both cases:

- invocation cwd is itself an IP root;
- invocation cwd is a workspace/project containing one or more IP roots.

Keep the resolved pack root only for locating scripts, schemas, and default
cache storage.

### 6. Isolate every evaluator before invoking a real hook

Each top-level evaluator should create an isolated hook-cache directory inside
its own temporary root and pass it to every hook subprocess:

```text
<eval-temp-root>/.hook-cache/
```

Required changes:

- Extend `smoke_test.context_hook(payload, extra_env=None)` to mirror
  `smoke_test.stop_gate(...)`.
- Prefer a shared helper that constructs an isolated hook environment instead
  of repeating variables at every call site.
- Update `oag_eval.py` so `case_context_injection_before_work` never unlinks the
  live `.codex/.cache/context_inject.json`.
- Update all `oag_eval.py` real-hook calls to use the evaluation cache root.
- Update `oag_answer_key_eval.py` context and Stop calls to use its temporary
  cache root.
- Update the full `smoke_test.py` hook cases to use a cache under that test's
  `TemporaryDirectory`.
- Preserve cache sharing within one test case where deduplication and
  PostCompact recovery are the behavior under test.
- Use separate cache namespaces between cases unless a case explicitly tests
  cross-call behavior.

Do not attempt to repair this only by restoring the live cache after evaluation.
That leaves the race window open, can overwrite legitimate concurrent updates,
and cannot safely merge two live sessions.

### 7. Make Stop diagnostics state the actual gate

Emit separate, accurate summaries for:

```text
OAG run incomplete
OAG locked-write evidence missing
OAG stop check failed closed
OAG main-write gate failed closed
```

The outer summary should be neutral, for example:

```text
OAG stop gate blocked this response. Resolve the matching item below.
```

Do not say that an active run exists when only the main-write gate failed.
Include the selected `ip_dir` and target source (`payload`, `environment`,
`session_context`, or `workspace_scan`) in a diagnostic field or debug log. Do
not add noisy internal details to normal user output unless a block occurs.

## Implementation Work Packages

### WP1: Runtime identity and cache helpers

Primary files:

- `.codex/hooks/oag_hook_utils.py`
- focused tests in `.codex/scripts/smoke_test.py`

Tasks:

- Add canonical payload `cwd` and `session_id` extraction.
- Add pack-root versus invocation-workspace terminology.
- Add safe session/workspace key generation.
- Add cache-path resolution with the precedence described above.
- Parameterize IP scanning by workspace root.
- Add tests for direct IP cwd, parent workspace cwd, symlinked `.codex`, missing
  session ID, relative explicit IP paths, and Windows-style path handling where
  supported.

### WP2: Context hook isolation and schema v2

Primary file:

- `.codex/hooks/codex_context_inject.py`

Tasks:

- Honor `OAG_CONTEXT_INJECT_CACHE` and `OAG_HOOK_CACHE_DIR`.
- Move default state to a session-scoped cache file.
- Record and validate session/workspace identity.
- Keep deduplication and PostCompact recovery within the same identity.
- Stop writing a global authoritative `last_target`.
- Treat legacy `oag_context_inject_cache.v1` only as non-authoritative stale
  state. Do not migrate its `last_target` into a live Stop target.
- Preserve JSON-only stdout and fail-open error handling.

### WP3: Stop target authority and diagnostics

Primary file:

- `.codex/hooks/codex_stop_gate.py`

Tasks:

- Read the same session-scoped context cache selected by the current payload.
- Replace `_recent_context_targets()` with an identity-validating resolver.
- Remove or constrain the physical-project global active-run scan.
- Use one authoritative target list for both `oag.stop_check` and the main-write
  gate.
- Preserve explicit payload/environment priority and `OAG_STOP_GATE_CACHE`.
- Make the default Stop repeat cache session-scoped.
- Include target-source information in diagnostic/debug state.
- Correct the misleading outer block message.
- Ensure an empty or ambiguous target remains silent rather than blocking an
  unrelated IP.

### WP4: Evaluation and smoke isolation

Primary files:

- `.codex/scripts/smoke_test.py`
- `.codex/scripts/oag_eval.py`
- `.codex/scripts/oag_answer_key_eval.py`

Tasks:

- Add `extra_env` to `context_hook()`.
- Create one isolated cache root per evaluator/test scope.
- Pass both context and Stop cache configuration to all real hook subprocesses.
- Remove every deletion of the live `.codex/.cache/context_inject.json`.
- Verify `--keep-temp` keeps only isolated test caches.
- Verify normal cleanup cannot modify live cache files.

### WP5: Regression and concurrency coverage

Add a focused incident regression before relying on the full suites. The test
must keep the foreign temporary directory alive while the live Stop hook runs;
testing only after cleanup does not cover the original race.

Minimum test matrix:

| Scenario | Expected result |
| --- | --- |
| Eval context hook writes temporary IP; live Stop runs concurrently | Live Stop never names or checks the eval IP |
| Two sessions, two workspaces, one physical `.codex` | Each Stop checks only its own target |
| Two sessions in the same workspace | Cached target from one session is not authoritative for the other |
| Same session and workspace with a locked-write violation | Stop blocks and names the correct IP |
| Same session after violation receives valid receipt/waiver | Stop no longer blocks for that issue |
| Explicit payload `ip_dir` | Explicit IP wins over all cached state |
| `OAG_IP_DIR` without payload IP | Environment IP wins over cached state |
| Missing session ID and no explicit target | No global recent-target fallback |
| Context PostCompact then UserPromptSubmit in one session | Recovery injection still works |
| PostCompact marker from another session | It does not force recovery in the current session |
| Invocation cwd is the IP root | Target discovery finds that IP |
| Invocation cwd contains multiple active IPs | Hook stays silent unless one is explicitly/session selected |
| `.codex` is a symlink outside the workspace | Pack assets load, but target discovery stays in the invocation workspace |
| Eval exits abnormally before cleanup | Live hook state remains unchanged |
| Eval uses `--keep-temp` | Kept fixture remains isolated and cannot become a live target |
| Legacy v1 cache contains an existing foreign path | Stop ignores it as authority |

Where practical, add a subprocess concurrency test using a barrier so the
temporary eval IP definitely exists during the live Stop call. Avoid timing-only
sleep tests.

### WP6: Documentation, migration, and cleanup

Primary files:

- `.codex/AGENTS.md`
- `.codex/oag/recovery-playbook.md` if runtime cache recovery is documented there
- this handoff, updated with implementation status or superseded by a final note

Tasks:

- Document hook cache variables and session/workspace ownership rules.
- Document that evaluators must never use live hook cache paths.
- State that deleting a cache is recovery hygiene, not an ownership mechanism.
- Ignore legacy cache files for target authority. They may be removed manually
  only after confirming that no live session or evaluator needs them.
- Do not commit `.codex/.cache` contents.

## Approaches That Must Not Be Used as the Final Fix

- Do not special-case names beginning with `oag-eval-`, `oag-answer-key-`, or
  paths under `/tmp`. A different external workspace would still leak.
- Do not solve the incident by deleting the cache once. The next evaluator can
  recreate the same failure.
- Do not restore a saved production cache after a test. That is race-prone and
  can discard real concurrent writes.
- Do not use only a TTL. Fresh cross-session state is still unauthorized.
- Do not create a waiver or receipt for the evaluation fixture from the MCTP
  session.
- Do not disable the main-write gate globally. The correct same-session locked
  write must remain blocked.
- Do not trust `Path(__file__).resolve().parents[...]` as the current workspace.
- Do not retain a global scan of every active IP as a silent fallback for every
  Stop event.
- Do not make a legacy v1 `last_target` authoritative merely because the path
  currently exists.

## Validation Commands

Run from the repository root after implementation:

```bash
python3 -m py_compile \
  .codex/hooks/oag_hook_utils.py \
  .codex/hooks/codex_context_inject.py \
  .codex/hooks/codex_stop_gate.py \
  .codex/scripts/smoke_test.py \
  .codex/scripts/oag_eval.py \
  .codex/scripts/oag_answer_key_eval.py

python3 .codex/scripts/smoke_test.py
python3 .codex/scripts/oag_eval.py --json
python3 .codex/scripts/oag_answer_key_eval.py --json
python3 .codex/scripts/oag_windows_smoke.py --json
python3 .codex/scripts/oag_pack_release_check.py --json
git diff --check
git status --short
```

Also run the new focused cross-session regression independently so a failure is
easy to diagnose before the full smoke/eval suites.

## Acceptance Criteria

All items are required:

- The exact incident is covered by an automated regression with the foreign
  fixture alive during the live Stop call.
- Running `oag_eval.py`, `oag_answer_key_eval.py`, or `smoke_test.py` does not
  change the live session cache files.
- A Stop event in a symlinked workspace cannot select an IP from an evaluator or
  another workspace through fallback state.
- Two simultaneous sessions sharing one pack cannot select each other's cached
  target.
- A valid same-session main-write violation still blocks.
- Explicit payload and environment target behavior remains compatible.
- PostCompact recovery and context deduplication still pass in the same session.
- Legacy global cache entries are non-authoritative.
- Block output distinguishes run-continuation failures from main-write failures.
- Full smoke, scenario eval, answer-key eval, Windows smoke, and pack release
  checks pass.
- No `.codex/.cache` artifact is committed.

## Suggested Execution Order

1. Add a failing focused regression that reproduces the cross-workspace block.
2. Add cache overrides and isolate all evaluator hook calls.
3. Add session/workspace identity helpers and session-scoped cache layout.
4. Convert context injection to the v2 identity-bearing cache.
5. Replace Stop target fallback and align main-write targeting.
6. Add same-session positive tests and cross-session negative tests.
7. Correct Stop diagnostics.
8. Run all validation commands.
9. Update this document with changed files, final schema, and test results.

## Scope Boundaries

In scope:

- context-injection cache isolation;
- Stop repeat-cache isolation;
- session/workspace-aware target selection;
- evaluator and smoke-test isolation;
- hook diagnostics and regression coverage.

Audit, but do not automatically redesign unless a matching defect is found:

- `codex_subagent_oag_gate.py` cache, which already consumes `cwd` and
  `session_id`;
- `codex_subagent_oag_start.py` append-only start log;
- non-hook OAG database and IP ontology state.

Out of scope:

- MCTP requirements or RTL;
- changing the OAG locked-write policy itself;
- fabricating or retroactively adding receipts to temporary fixtures;
- broad OAG workflow refactoring unrelated to hook identity and isolation.

## Handoff Prompt for the Implementing Agent

```text
Implement the root fix described in
.codex/oag/stop-hook-cache-isolation-handoff.md.

Start by reproducing the incident with a focused test. Preserve the current
same-session locked-write protection, isolate every evaluator from live hook
state, and make cached Stop targets require exact session/workspace identity.
Do not use temp-path filtering, cache deletion, TTL-only validation, or global
gate disablement as the fix. Run the complete validation command set and report
the final cache schema, target authority order, changed files, and regression
results.
```
