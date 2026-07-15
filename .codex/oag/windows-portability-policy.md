# Windows Portability Policy

OAG must treat Windows compatibility as a source-database property, not only as a
runtime smoke test. The same `.codex` pack should remain usable from Codex hooks,
cmd.exe-launched hooks, PowerShell-operated terminals, and Git for Windows
worktrees.

## Hard Rules

- Hook `commandWindows` entries must resolve the Git root and invoke `python`
  directly; do not depend on PowerShell parsing or the `python3` executable name
  for Windows hooks.
- Runtime scripts and hooks must not depend on `/bin/sh`, `sh.exe`,
  `bash -lc`, or `shell=True`.
- Python subprocess calls that execute tools must pass an argv list. If a user
  command string is accepted, split and reject shell metacharacters before
  execution.
- `.codex` source paths must avoid Windows case-insensitive collisions,
  reserved basenames (`CON`, `PRN`, `AUX`, `NUL`, `COM1`-`COM9`,
  `LPT1`-`LPT9`), trailing spaces/dots, and filename characters forbidden by
  Windows.
- IP-local paths stored in OAG records should be relative, normalized with
  forward slashes, and interpreted through Python path APIs rather than shell
  string concatenation.
- Git operations must call `git` directly from Python and allow Git for Windows
  discovery; do not force shell-specific wrappers.

## Advisory Rules

- Keep generated and source path lengths below legacy Windows tool limits where
  practical. Long path support is not guaranteed on every host.
- Avoid inline single-quoted JSON CLI examples for Windows-facing instructions.
  Prefer JSON files, stdin, or Python-generated payloads when commands must work
  in PowerShell and cmd.exe.
- Document `python3` examples for POSIX operator convenience, but keep hook
  execution and Windows smoke independent of the `python3` executable name.
- Treat PowerShell guidance as operator-facing only. Hooks should remain stable
  under the cmd.exe launcher.

## Deterministic Coverage

Run:

```bash
python3 .codex/scripts/oag_windows_smoke.py --json
```

This checks hook launchers, runtime shell assumptions, argv splitting,
Windows-path DB portability, Git for Windows discovery, known path escape
guards, and an actual PowerShell `oag_cli.py --file` argv probe when `pwsh` or
`powershell` is available. On a Windows or PowerShell CI lane, run with
`--require-powershell` so a missing PowerShell executable is a hard failure.
Warnings are advisory; hard issues block release readiness.
