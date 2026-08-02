# Rung 02 · Two doorbells, one door

**Adds:** `farm.py` — a SEPARATE PROCESS that renders and rings the **machine
doorbell** — and `approve`, the **human doorbell**. Both are the same thing:
`ring()` drives one `function_response` into the same durable session.

```bash
uv run python drive.py reset
uv run python drive.py start        # terminal 1: submit, park, exit
uv run python farm.py               # terminal 2: renders take 1 → QC FAILS → agent asks you
uv run python drive.py approve      # terminal 1: the human doorbell
uv run python farm.py               # terminal 2: take 2 → passes → TRAILER LOCKED
```

**The gate lives in the world:** the farm refuses to render `take > 1` without
an approval on file in the order book. The model may ask politely or may jump
the gun — the vendor does not start without a purchase order either way.
