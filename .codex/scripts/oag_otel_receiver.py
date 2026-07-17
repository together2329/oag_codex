#!/usr/bin/env python3
"""Local OTLP/HTTP JSON receiver for Codex telemetry.

The receiver intentionally implements only the small OTLP surface required by
Codex's native JSON log exporter. It binds to loopback, redacts account
identifiers, and stores one request per JSONL line for deterministic analysis.
"""

from __future__ import annotations

import argparse
import gzip
import json
import os
import signal
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_DIR = ROOT / ".cache" / "otel"
MAX_BODY_BYTES = 64 * 1024 * 1024
SENSITIVE_ATTRIBUTE_KEYS = {
    "user.account_id",
    "user.email",
    "enduser.id",
    "enduser.email",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _atomic_append(path: Path, value: dict[str, Any]) -> None:
    data = (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    try:
        os.write(fd, data)
    finally:
        os.close(fd)


def _redacted_value() -> dict[str, str]:
    return {"stringValue": "[REDACTED]"}


def redact_identifiers(value: Any) -> Any:
    if isinstance(value, list):
        return [redact_identifiers(item) for item in value]
    if not isinstance(value, dict):
        return value
    if str(value.get("key") or "") in SENSITIVE_ATTRIBUTE_KEYS and "value" in value:
        result = dict(value)
        result["value"] = _redacted_value()
        return result
    result: dict[str, Any] = {}
    for key, item in value.items():
        if key in SENSITIVE_ATTRIBUTE_KEYS:
            result[key] = "[REDACTED]"
        else:
            result[key] = redact_identifiers(item)
    return result


def _health_url(host: str, port: int) -> str:
    return f"http://{host}:{port}/healthz"


def receiver_is_ready(host: str, port: int) -> bool:
    try:
        with urllib.request.urlopen(_health_url(host, port), timeout=0.5) as response:
            return response.status == 200
    except Exception:
        return False


def _read_pid(path: Path) -> int | None:
    try:
        return int(path.read_text(encoding="utf-8").strip())
    except Exception:
        return None


def _pid_alive(pid: int | None) -> bool:
    if not pid:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def make_handler(output_path: Path) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server_version = "OagOtlpReceiver/1.0"

        def _send_json(self, status: int, value: dict[str, Any]) -> None:
            body = json.dumps(value, separators=(",", ":")).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:  # noqa: N802
            if self.path == "/healthz":
                self._send_json(200, {"status": "ok"})
            else:
                self._send_json(404, {"error": "not_found"})

        def do_POST(self) -> None:  # noqa: N802
            if self.path != "/v1/logs":
                self._send_json(404, {"error": "unsupported_signal"})
                return
            try:
                length = int(self.headers.get("Content-Length") or "0")
            except ValueError:
                self._send_json(400, {"error": "invalid_content_length"})
                return
            if length <= 0 or length > MAX_BODY_BYTES:
                self._send_json(413, {"error": "invalid_body_size"})
                return
            body = self.rfile.read(length)
            if self.headers.get("Content-Encoding", "").lower() == "gzip":
                try:
                    body = gzip.decompress(body)
                except Exception:
                    self._send_json(400, {"error": "invalid_gzip"})
                    return
            try:
                payload = json.loads(body.decode("utf-8"))
            except Exception:
                self._send_json(415, {"error": "otlp_json_required"})
                return
            record = {
                "schema_version": "oag_otlp_capture.v1",
                "received_at": utc_now(),
                "signal": "logs",
                "payload": redact_identifiers(payload),
            }
            try:
                _atomic_append(output_path, record)
            except Exception:
                self._send_json(500, {"error": "capture_failed"})
                return
            self._send_json(200, {})

        def log_message(self, _format: str, *_args: Any) -> None:
            return

    return Handler


def serve(args: argparse.Namespace) -> int:
    data_dir = Path(args.data_dir).expanduser().resolve()
    data_dir.mkdir(parents=True, exist_ok=True)
    output_path = data_dir / "codex-logs.jsonl"
    pid_path = data_dir / "receiver.pid"
    server = ThreadingHTTPServer((args.host, args.port), make_handler(output_path))
    pid_path.write_text(str(os.getpid()) + "\n", encoding="utf-8")
    os.chmod(pid_path, 0o600)
    try:
        server.serve_forever(poll_interval=0.25)
    finally:
        server.server_close()
        try:
            if _read_pid(pid_path) == os.getpid():
                pid_path.unlink()
        except Exception:
            pass
    return 0


def start(args: argparse.Namespace) -> int:
    data_dir = Path(args.data_dir).expanduser().resolve()
    data_dir.mkdir(parents=True, exist_ok=True)
    pid_path = data_dir / "receiver.pid"
    if receiver_is_ready(args.host, args.port):
        print(json.dumps({"status": "already_running", "pid": _read_pid(pid_path), "port": args.port}))
        return 0
    stale_pid = _read_pid(pid_path)
    if _pid_alive(stale_pid):
        print(json.dumps({"status": "error", "error": "pid_alive_but_receiver_unhealthy", "pid": stale_pid}))
        return 1
    try:
        pid_path.unlink()
    except FileNotFoundError:
        pass
    log_path = data_dir / "receiver.log"
    with log_path.open("ab", buffering=0) as log_file:
        proc = subprocess.Popen(
            [
                sys.executable,
                str(Path(__file__).resolve()),
                "serve",
                "--host",
                args.host,
                "--port",
                str(args.port),
                "--data-dir",
                str(data_dir),
            ],
            stdin=subprocess.DEVNULL,
            stdout=log_file,
            stderr=log_file,
            start_new_session=True,
            close_fds=True,
        )
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline:
        if receiver_is_ready(args.host, args.port):
            print(json.dumps({"status": "started", "pid": proc.pid, "port": args.port, "data_dir": str(data_dir)}))
            return 0
        if proc.poll() is not None:
            break
        time.sleep(0.1)
    print(json.dumps({"status": "error", "error": "receiver_start_failed", "log": str(log_path)}))
    return 1


def stop(args: argparse.Namespace) -> int:
    data_dir = Path(args.data_dir).expanduser().resolve()
    pid_path = data_dir / "receiver.pid"
    pid = _read_pid(pid_path)
    if not _pid_alive(pid):
        print(json.dumps({"status": "not_running"}))
        return 0
    assert pid is not None
    os.kill(pid, signal.SIGTERM)
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline and _pid_alive(pid):
        time.sleep(0.1)
    if _pid_alive(pid):
        print(json.dumps({"status": "error", "error": "receiver_stop_timeout", "pid": pid}))
        return 1
    try:
        pid_path.unlink()
    except FileNotFoundError:
        pass
    print(json.dumps({"status": "stopped", "pid": pid}))
    return 0


def status(args: argparse.Namespace) -> int:
    data_dir = Path(args.data_dir).expanduser().resolve()
    pid = _read_pid(data_dir / "receiver.pid")
    ready = receiver_is_ready(args.host, args.port)
    output_path = data_dir / "codex-logs.jsonl"
    result = {
        "status": "running" if ready else "stopped",
        "pid": pid if _pid_alive(pid) else None,
        "endpoint": f"http://{args.host}:{args.port}/v1/logs",
        "output": str(output_path),
        "output_bytes": output_path.stat().st_size if output_path.exists() else 0,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if ready else 1


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    sub = result.add_subparsers(dest="command", required=True)
    for name in ("start", "stop", "status", "serve"):
        command = sub.add_parser(name)
        command.add_argument("--host", default="127.0.0.1")
        command.add_argument("--port", type=int, default=4318)
        command.add_argument("--data-dir", default=str(DEFAULT_DATA_DIR))
    return result


def main() -> int:
    args = parser().parse_args()
    return {"start": start, "stop": stop, "status": status, "serve": serve}[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
