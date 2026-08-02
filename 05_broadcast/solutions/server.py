"""Room 2 live backend — same event contract as the replayer, a real ADK agent
inside. The Next.js app proxies /api/rooms/2/* here when ROOM2_AGENT_URL is set.

The spine (verified in room2-phase0-findings):
  - the producer agent fans out several LongRunningFunctionTool calls in one
    turn; every submit parks a pending call and the run ENDS — nothing runs
    while the farm renders;
  - the farm rings the MACHINE doorbell (a function_response) per finished job;
  - the human rings the HUMAN doorbell (POST /actions → rooms/2/reply);
  - both doorbells take the identical path: drive(session, function_response);
  - the JOIN is counted HERE, in the driver — the model only narrates.

Endpoints:
  GET  /events?restart=1   SSE stream of contract events (history on connect)
  POST /actions            {action: "rooms/2/reply", call_id: "...", ...}
  GET  /health
"""
from __future__ import annotations

import asyncio
import json
import os
import time

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse

import farm
from producer import app as adk_app

from google.adk.runners import Runner
from google.adk.sessions import DatabaseSessionService
from google.genai import types

DB = "sqlite+aiosqlite:///./floor.db"
APP_NAME = "production_floor"
USER = "u"
TOTAL_JOBS = 4
JOB_MEDIA = {"trailer": "veo", "poster": "image", "music": "audio",
             "localized_trailer": "veo"}

app = FastAPI()


class Run:
    """SSE fan-out + the driver state for one episode."""

    def __init__(self, sid: str):
        self.sid = sid
        self.started_at = time.time()
        self.task: asyncio.Task | None = None
        self.history: list[dict] = []
        self.subscribers: list[asyncio.Queue] = []
        self.session_service = DatabaseSessionService(db_url=DB)
        self.drive_lock = asyncio.Lock()      # serialize doorbells on one session
        self.submit_calls: dict[tuple, str] = {}   # (kind, take) -> call_id
        self.human_call: str | None = None
        self.done_jobs = 0
        self.shipped = False

    # ---- contract event helpers -------------------------------------------
    def emit(self, ev: dict):
        ev = {**ev, "ts": int(time.time() * 1000)}
        self.history.append(ev)
        for q in list(self.subscribers):
            q.put_nowait(ev)

    def say(self, text: str):
        self.emit({"type": "agent_said", "room": 2, "agent": "producer", "text": text})

    def patch(self, path: str, value):
        self.emit({"type": "world_patch", "path": path, "value": value})

    # ---- THE driver: one contract, every doorbell goes through here -------
    async def drive(self, *, new_message=None, invocation_id=None, label="?"):
        print(f"[drive:{label}] waiting for lock", flush=True)
        async with self.drive_lock:
            print(f"[drive:{label}] running", flush=True)
            runner = Runner(app=adk_app, session_service=self.session_service)
            async for ev in runner.run_async(user_id=USER, session_id=self.sid,
                                             new_message=new_message,
                                             invocation_id=invocation_id):
                for f in ev.get_function_calls() or []:
                    lr = ev.long_running_tool_ids and f.id in ev.long_running_tool_ids
                    if not lr:
                        continue
                    self._bridge_call(f)
                if ev.content and ev.content.parts:
                    for p in ev.content.parts:
                        if getattr(p, "thought", None):
                            continue            # never leak thinking into the feed
                        if p.text and p.text.strip():
                            self.say(p.text.strip())
                            if "PACKAGE SHIPPED" in p.text:
                                self._ship()

    def _bridge_call(self, f):
        """ADK function_call event -> contract event (the bridge layer)."""
        args = dict(f.args or {})
        if f.name == "submit_render":
            kind, take = args.get("kind"), int(args.get("take", 1))
            self.submit_calls[(kind, take)] = f.id
            self.emit({"type": "job_submitted", "job": kind,
                       "kind": JOB_MEDIA.get(kind, "veo")})
            self.patch(f"world/show.assets.{kind}",
                       {"status": "rendering", "take": take})
        elif f.name == "ask_human":
            self.human_call = f.id
            self.emit({"type": "job_paused_need_human", "job": "trailer",
                       "question": args.get("question", ""), "call_id": f.id})
            self.patch("world/show.assets.trailer", {"status": "paused", "take": 1})
            # the contract's wait signal — this is what enables the panel button
            self.emit({"type": "awaiting_action", "action": "rooms/2/reply",
                       "match": {"call_id": f.id}})

    # ---- doorbell #1: the machine (farm completion) -----------------------
    async def on_job_done(self, kind: str, take: int, result: dict):
        call_id = self.submit_calls.get((kind, take))
        if not call_id:
            return
        if result["qc"] == "passed":
            self.emit({"type": "job_completed", "job": kind,
                       "asset_url": result["asset_url"], "take": take})
            self.patch(f"world/show.assets.{kind}",
                       {"status": "done", "url": result["asset_url"], "take": take})
            self.done_jobs += 1                       # the join lives HERE
            self.emit({"type": "join_progress", "done": self.done_jobs,
                       "total": TOTAL_JOBS})
        resume = types.Content(role="user", parts=[types.Part(
            function_response=types.FunctionResponse(
                id=call_id, name="submit_render", response=result))])
        await self.drive(new_message=resume, label=f"machine:{kind}")

    # ---- doorbell #2: the human (POST /actions) ---------------------------
    async def on_human_reply(self, body: dict) -> bool:
        if not self.human_call or body.get("call_id") != self.human_call:
            return False
        call_id, self.human_call = self.human_call, None
        self.emit({"type": "action_received", "action": "rooms/2/reply"})
        resume = types.Content(role="user", parts=[types.Part(
            function_response=types.FunctionResponse(
                id=call_id, name="ask_human",
                response={"approved": True, "re_render": True}))])
        await self.drive(new_message=resume, label="human")
        return True

    def _ship(self):
        if self.shipped or self.done_jobs < TOTAL_JOBS:
            return                                    # model says shipped; driver verifies
        self.shipped = True
        self.emit({"type": "package_ready",
                   "assets": [farm.ASSET_URLS[k] for k in
                              [("trailer", 2), ("poster", 1), ("music", 1),
                               ("localized_trailer", 1)]]})
        self.patch("world/show.package_ready", True)
        self.emit({"type": "gate_check", "room": 2, "ok": True, "missing": []})
        self.emit({"type": "room_complete", "room": 2})


run: Run | None = None
_counter = 0


async def episode(r: Run):
    try:
        farm.configure(r.emit, r.on_job_done)
        await r.session_service.create_session(app_name=APP_NAME, user_id=USER,
                                               session_id=r.sid)
        r.patch("world/show.status", "in_production")
        await r.drive(new_message=types.Content(role="user", parts=[types.Part(
            text="Produce the launch package for 'Tuesday, Again'.")]), label="start")
    except Exception as e:
        r.emit({"type": "error", "room": 2, "message": f"live backend error: {e}"})
        r.emit({"type": "gate_check", "room": 2, "ok": False,
                "missing": [str(e)[:120]]})
        r.emit({"type": "room_complete", "room": 2})


def start_run() -> Run:
    global run, _counter
    # debounce: a dev-mode double-mount reconnects twice within a beat —
    # two racing episodes on one global farm scramble the floor
    if run and time.time() - run.started_at < 2.0:
        return run
    if run and run.task and not run.task.done():
        run.task.cancel()
    farm.reset()
    _counter += 1
    run = Run(sid=f"floor-{int(time.time())}-{_counter}")
    run.task = asyncio.get_event_loop().create_task(episode(run))
    return run


@app.get("/health")
async def health():
    from producer import MODEL
    return {"ok": True, "mode": "live", "model": MODEL}


@app.get("/events")
async def events(request: Request):
    global run
    if run is None or request.query_params.get("restart") == "1":
        start_run()
    r = run
    q: asyncio.Queue = asyncio.Queue()
    for ev in r.history:
        q.put_nowait(ev)
    r.subscribers.append(q)

    async def stream():
        try:
            while True:
                ev = await q.get()
                yield f"data: {json.dumps(ev)}\n\n"
        finally:
            if q in r.subscribers:
                r.subscribers.remove(q)

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache"})


@app.post("/actions")
async def actions(request: Request):
    body = await request.json()
    action = body.pop("action", "")
    ok = False
    if run and action == "rooms/2/reply":
        ok = await run.on_human_reply(body)
    return {"ok": ok}


if __name__ == "__main__":
    port = int(os.environ.get("ROOM2_PORT", "8052"))
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")
