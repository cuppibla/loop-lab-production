# Rung 04 · When no one rings

Two failures are SILENT — no error, no exception, no process anywhere:

```bash
# A. The lost bell — the world finished, the session waits forever
uv run python drive.py reset && uv run python drive.py start
uv run python farm.py --drop poster     # poster renders; its callback vanishes
uv run python backstop.py               # LOST BELL found → re-rings the stored result

# B. The ghost — the session waits for a job the farm never received
uv run python drive.py reset
CRASH_AFTER_SUBMITS=2 uv run python drive.py start   # dies mid-fan-out
uv run python drive.py resume            # replays calls as pending — does NOT re-run them
uv run python backstop.py                # GHOST found → answers the crashed turn AS A SET
```

**The backstop is a two-way diff between the session and the world**, plus two
rules that make it safe:
1. `ask_human` calls are **not its job** — that wake-up belongs to the human
   doorbell (Lab 1 Step 7's discriminator, same rule).
2. A crashed turn of parallel calls must be answered **as a set** — the crash
   loses the interim `pending` responses, and a lone answer can never complete
   the turn again (the model stays silent forever). Verified on ADK 2.5.0.

In production this runs on a clock. The deadline is the third doorbell.
