#!/usr/bin/env python3
"""Shared helpers for OAG Codex hook adapters."""

from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any

try:
    import fcntl
except ImportError:  # pragma: no cover - non-POSIX fallback
    fcntl = None

try:
    import msvcrt
except ImportError:  # pragma: no cover - non-Windows fallback
    msvcrt = None

ROOT = Path(__file__).resolve().parents[1]  # .codex/
PROJECT = ROOT.parent
INACTIVE_RUN_STATUSES = {"complete", "parked", "needs_human"}
IP_SCAN_EXCLUDED_DIRS = {
    ".cache",
    ".codex",
    ".git",
    ".tmp",
    ".venv",
    "__pycache__",
    "node_modules",
    "venv",
}
IP_SCAN_MAX_DEPTH = 6

STAGE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "req": ("req", "requirement", "requirements", "interview", "locked truth"),
    "rtl": ("rtl", "verilog", "systemverilog", "module", "implementation"),
    "tb": ("tb", "testbench", "scoreboard", "stimulus"),
    "sim": ("sim", "simulation", "verilator", "cocotb"),
    "lint": ("lint",),
    "formal": ("formal", "assertion", "sva"),
    "coverage": ("coverage", "coverpoint", "cov"),
    "signoff": ("signoff", "closure", "complete", "claim_complete"),
}

OAG_COMMAND_RE = re.compile(r"^\s*oag(?:\s|:|/|$)")
PATH_REF_RE = re.compile(
    r"(?<![A-Za-z0-9_./-])@?"
    r"(?P<path>(?:~|/|\.{1,2}/)?[A-Za-z0-9_.+~-]+(?:/[A-Za-z0-9_.+~-]+)+)"
)
BARE_FILE_REF_RE = re.compile(
    r"(?<![A-Za-z0-9_.+~-])@(?P<name>[A-Za-z0-9_.+~-]+\.[A-Za-z0-9_+~-]+)(?![A-Za-z0-9_.+~-])"
)
BARE_FILE_SEARCH_DIRS = (
    "rtl",
    "tb",
    "list",
    "ontology",
    "req",
    "formal",
    "lint",
    "cov",
    "doc",
    "sdc",
    "syn",
    "sim",
)

APPROVAL_ONLY_RE = re.compile(
    r"^\s*(승인|승인합니다|approve|approved|approval|ok|okay|yes|y|확인|동의|허가)\s*[.!?。]*\s*$",
    re.IGNORECASE,
)
RUN_LIMIT_COMMAND_RE = re.compile(
    r"^\s*(?:[A-Za-z_][A-Za-z0-9_]*\s+)?"
    r"(?P<stage>requirements?|req|요구사항|rtl|lint|tb|testbench|formal|sim|simulation|시뮬|시뮬레이션|coverage|cov|signoff|사인오프)"
    r"\s*(?:까지만|까지|만)\s*[.!?。]*\s*$",
    re.IGNORECASE,
)
RUN_LIMIT_ALL_RE = re.compile(
    r"^\s*(?:[A-Za-z_][A-Za-z0-9_]*\s+)?(?:끝까지|쭉쭉\s*다|전부|전체|all|full)\s*[.!?。]*\s*$",
    re.IGNORECASE,
)
RUN_LIMIT_NONE_RE = re.compile(
    r"^\s*(?:[A-Za-z_][A-Za-z0-9_]*\s+)?(?:자동\s*진행\s*(?:꺼|끄기|중지|off)|auto\s*continue\s*off|none)\s*[.!?。]*\s*$",
    re.IGNORECASE,
)
RUN_LIMIT_ALIASES = {
    "req": "requirements",
    "requirement": "requirements",
    "requirements": "requirements",
    "요구사항": "requirements",
    "rtl": "rtl",
    "lint": "lint",
    "tb": "tb",
    "testbench": "tb",
    "formal": "formal",
    "sim": "sim",
    "simulation": "sim",
    "시뮬": "sim",
    "시뮬레이션": "sim",
    "coverage": "coverage",
    "cov": "coverage",
    "signoff": "signoff",
    "사인오프": "signoff",
}


def read_payload() -> dict[str, Any]:
    try:
        raw = os.read(0, 1_000_000).decode("utf-8")
    except Exception:
        return {}
    if not raw.strip():
        return {}
    try:
        data = json.loads(raw)
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def first_text(payload: Any, keys: tuple[str, ...]) -> str:
    if isinstance(payload, dict):
        for key in keys:
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value
        for value in payload.values():
            found = first_text(value, keys)
            if found:
                return found
    elif isinstance(payload, list):
        for value in payload:
            found = first_text(value, keys)
            if found:
                return found
    return ""


def prompt_text(payload: dict[str, Any]) -> str:
    return first_text(payload, ("prompt", "user_prompt", "userPrompt", "message", "content", "input"))


def project_path(value: str, *, base: Path | None = None) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = (base or PROJECT) / path
    return path.resolve()


def payload_session_id(payload: dict[str, Any]) -> str:
    return first_text(payload, ("session_id", "sessionId", "conversation_id", "conversationId")).strip()


def invocation_cwd(payload: dict[str, Any]) -> Path:
    raw = first_text(payload, ("cwd", "working_directory", "workingDirectory")).strip()
    path = Path(raw).expanduser() if raw else Path.cwd()
    if not path.is_absolute():
        path = Path.cwd() / path
    try:
        resolved = path.resolve()
    except OSError:
        return Path.cwd().resolve()
    return resolved if resolved.is_dir() else Path.cwd().resolve()


def invocation_workspace(payload: dict[str, Any], *, cwd: Path | None = None) -> Path:
    explicit = first_text(payload, ("workspace_root", "workspaceRoot")).strip()
    explicit = explicit or os.environ.get("OAG_WORKSPACE_ROOT", "").strip()
    if explicit:
        return project_path(explicit, base=cwd or invocation_cwd(payload))
    current = (cwd or invocation_cwd(payload)).resolve()
    candidates = (current, *current.parents)
    for candidate in candidates:
        if is_ip_dir(candidate):
            return candidate
    for marker in (".git", ".codex"):
        for candidate in candidates:
            if (candidate / marker).exists():
                return candidate
    return current


def _identity_digest(*parts: str) -> str:
    return hashlib.sha256("\0".join(parts).encode("utf-8")).hexdigest()[:24]


def hook_identity(payload: dict[str, Any]) -> dict[str, str]:
    cwd = invocation_cwd(payload)
    workspace = invocation_workspace(payload, cwd=cwd)
    session_id = payload_session_id(payload)
    workspace_key = _identity_digest(str(workspace))
    session_key = _identity_digest(session_id, str(workspace)) if session_id else f"anonymous-{workspace_key}"
    return {
        "session_id": session_id,
        "session_key": session_key,
        "workspace_key": workspace_key,
        "cwd": str(cwd),
        "workspace_root": str(workspace),
    }


def hook_cache_path(payload: dict[str, Any], *, hook_name: str, exact_env: str) -> Path:
    identity = hook_identity(payload)
    exact = os.environ.get(exact_env, "").strip()
    if exact:
        return project_path(exact, base=Path(identity["cwd"]))
    base_raw = os.environ.get("OAG_HOOK_CACHE_DIR", "").strip()
    base = project_path(base_raw, base=Path(identity["cwd"])) if base_raw else ROOT / ".cache"
    return base / hook_name / f"{identity['session_key']}.json"


@contextmanager
def cache_file_lock(cache_path: Path):
    lock_path = cache_path.with_suffix(cache_path.suffix + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+b") as handle:
        if fcntl is not None:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        elif msvcrt is not None:
            handle.seek(0, os.SEEK_END)
            if handle.tell() == 0:
                handle.write(b"\0")
                handle.flush()
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
        else:  # pragma: no cover - supported runtime platforms provide one backend
            raise RuntimeError("platform file locking is unavailable for OAG hook cache")
        try:
            yield
        finally:
            if fcntl is not None:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            elif msvcrt is not None:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)


def identity_matches(value: Any, identity: dict[str, str]) -> bool:
    if not isinstance(value, dict):
        return False
    return all(
        str(value.get(key) or "") == identity[key]
        for key in ("session_id", "session_key", "workspace_key", "workspace_root")
    )


def path_under(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
    except (OSError, ValueError):
        return False
    return True


def state_root(ip_dir: Path) -> Path:
    hidden = ip_dir / ".oag"
    if (hidden / "ontology").is_dir() or (hidden / "knowledge").is_dir():
        return hidden
    return ip_dir


def state_path(ip_dir: Path, relative: str | Path) -> Path:
    return state_root(ip_dir) / Path(relative)


def is_ip_dir(path: Path) -> bool:
    ontology = state_path(path, "ontology")
    return ontology.is_dir() and (
        (ontology / "requirements.yaml").is_file()
        or (ontology / "ip.yaml").is_file()
        or (path / "req" / "locked_truth.md").is_file()
    )


def scan_ip_dirs(root_path: Path | None = None) -> list[Path]:
    scan_root = (root_path or PROJECT).expanduser().resolve()
    ips: list[Path] = []
    seen: set[Path] = set()
    for root, dirnames, _filenames in os.walk(scan_root):
        current = Path(root)
        try:
            rel_parts = current.relative_to(scan_root).parts
        except ValueError:
            dirnames[:] = []
            continue
        if len(rel_parts) > IP_SCAN_MAX_DEPTH:
            dirnames[:] = []
            continue
        dirnames[:] = sorted(
            dirname
            for dirname in dirnames
            if dirname not in IP_SCAN_EXCLUDED_DIRS
        )
        if not is_ip_dir(current):
            continue
        resolved = current.resolve()
        if resolved not in seen:
            seen.add(resolved)
            ips.append(resolved)
        dirnames[:] = []
    return ips


def active_run_ips(root_path: Path | None = None) -> list[Path]:
    ips: list[Path] = []
    for ip in scan_ip_dirs(root_path):
        active = state_path(ip, "ontology/runs/active_run.json")
        if not active.is_file():
            continue
        try:
            data = json.loads(active.read_text(encoding="utf-8"))
        except Exception:
            data = {}
        status = str(data.get("status") or "") if isinstance(data, dict) else ""
        run_id = str(data.get("run_id") or "") if isinstance(data, dict) else ""
        if not status and run_id:
            run_state_path = state_path(ip, f"ontology/runs/{run_id}/run_state.json")
            try:
                state = json.loads(run_state_path.read_text(encoding="utf-8"))
            except Exception:
                state = {}
            status = str(state.get("status") or "") if isinstance(state, dict) else ""
        if status in INACTIVE_RUN_STATUSES:
            continue
        ips.append(ip.resolve())
    return ips


def infer_stage(text: str, fallback: str = "") -> str:
    lower = text.lower()
    for stage, words in STAGE_KEYWORDS.items():
        if any(re.search(rf"\b{re.escape(word)}\b", lower) for word in words):
            return stage
    return fallback


def has_oag_work_signal(text: str) -> bool:
    return bool(OAG_COMMAND_RE.search(text or ""))


def _is_approval_only(text: str) -> bool:
    return bool(APPROVAL_ONLY_RE.match(text or ""))


def parse_run_limit_command(text: str) -> str:
    if RUN_LIMIT_NONE_RE.match(text or ""):
        return "none"
    if RUN_LIMIT_ALL_RE.match(text or ""):
        return "all"
    match = RUN_LIMIT_COMMAND_RE.match(text or "")
    if not match:
        return ""
    return RUN_LIMIT_ALIASES.get(match.group("stage").lower(), "")


def _ip_name_in_prompt(ip_name: str, prompt: str) -> bool:
    pattern = rf"(?<![A-Za-z0-9_.-]){re.escape(ip_name.lower())}(?![A-Za-z0-9_.-])"
    return re.search(pattern, prompt.lower()) is not None


def prompt_path_refs(prompt: str) -> list[str]:
    refs: list[str] = []
    seen: set[str] = set()
    for match in PATH_REF_RE.finditer((prompt or "").replace("\\", "/")):
        ref = match.group("path").strip().strip("`'\"<>()[]{}.,;:!?。")
        if not ref or "://" in ref:
            continue
        if ref not in seen:
            seen.add(ref)
            refs.append(ref)
    return refs


def prompt_bare_file_refs(prompt: str) -> list[str]:
    refs: list[str] = []
    seen: set[str] = set()
    for match in BARE_FILE_REF_RE.finditer(prompt or ""):
        ref = match.group("name").strip()
        if ref not in seen:
            seen.add(ref)
            refs.append(ref)
    return refs


def _path_under(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _ip_has_bare_file_ref(ip: Path, ref: str) -> bool:
    if (ip / ref).is_file():
        return True
    for dirname in BARE_FILE_SEARCH_DIRS:
        root = state_path(ip, dirname) if dirname in {"ontology", "knowledge"} else ip / dirname
        if not root.is_dir():
            continue
        try:
            next(root.rglob(ref))
        except StopIteration:
            continue
        except OSError:
            continue
        return True
    return False


def _target_ip_dirs_from_paths(prompt: str, ips: list[Path], *, base: Path | None = None) -> list[Path]:
    matches: list[Path] = []
    for ref in prompt_path_refs(prompt):
        try:
            resolved = project_path(ref, base=base)
        except (OSError, RuntimeError):
            continue
        for ip in ips:
            if _path_under(resolved, ip) and ip not in matches:
                matches.append(ip)
    for ref in prompt_bare_file_refs(prompt):
        for ip in ips:
            if _ip_has_bare_file_ref(ip, ref) and ip not in matches:
                matches.append(ip)
    return matches if len(matches) == 1 else []


def target_ip_selections(
    payload: dict[str, Any],
    *,
    require_signal: bool = True,
    workspace_root: Path | None = None,
) -> list[dict[str, Any]]:
    prompt = prompt_text(payload)
    cwd = invocation_cwd(payload)
    if workspace_root is not None and not first_text(payload, ("cwd", "working_directory", "workingDirectory")).strip():
        cwd = workspace_root.resolve()
    workspace = (workspace_root or invocation_workspace(payload, cwd=cwd)).resolve()
    payload_ip = str(payload.get("ip_dir") or "").strip()
    env_ip = os.environ.get("OAG_IP_DIR", "").strip()
    explicit = payload_ip or env_ip
    if explicit:
        path = project_path(explicit, base=cwd)
        return [{"ip_dir": path, "source": "payload" if payload_ip else "environment"}] if path.exists() else []

    ips = scan_ip_dirs(workspace)
    path_matches = _target_ip_dirs_from_paths(prompt, ips, base=cwd)
    if path_matches:
        return [{"ip_dir": path, "source": "prompt"} for path in path_matches]

    matches = [ip for ip in ips if _ip_name_in_prompt(ip.name, prompt)]
    if matches:
        return [{"ip_dir": matches[0], "source": "prompt"}] if len(matches) == 1 else []

    if _is_approval_only(prompt):
        return []

    if is_ip_dir(cwd) and (not require_signal or has_oag_work_signal(prompt)):
        return [{"ip_dir": cwd, "source": "workspace_cwd"}]

    active = active_run_ips(workspace)
    if len(active) == 1 and (not require_signal or has_oag_work_signal(prompt)):
        return [{"ip_dir": active[0], "source": "workspace_scan"}]
    return []


def target_ip_dirs(
    payload: dict[str, Any],
    *,
    require_signal: bool = True,
    workspace_root: Path | None = None,
) -> list[Path]:
    return [
        item["ip_dir"]
        for item in target_ip_selections(payload, require_signal=require_signal, workspace_root=workspace_root)
        if isinstance(item.get("ip_dir"), Path)
    ]


def hook_additional_context(text: str, hook_event: str = "UserPromptSubmit") -> dict[str, Any]:
    return {
        "hookSpecificOutput": {
            "hookEventName": hook_event,
            "additionalContext": text,
        }
    }
