#!/usr/bin/env python3
"""Minimal MCP client for LOTUS (stdio JSON-RPC), used by the sinjoh harness.

LOTUS v0.0.2 serves the same tools headless (`lotus-mcp`) and windowed
(`lotus-desktop --mcp`). The window is how a person watches the run; the MCP
session is how the harness drives it.

Usage:
    python tools/lotus_mcp.py --config <host.json> tools
    python tools/lotus_mcp.py --config <host.json> call <tool> '<json-args>'
    python tools/lotus_mcp.py --config <host.json> shell        # JSON lines on stdin
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import threading
from pathlib import Path

LOTUS = Path(r"C:\Users\terezi\workdir\LOTUS-v0.0.2-windows-x64")


class Mcp:
    def __init__(self, windowed: bool, config: Path) -> None:
        exe = LOTUS / "bin" / ("lotus-desktop.exe" if windowed else "lotus-mcp.exe")
        args = [str(exe)]
        if windowed:
            args.append("--mcp")
        args.append(str(config))
        self.proc = subprocess.Popen(
            args, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, text=True, encoding="utf-8", bufsize=1,
        )
        self.next_id = 1
        self.lines = []
        self.lock = threading.Lock()
        self.pending: dict[int, dict] = {}
        self.reader = threading.Thread(target=self._read, daemon=True)
        self.reader.start()

    def _read(self) -> None:
        assert self.proc.stdout is not None
        for line in self.proc.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                print("[lotus-mcp] non-json:", line[:200], file=sys.stderr)
                continue
            if "id" in msg and isinstance(msg["id"], int):
                with self.lock:
                    self.pending[msg["id"]] = msg
            else:
                print("[lotus-mcp] event:", line[:300], file=sys.stderr)

    def request(self, method: str, params: dict | None = None, timeout: float = 60.0) -> dict:
        self.next_id += 1
        rid = self.next_id
        payload = {"jsonrpc": "2.0", "id": rid, "method": method}
        if params is not None:
            payload["params"] = params
        assert self.proc.stdin is not None
        self.proc.stdin.write(json.dumps(payload) + "\n")
        self.proc.stdin.flush()
        import time
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            with self.lock:
                if rid in self.pending:
                    return self.pending.pop(rid)
            time.sleep(0.02)
        raise TimeoutError(f"{method} timed out")

    def notify(self, method: str, params: dict | None = None) -> None:
        payload = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            payload["params"] = params
        assert self.proc.stdin is not None
        self.proc.stdin.write(json.dumps(payload) + "\n")
        self.proc.stdin.flush()

    def initialize(self) -> dict:
        reply = self.request("initialize", {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "clientInfo": {"name": "sinjoh-harness", "version": "0.1.0"},
        })
        self.notify("notifications/initialized")
        return reply

    def tools(self) -> list[dict]:
        return self.request("tools/list", {}).get("result", {}).get("tools", [])

    def call(self, name: str, args: dict, timeout: float = 300.0) -> dict:
        return self.request("tools/call", {"name": name, "arguments": args}, timeout)

    def close(self) -> None:
        try:
            self.request("shutdown", {}, timeout=2.0)
        except Exception:
            pass
        self.proc.terminate()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True, type=Path)
    ap.add_argument("--headless", action="store_true")
    ap.add_argument("command", choices=["tools", "call", "shell", "status"])
    ap.add_argument("rest", nargs="*")
    a = ap.parse_args()
    m = Mcp(windowed=not a.headless, config=a.config)
    try:
        m.initialize()
        if a.command == "tools":
            print(json.dumps(m.tools(), indent=2))
        elif a.command == "status":
            print(json.dumps(m.call("lotus_status", {}), indent=2))
        elif a.command == "call":
            print(json.dumps(m.call(a.rest[0], json.loads(a.rest[1])), indent=2))
        else:
            for line in sys.stdin:
                line = line.strip()
                if not line:
                    continue
                req = json.loads(line)
                print(json.dumps(m.call(req["tool"], req.get("args", {})), indent=2))
    finally:
        m.close()


if __name__ == "__main__":
    main()
