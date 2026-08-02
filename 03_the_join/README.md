# Rung 03 · The join

**Adds:** fan-out (three parallel long-running calls in ONE model turn, a
fourth gated on a dependency) and THE JOIN — four lines in `ring()` that count
qc-passed jobs **in the order book**, not in the chat.

```bash
uv run python drive.py reset
uv run python drive.py start        # 3 parallel pending calls, run ends
uv run python farm.py               # completions land out of order; trailer fails QC
uv run python drive.py approve
uv run python farm.py               # take 2 → dependency unlocks → localized → 4/4
```

Watch for the model announcing **PACKAGE SHIPPED at 3/4** — and the driver's
join meter correcting it. The model narrates; the driver verifies. That's why
the join is yours to write.
