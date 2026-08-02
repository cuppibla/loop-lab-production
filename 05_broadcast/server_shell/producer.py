"""Room 2 live backend — the producer agent (ADK).

One agent, several long-running calls at once. Both tools are
LongRunningFunctionTools: every submit parks a pending call and ENDS the run;
the outside world (the render farm / the human) rings a doorbell later and the
server re-drives the same durable session with a function_response.

Verified spine (see Topics/vibeflix/room2-phase0-findings.md): one-turn
parallel fan-out, one-at-a-time out-of-order resume matching, join in the
driver. The join TRUTH lives in server.py (counted events), not in the model.
"""
import os

from dotenv import load_dotenv

load_dotenv()
os.environ.pop("GOOGLE_GENAI_USE_VERTEXAI", None)

import farm
from google.adk.agents import Agent
from google.adk.apps.app import App, ResumabilityConfig
from google.adk.tools import LongRunningFunctionTool, ToolContext
from google.genai import types as genai_types

MODEL = os.environ.get("ROOM2_MODEL", "gemini-3-flash-preview")

INSTRUCTION = (
    "You are the producer agent on the VibeFlix production floor, making the "
    "launch package for the show 'Tuesday, Again'. Four assets: trailer, "
    "poster, music, localized_trailer.\n"
    "Rules:\n"
    "1. When asked to produce the package, first say one short confident line, "
    "then call submit_render for kind='trailer', kind='poster' and "
    "kind='music' (all take=1) IN A SINGLE TURN — three parallel calls. Do NOT "
    "submit localized_trailer yet: it depends on a finished, QC-passed trailer.\n"
    "2. Every submit_render returns status=pending. That is normal. Your run "
    "ends; results arrive later as function responses.\n"
    "3. When a render result arrives with qc='failed', do not accept it: call "
    "ask_human ONCE with a short question that quotes the QC report and "
    "proposes a re-render. Wait for the answer.\n"
    "4. When the human approves a re-render, call submit_render again for that "
    "kind with take incremented (e.g. take=2).\n"
    "5. When the trailer result arrives with qc='passed', submit_render "
    "kind='localized_trailer' take=1 in the same turn — the dependency is now "
    "unlocked. Say so.\n"
    "6. When and only when all FOUR kinds have a qc='passed' result, reply "
    "exactly: PACKAGE SHIPPED. Never say it earlier.\n"
    "Keep every spoken line to one or two sentences, in the voice of a calm "
    "professional producer."
)


def submit_render(kind: str, take: int, tool_context: ToolContext) -> dict:
    """Submit one long render job to the farm. Returns pending; the finished
    result arrives later as a function response."""
    job_id = farm.submit(kind, take)          # idempotent per (kind, take)
    return {"status": "pending", "job_id": job_id, "kind": kind, "take": take}


def ask_human(question: str, tool_context: ToolContext) -> dict:
    """Ask the human on the floor a question (e.g. approve a re-render).
    Returns pending; their answer arrives later as a function response."""
    return {"status": "pending", "question": question}


# NOTE: do NOT set thinking_budget=0 here — gemini-3-flash-preview stalls the
# doorbell turn under it (verified live, twice). Thought text is kept out of
# the feed by the bridge's p.thought filter in server.py instead.
root_agent = Agent(
    name="producer",
    model=MODEL,
    instruction=INSTRUCTION,
    tools=[LongRunningFunctionTool(submit_render), LongRunningFunctionTool(ask_human)],
)

app = App(name="production_floor", root_agent=root_agent,
          resumability_config=ResumabilityConfig(is_resumable=True))
