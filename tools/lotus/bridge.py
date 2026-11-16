#!/usr/bin/env python3
"""One long-lived windowed LOTUS, shared by JSON-over-TCP clients.

`lotus-desktop --mcp` speaks MCP on stdio, so only the process that spawns it
can drive it. This bridge owns that stdio, keeps the window open, and exposes
the same calls on 127.0.0.1 so several shells/agents can use one LOTUS and one
set of sessions. It is a local, single-user convenience: no authentication.

    python tools/lotus/bridge.py --port 45761

Each client sends one JSON object per line and reads one JSON reply per line:

    {"op": "call", "name": "lotus_status", "args": {}}
    {"op": "call", "name": "lotus_create_session",
     "args": {"kind": "secondary", "asset": "sinjoh"}}
    {"op": "resource", "uri": "lotus://artifact/..."}
    {"op": "tools"}
    {"op": "shutdown"}

`tools/lotus/ctl.py` is the command-line client. Sessions are created and
discarded through the usual MCP tools; the bridge keeps the window and the
supervisor alive between tests. If the bridge exits, its sessions stop (a
primary card keeps its data).
"""
from __future__ import annotations

import argparse
import json
import socket
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from lotus_mcp import Mcp  # noqa: E402

LOTUS = Path(r"C:\Users\terezi\workdir\LOTUS-v0.0.3-windows-x64")


class Bridge:
    def __init__(self, config: Path) -> None:
        self.m = Mcp(windowed=True, config=config)
        self.lock = threading.Lock()
        self.closing = threading.Event()

    def start(self) -> None:
        self.m.initialize()

    def handle(self, req: dict) -> dict:
        op = req.get("op")
        if op == "shutdown":
            self.closing.set()
            return {"ok": True}
        with self.lock:
            if op == "call":
                reply = self.m.call(req.get("name", ""), req.get("args") or {},
                                    timeout=float(req.get("timeout", 300)))
                return {"ok": True, "reply": reply}
            if op == "resource":
                reply = self.m.request("resources/read", {"uri": req.get("uri", "")},
                                       timeout=float(req.get("timeout", 60)))
                return {"ok": True, "reply": reply}
            if op == "tools":
                return {"ok": True, "tools": self.m.tools()}
        return {"ok": False, "error": f"unknown op {op!r}"}

    def serve(self, port: int) -> None:
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(("127.0.0.1", port))
        server.listen(8)
        server.settimeout(0.5)
        print(f"[bridge] LOTUS window + MCP on 127.0.0.1:{port}", flush=True)
        while not self.closing.is_set():
            try:
                conn, _ = server.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            threading.Thread(target=self.client, args=(conn,), daemon=True).start()
        server.close()

    def client(self, conn: socket.socket) -> None:
        try:
            with conn:
                reader = conn.makefile("r", encoding="utf-8")
                writer = conn.makefile("w", encoding="utf-8")
                for line in reader:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        reply = self.handle(json.loads(line))
                    except Exception as exc:  # keep one bad call from ending the bridge
                        reply = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
                    writer.write(json.dumps(reply) + "\n")
                    writer.flush()
        except (ConnectionError, OSError, ValueError):
            pass

    def close(self) -> None:
        try:
            self.m.close()
        except Exception:
            pass


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", type=Path, default=LOTUS / "shared-host.json")
    ap.add_argument("--port", type=int, default=45761)
    a = ap.parse_args()
    bridge = Bridge(a.config)
    try:
        bridge.start()
        bridge.serve(a.port)
    finally:
        bridge.close()
    print("[bridge] closed; sessions stopped", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
