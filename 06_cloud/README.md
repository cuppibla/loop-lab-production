# Rung 06 · To the cloud (guided runbook)

Nothing about the agent changes. Four swaps, in order of effort:

## 1. The session store — a connection string

```python
# local:  sqlite+aiosqlite:///./floor.db
# cloud:  postgresql+asyncpg://…   (Cloud SQL Python Connector; async driver, NOT pg8000)
```
Same rule as [loop-lab-onboarding Step 6](https://github.com/cuppibla/loop-lab-onboarding) — durability is a connection string, not a rewrite.

## 2. The server — Cloud Run

Deploy `05_broadcast/solutions/` as a Cloud Run service (port from `$PORT`,
`ROOM2_PORT` env). Your webhook endpoints (`/actions`, and the farm's callback
if you split it out) become real URLs. Point the app's `ROOM2_AGENT_URL` at it.

## 3. The farm — real Veo

Swap `farm._render` for `client.models.generate_videos(...)`. The doorbell
contract does not change:

- `webhook_config=WebhookConfig(uris=[...], user_metadata={"call_id": ...})` —
  Veo calls YOU back on completion, and `user_metadata` carries the call_id
  correlation your doorbell needs (google-genai ≥ 2.10).
- `pubsub_topic=...` — render **progress** to Pub/Sub → your `job_progress` events.
- If your surface only offers the polling operation: build the doorbell out of
  a poller — poll the operation in a small worker and ring on `done` (rung 02's
  pattern, unchanged).

> ⚠️ Verify which API surface (Vertex vs Developer API) supports
> `webhook_config` on your project before designing around it — and remember
> Veo renders bill real money. Guard with rung 02's idempotent submit.

## 4. The backstop — a clock

`backstop.py` unchanged, run by **Cloud Scheduler** (periodic sweep) or
**Cloud Tasks** (a deadline per job, enqueued at submit time). The deadline is
the third doorbell.

## Teardown

Cloud SQL and Cloud Run bill while they exist; delete the instance and the
service when you finish. This rung is a guided map, not a scripted path — the
cloud pieces here were designed against, not executed by, this repo's CI.
