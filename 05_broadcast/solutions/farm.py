"""The render farm — fake but honest: jobs take real seconds, emit real
progress, finish independently, and ring a machine doorbell on completion.

Deterministic QC: the trailer's take 1 always fails QC (noise in act 3);
everything else passes. Swap `_render` for a real Veo call later — the
doorbell contract does not change (Veo's webhook_config/user_metadata maps
onto exactly this callback; see room2-phase0-findings).
"""
import asyncio

# injected by server.configure()
_emit = None          # emit(contract_event_dict)
_doorbell = None      # async doorbell(kind, take, result_dict)

DURATIONS = {"trailer": 11, "poster": 6, "music": 9, "localized_trailer": 8}
ASSET_URLS = {
    ("trailer", 2): "/world/assets/trailer_t2.mp4",
    ("poster", 1): "/world/assets/poster_t1.png",
    ("music", 1): "/world/assets/theme_t1.mp3",
    ("localized_trailer", 1): "/world/assets/trailer_t2_intl.mp4",
}
QC_REPORT = ("Act 3, the rain scene: visible noise in the low-light shots, "
             "and the lead's face loses detail.")

_jobs: dict[tuple, dict] = {}
_tasks: list[asyncio.Task] = []


def configure(emit, doorbell):
    global _emit, _doorbell
    _emit, _doorbell = emit, doorbell


def reset():
    for t in _tasks:
        t.cancel()
    _tasks.clear()
    _jobs.clear()


def submit(kind: str, take: int) -> str:
    """Idempotent per (kind, take): a duplicate submit returns the same job."""
    key = (kind, take)
    if key in _jobs:                                   # the guard
        return _jobs[key]["job_id"]
    job = {"job_id": f"JOB-{kind}-t{take}", "kind": kind, "take": take}
    _jobs[key] = job
    _tasks.append(asyncio.get_running_loop().create_task(_render(job)))
    return job["job_id"]


async def _render(job):
    kind, take = job["kind"], job["take"]
    dur = DURATIONS.get(kind, 8)
    steps = 4
    for i in range(1, steps):
        await asyncio.sleep(dur / steps)
        _emit({"type": "job_progress", "job": kind, "pct": round(100 * i / steps)})
    await asyncio.sleep(dur / steps)
    _emit({"type": "job_progress", "job": kind, "pct": 100})

    qc = "failed" if (kind == "trailer" and take == 1) else "passed"
    result = {"status": "done", "kind": kind, "take": take, "qc": qc}
    if qc == "passed":
        result["asset_url"] = ASSET_URLS.get((kind, take), f"/world/assets/{kind}_t{take}")
    else:
        result["qc_report"] = QC_REPORT
    try:
        await _doorbell(kind, take, result)            # the machine doorbell
    except asyncio.CancelledError:
        raise
    except Exception:                                  # never die silently
        import traceback
        print(f"[farm] doorbell for {kind} t{take} FAILED:")
        traceback.print_exc()
