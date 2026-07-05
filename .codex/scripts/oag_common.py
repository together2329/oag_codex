#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


JsonObject = dict[str, Any]


def text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def as_list(value: Any) -> list[Any]:
    return [] if value is None else value if isinstance(value, list) else [value]


def str_items(value: Any) -> list[str]:
    return [text(item) for item in as_list(value) if text(item)]


def issue(code: str, message: str, path: str = "") -> dict[str, str]:
    payload = {"code": code, "message": message}
    if path:
        payload["path"] = path
    return payload


def read_json(path: Path) -> JsonObject:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {"__load_error__": str(exc)}
    return data if isinstance(data, dict) else {"__load_error__": "root is not an object"}


def read_yaml(path: Path) -> JsonObject:
    if not path.is_file():
        return {}
    try:
        import yaml  # type: ignore
    except ImportError as exc:
        return {"__load_error__": str(exc)}

    try:
        raw = path.read_text(encoding="utf-8")
        data = yaml.safe_load(raw) or {}
    except (OSError, yaml.YAMLError) as exc:
        return {"__load_error__": str(exc)}
    return data if isinstance(data, dict) else {"__load_error__": "root is not an object"}


def read_structured(path: Path) -> JsonObject:
    if path.suffix.lower() == ".json":
        return read_json(path)
    return read_yaml(path)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
