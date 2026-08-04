# The Production Floor · doorbells, fan-out, joins, and the backstop

> **🌅 Want the full course?** This lab and its prequel are merged into
> **[Overnight Studios](https://github.com/cuppibla/overnight-studios)** — the
> comprehensive long-running-agent lab (nine rungs, one axis, Colab included).
> This repo remains the standalone trigger-layer climb.

A hands-on ADK lab about the **Trigger layer** of a long-running agent: who —
or what — presses "Continue". You build a producer agent that fans one request
out into four long render jobs, gets woken by **two doorbells** (a machine
callback and a human click — the identical resume path), hand-writes the
**join**, and then builds the **backstop** that catches the failures nobody
rings a bell for.

> **Concept:** an agent's wake-ups come from exactly three places — an event
> from a machine, a click from a human, or a clock. This lab builds the first
> two and the clock-driven safety net. The crash-driven wake-up (the sweeper)
> lives in [Lab 1 · The Long-Running Agent](https://github.com/cuppibla/loop-lab-onboarding),
> Step 7 — the two labs split the story along the two kinds of resume.

**Scenario:** the VibeFlix production floor — ship the launch package for
*Tuesday, Again*: trailer, poster, music, localized trailer. The localized cut
can't start until the trailer is final; the trailer's take 1 always fails QC.
The render farm is a local stub with real seconds and real progress; rung 06
maps it onto real Veo.

> **📖 Following the guided codelab?** See **[CODELAB.md](CODELAB.md)** — the
> step-by-step walkthrough (claat-ready).

## Setup

```bash
./setup_venv.sh            # Windows: setup_venv.bat   — or:  uv sync
source .venv/bin/activate
cp .env.example .env       # put your Gemini API key in .env
```

## The cast (the same five things in every rung)

| | What it is |
|---|---|
| `agent.py` | the agent's *definition* — instructions + tools. Never runs on its own. |
| `drive.py` | **the CLI you type** (`reset` / `start` / `approve` / …). Starts one run, then the process exits. |
| `farm.py` | the render farm — a **separate program**, standing in for the outside world. |
| `floor.db` | **THE SESSION** — the agent's memory (SQLite of events, written by ADK). |
| `render_farm.json` | **THE WORLD** — what was really submitted, rendered, approved. |

`drive.py reset` deletes those last two files and nothing else — progress
lives on disk, so replaying a rung has to be explicit. Keep session and world
apart in your head: rung 04 is entirely about what to do when they disagree.

## The ladder (run each in its own folder)

| Rung | Adds | The lesson |
|---|---|---|
| **[01_one_long_job](01_one_long_job)** | one `LongRunningFunctionTool` call | while it "renders": no process — one DB row + one order-book row |
| **[02_two_doorbells](02_two_doorbells)** | the farm (a separate process) + `approve` | machine and human wake-ups are the SAME `function_response`; the re-render gate lives in the world |
| **[03_the_join](03_the_join)** | fan-out ×3 + a dependency + the join | the model narrates ("PACKAGE SHIPPED" at 3/4!); the driver counts the world |
| **[04_when_no_one_rings](04_when_no_one_rings)** | `backstop.py` | lost bells and **ghost pendings**; a crashed parallel turn must be answered **as a set** |
| **[05_broadcast](05_broadcast)** | a server shell + `scripts/check.py` | same mechanics as a typed event stream; a robot attendee grades you |
| **[06_cloud](06_cloud)** | a runbook | Cloud SQL · Cloud Run · real Veo webhooks · the backstop on a clock |

Soft prerequisite: Lab 1 Steps 2–4 (~30 min) — durable sessions, pause/resume.
Skip lanes are marked; this lab is fully standalone.

## The three money moments

1. **`drive.py pending` in rung 01** — the entire "running" agent is two rows.
2. **Rung 03's join meter** — the model announces victory at 3/4; the driver's
   count corrects it. *Whatever the model says, the world is the score.*
3. **Rung 04's ghost** — a crash leaves the session waiting for a job the farm
   never received. No error will ever fire. Only a two-way diff finds it.

## Notes / gotchas (all verified on ADK 2.5.0 + gemini-3-flash-preview)

- A long-running call's interim `{'status': 'pending'}` is itself logged as a
  function_response. Two consequences: don't infer "still open" by counting
  responses casually — and after a **crash** those interims are lost, so a
  turn of parallel calls can only be revived by answering **the whole set** in
  one message (see `04/backstop.py`).
- On re-drive after a crash, announced long-running calls **replay as pending
  and do not re-run** (normal tools re-run). That is where ghosts come from.
- Do **not** set `generate_content_config` (thinking_budget, even temperature)
  on this model here — it intermittently stalls long-running resume turns.
  Steer with tool **results** (`"next": "…STOP…"`) instead; it works better
  than system-prompt rules anyway.
- Filter `part.thought` before showing model text — thinking leaks as text
  parts on 2.5.
- The model will sometimes narrate results that haven't happened. Let it. The
  world-side gate + the driver-side join are the actual control surface.

## Companion

`05_broadcast/solutions/` is byte-for-byte the live backend behind the
VibeFlix Studios "Production Floor" room — the same event contract this lab's
`check.py` grades. One log, two audiences: your terminal and a Netflix-style
set.
