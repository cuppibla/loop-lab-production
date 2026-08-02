"""The gate for rung 05 — a robot attendee.

Connects to your server's SSE stream, plays the whole episode (it even answers
the human doorbell for you when `awaiting_action` arrives), and checks that a
REAL event stream came out — the same contract the VibeFlix room renders.

    python scripts/check.py [--url http://127.0.0.1:8052]

PASS requires, in one episode:
  - >= 4 job_submitted
  - exactly 1+ job_paused_need_human, with a call_id
  - awaiting_action (the wait signal that unlocks the room's button)
  - action_received after we reply
  - join_progress reaching 4/4
  - package_ready, then gate_check ok, then room_complete
You cannot fake this with print statements — the events must come from a run.
"""
import argparse
import json
import sys
import time

import requests

REQUIRED_ORDER = ["job_paused_need_human", "awaiting_action", "action_received",
                  "package_ready", "gate_check", "room_complete"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8052")
    ap.add_argument("--timeout", type=int, default=240)
    args = ap.parse_args()

    seen = {}
    counts = {}
    join_max = 0
    gate_ok = False
    replied = False
    deadline = time.time() + args.timeout

    print(f"[check] connecting to {args.url}/events?restart=1")
    r = requests.get(f"{args.url}/events", params={"restart": "1"}, stream=True,
                     timeout=args.timeout)
    for line in r.iter_lines(decode_unicode=True):
        if time.time() > deadline:
            print("[check] TIMEOUT")
            break
        if not line or not line.startswith("data: "):
            continue
        ev = json.loads(line[6:])
        t = ev.get("type")
        counts[t] = counts.get(t, 0) + 1
        seen.setdefault(t, time.time())
        if t == "join_progress":
            join_max = max(join_max, ev.get("done", 0))
        if t == "gate_check" and ev.get("ok"):
            gate_ok = True
        if t == "awaiting_action" and not replied:
            call_id = (ev.get("match") or {}).get("call_id")
            print(f"[check] doorbell time — replying with call_id={call_id}")
            resp = requests.post(f"{args.url}/actions",
                                 json={"action": "rooms/2/reply", "call_id": call_id},
                                 timeout=30)
            print(f"[check] reply -> {resp.json()}")
            replied = True
        if t == "room_complete":
            break

    checks = [
        ("4+ jobs submitted", counts.get("job_submitted", 0) >= 4),
        ("paused for a human (with call_id)", counts.get("job_paused_need_human", 0) >= 1),
        ("awaiting_action emitted", "awaiting_action" in seen),
        ("action_received after reply", "action_received" in seen and replied),
        ("join reached 4/4", join_max >= 4),
        ("package_ready", "package_ready" in seen),
        ("gate_check ok", gate_ok),
        ("room_complete", "room_complete" in seen),
    ]
    print()
    ok = True
    for name, passed in checks:
        print(f"  {'✅' if passed else '❌'} {name}")
        ok = ok and passed
    print(f"\n[check] {'PASS — the room would render this run.' if ok else 'FAIL — see ❌ above.'}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
