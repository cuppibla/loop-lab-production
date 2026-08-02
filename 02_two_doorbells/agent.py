"""Rung 02 — two doorbells, one door.

Same producer, now with QC in the loop. Two LongRunningFunctionTools:

  submit_render  -> woken by the MACHINE doorbell (the farm worker finishes)
  ask_human      -> woken by the HUMAN doorbell (you approve the re-render)

Both wake-ups are the same thing: a function_response driven into the same
durable session. Only the latency differs.
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
    "launch package for the show 'Tuesday, Again'.\n"
    "Rules:\n"
    "1. When asked to start, say one short line, then call "
    "submit_render(kind='trailer', take=1).\n"
    "2. Every submit_render returns status=pending. That is normal: your run "
    "ends; the finished result arrives later as a function response.\n"
    "3. When a render result arrives with qc='failed', do not accept it: call "
    "ask_human ONCE with a short question that quotes the QC report and "
    "proposes a re-render. Do nothing else in that turn.\n"
    "4. When the human approves, call submit_render for the same kind with "
    "take incremented (take=2).\n"
    "5. When a render result arrives with qc='passed', reply exactly: "
    "TRAILER LOCKED, take N. (with the take number)\n"
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
