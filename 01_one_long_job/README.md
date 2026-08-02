# Rung 01 · One long job

**Adds:** a producer agent whose only tool is a `LongRunningFunctionTool`.
It submits ONE render, gets `pending`, and the run ENDS. Nothing in this rung
can ever finish the job — that is the cliffhanger.

```bash
uv run python drive.py reset
uv run python drive.py start      # submits, parks, exits
uv run python drive.py pending    # the whole world: one open call + one order-book row
```

While the trailer "renders" there is no process, no thread, no await — one
row in `floor.db`, one row in `render_farm.json`. Who rings the doorbell? → 02

*(Done Lab 1 Steps 2–3? Same mechanic, new domain — skim and move on.)*
