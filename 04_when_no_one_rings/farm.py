"""The render farm — a SEPARATE PROCESS. Run it in its own terminal.

It never shares a process with the agent. It reads the order book, renders
(real seconds, with progress), then rings the MACHINE doorbell: it drives the
same durable session with a function_response for the job's stored call_id.

Deterministic QC: the trailer's take 1 always fails (noise in act 3).

The gate lives HERE, in the world: the farm refuses to start a take > 1
without a recorded human approval. The model may ask nicely or may jump the
gun — the vendor does not start without a purchase order either way.

Usage:  python farm.py                  normal shifts
        python farm.py --drop trailer   render trailer normally but LOSE its
                                        doorbell (the callback network blip)
"""
import asyncio
import sys
import time

import jobs
from drive import ring

DURATIONS = {"trailer": 8, "poster": 3, "music": 5, "localized_trailer": 4}
ASSET_URLS = {("trailer", 2): "/world/assets/trailer_t2.mp4",
              ("poster", 1): "/world/assets/poster_t1.png",
              ("music", 1): "/world/assets/theme_t1.mp3",
              ("localized_trailer", 1): "/world/assets/trailer_t2_intl.mp4"}
QC_REPORT = ("Act 3, the rain scene: visible noise in the low-light shots, "
             "and the lead's face loses detail.")


async def render(job):
    kind, take = job["kind"], job["take"]
    dur = DURATIONS.get(kind, 5)
    print(f"[farm] rendering {job['job_id']} ({dur}s)...")
    for i in (25, 50, 75, 100):
        await asyncio.sleep(dur / 4)
        print(f"[farm]   {job['job_id']} {i}%")
    qc = "failed" if (kind == "trailer" and take == 1) else "passed"
    result = {"status": "done", "kind": kind, "take": take, "qc": qc}
    if qc == "passed":
        result["asset_url"] = ASSET_URLS.get((kind, take), f"/assets/{kind}_t{take}")
    else:
        result["qc_report"] = QC_REPORT
    jobs.update(job["job_id"], status="done", qc=qc)
    if job["kind"] in DROP:
        print(f"[farm] {job['job_id']} done, qc={qc} — but the callback got LOST (nobody rings)")
        return
    print(f"[farm] {job['job_id']} done, qc={qc} — ringing the machine doorbell")
    await ring(job["call_id"], "submit_render", result)   # <-- the doorbell
    jobs.update(job["job_id"], rung=True)


async def main():
    idle_since = time.time()
    while True:
        todo = [j for j in jobs.all_jobs() if j["status"] == "submitted"]
        # the world-side gate: no approval, no take 2
        gated = [j for j in todo if j["take"] > 1 and not jobs.rerender_approved(j["kind"])]
        for j in gated:
            print(f"[farm] {j['job_id']} waiting — take {j['take']} needs a human approval on file")
        runnable = [j for j in todo if j not in gated]
        if runnable:
            runnable.sort(key=lambda j: DURATIONS.get(j["kind"], 5))
            for j in runnable:
                await render(j)
            idle_since = time.time()
            continue
        if time.time() - idle_since > 15:
            print("[farm] nothing to do — clocking out")
            return
        await asyncio.sleep(1)


DROP = set()

if __name__ == "__main__":
    if "--drop" in sys.argv:
        DROP.add(sys.argv[sys.argv.index("--drop") + 1])
    asyncio.run(main())
