#!/usr/bin/env python3
"""Drive a LOTUS session from the title into the field and take steady windows.

    python tools/lotus/field_run.py --asset sinjoh-dbg --windows 3

Continues the staged save (the journal screen the loaded save opens with) and
then records whole 600-frame windows of the standing field. The bridge owns
the windowed session (tools/lotus/bridge.py); this script only sends the
inputs the save needs:

    START at the title     -> main menu
    A on Continue          -> game_start, then the journal
    START on the journal   -> the field

The journal closes on START, not A: it only turns pages on A/left/right and
closes on START or on B at page 0 (journal_controller.c,
JournalController_HandleInput). A save with one page therefore looks frozen
under A presses.

The metrics are read from the guest log the same session is writing, so the
numbers are the ones the debug build printed for those windows. The last
capture goes to --out.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ctl import call, send  # noqa: E402

LOTUS = Path(r"C:\Users\terezi\workdir\LOTUS-v0.0.3-windows-x64")
LOG = LOTUS / "data/citnlo/sessions/cards/sinjoh/sdmc/3ds/sinjoh/logs/platinum.log"

# lotus_input's buttons are NativeButton bits, not DS/libctru bits.
A = 0x001
START = 0x400

TAP_FRAMES = 20
RELEASE_FRAMES = 60


def tap(port: int, sid: str, button: int, after: int = RELEASE_FRAMES) -> None:
    call(port, "lotus_input",
         {"session": sid, "owner": "live", "buttons": button, "x": 0, "y": 0,
          "touch": False})
    run(port, sid, TAP_FRAMES)
    call(port, "lotus_input",
         {"session": sid, "owner": "live", "buttons": 0, "x": 0, "y": 0,
          "touch": False})
    run(port, sid, after)


def run(port: int, sid: str, frames: int) -> dict:
    """lotus_run_until is capped at 600 frames per call."""
    left, reply = frames, {}
    while left > 0:
        n = min(600, left)
        reply = call(port, "lotus_run_until", {"session": sid, "frames": n}, 300)
        left -= n
        if reply.get("last_error"):
            raise SystemExit(f"LOTUS run failed: {reply['last_error']}")
    return reply


def log_since(mark: int) -> list[str]:
    if not LOG.is_file():
        return []
    return LOG.read_text(encoding="utf-8", errors="replace").splitlines()[mark:]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=45761)
    ap.add_argument("--card", default="sinjoh")
    ap.add_argument("--asset", default="sinjoh-dbg")
    ap.add_argument("--title-frames", type=int, default=6600)
    ap.add_argument("--windows", type=int, default=3)
    ap.add_argument("--out", type=Path, default=Path("build/lotus/field"))
    a = ap.parse_args()
    port = a.port

    mark = len(LOG.read_text(encoding="utf-8", errors="replace").splitlines()) if LOG.is_file() else 0

    created = call(port, "lotus_create_session",
                   {"kind": "primary", "card": a.card, "asset": a.asset})
    sid = created.get("session") or created.get("session_id")
    if not sid and "already has a primary session" in json.dumps(created):
        # A stopped session still owns its card until it is stopped; a previous
        # field run leaves one behind.
        sessions = call(port, "lotus_list_sessions", {})
        if isinstance(sessions, dict):
            sessions = sessions.get("sessions", [])
        for s in sessions:
            if s.get("card") == a.card:
                call(port, "lotus_control", {"session": s["id"], "operation": "stop"})
        created = call(port, "lotus_create_session",
                       {"kind": "primary", "card": a.card, "asset": a.asset})
        sid = created.get("session") or created.get("session_id")
    if not sid:
        raise SystemExit(f"no session in {json.dumps(created)[:400]}")
    (Path(__file__).resolve().parent.parent.parent / "build" / "lotus" / "sid.txt").write_text(sid)
    print(f"session {sid}")

    run(port, sid, a.title_frames)
    tap(port, sid, START, after=400)   # title -> main menu
    tap(port, sid, A, after=600)       # Continue -> game_start + journal
    tap(port, sid, START, after=600)   # journal -> field

    for i in range(a.windows):
        run(port, sid, 600)
        print(f"window {i + 1} of {a.windows} done")
        sys.stdout.flush()

    a.out.mkdir(parents=True, exist_ok=True)
    cap = call(port, "lotus_capture", {"session": sid})
    links = [x for x in cap.get("content", []) if x.get("type") == "resource_link"]
    from run_sinjoh import size_of, write_png  # noqa: E402  (shares the PNG writer)
    import base64

    saved = []
    for i, link in enumerate(links):
        res = send({"op": "resource", "uri": link["uri"]}, port)["reply"]
        for item in res.get("result", {}).get("contents", []):
            if item.get("blob"):
                w, h = size_of(link)
                path = a.out / f"{link.get('name', i)}.png"
                write_png(path, base64.b64decode(item["blob"]), w, h)
                saved.append(str(path))
    print("saved:", ", ".join(saved) or "(none)")

    lines = log_since(mark)
    keep = re.compile(r"^.*\[(perf|gamecpu|scene|gpu|ds|pace|mon)\]")
    for line in lines[-60:]:
        if keep.match(line):
            print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
