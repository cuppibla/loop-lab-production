"""Rung 01 — one long job.

The producer agent submits ONE render job (the trailer). The tool is a
LongRunningFunctionTool: it returns `pending` and the run ENDS. Nothing in
this rung can ever finish the job — that is the point. The doorbells arrive
in rung 02.

(Done Lab 1 'The Long-Running Agent' Steps 2–3? This rung is the same
mechanic in a new domain — skim it and move on.)
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
    "When asked to start, say one short line, then call "
    "submit_render(kind='trailer', take=1). It returns status=pending — that "
    "is normal: your run ends and the finished result arrives later as a "
    "function response. When a result arrives with qc='passed', reply exactly: "
    "TRAILER LOCKED."
)


def submit_render(kind: str, take: int, tool_context: ToolContext) -> dict:
    """Submit one long render job to the farm. Returns pending; the finished
    result arrives later."""
    job_id = jobs.submit(kind, take, call_id=tool_context.function_call_id)
    return {"status": "pending", "job_id": job_id}


root_agent = Agent(name="producer", model=MODEL, instruction=INSTRUCTION,
                   tools=[LongRunningFunctionTool(submit_render)])

app = App(name="production_floor", root_agent=root_agent,
          resumability_config=ResumabilityConfig(is_resumable=True))
