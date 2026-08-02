# Rung 05 · Broadcast — light up the room

Everything so far lived in your terminal. This rung packages the SAME
mechanics as one service speaking a typed event contract — the stream the
VibeFlix "Production Floor" room renders.

```bash
cd server_shell
uv run python server.py                       # then, from the repo root:
uv run python ../scripts/check.py             # ❌ until you implement the hooks
```

Implement the three `TODO(HOOK n)` sites in `server_shell/server.py`:
1. **submit → `job_submitted`** + a world_patch (the board shows the job)
2. **ask_human → `job_paused_need_human` + `awaiting_action`** (the wait
   signal — without it the room's button stays disabled)
3. **the join → `job_completed` + `join_progress`** (counted here, never in
   the model)

`scripts/check.py` is a robot attendee: it replays the episode, answers the
doorbell itself, and passes only on a real event stream. `solutions/` is the
exact backend the VibeFlix app runs.
