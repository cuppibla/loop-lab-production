"""Rung 04 — the backstop: what rings when no one rings.

Two failures are SILENT — no error, no exception, no process anywhere:

  1. The lost bell:  the farm rendered the job, but the callback vanished.
                     The world is done; the session still waits.
  2. The ghost:      the process died mid-fan-out. On re-drive, announced
                     long-running calls replay as pending WITHOUT re-running
                     (verified on ADK 2.5.0) — the session waits for a job
                     the farm never received. That bell has nothing to ring it.

And one rule that makes recovery work at all (verified the hard way):

  A turn of PARALLEL calls must be answered AS A SET. On the clean path the
  framework logs an interim {'status': 'pending'} response per long-running
  call — that is what lets a later single function_response complete the set.
  A crash loses those interims, so a single answer can never complete the
  turn again: the model stays silent forever. The backstop must answer the
  WHOLE crashed turn in one message — real results for what finished, a
  'failed' for the ghost, a fresh interim 'pending' for what still renders.

How to tell the cases apart: count responses per call in the session.
  0 responses  -> crashed turn (interims lost)      -> batch-answer the set
  1 response   -> interim only; if world says done+unrung -> LOST BELL, re-ring
  2+ responses -> answered                          -> healthy
  ask_human    -> a human's pause. NOT MY JOB (Lab 1 Step 7's discriminator).

Run it by hand here; in production it runs on a clock (Cloud Tasks / Cloud
Scheduler). The deadline IS the third doorbell.
"""
import asyncio

from google.genai import types

import jobs
from drive import APP, SESSION, USER, drive, ring, session_service
from farm import ASSET_URLS, QC_REPORT


def _result_for(j):
    r = {"status": "done", "kind": j["kind"], "take": j["take"], "qc": j["qc"]}
    if j["qc"] == "passed":
        r["asset_url"] = ASSET_URLS.get((j["kind"], j["take"]),
                                        f"/assets/{j['kind']}_t{j['take']}")
    else:
        r["qc_report"] = QC_REPORT
    return r


async def main():
    service = session_service()
    s = await service.get_session(app_name=APP, user_id=USER, session_id=SESSION)
    if not s:
        print("[backstop] no session — nothing to do")
        return

    lr_calls, resp_count = {}, {}
    for ev in s.events:
        if ev.long_running_tool_ids:
            for f in ev.get_function_calls() or []:
                if f.id in ev.long_running_tool_ids:
                    lr_calls[f.id] = (f.name, dict(f.args or {}))
        for r in ev.get_function_responses() or []:
            resp_count[r.id] = resp_count.get(r.id, 0) + 1

    by_call = {j["call_id"]: j for j in jobs.all_jobs()}
    print(f"[backstop] diffing {len(lr_calls)} session call(s) against the order book")

    batch = []                       # the crashed turn, answered as a set
    for cid, (name, args) in lr_calls.items():
        n = resp_count.get(cid, 0)
        if name == "ask_human":
            print(f"  {cid} ask_human -> awaiting a human. Not my job (doorbell).")
            continue
        j = by_call.get(cid)
        if n >= 2:
            print(f"  {cid} -> answered. Healthy.")
            continue
        if n == 1:                   # interim on file: the clean path
            if j and j["status"] == "done" and not j.get("rung"):
                print(f"  {cid} {j['job_id']} -> LOST BELL: world done, session "
                      "waiting. Re-ringing with the stored result.")
                await ring(cid, "submit_render", _result_for(j))
                jobs.update(j["job_id"], rung=True)
            else:
                print(f"  {cid} {j['job_id'] if j else '?'} -> still rendering. Healthy.")
            continue
        # n == 0: part of a crashed turn — collect, answer as a set
        if j is None:
            kind, take = args.get("kind"), args.get("take", 1)
            print(f"  {cid} submit_render({args}) -> GHOST (crashed turn): the "
                  "farm never heard of it.")
            batch.append((cid, {"status": "failed",
                                "reason": "the submit never reached the farm",
                                "next": f"Call submit_render(kind='{kind}', "
                                        f"take={take}) again now."}))
        elif j["status"] == "done":
            print(f"  {cid} {j['job_id']} -> done in the world (crashed turn).")
            batch.append((cid, _result_for(j)))
            jobs.update(j["job_id"], rung=True)
        else:
            print(f"  {cid} {j['job_id']} -> still rendering (crashed turn): "
                  "answering with a fresh interim pending.")
            batch.append((cid, {"status": "pending",
                                "note": "still rendering — the result will arrive"}))

    if batch:
        print(f"[backstop] answering the crashed turn as a set ({len(batch)} responses in one message)")
        msg = types.Content(role="user", parts=[
            types.Part(function_response=types.FunctionResponse(
                id=cid, name="submit_render", response=resp))
            for cid, resp in batch])
        out = await drive(new_message=msg)
        print(f"[backstop] crashed turn answered -> {out}")


if __name__ == "__main__":
    asyncio.run(main())
