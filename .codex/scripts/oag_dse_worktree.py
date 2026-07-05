#!/usr/bin/env python3
# noqa: SIZE_OK - Single OAG CLI owns DSE candidate isolation, copy-back, and prune lifecycle together.
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Literal, NamedTuple


SCHEMA_VERSION = "oag_dse_worktree.v1"
ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]*")
PRODUCT_DIRS = frozenset({"rtl", "tb"})
COPY_BLOCKED_TOP = PRODUCT_DIRS | frozenset({".git", ".oag_worktrees"})
STATE_NAME = "dse_worktree.json"
GIT_TIMEOUT_SEC = 30


class CandidateRef(NamedTuple):
    ip_dir: Path
    run_id: str
    candidate: str
    mission: str


class DseError(RuntimeError):
    def __init__(self, code: str, message: str, path: Path | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.path = path


def issue(code: str, message: str, path: Path | None = None) -> dict[str, str]:
    return {"code": code, "message": message, **({"path": str(path)} if path is not None else {})}


def clean_id(kind: str, value: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise DseError("DSE_ID_REQUIRED", f"{kind} is required")
    path = Path(text)
    if path.is_absolute() or len(path.parts) != 1 or path.parts[0] in {".", ".."}:
        raise DseError("DSE_ID_PATH_ESCAPE", f"{kind} must be one safe path segment: {value}")
    if not ID_RE.fullmatch(text):
        raise DseError("DSE_ID_UNSUPPORTED_CHARS", f"{kind} contains unsupported characters: {value}")
    return text


def ip_root(value: str) -> Path: return Path(value).expanduser().resolve()


def candidate_ref(args: argparse.Namespace) -> CandidateRef:
    return CandidateRef(ip_root(args.ip_dir), clean_id("run_id", args.run_id), clean_id("candidate", args.candidate), clean_id("mission", getattr(args, "mission", "mission")))


def arch_root(ip_dir: Path) -> Path: return ip_dir / "knowledge" / "arch_exploration"


def candidate_dir(ref: CandidateRef) -> Path: return arch_root(ref.ip_dir) / ref.run_id / ref.candidate


def worktree_root(ip_dir: Path) -> Path: return ip_dir / ".oag_worktrees"


def worktree_dir(ref: CandidateRef) -> Path: return worktree_root(ref.ip_dir) / ref.candidate


def branch_name(ref: CandidateRef) -> str: return f"oag/dse/{ref.mission}/{ref.candidate}"


def ensure_inside(base: Path, path: Path, code: str) -> Path:
    resolved_base = base.resolve()
    resolved_path = path.resolve()
    try:
        resolved_path.relative_to(resolved_base)
    except ValueError as exc:
        raise DseError(code, "path escapes allowed DSE root", resolved_path) from exc
    return resolved_path


def git_executable() -> str | None: return shutil.which("git")


def run_git(ip_dir: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    git = git_executable()
    if git is None:
        return subprocess.CompletedProcess(["git", "-C", str(ip_dir), *args], 127, "", "git executable is not available")
    try:
        return subprocess.run([git, "-C", str(ip_dir), *args], text=True, capture_output=True, check=False, timeout=GIT_TIMEOUT_SEC)
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
        return subprocess.CompletedProcess([git, "-C", str(ip_dir), *args], 124, stdout, stderr or f"git command timed out after {GIT_TIMEOUT_SEC}s")


def list_dse_branches(ip_dir: Path) -> list[str]:
    if git_executable() is None or not (ip_dir / ".git").exists():
        return []
    proc = run_git(ip_dir, ["for-each-ref", "--format=%(refname:short)", "refs/heads/oag/dse"])
    if proc.returncode != 0:
        return []
    return [line.strip() for line in proc.stdout.splitlines() if line.strip()]


def delete_branch(ip_dir: Path, branch: str) -> dict[str, str] | None:
    if not branch:
        return None
    proc = run_git(ip_dir, ["show-ref", "--verify", "--quiet", f"refs/heads/{branch}"])
    if proc.returncode != 0:
        return None
    delete = run_git(ip_dir, ["branch", "-D", branch])
    if delete.returncode != 0:
        return issue("DSE_BRANCH_DELETE_FAILED", delete.stderr.strip() or delete.stdout.strip(), ip_dir)
    return None


def git_usable(ip_dir: Path) -> tuple[bool, str]:
    if git_executable() is None:
        return False, "git executable is not available"
    if not (ip_dir / ".git").exists():
        return False, "ip_dir is not a git repository"
    proc = run_git(ip_dir, ["worktree", "list", "--porcelain"])
    if proc.returncode != 0:
        return False, proc.stderr.strip() or proc.stdout.strip() or "git worktree is unavailable"
    return True, ""


def read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def states_for_run(ip_dir: Path, run_id: str) -> list[dict[str, Any]]:
    run_root = arch_root(ip_dir) / run_id
    states: list[dict[str, Any]] = []
    if not run_root.is_dir():
        return states
    for path in sorted(run_root.glob(f"*/{STATE_NAME}")):
        data = read_json(path)
        if data:
            states.append(data)
    return states


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def active_worktree_count(ip_dir: Path) -> int:
    root = worktree_root(ip_dir)
    return sum(1 for child in root.iterdir() if child.is_dir()) if root.is_dir() else 0


def enforce_budget(ip_dir: Path, max_worktrees: int) -> None:
    if max_worktrees < 0:
        raise DseError("DSE_MAX_WORKTREES_INVALID", "max_worktrees must be non-negative")
    count = active_worktree_count(ip_dir)
    if count >= max_worktrees:
        raise DseError("DSE_MAX_WORKTREES_EXCEEDED", f"active worktrees {count} >= max_worktrees {max_worktrees}", worktree_root(ip_dir))


def state_payload(ref: CandidateRef, tier: Literal["A", "B"], status: str, warnings: list[dict[str, str]]) -> dict[str, Any]:
    return {"schema_version": SCHEMA_VERSION, "run_id": ref.run_id, "candidate": ref.candidate, "mission": ref.mission, "tier": tier, "status": status, "candidate_dir": str(candidate_dir(ref)), "worktree_dir": str(worktree_dir(ref)) if tier == "B" else "", "branch": branch_name(ref) if tier == "B" else "", "warnings": warnings}


def create_candidate(args: argparse.Namespace) -> dict[str, Any]:
    ref = candidate_ref(args)
    tier = args.tier
    dest = candidate_dir(ref)
    ensure_inside(arch_root(ref.ip_dir), dest, "DSE_ARCH_PATH_ESCAPE")
    warnings: list[dict[str, str]] = []
    if tier == "B":
        enforce_budget(ref.ip_dir, args.max_worktrees)
    if dest.exists() and any(dest.iterdir()) and not args.force:
        raise DseError("DSE_CANDIDATE_EXISTS", "candidate directory already exists; pass --force to reuse", dest)
    dest.mkdir(parents=True, exist_ok=True)
    status = "pass"
    if tier == "B":
        usable, reason = git_usable(ref.ip_dir)
        wt = ensure_inside(worktree_root(ref.ip_dir), worktree_dir(ref), "DSE_WORKTREE_PATH_ESCAPE")
        if usable:
            proc = run_git(ref.ip_dir, ["worktree", "add", "-B", branch_name(ref), str(wt), "HEAD"])
            if proc.returncode != 0:
                status = "degraded"
                warnings.append(issue("DSE_GIT_WORKTREE_CREATE_FAILED", proc.stderr.strip() or proc.stdout.strip(), wt))
        else:
            status = "degraded"
            warnings.append(issue("DSE_GIT_WORKTREE_UNAVAILABLE", reason, ref.ip_dir))
    payload = state_payload(ref, tier, status, warnings)
    write_json(dest / STATE_NAME, payload)
    return {"schema_version": SCHEMA_VERSION, "operation": "create", **payload}


def git_status_for(ip_dir: Path, wt: Path) -> tuple[str, str]:
    if not wt.exists():
        return "missing", "worktree path missing"
    proc = run_git(ip_dir, ["-C", str(wt), "status", "--porcelain"])
    if proc.returncode != 0:
        return "unknown", proc.stderr.strip() or proc.stdout.strip() or "git status failed"
    return ("dirty", proc.stdout.strip()) if proc.stdout.strip() else ("clean", "")


def list_candidates(args: argparse.Namespace) -> dict[str, Any]:
    ip_dir = ip_root(args.ip_dir)
    rows: list[dict[str, Any]] = []
    for state in sorted(arch_root(ip_dir).glob(f"*/*/{STATE_NAME}")):
        data = read_json(state)
        if not data:
            continue
        hazards: list[dict[str, str]] = []
        if data.get("tier") == "B":
            wt = Path(str(data.get("worktree_dir") or ""))
            status, detail = git_status_for(ip_dir, wt)
            if status != "clean":
                hazards.append(issue(f"DSE_WORKTREE_{status.upper()}", detail, wt))
            data["worktree_status"] = status
        data["state_path"] = str(state)
        data["stale_hazards"] = hazards
        rows.append(data)
    return {"schema_version": SCHEMA_VERSION, "operation": "list", "status": "pass", "ip_dir": str(ip_dir), "max_worktrees": args.max_worktrees, "active_worktrees": active_worktree_count(ip_dir), "candidates": rows}


def safe_copy_tree(source: Path, dest: Path) -> list[str]:
    copied: list[str] = []
    source_resolved = source.resolve()
    dest.mkdir(parents=True, exist_ok=True)
    for item in sorted(source_resolved.rglob("*")):
        rel = item.relative_to(source_resolved)
        if not rel.parts or rel.parts[0] in COPY_BLOCKED_TOP or any(part in {"..", ""} for part in rel.parts):
            raise DseError("DSE_COPY_BLOCKED_PATH", "copy-back source contains a blocked path", item)
        if item.is_symlink():
            raise DseError("DSE_COPY_SYMLINK_BLOCKED", "copy-back refuses symlinks", item)
        target = dest / rel
        ensure_inside(dest, target, "DSE_COPY_DEST_ESCAPE")
        if item.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, target)
            copied.append(str(target))
    return copied


def copy_back(args: argparse.Namespace) -> dict[str, Any]:
    ref = candidate_ref(args)
    dest = candidate_dir(ref)
    ensure_inside(arch_root(ref.ip_dir), dest, "DSE_ARCH_PATH_ESCAPE")
    source = Path(args.source_dir).expanduser().resolve() if args.source_dir else dest
    if args.source_dir is None:
        state = read_json(dest / STATE_NAME)
        if state.get("tier") == "B" and state.get("worktree_dir"):
            source = Path(str(state["worktree_dir"])) / "knowledge" / "arch_exploration" / ref.run_id / ref.candidate
    if not source.is_dir():
        raise DseError("DSE_COPY_SOURCE_MISSING", "copy-back source directory is missing", source)
    copied = [] if source.resolve() == dest.resolve() else safe_copy_tree(source, dest)
    return {"schema_version": SCHEMA_VERSION, "operation": "copy-back", "status": "pass", "source": str(source), "destination": str(dest), "copied": copied}


def prune_one(args: argparse.Namespace) -> dict[str, Any]:
    ref = candidate_ref(args)
    removed: list[str] = []
    issues: list[dict[str, str]] = []
    wt = worktree_dir(ref)
    if wt.exists():
        proc = run_git(ref.ip_dir, ["worktree", "remove", "--force", str(wt)])
        if proc.returncode != 0:
            shutil.rmtree(wt)
        removed.append(str(wt))
    branch = branch_name(ref)
    branch_issue = delete_branch(ref.ip_dir, branch)
    if branch_issue is None:
        removed.append(branch)
    else:
        issues.append(branch_issue)
    return {"schema_version": SCHEMA_VERSION, "operation": "prune", "status": "fail" if issues else "pass", "removed": removed, "issues": issues}


def prune_all(args: argparse.Namespace) -> dict[str, Any]:
    ip_dir = ip_root(args.ip_dir)
    removed: list[str] = []
    issues: list[dict[str, str]] = []
    run_id = clean_id("run_id", args.run_id) if args.run_id else ""
    run_states = states_for_run(ip_dir, run_id) if run_id else []
    if run_id:
        worktrees = sorted(Path(str(state.get("worktree_dir"))) for state in run_states if str(state.get("worktree_dir") or ""))
    else:
        worktrees = sorted(worktree_root(ip_dir).glob("*"))
    for wt in worktrees:
        if wt.is_dir():
            proc = run_git(ip_dir, ["worktree", "remove", "--force", str(wt)])
            if proc.returncode != 0 and wt.exists():
                shutil.rmtree(wt)
            removed.append(str(wt))
    branches = sorted({str(state.get("branch")) for state in run_states if str(state.get("branch") or "")}) if run_id else list_dse_branches(ip_dir)
    for branch in branches:
        branch_issue = delete_branch(ip_dir, branch)
        if branch_issue is None:
            removed.append(branch)
        else:
            issues.append(branch_issue)
    return {"schema_version": SCHEMA_VERSION, "operation": "prune-all", "status": "fail" if issues else "pass", "removed": removed, "issues": issues}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create isolated OAG DSE candidate spaces.")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("create", "list", "copy-back", "prune", "prune-all"):
        p = sub.add_parser(name)
        p.add_argument("--ip-dir", required=True)
        p.add_argument("--json", action="store_true")
        p.add_argument("--max-worktrees", type=int, default=4)
        if name in {"create", "copy-back", "prune"}:
            p.add_argument("--run-id", required=True)
            p.add_argument("--candidate", required=True)
            p.add_argument("--mission", default="mission")
        if name == "create":
            p.add_argument("--tier", choices=("A", "B"), default="A")
            p.add_argument("--force", action="store_true")
        if name == "copy-back":
            p.add_argument("--source-dir")
        if name == "prune-all":
            p.add_argument("--run-id")
    return parser


def dispatch(args: argparse.Namespace) -> dict[str, Any]:
    if args.command == "create":
        return create_candidate(args)
    if args.command == "list":
        return list_candidates(args)
    if args.command == "copy-back":
        return copy_back(args)
    if args.command == "prune":
        return prune_one(args)
    if args.command == "prune-all":
        return prune_all(args)
    raise DseError("DSE_UNKNOWN_COMMAND", f"unknown command: {args.command}")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        payload = dispatch(args)
    except DseError as exc:
        payload = {"schema_version": SCHEMA_VERSION, "status": "fail", "issues": [issue(exc.code, str(exc), exc.path)]}
        if args.json:
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            print(f"FAIL {exc.code}: {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"{payload.get('status', 'pass').upper()} {SCHEMA_VERSION} {payload.get('operation', '')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
