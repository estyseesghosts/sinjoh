#!/usr/bin/env python3
"""Drive one windowed LOTUS session over MCP, batch-run it, capture both screens.

    python tools/lotus/run_sinjoh.py --asset sinjoh --frames 600
    python tools/lotus/run_sinjoh.py --asset sinjoh-dbg --frames 4000 --hold 300

The window is the point: LOTUS serves MCP on stdio from the visible desktop,
so the person watches the same session the harness drives. The process owns
the session; when it exits the session stops (a primary card keeps its data).

Captures are raw 32-bit BGRA from the worker; this writes them as PNG. The
game's own sdmc:/3ds/sinjoh/script.txt still drives input, so stage a script
on the card for deterministic runs (the same files the Azahar harness uses).
"""
from __future__ import annotations

import argparse
import base64
import json
import struct
import sys
import time
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from lotus_mcp import Mcp  # noqa: E402

LOTUS = Path(r"C:\Users\terezi\workdir\LOTUS-v0.0.3-windows-x64")
MAX_BATCH = 600


def payload(reply: dict) -> dict:
    """The tool's structured value, from structuredContent or the JSON text."""
    result = reply.get("result", reply)
    if isinstance(result, dict) and "structuredContent" in result:
        return result["structuredContent"]
    content = result.get("content") if isinstance(result, dict) else None
    if content:
        for item in content:
            if item.get("type") == "text":
                try:
                    return json.loads(item["text"])
                except json.JSONDecodeError:
                    return {"text": item["text"]}
    return result


def write_png(path: Path, bgra: bytes, w: int, h: int) -> None:
    """A minimal PNG writer: 32-bit BGRA input, 8-bit RGB output."""
    rows = bytearray()
    for y in range(h):
        row = bgra[y * w * 4:(y + 1) * w * 4]
        rows.append(0)  # filter: none
        for x in range(w):
            b, g, r = row[x * 4], row[x * 4 + 1], row[x * 4 + 2]
            rows += bytes((r, g, b))

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (struct.pack(">I", len(data)) + tag + data +
                struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

    png = (b"\x89PNG\r\n\x1a\n" +
           chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)) +
           chunk(b"IDAT", zlib.compress(bytes(rows), 9)) + chunk(b"IEND", b""))
    path.write_bytes(png)


def size_of(link: dict) -> tuple[int, int]:
    desc = link.get("description", "")
    for token in desc.replace(",", " ").split():
        if "x" in token and token.replace("x", "").isdigit():
            w, h = token.split("x")
            return int(w), int(h)
    return (400, 240) if link.get("name") == "top" else (320, 240)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", type=Path, default=LOTUS / "sinjoh-host.json")
    ap.add_argument("--asset", default="sinjoh")
    ap.add_argument("--card", default="sinjoh")
    ap.add_argument("--frames", type=int, default=240)
    ap.add_argument("--hold", type=float, default=0.0,
                    help="seconds to leave the window open after the capture")
    ap.add_argument("--play", action="store_true",
                    help="start continuous running before the hold (live input)")
    ap.add_argument("--out", type=Path, default=Path("build/lotus/last"))
    ap.add_argument("--keep", action="store_true", help="do not stop the session")
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)

    m = Mcp(windowed=True, config=a.config)
    report: dict = {"config": str(a.config), "asset": a.asset}
    try:
        m.initialize()
        report["status"] = payload(m.call("lotus_status", {}))
        created = payload(m.call("lotus_create_session", {
            "kind": "primary", "card": a.card, "asset": a.asset}))
        sid = created.get("session") or created.get("session_id") or created.get("id")
        if not sid:
            raise SystemExit(f"no session id in {json.dumps(created)[:800]}")
        report["session"] = sid
        done = 0
        while done < a.frames:
            n = min(MAX_BATCH, a.frames - done)
            reply = payload(m.call("lotus_run_until", {"session": sid, "frames": n},
                                   timeout=120))
            done += n
            if reply.get("last_error"):
                report["error"] = reply["last_error"]
                break
        status = payload(m.call("lotus_session_status", {"session": sid}))
        report["run"] = status
        st = status.get("status", status)
        report["summary"] = {
            "frontend": report["status"].get("frontend"),
            "backend": st.get("backend_name"),
            "renderer": st.get("renderer"),
            "renderer_fallback": st.get("renderer_fallback"),
            "frames": st.get("frames"),
            "fps": status.get("session", {}).get("telemetry", {}).get("fps"),
        }
        cap = payload(m.call("lotus_capture", {"session": sid}))
        report["capture"] = cap
        links = [item for item in cap.get("content", [])
                 if item.get("type") == "resource_link"]
        saved = []
        for i, link in enumerate(links):
            res = m.request("resources/read", {"uri": link["uri"]}, timeout=60)
            for item in res.get("result", {}).get("contents", []):
                blob = item.get("blob")
                if blob:
                    w, h = size_of(link)
                    path = a.out / f"{link.get('name', i)}.png"
                    write_png(path, base64.b64decode(blob), w, h)
                    saved.append(str(path))
        report["saved"] = saved
        (a.out / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report["summary"], indent=2))
        print("saved:", ", ".join(saved) or "(none)")
        if a.play:
            payload(m.call("lotus_control", {"session": sid, "operation": "run"}))
            print("running continuously; live input is the window's")
        if a.hold:
            print(f"holding the window for {a.hold:.0f}s ...")
            time.sleep(a.hold)
        if not a.keep:
            payload(m.call("lotus_control", {"session": sid, "operation": "stop"}))
    finally:
        m.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
