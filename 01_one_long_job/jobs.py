"""The render farm's order book — a JSON file on disk.

This file is the EXTERNAL WORLD: what was really submitted, really rendered,
really approved. Every process in this lab (the driver, the farm worker, the
backstop) reads and writes it. The agent's session is the agent's memory;
this file is the truth to reconcile against.
"""
import json
import os

STORE = "render_farm.json"


def _load():
    if os.path.exists(STORE):
        with open(STORE) as f:
            return json.load(f)
    return {"jobs": [], "approvals": []}


def _save(d):
    with open(STORE, "w") as f:
        json.dump(d, f, indent=2)


def reset():
    _save({"jobs": [], "approvals": []})


def get(kind, take):
    for j in _load()["jobs"]:
        if j["kind"] == kind and j["take"] == take:
            return j
    return None


def submit(kind, take, call_id):
    """Idempotent per (kind, take): a duplicate submit returns the same job."""
    d = _load()
    for j in d["jobs"]:
        if j["kind"] == kind and j["take"] == take:
            return j["job_id"]
    job = {"job_id": f"JOB-{kind}-t{take}", "kind": kind, "take": take,
           "call_id": call_id, "status": "submitted", "rung": False}
    d["jobs"].append(job)
    _save(d)
    return job["job_id"]


def update(job_id, **fields):
    d = _load()
    for j in d["jobs"]:
        if j["job_id"] == job_id:
            j.update(fields)
    _save(d)


def all_jobs():
    return _load()["jobs"]


def approve_rerender(kind):
    d = _load()
    if kind not in d["approvals"]:
        d["approvals"].append(kind)
    _save(d)


def rerender_approved(kind):
    return kind in _load()["approvals"]


def done_passed_count():
    return len([j for j in _load()["jobs"]
                if j["status"] == "done" and j.get("qc") == "passed"])


def summary():
    return [(j["kind"], f"t{j['take']}", j["status"], j.get("qc", "-"))
            for j in _load()["jobs"]]
