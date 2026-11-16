#!/usr/bin/env python3
"""Command-line client for the shared LOTUS bridge (tools/lotus/bridge.py).

    python tools/lotus/ctl.py status
    python tools/lotus/ctl.py create --kind primary --card sinjoh --asset sinjoh
    python tools/lotus/ctl.py run <session> 600
    python tools/lotus/ctl.py capture <session> --out build/lotus/cap
    python tools/lotus/ctl.py stop <session>

The bridge keeps one windowed LOTUS and its sessions; these commands create
and discard sessions on it. Start the bridge once (or leave it running):

    python tools/lotus/bridge.py --port 45761
"""
from __future__ import annotations

import argparse
import base64
import json
import socket
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from lotus.run_sinjoh import payload, size_of, write_png  # noqa: E402


def send(req: dict, port: int) -> dict:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=5) as conn:
            conn.settimeout(600)
            conn.sendall((json.dumps(req) + "\n").encode("utf-8"))
            with conn.makefile("r", encoding="utf-8") as reader:
                line = reader.readline()
    except OSError as exc:
        raise SystemExit(f"LOTUS bridge not reachable on 127.0.0.1:{port} "
                         f"({exc}); start it with tools/lotus/bridge.py") from exc
    if not line:
        raise SystemExit("LOTUS bridge closed the connection")
    reply = json.loads(line)
    if not reply.get("ok"):
        raise SystemExit(f"bridge error: {reply.get('error')}")
    return reply


def call(port: int, name: str, args: dict, timeout: float = 300.0) -> dict:
    return payload(send({"op": "call", "name": name, "args": args,
                         "timeout": timeout}, port)["reply"])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=45761)
    sub = ap.add_subparsers(dest="command", required=True)
    sub.add_parser("status")
    sub.add_parser("sessions")
    sub.add_parser("cards")
    sub.add_parser("tools")
    sub.add_parser("shutdown")
    p = sub.add_parser("create")
    p.add_argument("--kind", choices=("primary", "secondary"), default="secondary")
    p.add_argument("--card")
    p.add_argument("--asset")
    p = sub.add_parser("run")
    p.add_argument("session")
    p.add_argument("frames", type=int)
    p = sub.add_parser("pause")
    p.add_argument("session")
    p = sub.add_parser("stop")
    p.add_argument("session")
    p = sub.add_parser("call")
    p.add_argument("name")
    p.add_argument("args", nargs="?", default="{}")
    p = sub.add_parser("capture")
    p.add_argument("session")
    p.add_argument("--out", type=Path, default=Path("build/lotus/cap"))
    a = ap.parse_args()

    if a.command == "status":
        print(json.dumps(call(a.port, "lotus_status", {}), indent=2))
    elif a.command == "sessions":
        print(json.dumps(call(a.port, "lotus_list_sessions", {}), indent=2))
    elif a.command == "cards":
        print(json.dumps(call(a.port, "lotus_list_cards", {}), indent=2))
    elif a.command == "tools":
        print(json.dumps(send({"op": "tools"}, a.port)["tools"], indent=2))
    elif a.command == "create":
        args = {"kind": a.kind}
        if a.card:
            args["card"] = a.card
        if a.asset:
            args["asset"] = a.asset
        print(json.dumps(call(a.port, "lotus_create_session", args), indent=2))
    elif a.command == "run":
        left = a.frames
        while left > 0:
            n = min(600, left)
            r = call(a.port, "lotus_run_until", {"session": a.session, "frames": n}, 120)
            left -= n
            if r.get("last_error"):
                print(json.dumps(r, indent=2))
                return 1
        print(json.dumps(r, indent=2))
    elif a.command == "pause":
        print(json.dumps(call(a.port, "lotus_control",
                              {"session": a.session, "operation": "pause"}), indent=2))
    elif a.command == "stop":
        print(json.dumps(call(a.port, "lotus_control",
                              {"session": a.session, "operation": "stop"}), indent=2))
    elif a.command == "call":
        print(json.dumps(call(a.port, a.name, json.loads(a.args)), indent=2))
    elif a.command == "capture":
        a.out.mkdir(parents=True, exist_ok=True)
        cap = call(a.port, "lotus_capture", {"session": a.session})
        saved = []
        for i, link in enumerate([x for x in cap.get("content", [])
                                  if x.get("type") == "resource_link"]):
            res = send({"op": "resource", "uri": link["uri"]}, a.port)["reply"]
            for item in res.get("result", {}).get("contents", []):
                blob = item.get("blob")
                if blob:
                    w, h = size_of(link)
                    path = a.out / f"{link.get('name', i)}.png"
                    write_png(path, base64.b64decode(blob), w, h)
                    saved.append(str(path))
        print("saved:", ", ".join(saved) or "(none)")
    elif a.command == "shutdown":
        print(json.dumps(send({"op": "shutdown"}, a.port), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
