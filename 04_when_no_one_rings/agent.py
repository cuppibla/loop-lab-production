"""Rung 04 — when no one rings.

Same agent as rung 03 (diff: only the CRASH flag below). The new machinery is
backstop.py — the thing that notices SILENT failures: a doorbell that got
lost, and a submit that never reached the farm (the ghost pending).

Env flag:
  CRASH_AFTER_SUBMITS=N -> hard-crash right after the Nth submit's side
                           effect (the fan-out crash window).
"""
import os

from dotenv import load_dotenv

load_dotenv()
os.environ.pop("GOOGLE_GENAI_USE_VERTEXAI", None)

import jobs
from google.adk.agents import Agent
from google.adk.apps.app import App, ResumabilityConfig
from google.adk.tools import LongRunningFunctionTool, ToolContext

MODEL = "gemini-3-flash-preview"

INSTRUCTION = (
    "You are the producer agent on the VibeFlix production floor, making the "
    "launch package for the show 'Tuesday, Again'. Four assets: trailer, "
    "poster, music, localized_trailer.\n"
    "Rules:\n"
    "1. When asked to start, say one short line, then call submit_render for "
    "kind='trailer', kind='poster' and kind='music' (all take=1) IN A SINGLE "
    "TURN — three parallel calls. Do NOT submit localized_trailer yet: it "
    "depends on a finished, QC-passed trailer.\n"
    "2. Every submit_render returns status=pending. That is normal: your run "
    "ends; results arrive later as function responses.\n"
    "3. When a render result arrives with qc='failed', do not accept it: call "
    "ask_human ONCE with a short question that quotes the QC report and "
    "proposes a re-render. Do nothing else in that turn.\n"
    "4. When the human approves, call submit_render for that kind with take "
    "incremented (take=2).\n"
    "5. When the trailer result arrives with qc='passed', call "
    "submit_render(kind='localized_trailer', take=1) — the dependency is now "
    "unlocked. Say so.\n"
    "6. When and only when all FOUR kinds have a qc='passed' result, reply "
    "exactly: PACKAGE SHIPPED. Never say it earlier.\n"
    "Keep every spoken line to one or two sentences.\n"
    "HARD RULES: Results and approvals arrive ONLY as function responses. "
    "NEVER invent, assume or narrate a result, approval or QC report that "
    "has not arrived. Never call submit_render for a kind and take you "
    "have already submitted (already_submitted means it is in progress — "
    "do not resubmit). Each turn: make the required tool calls, or say ONE "
    "short status line. Nothing else."
)


def submit_render(kind: str, take: int, tool_context: ToolContext) -> dict:
    """Submit one long render job to the farm. Returns pending; the finished
    result arrives later."""
    if jobs.get(kind, take):
        return {"status": "pending", "note": "already_submitted — do not resubmit; the result will arrive"}
    job_id = jobs.submit(kind, take, call_id=tool_context.function_call_id)
    n = int(os.environ.get("CRASH_AFTER_SUBMITS", "0"))
    if n and len(jobs.all_jobs()) >= n:
        print(f"    [SIMULATED CRASH] after {n} submit(s); dying before logging...")
        os._exit(1)
    return {"status": "pending", "job_id": job_id, "next": "Render submitted and running. Say ONE short status line and STOP — the result will arrive later as a function response. Do not call any more tools in this turn unless a rule requires it."}


def ask_human(question: str, tool_context: ToolContext) -> dict:
    """Ask the human on the floor a question. Returns pending; their answer
    arrives later."""
    return {"status": "pending", "question": question,
            "next": "Question delivered to the human. Say ONE short waiting line and STOP. The answer will arrive later as a function response — NEVER assume it."}


# NOTE: no generate_content_config here — on gemini-3-flash-preview + ADK
# 2.5.0, configs (thinking_budget=0, even temperature) intermittently stall
# long-running resume turns. Steering lives in the tool RESULTS instead.
root_agent = Agent(name="producer", model=MODEL, instruction=INSTRUCTION,
                   tools=[LongRunningFunctionTool(submit_render),
                          LongRunningFunctionTool(ask_human)])

app = App(name="production_floor", root_agent=root_agent,
          resumability_config=ResumabilityConfig(is_resumable=True))
