#!/usr/bin/env python3
"""Manage an IP-local git repository with OAG-safe ignore defaults."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "oag_ip_git.v1"
DEFAULT_COMMIT_AUTHOR = ("OAG IP Steward", "oag-ip-steward@example.invalid")
WINDOWS_GIT_CANDIDATES = (
    (Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Git" / "cmd" / "git.exe"),
    (Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Git" / "bin" / "git.exe"),
    (Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Git" / "cmd" / "git.exe"),
    (Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Git" / "bin" / "git.exe"),
    (Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Git" / "cmd" / "git.exe"),
    (Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Git" / "bin" / "git.exe"),
)

GITIGNORE_LINES = [
    "# OAG IP-local generated/transient artifacts",
    ".DS_Store",
    "__pycache__/",
    "*.pyc",
    "",
    "# Simulator and waveform dumps",
    "*.vcd",
    "*.fst",
    "*.fsdb",
    "*.vpd",
    "*.wlf",
    "*.lxt",
    "*.lxt2",
    "sim/waves/*",
    "!sim/waves/.gitkeep",
    "",
    "# Build directories and simulator databases",
    "sim/build/",
    "sim/obj_dir/",
    "sim/uvm_obj_dir/",
    "sim/runs/*/obj_dir/",
    "work/",
    "INCA_libs/",
    "xcelium.d/",
    "*.vdb/",
    "*.ucdb",
    "*.vcdplus.vpd",
    "",
    "# Large or rerunnable reports/logs",
    "*.log",
    "*.jou",
    "*.pb",
    "lint/reports/*",
    "!lint/reports/.gitkeep",
    "cov/reports/*",
    "!cov/reports/.gitkeep",
    "syn/reports/*",
    "!syn/reports/.gitkeep",
    "syn/netlist/*",
    "!syn/netlist/.gitkeep",
    "",
    "# Caches and local tool state",
    ".cache/",
    ".pytest_cache/",
    ".mypy_cache/",
    ".verilator/",
    "",
    "# Keep compact OAG source-of-record files tracked.",
    "!req/**",
    "!ontology/**",
    "!knowledge/**",
    "!rtl/**",
    "!tb/**",
    "!list/**",
    "!sdc/**",
    "!doc/**",
    "!scripts/**",
    "!*.md",
]


def git_executable() -> str | None:
    override = os.environ.get("OAG_GIT")
    if override:
        resolved = shutil.which(override) or override
        if Path(resolved).is_file():
            return resolved
    discovered = shutil.which("git")
    if discovered:
        return discovered
    for candidate in WINDOWS_GIT_CANDIDATES:
        if str(candidate) and candidate.is_file():
            return str(candidate)
    return None


def run_git(ip_dir: Path, args: list[str], *, check: bool = False) -> subprocess.CompletedProcess[str]:
    git = git_executable()
    if git is None:
        return subprocess.CompletedProcess(["git", "-C", str(ip_dir), *args], 127, "", "git executable is not available")
    return subprocess.run(
        [git, "-C", str(ip_dir), *args],
        text=True,
        capture_output=True,
        check=check,
    )


def git_available() -> bool:
    git = git_executable()
    if git is None:
        return False
    proc = subprocess.run([git, "--version"], text=True, capture_output=True, check=False)
    return proc.returncode == 0


def repository_status_paths(ip_dir: Path, project_root: Path) -> tuple[str, list[str], str]:
    """Return project-relative porcelain paths from the repository that owns *ip_dir*.

    An IP may intentionally be its own nested repository. Running status only in
    the product repository then reports the IP as one untracked directory and
    hides modified RTL below it. Resolve the owning repository first and use
    NUL-delimited porcelain output so spaces, renames, and Windows paths remain
    unambiguous.
    """

    ip_dir = ip_dir.expanduser().resolve()
    project_root = project_root.expanduser().resolve()
    git = git_executable()
    if git is None:
        return "", [], "git executable is not available"
    root_probe = subprocess.run(
        [git, "-C", str(ip_dir), "rev-parse", "--show-toplevel"],
        text=True,
        capture_output=True,
        check=False,
    )
    if root_probe.returncode != 0:
        return "", [], root_probe.stderr.strip() or root_probe.stdout.strip() or "IP is not inside a git repository"
    repo_root = Path(root_probe.stdout.strip()).expanduser().resolve()
    try:
        ip_pathspec = ip_dir.relative_to(repo_root).as_posix()
    except ValueError:
        return "", [], f"resolved git root does not contain IP directory: {repo_root}"
    args = [git, "-C", str(repo_root), "status", "--porcelain=v1", "-z", "--untracked-files=all"]
    if ip_pathspec not in {"", "."}:
        args.extend(["--", ip_pathspec])
    proc = subprocess.run(args, text=True, capture_output=True, check=False)
    if proc.returncode != 0:
        return proc.stdout.replace("\0", "\n"), [], proc.stderr.strip() or "git status failed"

    paths: list[str] = []
    entries = proc.stdout.split("\0")
    index = 0
    while index < len(entries):
        entry = entries[index]
        index += 1
        if len(entry) < 4:
            continue
        status = entry[:2]
        raw_path = entry[3:]
        if not raw_path:
            continue
        if "R" in status or "C" in status:
            index += 1  # the following NUL field is the original path
        absolute = (repo_root / Path(raw_path)).resolve()
        try:
            normalized = absolute.relative_to(project_root).as_posix()
        except ValueError:
            normalized = absolute.as_posix()
        paths.append(normalized)
    return proc.stdout.replace("\0", "\n"), sorted(set(paths)), ""


def issue(code: str, message: str, path: str = "") -> dict[str, str]:
    payload = {"code": code, "message": message}
    if path:
        payload["path"] = path
    return payload


def ensure_gitignore(ip_dir: Path) -> dict[str, Any]:
    path = ip_dir / ".gitignore"
    existing = path.read_text(encoding="utf-8").splitlines() if path.is_file() else []
    merged = list(existing)
    added: list[str] = []
    for line in GITIGNORE_LINES:
        if line not in merged:
            merged.append(line)
            added.append(line)
    path.write_text("\n".join(merged).rstrip() + "\n", encoding="utf-8")
    return {"path": str(path), "added_count": len(added), "changed": bool(added)}


def ensure_repo(ip_dir: Path) -> tuple[dict[str, Any], list[dict[str, str]]]:
    issues: list[dict[str, str]] = []
    ip_dir.mkdir(parents=True, exist_ok=True)
    if not git_available():
        return {"initialized": False, "git_available": False}, [issue("IP_GIT_NOT_AVAILABLE", "git executable is not available.")]
    initialized = False
    if not (ip_dir / ".git").exists():
        git = git_executable()
        if git is None:
            return {"initialized": False, "git_available": False}, [issue("IP_GIT_NOT_AVAILABLE", "git executable is not available.")]
        proc = subprocess.run([git, "init", str(ip_dir)], text=True, capture_output=True, check=False)
        if proc.returncode != 0:
            issues.append(issue("IP_GIT_INIT_FAILED", proc.stderr.strip() or proc.stdout.strip(), str(ip_dir)))
        else:
            initialized = True
    raw_bytes_configured = False
    if not issues:
        config = run_git(ip_dir, ["config", "--local", "core.autocrlf", "false"])
        if config.returncode != 0:
            issues.append(issue("IP_GIT_CONFIG_FAILED", config.stderr.strip() or config.stdout.strip(), str(ip_dir)))
        else:
            raw_bytes_configured = True
    return {
        "initialized": initialized,
        "git_available": True,
        "core_autocrlf": "false" if raw_bytes_configured else "",
    }, issues


def status_porcelain(ip_dir: Path) -> str:
    proc = run_git(ip_dir, ["status", "--porcelain"])
    return proc.stdout


def staged_diff_exists(ip_dir: Path) -> bool:
    proc = run_git(ip_dir, ["diff", "--cached", "--quiet"])
    return proc.returncode == 1


def current_head(ip_dir: Path) -> str:
    proc = run_git(ip_dir, ["rev-parse", "--verify", "HEAD"])
    return proc.stdout.strip() if proc.returncode == 0 else ""


def commit_all(ip_dir: Path, message: str) -> tuple[dict[str, Any], list[dict[str, str]]]:
    issues: list[dict[str, str]] = []
    add = run_git(ip_dir, ["add", "-A", "--", "."])
    if add.returncode != 0:
        return {"committed": False, "commit": ""}, [issue("IP_GIT_ADD_FAILED", add.stderr.strip() or add.stdout.strip(), str(ip_dir))]
    if not staged_diff_exists(ip_dir):
        return {"committed": False, "commit": current_head(ip_dir), "reason": "no_changes"}, []
    name, email = DEFAULT_COMMIT_AUTHOR
    commit = run_git(
        ip_dir,
        [
            "-c",
            f"user.name={name}",
            "-c",
            f"user.email={email}",
            "commit",
            "-m",
            message,
        ],
    )
    if commit.returncode != 0:
        issues.append(issue("IP_GIT_COMMIT_FAILED", commit.stderr.strip() or commit.stdout.strip(), str(ip_dir)))
        return {"committed": False, "commit": ""}, issues
    return {"committed": True, "commit": current_head(ip_dir)}, []


def init_ip_git(ip_dir: Path, *, initial_commit: bool, message: str) -> dict[str, Any]:
    repo, issues = ensure_repo(ip_dir)
    gitignore = ensure_gitignore(ip_dir) if not issues else {"changed": False, "path": str(ip_dir / ".gitignore")}
    commit: dict[str, Any] = {"committed": False, "commit": ""}
    if initial_commit and not issues:
        commit, commit_issues = commit_all(ip_dir, message)
        issues.extend(commit_issues)
    return {
        "schema_version": SCHEMA_VERSION,
        "operation": "init",
        "status": "fail" if issues else "pass",
        "ip_dir": str(ip_dir.resolve()),
        "repo": repo,
        "gitignore": gitignore,
        "commit": commit,
        "status_porcelain": status_porcelain(ip_dir) if (ip_dir / ".git").exists() else "",
        "issues": issues,
    }


def checkpoint_ip_git(ip_dir: Path, *, message: str) -> dict[str, Any]:
    repo, issues = ensure_repo(ip_dir)
    gitignore = ensure_gitignore(ip_dir) if not issues else {"changed": False, "path": str(ip_dir / ".gitignore")}
    commit: dict[str, Any] = {"committed": False, "commit": ""}
    if not issues:
        commit, commit_issues = commit_all(ip_dir, message)
        issues.extend(commit_issues)
    return {
        "schema_version": SCHEMA_VERSION,
        "operation": "checkpoint",
        "status": "fail" if issues else "pass",
        "ip_dir": str(ip_dir.resolve()),
        "repo": repo,
        "gitignore": gitignore,
        "commit": commit,
        "status_porcelain": status_porcelain(ip_dir) if (ip_dir / ".git").exists() else "",
        "issues": issues,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    init = sub.add_parser("init", help="initialize an IP-local git repo and OAG-safe .gitignore")
    init.add_argument("--ip-dir", required=True)
    init.add_argument("--initial-commit", action="store_true")
    init.add_argument("--message", default="OAG IP scaffold checkpoint")
    init.add_argument("--json", action="store_true")

    checkpoint = sub.add_parser("checkpoint", help="commit current meaningful IP-local changes")
    checkpoint.add_argument("--ip-dir", required=True)
    checkpoint.add_argument("--message", required=True)
    checkpoint.add_argument("--json", action="store_true")

    args = parser.parse_args(argv)
    if args.cmd == "init":
        result = init_ip_git(Path(args.ip_dir), initial_commit=bool(args.initial_commit), message=str(args.message))
    else:
        result = checkpoint_ip_git(Path(args.ip_dir), message=str(args.message))

    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    elif result["status"] == "pass":
        commit = result.get("commit", {})
        suffix = f" {commit.get('commit')}" if commit.get("committed") else ""
        print(f"PASS OAG IP git {result['operation']}{suffix}")
    else:
        print(f"FAIL OAG IP git {result['operation']}", file=sys.stderr)
        for item in result.get("issues", []):
            print(f"- {item.get('code')}: {item.get('message')}", file=sys.stderr)
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
