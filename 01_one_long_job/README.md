# Rung 01 · One long job

**Adds:** a producer agent whose only tool is a `LongRunningFunctionTool`.
It submits ONE render, gets `pending`, and the run ENDS. Nothing in this rung
can ever finish the job — that is the cliffhanger.

## The cast

| File | What it is |
|---|---|
| `agent.py` | the agent's *definition* — never runs on its own |
| `drive.py` | **the CLI you type**; each command starts one run, then the process exits |
| `peek.py` | prints the entire state of the system (both files + whether anything is alive) |
| `jobs.py` | the render farm's order book helper |
| `floor.db` | **THE SESSION** — the agent's memory (SQLite, written by ADK) |
| `render_farm.json` | **THE WORLD** — what was really submitted/rendered/approved |

`drive.py reset` deletes those last two files. That's all it does — progress
lives on disk, so starting over has to be explicit.

## Run it

```bash
uv run python drive.py reset
uv run python drive.py start      # submits, parks, exits
ps ax | grep drive.py | grep -v grep   # → nothing
uv run python peek.py             # → 0 processes, 204 bytes of world, 4 events
```

**A render in progress = one unanswered call in a database + one row in a JSON
file + zero processes.** The same `call_id` appears in both files — that is
the return address the doorbell will use. Who rings it? → 02

*(Done Lab 1 Steps 2–3? Same mechanic, new domain — skim and move on.)*
