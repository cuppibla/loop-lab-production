"""Rung 01 driver — the same drive() contract as Lab 1's Step 7.

Commands: reset | start | status | pending

`pending` shows what the world is reduced to while the job renders:
open long-running calls in the durable session, and rows in the farm's
order book. No process anywhere.
"""
import asyncio
import os
import sys

from dotenv import load_dotenv

load_dotenv()
os.environ.pop("GOOGLE_GENAI_USE_VERTEXAI", None)

from google.adk.runners import Runner
from google.adk.sessions import DatabaseSessionService
from google.genai import types

import jobs
from agent import app

DB = "sqlite+aiosqlite:///./floor.db"
APP = "production_floor"
USER = "u"
SESSION = "floor"      # one fixed session for the whole episode


def session_service():
    return DatabaseSessionService(db_url=DB)


async def drive(*, new_message=None, invocation_id=None, service=None):
    """One run against the durable session. Returns 'PAUSED' or 'ENDED'."""
    service = service or session_service()
    runner = Runner(app=app, session_service=service)
    outcome = "ENDED"
    async for ev in runner.run_async(user_id=USER, session_id=SESSION,
                                     new_message=new_message, invocation_id=invocation_id):
        for f in ev.get_function_calls() or []:
            lr = ev.long_running_tool_ids and f.id in ev.long_running_tool_ids
            print(f"    -> {f.name}({dict(f.args)}){' [PENDING]' if lr else ''}  id={f.id}")
            if lr:
                outcome = "PAUSED"
        if ev.content and ev.content.parts:
            for p in ev.content.parts:
                if getattr(p, "thought", None):
                    continue
                if p.text and p.text.strip():
                    print(f"    <agent> {p.text.strip()}")
    return outcome


async def open_calls(service):
    """Long-running calls announced in the session, latest per (name, kind)."""
    s = await service.get_session(app_name=APP, user_id=USER, session_id=SESSION)
    if not s:
        return {}
    found = {}
    for ev in s.events:
        if ev.long_running_tool_ids:
            for f in ev.get_function_calls() or []:
                if f.id in ev.long_running_tool_ids:
                    found[f.id] = (f.name, dict(f.args or {}))
    return found


async def cmd_start():
    service = session_service()
    await service.create_session(app_name=APP, user_id=USER, session_id=SESSION)
    print("[start] one long job")
    out = await drive(new_message=types.Content(role="user", parts=[types.Part(
        text="Start the trailer render for 'Tuesday, Again'.")]), service=service)
    print(f"[drive] -> {out}   (the process you are in is about to exit)")


async def cmd_pending():
    calls = await open_calls(session_service())
    print(f"[pending] {len(calls)} open long-running call(s) in the session:")
    for cid, (name, args) in calls.items():
        print(f"    {cid}  {name}({args})")
    print(f"[world]   farm order book: {jobs.summary()}")


async def cmd_status():
    print(f"[status] farm: {jobs.summary()}")


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    if cmd == "reset":
        for f in ["floor.db", jobs.STORE]:
            if os.path.exists(f):
                os.remove(f)
        jobs.reset()
        print("[reset] clean slate")
        return
    asyncio.run({"start": cmd_start, "pending": cmd_pending,
                 "status": cmd_status}[cmd]())


if __name__ == "__main__":
    main()
