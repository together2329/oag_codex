#!/usr/bin/env python3
"""Check OAG pack assumptions that commonly break on Windows hosts."""

from __future__ import annotations

import argparse
import importlib
import json
import os
import platform
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


SCRIPTS_DIR = Path(__file__).resolve().parent
CODEX_ROOT = SCRIPTS_DIR.parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

oag_ip_git = importlib.import_module("oag_ip_git")
oag_cli = importlib.import_module("oag_cli")
oag_spec_to_rtl_loop = importlib.import_module("oag_spec_to_rtl_loop")
oag_arch_bench = importlib.import_module("oag_arch_bench")
oag_dse_worktree = importlib.import_module("oag_dse_worktree")


SCHEMA_VERSION = "oag_windows_smoke.v1"
FORBIDDEN_RUNTIME_TOKENS = ("/bin/sh", "sh.exe", "shell=True", "bash -lc")
WINDOWS_HOOK_PREFIX = r"cmd.exe /d /c .codex\bin\oag-python.cmd "
WINDOWS_LAUNCHER = CODEX_ROOT / "bin" / "oag-python.cmd"


def issue(code: str, message: str, path: str = "") -> dict[str, str]:
    payload = {"code": code, "message": message}
    if path:
        payload["path"] = path
    return payload


def scan_runtime_sources() -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    issues: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    roots = [CODEX_ROOT / "hooks", CODEX_ROOT / "scripts"]
    excluded = {"smoke_test.py", "oag_windows_smoke.py"}
    for root in roots:
        for path in sorted(root.glob("*.py")):
            if path.name in excluded:
                continue
            text = path.read_text(encoding="utf-8")
            for token in FORBIDDEN_RUNTIME_TOKENS:
                if token in text:
                    issues.append(issue("WINDOWS_SHELL_ASSUMPTION", f"runtime source contains {token!r}", str(path)))
    hooks = CODEX_ROOT / "hooks.json"
    try:
        payload = json.loads(hooks.read_text(encoding="utf-8"))
    except Exception as exc:
        issues.append(issue("HOOKS_JSON_LOAD", str(exc), str(hooks)))
        return issues, warnings
    commands: list[tuple[str, str]] = []
    for entries in payload.get("hooks", {}).values():
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            for hook in entry.get("hooks", []) if isinstance(entry.get("hooks"), list) else []:
                if isinstance(hook, dict) and hook.get("command"):
                    commands.append(("command", str(hook["command"])))
                    if hook.get("commandWindows"):
                        commands.append(("commandWindows", str(hook["commandWindows"])))
                    else:
                        warnings.append(issue("HOOK_WINDOWS_COMMAND_MISSING", "hook has no Windows-specific command override", str(hook["command"])))
    for field, command in commands:
        if any(token in command for token in FORBIDDEN_RUNTIME_TOKENS):
            issues.append(issue("HOOK_COMMAND_SHELL_ASSUMPTION", f"{field} depends on a shell-specific executable", "hooks.json"))
        if field == "command" and not command.startswith("python3 "):
            warnings.append(issue("HOOK_COMMAND_NOT_PYTHON3", "default hook command is not a direct python3 invocation", command))
        if field == "commandWindows" and not command.startswith(WINDOWS_HOOK_PREFIX):
            issues.append(issue("HOOK_WINDOWS_COMMAND_NOT_LAUNCHER", "Windows hook command must use the stable cmd.exe Python launcher", command))
        if field == "commandWindows" and ("powershell" in command.lower() or "pwsh" in command.lower()):
            issues.append(issue("HOOK_WINDOWS_POWERSHELL_DEPENDENCY", "Windows hook command must not depend on PowerShell parsing", command))
        if field == "commandWindows" and '""' in command:
            issues.append(issue("HOOK_WINDOWS_EMPTY_QUOTE", "Windows hook command must avoid nested empty-quote cmd.exe patterns", command))
    if not WINDOWS_LAUNCHER.is_file():
        issues.append(issue("WINDOWS_PYTHON_LAUNCHER_MISSING", "Windows Python launcher is missing", str(WINDOWS_LAUNCHER)))
    else:
        launcher = WINDOWS_LAUNCHER.read_text(encoding="utf-8", errors="ignore").lower()
        if "py.exe -3" not in launcher or "python.exe" not in launcher:
            issues.append(issue("WINDOWS_PYTHON_LAUNCHER_FALLBACK", "Windows Python launcher must try py.exe -3 and python.exe", str(WINDOWS_LAUNCHER)))
        if "%*" in launcher:
            issues.append(issue("WINDOWS_PYTHON_LAUNCHER_ARG_SPLAT", "Windows Python launcher must quote the hook script directly instead of forwarding %*", str(WINDOWS_LAUNCHER)))
        if '"%oag_script%"' not in launcher:
            issues.append(issue("WINDOWS_PYTHON_LAUNCHER_SCRIPT_QUOTE", "Windows Python launcher must quote the hook script path internally", str(WINDOWS_LAUNCHER)))
        if "if not errorlevel 1 (" in launcher:
            issues.append(issue("WINDOWS_PYTHON_LAUNCHER_ERRORLEVEL_CAPTURE", "launcher must not read %ERRORLEVEL% inside a parenthesized block", str(WINDOWS_LAUNCHER)))
    return issues, warnings


def check_windows_launcher_runtime() -> list[dict[str, str]]:
    if os.name != "nt" or not WINDOWS_LAUNCHER.is_file():
        return []
    with tempfile.TemporaryDirectory() as tmp:
        probe = Path(tmp) / "exit_probe.py"
        probe.write_text("raise SystemExit(23)\n", encoding="utf-8")
        proc = subprocess.run(
            ["cmd.exe", "/d", "/c", str(WINDOWS_LAUNCHER), str(probe)],
            text=True,
            capture_output=True,
            check=False,
        )
    if proc.returncode == 23:
        return []
    return [
        issue(
            "WINDOWS_PYTHON_LAUNCHER_EXIT_CODE",
            f"launcher returned {proc.returncode} instead of the Python exit code 23: {proc.stderr.strip() or proc.stdout.strip()}",
            str(WINDOWS_LAUNCHER),
        )
    ]


def check_ledger_locking() -> list[dict[str, str]]:
    if os.name != "nt":
        return []
    if getattr(oag_cli, "msvcrt", None) is None:
        return [issue("WINDOWS_LEDGER_LOCK_UNAVAILABLE", "msvcrt locking is unavailable")]
    try:
        with tempfile.TemporaryDirectory() as tmp:
            with oag_cli._ledger_append_lock(Path(tmp)):  # pylint: disable=protected-access
                pass
    except Exception as exc:
        return [issue("WINDOWS_LEDGER_LOCK_FAILED", str(exc))]
    return []


def check_command_splitting() -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    argv, error = oag_spec_to_rtl_loop._split_command('python -c "print(1)"')  # pylint: disable=protected-access
    if error or argv != ["python", "-c", "print(1)"]:
        issues.append(issue("ARGV_SPLIT_DIRECT_COMMAND", f"direct command split failed: argv={argv!r} error={error!r}"))
    argv, error = oag_spec_to_rtl_loop._split_command(r'python tool.py --out "C:\Program Files\OAG\out.json"')  # pylint: disable=protected-access
    if error or argv[-1:] != [r"C:\Program Files\OAG\out.json"]:
        issues.append(issue("ARGV_SPLIT_WINDOWS_PATH", f"quoted Windows path split failed: argv={argv!r} error={error!r}"))
    argv, error = oag_spec_to_rtl_loop._split_command("python good.py && python bad.py")  # pylint: disable=protected-access
    if not error:
        issues.append(issue("ARGV_SPLIT_SHELL_META_ALLOWED", f"shell metacharacter command should be rejected: {argv!r}"))
    return issues


def check_arch_bench_path_guard() -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    for value in ("../escape", "nested/candidate"):
        try:
            oag_arch_bench.clean_id("candidate", value)
        except ValueError:
            continue
        issues.append(issue("ARCH_BENCH_PATH_ESCAPE_ALLOWED", f"candidate path escape should be rejected: {value}"))
    return issues


def check_dse_worktree_path_guard() -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    for value in ("../escape", "nested/candidate"):
        try:
            oag_dse_worktree.clean_id("candidate", value)
        except oag_dse_worktree.DseError:
            continue
        issues.append(issue("DSE_WORKTREE_PATH_ESCAPE_ALLOWED", f"DSE candidate path escape should be rejected: {value}"))
    return issues


def check_git_probe() -> tuple[list[dict[str, str]], list[dict[str, str]], dict[str, Any]]:
    issues: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    git = oag_ip_git.git_executable()
    probe = {
        "git_executable": git or "",
        "windows_candidate_count": len(oag_ip_git.WINDOWS_GIT_CANDIDATES),
        "git_version": "",
        "available": False,
    }
    if not oag_ip_git.WINDOWS_GIT_CANDIDATES:
        issues.append(issue("WINDOWS_GIT_CANDIDATES_MISSING", "Git for Windows candidate paths are not configured"))
    if git is None:
        warnings.append(issue("GIT_NOT_AVAILABLE", "git was not found on PATH or known Windows install locations"))
        return issues, warnings, probe
    proc = subprocess.run([git, "--version"], text=True, capture_output=True, check=False)
    probe["available"] = proc.returncode == 0
    probe["git_version"] = proc.stdout.strip()
    if proc.returncode != 0:
        warnings.append(issue("GIT_VERSION_FAILED", proc.stderr.strip() or proc.stdout.strip() or "git --version failed", git))
    return issues, warnings, probe


def run() -> dict[str, Any]:
    issues, warnings = scan_runtime_sources()
    launcher_runtime_issues = check_windows_launcher_runtime()
    issues.extend(launcher_runtime_issues)
    ledger_lock_issues = check_ledger_locking()
    issues.extend(ledger_lock_issues)
    issues.extend(check_command_splitting())
    issues.extend(check_arch_bench_path_guard())
    issues.extend(check_dse_worktree_path_guard())
    git_issues, git_warnings, git_probe = check_git_probe()
    issues.extend(git_issues)
    warnings.extend(git_warnings)
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "fail" if issues else "pass",
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "python": sys.version.split()[0],
        },
        "git": git_probe,
        "checks": {
            "runtime_source_scan": "pass" if not [item for item in issues if item.get("code") == "WINDOWS_SHELL_ASSUMPTION"] else "fail",
            "hook_commands": "pass" if not [item for item in issues if item.get("code") == "HOOK_COMMAND_SHELL_ASSUMPTION"] else "fail",
            "launcher_exit_code": "not_applicable" if os.name != "nt" else ("pass" if not launcher_runtime_issues else "fail"),
            "ledger_lock": "not_applicable" if os.name != "nt" else ("pass" if not ledger_lock_issues else "fail"),
            "argv_command_split": "pass" if not [item for item in issues if item.get("code", "").startswith("ARGV_SPLIT")] else "fail",
            "arch_bench_path_guard": "pass" if not [item for item in issues if item.get("code", "").startswith("ARCH_BENCH_PATH")] else "fail",
            "dse_worktree_path_guard": "pass" if not [item for item in issues if item.get("code", "").startswith("DSE_WORKTREE_PATH")] else "fail",
            "git_probe": "pass" if not git_issues else "fail",
        },
        "issues": issues,
        "warnings": warnings,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    payload = run()
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    elif payload["status"] == "pass":
        print(f"PASS {SCHEMA_VERSION}")
    else:
        print(f"FAIL {SCHEMA_VERSION}", file=sys.stderr)
        for item in payload["issues"]:
            print(f"- {item.get('code')}: {item.get('message')}", file=sys.stderr)
    return 0 if payload["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
