"""Peek at the two files that ARE the running agent.

Run this after `drive.py start`, while the trailer is "rendering". It prints
the entire state of the system — because the entire state of the system is
two files on disk, and nothing else.

  python peek.py
"""
import json
import os
import sqlite3
import subprocess
import sys

import jobs

DB = "floor.db"


def section(title):
    print(f"\n─── {title} " + "─" * max(0, 58 - len(title)))


# ── 1. is anything actually running? ─────────────────────────────────────────
section("Processes belonging to this agent")
try:
    ps = subprocess.run(["ps", "ax", "-o", "pid=,command="],
                        capture_output=True, text=True).stdout
    mine = [l for l in ps.splitlines()
            if ("drive.py" in l or "farm.py" in l) and "grep" not in l]
except Exception:
    mine = []
print(f"  {len(mine)} process(es) alive")
for l in mine:
    print("   ", l.strip()[:90])
if not mine:
    print("    (none — no process, no thread, no container)")

# ── 2. the world: the render farm's order book ───────────────────────────────
section("THE WORLD — render_farm.json (what really happened)")
if os.path.exists(jobs.STORE):
    raw = open(jobs.STORE).read()
    print(f"  {len(raw)} bytes on disk:")
    for line in raw.splitlines():
        print("   ", line)
else:
    print("    (no file yet — run drive.py start)")

# ── 3. the session: the agent's memory ───────────────────────────────────────
section("THE SESSION — floor.db (the agent's memory)")
if not os.path.exists(DB):
    print("    (no database yet — run drive.py start)")
    sys.exit(0)

con = sqlite3.connect(DB)
rows = con.execute("select event_data from events order by timestamp").fetchall()
print(f"  {len(rows)} event(s) logged. In order:\n")

open_calls = {}
for i, (blob,) in enumerate(rows, 1):
    d = json.loads(blob)
    parts = (d.get("content") or {}).get("parts") or []
    print(f"  event {i} · author={d.get('author')}")
    for p in parts:
        if p.get("text") and p["text"].strip():
            print(f"      text          : {p['text'].strip()[:70]}")
        if p.get("function_call"):
            fc = p["function_call"]
            print(f"      function_call : {fc['name']}({fc.get('args')})  id={fc.get('id')}")
        if p.get("function_response"):
            fr = p["function_response"]
            status = (fr.get("response") or {}).get("status")
            print(f"      function_resp : {fr['name']} → status={status}")
    for cid in (d.get("long_running_tool_ids") or []):
        open_calls[cid] = True
        print(f"      ⏳ long_running_tool_ids = ['{cid}']   ← the call still on hold")

# ── 4. the punchline ─────────────────────────────────────────────────────────
section("So what is 'a render in progress'?")
book = {j["call_id"]: j for j in jobs.all_jobs()}
for cid in open_calls:
    j = book.get(cid)
    print(f"  call_id {cid}")
    print(f"    · in the SESSION: an unanswered call, waiting for a function_response")
    print(f"    · in the WORLD  : {j['job_id'] if j else '(not in the order book!)'}"
          f"{'  status=' + j['status'] if j else ''}")
    print(f"    · the SAME id in both files — that is the return address the")
    print(f"      doorbell will use to find its way back to this conversation.")
if not open_calls:
    print("  Nothing is on hold. Run drive.py start first.")
print()
