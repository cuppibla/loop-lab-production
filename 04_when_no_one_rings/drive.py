"""Rung 04 driver — 03's plus `resume` (re-drive after a crash).

Commands: reset | start | resume | approve | status | pending
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
SESSION = "floor"


def session_service():
    return DatabaseSessionService(db_url=DB)


async def drive(*, new_message=None, invocation_id=None, service=None):
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


async def ring(call_id: str, name: str, response: dict):
    """THE doorbell: answer an open long-running call. Machine and human
    wake-ups both come through here — that is the whole lesson."""
    msg = types.Content(role="user", parts=[types.Part(
        function_response=types.FunctionResponse(id=call_id, name=name,
                                                 response=response))])
    out = await drive(new_message=msg)
    done = jobs.done_passed_count()
    print(f"[ring] {name}({call_id}) -> {out}")
    print(f"[join] {done}/4 assets passed QC")          # <-- the join, in code
    if done == 4:
        print("[gate] driver-verified: all four in the world. The model's "
              "'PACKAGE SHIPPED' above is narration; THIS line is the check.")
    return out


async def last_call(service, tool_name):
    """Most recent long-running call to `tool_name` in the session."""
    s = await service.get_session(app_name=APP, user_id=USER, session_id=SESSION)
    found = None
    for ev in (s.events if s else []):
        if ev.long_running_tool_ids:
            for f in ev.get_function_calls() or []:
                if f.id in ev.long_running_tool_ids and f.name == tool_name:
                    found = (f.id, dict(f.args or {}))
    return found


async def cmd_start():
    service = session_service()
    await service.create_session(app_name=APP, user_id=USER, session_id=SESSION)
    print("[start] fan-out: one request, four long jobs")
    out = await drive(new_message=types.Content(role="user", parts=[types.Part(
        text="Produce the launch package for 'Tuesday, Again'.")]), service=service)
    print(f"[drive] -> {out}")


async def cmd_approve():
    """The HUMAN doorbell. Records the approval in the world first (that is
    what unlocks the farm's gate), then answers the agent's question."""
    jobs.approve_rerender("trailer")
    print("[approve] approval recorded in the order book (the farm's gate reads this)")
    pending = await last_call(session_service(), "ask_human")
    if not pending:
        print("[approve] the agent has not asked anything (yet) — approval is on file anyway")
        return
    cid, args = pending
    print(f"[approve] answering: {args.get('question', '')[:80]}...")
    await ring(cid, "ask_human", {"approved": True, "re_render": True})


async def cmd_resume():
    service = session_service()
    s = await service.get_session(app_name=APP, user_id=USER, session_id=SESSION)
    inv = s.events[-1].invocation_id
    print(f"[resume] re-driving unfinished invocation {inv}")
    out = await drive(invocation_id=inv, service=service)
    print(f"[drive] -> {out}")


async def cmd_pending():
    s = await session_service().get_session(app_name=APP, user_id=USER, session_id=SESSION)
    calls = {}
    for ev in (s.events if s else []):
        if ev.long_running_tool_ids:
            for f in ev.get_function_calls() or []:
                if f.id in ev.long_running_tool_ids:
                    calls[f.id] = (f.name, dict(f.args or {}))
    print(f"[pending] {len(calls)} long-running call(s) ever announced:")
    for cid, (name, args) in calls.items():
        print(f"    {cid}  {name}({args})")
    print(f"[world]   {jobs.summary()}  approvals={jobs._load()['approvals']}")


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
    asyncio.run({"start": cmd_start, "approve": cmd_approve, "resume": cmd_resume,
                 "pending": cmd_pending, "status": cmd_status}[cmd]())


if __name__ == "__main__":
    main()
