author: Annie Wang (cuppibla)
summary: Build the Trigger layer of a long-running agent with Google's ADK — two doorbells (machine + human), a hand-written join over fanned-out long jobs, and the backstop that catches the failures nobody rings a bell for.
id: lab-production-floor
categories: ai,adk,agents,gemini
environments: Web
status: Draft
feedback link: https://github.com/cuppibla/loop-lab-production/issues

# The Production Floor: Who Presses Continue?

## Overview
Duration: 3:00

Your studio just greenlit *Tuesday, Again*. Tonight you are the producer on
duty, and the launch package needs four assets: a trailer, a poster, theme
music, and a localized cut of the trailer. Renders take minutes to hours.
QC takes a human. The localized cut can't even start until the trailer is
final.

An agent that *waits* for any of that is an agent that dies waiting. You may
already know the fix — a durable session that short-lived runs read and write
(that's [Lab 1: The Long-Running Agent](https://github.com/cuppibla/loop-lab-onboarding)).
But a durable session only makes waking up *possible*. This lab is about the
half nobody teaches: **who actually presses Continue?**

![The Production Floor — the six-rung climb](codelab-assets/roadmap-hero.png)

![Rung map: one long job → two doorbells → the join → the backstop → broadcast → cloud](codelab-assets/roadmap.png)

### What you'll build

A producer agent that:

- ✅ fans one request out into **several long-running jobs at once** — and holds
  all their pending calls in one durable session,
- ✅ gets woken by **two doorbells** — a render-farm callback and your own
  click — which turn out to be the *same* mechanism,
- ✅ closes a **hand-written join**: four jobs, finished out of order, counted
  in code (not in the model's imagination — you'll catch it lying),
- ✅ survives the failures that make **no sound at all**: a lost callback, and
  a crash that leaves the session waiting for a job that doesn't exist,
- ✅ and finally broadcasts the whole episode as a **typed event stream** that a
  real web app renders — graded by a robot attendee.

### Who this is for

Anyone who has built a basic ADK agent. Lab 1's Steps 2–4 (durable sessions,
pause/resume — ~30 min) are a *soft* prerequisite: this lab re-derives the
minimum in Rung 01, with skip lanes marked if you've been there.

Each rung lives in its own folder (`01_…` → `06_…`) and adds exactly one idea
— `diff` two neighbours to see the lesson.

> 📦 **All the code:** [github.com/cuppibla/loop-lab-production](https://github.com/cuppibla/loop-lab-production)

## The big idea: three doorbells
Duration: 5:00

A long-running agent's process is *dead* almost all of the time — that is the
design, not a failure. So every piece of progress starts with something
*outside* the agent waking it up. Sort every wake-up in every production
system you will ever build, and you get exactly three doorbells:

| Doorbell | Rung by | Examples | Latency |
|---|---|---|---|
| **Machine** | an external system finishing | render done, payment settled, CI green | seconds–hours |
| **Human** | a person deciding | approve, re-render, reject | minutes–days |
| **Clock** | nobody — that's the point | deadline passed, nightly sweep | whenever you schedule it |

The first two are *events*: something happened, and it rings you. The third
exists because **events get lost**. A callback network-blips into nothing. A
process dies between a side effect and its log line. No event will ever fire
for these — only a clock that goes *looking* can find them. The fast path
handles the 99%; **the clock is where your reliability comes from.**

The whole lab is these three doorbells aimed at two files:

```
        MACHINE                HUMAN                 CLOCK
    (farm callback)         (your click)         (the backstop)
          │                      │                     │
          ▼                      ▼                     ▼
    ┌─────────────────────────────────────────────────────┐
    │              drive(session, ...)                    │  ← one contract
    └──────────────────────────┬──────────────────────────┘
                    reads / appends events
    ┌──────────────────────────▼──────────────────────────┐
    │  floor.db          — THE SESSION (the agent's memory)│
    │  render_farm.json  — THE WORLD  (the farm's order    │
    │                       book: what really happened)    │
    └──────────────────────────────────────────────────────┘
```

Keep the two files apart in your head — most of rung 04 is what happens when
they disagree.

> aside positive
> **"Isn't a doorbell just a webhook?"** A webhook is *transport* — an HTTP
> request that arrives somewhere. A doorbell is the *resume semantic*: a
> `function_response` matched to a paused call in a durable session, waking a
> conversation that has no process. A webhook with nobody to wake is just an
> HTTP 200. In rung 05 you'll wire the transport; the semantic is what rungs
> 01–04 build.

And here is the punchline this whole lab builds toward: all three doorbells
converge on **one function**:

```python
drive(session, new_message=function_response(...))   # machine & human
drive(session, ...whatever the backstop decides...)  # clock
```

One durable session. One driver contract. What varies is only *who calls it*.

> aside positive
> **Where this sits in the bigger story.** Lab 1 taught the durable half:
> session, pause, crash-replay, idempotency — and its Step 7 built the
> *sweeper*, the wake-up for **crashed** runs. This lab owns the wake-ups for
> **cleanly waiting** runs: the doorbells. Two labs, two kinds of resume, one
> `drive()` contract between them.

## Setup
Duration: 5:00

👉💻 **Clone and set up** (same pattern as Lab 1):

```bash
git clone https://github.com/cuppibla/loop-lab-production.git
cd loop-lab-production
./setup_venv.sh                   # Windows: setup_venv.bat  — or: uv sync
source .venv/bin/activate
cp .env.example .env              # then put your Gemini API key in .env
```

Need a key? [aistudio.google.com/apikey](https://aistudio.google.com/apikey) —
free, no cloud project, ~1 minute. It starts with `AIza…`; treat it like a
password (`.env` is gitignored — keep it that way).

> ℹ️ **Two files are "the world" in every rung:** `floor.db` (the durable
> session — the agent's memory) and `render_farm.json` (the farm's order book
> — what was *really* submitted, rendered, approved). Keeping those two
> honest with each other is, in the end, the whole lab.

> ℹ️ ADK 2.5 prints a couple of harmless one-line `[EXPERIMENTAL]` warnings.
> Ignore them; expected outputs below omit them.

## Rung 01 · One long job
Duration: 5:00

📂 [`01_one_long_job/`](https://github.com/cuppibla/loop-lab-production/tree/main/01_one_long_job)

👉💻
```bash
cd 01_one_long_job
python drive.py reset
python drive.py start
```

**Expected output:**
```
[start] one long job
    -> submit_render({'kind': 'trailer', 'take': 1}) [PENDING]  id=o6297pl6
    <agent> Ready to roll. Starting the render for 'Tuesday, Again' now.
[drive] -> PAUSED   (the process you are in is about to exit)
```

The tool is a `LongRunningFunctionTool`: it returns `pending` and **the run
ends**. The process exits. Now look at what "a running render" actually is:

👉💻
```bash
python drive.py pending
```

```
[pending] 1 open long-running call(s) in the session:
    o6297pl6  submit_render({'kind': 'trailer', 'take': 1})
[world]   farm order book: [('trailer', 't1', 'submitted', '-')]
```

One open call in the session. One row in the order book. **That is the entire
system.** No process, no thread, no `await`.

### What just happened, mechanically

1. The model called `submit_render` — a `LongRunningFunctionTool`.
2. The tool ran for a millisecond: it wrote one row to the order book and
   returned `{"status": "pending", ...}`.
3. ADK logged the call, logged that interim `pending` result, and **ended the
   run cleanly**. (That interim response matters enormously in rung 04 —
   remember it exists.)
4. `drive.py` got control back and the process exited.

> aside positive
> **The return address.** Look at the tool's one interesting line:
> `jobs.submit(kind, take, call_id=tool_context.function_call_id)`. The tool
> stored *its own call id* into the order-book row. When the farm finishes —
> minutes or days later, in a different process — that stored id is how the
> result finds its way back to **this** conversation. Every callback system
> you will ever build has this "reply-to" header somewhere; here it is in
> nine characters.

And notice the trap we've built: nothing in this rung can ever *finish* the
job. The farm doesn't exist yet. Who rings the doorbell?

*(Lab 1 alumni: this was Steps 2–3 in a new costume. Skim ahead.)*

### What you learned

- A long-running call **parks** in the durable session and the run ends —
  "waiting" costs zero compute and survives any restart.
- The **return address**: the tool stores its own `function_call_id` next to
  the external job. That correlation is the whole callback architecture.

> aside positive
> **On your own agent:** take any tool of yours that waits on something slow —
> a batch API, an export, a human review — and convert it: return `pending`,
> and store `tool_context.function_call_id` alongside your external reference
> (order id, ticket id, operation name), somewhere durable. If you can't point
> at where that correlation lives, you don't have a long-running agent yet —
> you have a request that hasn't timed out.

## Rung 02 · Two doorbells, one door
Duration: 12:00

📂 [`02_two_doorbells/`](https://github.com/cuppibla/loop-lab-production/tree/main/02_two_doorbells)

This rung adds the farm — and it is a **separate process**. It never shares a
process with the agent. That's not an implementation detail; it *is* the
lesson: the outside world runs on its own clock.

👉💻 **Terminal 1 — submit and park:**
```bash
cd 02_two_doorbells
python drive.py reset
python drive.py start
```

👉💻 **Terminal 2 — run the farm:**
```bash
python farm.py
```

**Expected output (terminal 2):**
```
[farm] rendering JOB-trailer-t1 (8s)...
[farm]   JOB-trailer-t1 25%
...
[farm] JOB-trailer-t1 done, qc=failed — ringing the machine doorbell
    -> ask_human({'question': 'The trailer take 1 failed QC: "Act 3, the rain
       scene: visible noise in the low-light shots..." Should I proceed with a
       re-render?'}) [PENDING]  id=hlt2hi49
    <agent> Waiting for the producer's decision on the re-render.
[ring] submit_render(mecah2nv) -> PAUSED
[farm] nothing to do — clocking out
```

Read that carefully — three remarkable things happened:

1. The farm finished the render and **rang the machine doorbell**: it looked
   up the job's stored `call_id` and drove a `function_response` into the
   durable session. The agent woke up *inside the farm's process*.
2. The take failed QC, so the woken agent called `ask_human` — a *second*
   long-running call — and parked again. The farm, out of work, clocked out.
   **Nothing is running again.**
3. The `ring()` that the farm used is the same `ring()` you're about to use.

> aside positive
> **Whose process did the agent just run in?** The farm's. Read that again —
> the "agent" your terminal 1 started was woken up, reasoned, and called a
> tool *inside terminal 2's process*, because that's where `drive()` happened
> to be called. The agent has no home process. It materializes wherever
> someone drives its session, then vanishes. **The agent *is* the session.**
> Once this clicks, "deploy the agent" stops meaning "keep a process alive"
> and starts meaning "put the session somewhere every doorbell can reach."

👉💻 **Terminal 1 — you are the second doorbell:**
```bash
python drive.py approve
python farm.py        # one more shift for take 2
```

```
[approve] approval recorded in the order book (the farm's gate reads this)
[approve] answering: The trailer take 1 failed QC: ...
    -> submit_render({'take': 2, 'kind': 'trailer'}) [PENDING]  id=3407akgx
    <agent> Understood, take 2 is in progress.
...
[farm] JOB-trailer-t2 done, qc=passed — ringing the machine doorbell
    <agent> TRAILER LOCKED, take 2.
```

> aside positive
> **Two doorbells, one door.** A render farm finishing and a human clicking
> "approve" are, architecturally, the *same event*: a `function_response`
> driven into the same session. Only the latency differs. Everything you ever
> wire — webhooks, queues, review UIs — is one of these two, aimed at one
> `drive()`.

> aside negative
> **Where the gate lives.** `approve` wrote the approval into the **order
> book** first — and the farm *refuses* to render a take 2 that has no
> approval on file. Why not just trust the agent to wait? Because it won't,
> reliably: under load this model sometimes narrates an approval that never
> happened and submits take 2 on its own. The world-side gate makes that
> harmless — the job just sits there, unrendered, until a real human says so.
> **A gate is a code check, not a hopeful prompt.** (You'll watch the model
> try it in the next rung.)

The full arc, as captured — two terminals, four wake-ups, zero waiting
processes:

![Rung 02, the real session: submit, farm rings, you approve, farm rings again](codelab-assets/term-02-doorbells.png)

### What you learned

- Machine and human wake-ups are **the same mechanism**: one
  `function_response`, one `ring()`, one session. Only the latency differs.
- The agent **materializes wherever `drive()` is called** — it ran in the
  farm's process. The agent *is* the session.
- Approval gates live **in the world** (the store the executor checks), not
  in the prompt.

> aside positive
> **On your own agent:** inventory every wait in your flow and label its
> doorbell — machine or human. Then make both ring the *same* resume helper;
> if your webhook handler and your approval UI take different code paths into
> the agent, unify them now. And move every "requires approval" check into
> the system that *performs* the action — your DB, your payment layer, your
> deploy pipeline — never into model politeness.

## Rung 03 · The join
Duration: 12:00

📂 [`03_the_join/`](https://github.com/cuppibla/loop-lab-production/tree/main/03_the_join)

Real launches don't have one job. One request now fans out into **three
parallel long-running calls in a single model turn** — and a fourth, the
localized trailer, that must wait for the trailer to be final.

👉💻
```bash
cd 03_the_join
python drive.py reset
python drive.py start
```

```
[start] fan-out: one request, four long jobs
    -> submit_render({'kind': 'trailer', 'take': 1}) [PENDING]  id=whng0myq
    -> submit_render({'take': 1, 'kind': 'poster'}) [PENDING]  id=gkq7k4a3
    -> submit_render({'kind': 'music', 'take': 1}) [PENDING]  id=tylbet2d
    <agent> Starting the launch package for 'Tuesday, Again' now.
[drive] -> PAUSED
```

Three open calls, one session, no process. This is a different *kind* of
parallelism than the one agent frameworks usually mean:

| | `ParallelAgent` | This rung |
|---|---|---|
| What runs in parallel | model branches (reasoning) | **the outside world** (renders) |
| Where the fan-out lives | the agent graph, at build time | one model turn's N calls, at run time |
| What it costs while running | N live model contexts | zero — everything is parked |
| Who collects the results | the framework | **you, in the driver** |

Nothing about the agent's *reasoning* is parallel — it made three calls in
one breath and went to sleep. **What runs in parallel is the world.** And
that's why the framework can't join it for you: the framework can't see the
render farm. Here is the entire join, from `drive.py`:

```python
done = jobs.done_passed_count()                 # count the WORLD, not the chat
print(f"[join] {done}/4 assets passed QC")
if done == 4:
    print("[gate] driver-verified: all four in the world. ...")
```

👉💻 **Run the farm, then approve when asked, then one more farm shift:**
```bash
python farm.py            # poster (3s), music (5s), trailer (8s) — out of order
python drive.py approve
python farm.py            # take 2, then the unlocked localized trailer
```

The completions come back in duration order, not submission order, and each
doorbell run ends with the driver counting **the order book**:

```
[ring] submit_render(gkq7k4a3) -> ENDED
[join] 1/4 assets passed QC
...
    <agent> The localized trailer render is currently pending.The localized
            trailer has passed QC.

PACKAGE SHIPPED.
[ring] submit_render(obr0yf1p) -> PAUSED
[join] 3/4 assets passed QC          ← the driver disagrees
...
[ring] submit_render(tu6erntj) -> ENDED
[join] 4/4 assets passed QC
[gate] driver-verified: all four in the world. The model's 'PACKAGE SHIPPED'
       above is narration; THIS line is the check.
```

> aside negative
> **Look at the transcript above — the model announced "PACKAGE SHIPPED" at
> 3/4.** It saw a passing result, got ahead of the story, and declared
> victory with a render still on the farm. This is not a bug to be prompted
> away; it is what probabilistic narrators do. The join is four lines of code
> in `ring()` that count qc-passed rows in the order book. **The model
> narrates; the driver verifies.** That division of labor *is* this rung.

> aside positive
> **The dependency edge worked the other way, too:** the agent submitted
> `localized_trailer` only after the trailer's `qc='passed'` response arrived
> — a *data* dependency enforced at the only moment it can be: when the
> result actually exists.

Here is that exact moment, captured — victory declared at three, corrected by
the count:

![Rung 03, the real session: the model says PACKAGE SHIPPED at 3/4; the driver's join meter and gate line correct it](codelab-assets/term-03-join.png)

### What you learned

- One model turn can hold **several pending calls**; the world finishes them
  in its own order; nothing about this needs `ParallelAgent`.
- The **join is code**: count completions in the external store. Model
  narration is color commentary, not state.

> aside positive
> **On your own agent:** find every place you currently *believe* the model's
> summary of progress — "all subtasks complete", "email sent", "deploy done".
> Replace each with a driver-side count of the external system's records, and
> make that count the gate. When the model's claim and the count disagree,
> the count wins — and log the disagreement: it is the cheapest eval signal
> you will ever collect.

## Rung 04 · When no one rings
Duration: 15:00

📂 [`04_when_no_one_rings/`](https://github.com/cuppibla/loop-lab-production/tree/main/04_when_no_one_rings)

Everything so far assumed the doorbell *works*. Two failures make no sound at
all, and no event will ever fire for either:

### A. The lost bell

👉💻
```bash
cd 04_when_no_one_rings
python drive.py reset && python drive.py start
python farm.py --drop poster       # poster renders fine; its callback vanishes
```

The world says the poster is done. The session says it's waiting. Forever.
Nothing crashed; there is nothing to alert on.

👉💻
```bash
python backstop.py
```

```
[backstop] diffing 4 session call(s) against the order book
  2utbl1q9 -> answered. Healthy.
  4k0js3pd JOB-poster-t1 -> LOST BELL: world done, session waiting.
           Re-ringing with the stored result.
  pjveiq3y -> answered. Healthy.
  8jsm4j4a ask_human -> awaiting a human. Not my job (doorbell).
```

Note the last line: the backstop found a pending `ask_human` and **refused to
touch it** — a pause for a human belongs to the human doorbell. Lab 1's
Step 7 sweeper has the identical rule from the crash side. This discriminator
is a security boundary, not tidiness.

### B. The ghost

👉💻
```bash
python drive.py reset
CRASH_AFTER_SUBMITS=2 python drive.py start    # dies mid-fan-out
python drive.py resume
python drive.py pending
```

```
[pending] 3 long-running call(s) ever announced:
    yg5e9pzp  submit_render({'take': 1, 'kind': 'trailer'})
    y2fmh17t  submit_render({'kind': 'poster', 'take': 1})
    wsk2qzli  submit_render({'kind': 'music', 'take': 1})
[world]   [('trailer', 't1', 'submitted', '-'), ('poster', 't1', 'submitted', '-')]
```

Count them. The session holds **three** pending calls. The order book has
**two** jobs. On re-drive, announced long-running calls **replay as pending —
they do not re-run** (normal tools re-run; long-running tools are assumed to
be "waiting on the world"). The music submit's side effect died with the
process, so the session now waits for a job the farm never received. That
doorbell has *nothing on the other end*. This is the **ghost pending**, and
without a backstop it is a permanent, silent stall.

👉💻
```bash
python backstop.py
```

```
  f0cwo3rv JOB-trailer-t1 -> still rendering (crashed turn): answering with a
           fresh interim pending.
  dbmjl1ml JOB-poster-t1 -> still rendering (crashed turn): ...
  0qg0i6u3 submit_render({'take': 1, 'kind': 'music'}) -> GHOST (crashed
           turn): the farm never heard of it.
[backstop] answering the crashed turn as a set (3 responses in one message)
    -> submit_render({'kind': 'music', 'take': 1}) [PENDING]  id=jcg2jmw7
    <agent> Resubmitting the music render for take 1.
```

The ghost is answered `failed`, the agent resubmits, and the episode is back
on rails — finish it with `farm.py`, `approve`, `farm.py` as usual.

### The discriminator, exactly

The backstop tells the three cases apart by **counting responses per call**
in the session:

| Responses logged | Meaning | Backstop does |
|---|---|---|
| **0** | crashed turn — the interims died with the process | answer the **whole set** in one message |
| **1** | the interim only — clean path, still open | world says done+unrung → **re-ring**; otherwise healthy |
| **2+** | interim + final — answered | nothing |
| *(any, `ask_human`)* | a human's pause | **not my job** — the human doorbell owns it |

> aside negative
> **"Wait — Lab 1 said counting responses is a trap!"** It is, if you don't
> know what the counts mean. The trap is assuming *one response = answered*.
> The truth is *one response = the interim pending*, because a long-running
> tool's interim result is itself logged as a `function_response`. Count
> **knowingly** — 0 / 1 / 2+ each mean something precise — and the same
> mechanism that was a trap becomes your diagnostic.

> aside negative
> **Why "as a set" is load-bearing.** On the clean path, every long-running
> call's interim `{'status': 'pending'}` result is itself logged — that is
> what lets a later, *single* `function_response` complete the turn. A crash
> loses those interims. From then on, a lone answer can never complete the
> parallel turn again, and the model simply stays silent — no error, nothing.
> (We found this the hard way; it costs you nothing because `backstop.py`
> answers the whole crashed turn in one message: real results for what
> finished, `failed` for the ghost, fresh interims for what still renders.)

> aside positive
> **The backstop in one sentence:** a two-way diff between the session and
> the world, run by a clock. `session waiting + world done → re-ring` ·
> `session waiting + world never heard → ring failed` · `ask_human → not my
> job`. In production the clock is Cloud Scheduler or a Cloud Tasks deadline
> enqueued at submit time. **The deadline is the third doorbell.**

The ghost hunt, as captured — three waited for, two existed, one exorcised:

![Rung 04, the real session: crash mid-fan-out, resume replays three pendings, the world has two jobs, the backstop answers the crashed turn as a set](codelab-assets/term-04-ghost.png)

### What you learned

- Two failures make **no sound**: a lost callback, and a ghost pending. No
  event will ever fire for either; only a clock that goes looking finds them.
- Crash recovery **replays long-running calls as pending** — it does not
  re-run them. That is where ghosts come from.
- A crashed **parallel** turn can only be revived by answering the whole set
  in one message.

> aside positive
> **On your own agent:** schedule a reconciler. It (a) lists the session's
> open calls, (b) lists the external system's records, (c) answers *both*
> mismatch directions — re-ring what the world finished, fail what the world
> never received — and (d) leaves human pauses alone. Enqueue a deadline the
> moment you submit anything. If your agent has run for a week and this job
> has never once found a mismatch, check that it's actually running.

## Rung 05 · Broadcast — light up the room
Duration: 12:00

📂 [`05_broadcast/`](https://github.com/cuppibla/loop-lab-production/tree/main/05_broadcast)

Your terminal has been reading print statements. A real operation reads a
**typed event stream** — and the VibeFlix Studios app has a whole
Netflix-style "Production Floor" room that renders exactly this episode:
job cards filling, a join meter, the agent chip flipping to OFFLINE, a pause
card whose button is your `approve`.

`server_shell/` packages rungs 02–04 as one FastAPI service: SSE `/events`
out, `/actions` in. The agent, the farm, the doorbells are all given — what's
gutted is the **bridge**: three `TODO(HOOK n)` sites where ADK events become
contract events.

👉💻 **Terminal 1:**
```bash
cd 05_broadcast/server_shell
python server.py
```

👉💻 **Terminal 2 — the robot attendee:**
```bash
python scripts/check.py        # from the repo root
```

`check.py` restarts the episode, watches the stream, **answers the human
doorbell itself** when `awaiting_action` arrives, and grades the run:

```
  ✅ 4+ jobs submitted
  ✅ paused for a human (with call_id)
  ✅ awaiting_action emitted
  ✅ action_received after reply
  ✅ join reached 4/4
  ✅ package_ready
  ✅ gate_check ok
  ✅ room_complete

[check] PASS — the room would render this run.
```

It will say ❌ until your hooks are real — you cannot fake an event stream
with print statements. Implement the three hooks (each is a few lines; the
comments tell you the exact event shapes), re-run, iterate.

> aside positive
> **The hook everyone forgets is `awaiting_action`.** Emitting the pause card
> is not enough — the contract has an explicit *wait signal*, and the room's
> button stays disabled without it. An event contract is an interface: the
> renderer knows nothing about your agent, and that is the point. One log,
> two audiences — your terminal and a set dressed like Netflix.

The contract, in one table — every event your hooks must produce:

| Event | Emitted when | The room renders it as |
|---|---|---|
| `job_submitted` + `world_patch` | a submit call is bridged (HOOK 1) | a job card appearing on the board |
| `job_progress` | the farm ticks (given) | the card's progress bar |
| `job_paused_need_human` + `awaiting_action` | an ask_human call is bridged (HOOK 2) | the pause card — and its **enabled** button |
| `job_completed` + `join_progress` | a qc-passed doorbell (HOOK 3) | the card flipping to done; the join meter |
| `package_ready` → `gate_check` → `room_complete` | the driver verifies 4/4 (given) | the finale |

> aside positive
> **Why a replay can stand in for you.** The VibeFlix room was built against a
> hand-written *replay* of this exact contract, long before this backend
> existed — and the frontend cannot tell the difference. That symmetry is the
> whole trick: the contract is the interface, so a recorded stream is a
> perfect stunt double for a live agent. (On stage, that's your demo
> insurance; in tests, it's your fixture.)

`solutions/` is byte-for-byte the live backend the VibeFlix app runs. If you
have the app, point `ROOM2_AGENT_URL` at your server and watch your own run
play as television. This is what your event stream looks like on the set —
every frame below is a real episode driven by this exact backend:

**The fan-out — HOOK 1's payoff.** Job cards appear the moment your bridge
emits `job_submitted`; the localized trailer sits grey on the board, waiting
on its dependency:

![Act 1: three cards rendering with progress bars, localized trailer greyed out, join meter live](codelab-assets/ui-fanout.png)

**The wait — the room goes dark.** The agent chip flips to OFFLINE, the feed
prints *"producer agent has left the floor"*, the WORLD RECORD panel shows
the one row that exists (`PENDING · awaiting human`), and the pause card's
button is live because your HOOK 2 emitted `awaiting_action`:

![The dark room: OFFLINE agent, join 2/4, the world record row, and the enabled Re-render button](codelab-assets/ui-darkroom.png)

**The finale — your join on television.** Take 1 rejected and take 2 final
side by side, the join meter at 4/4, gate PASSED — and the consumer page
playing the assets your run shipped:

![Shipped: all four assets done, join 4/4, the package live on the consumer page](codelab-assets/ui-shipped.png)

### What you learned

- A typed event contract is an **interface**: the same stream feeds your
  terminal, a robot grader, and a Netflix-dressed set — none of them know
  what's behind it.
- The wait signal (`awaiting_action`) is part of the contract — UIs need to
  know *that* you're waiting, not just *why*.

> aside positive
> **On your own agent:** define an event schema for your loop's moments —
> submitted, progress, paused-for-human, resumed, completed, verified. Emit
> them **from the driver** (never from model text), and write one CI check
> that replays a full episode against a stub world and asserts the stream,
> answering its own doorbells like `check.py` does. That one check regresses
> your entire Trigger layer.

## Rung 06 · To the cloud
Duration: 5:00

📂 [`06_cloud/`](https://github.com/cuppibla/loop-lab-production/tree/main/06_cloud)

A guided runbook, not a script — four swaps and nothing about the agent
changes:

1. **Session store** → Cloud SQL (`postgresql+asyncpg://…` — the async-driver
   rule from Lab 1).
2. **Server** → Cloud Run; your doorbell endpoints become real URLs.
3. **Farm** → real **Veo**: `generate_videos` with
   `webhook_config(uris=…, user_metadata={"call_id": …})` — the completion
   webhook carries your correlation id — and `pubsub_topic` for progress. If
   your surface only offers polling, build the doorbell out of a poller;
   rung 02's pattern, unchanged.
4. **Backstop** → Cloud Scheduler / Cloud Tasks. The deadline is enqueued the
   moment the job is submitted.

> ‼️ Veo renders and Cloud SQL bill real money. Rung 02's idempotent submit is
> not optional there — and tear everything down when you finish.

## Recap
Duration: 3:00

| Rung | The idea | The line to remember |
|---|---|---|
| 01 | one long job | "a running render" is two rows and no process |
| 02 | two doorbells | machine and human are the same `function_response` |
| 03 | the join | the model narrates; the driver counts the world |
| 04 | the backstop | a two-way session↔world diff; the deadline is the third doorbell |
| 05 | broadcast | an event contract is an interface; a robot can grade it |
| 06 | cloud | four swaps, zero agent changes |

Every wake-up in every system you will ever ship is a machine event, a human
event, or a clock. The first two are your fast path. The clock is your
reliability. And all three converge on one boring, durable function:

**`drive(session, …)` — what changes is who calls it, never what it is.**

### Take it home: seven checks for any long-running agent

Point these at an agent you already have — each one is an afternoon, and each
maps to a rung you just climbed:

1. **Name every wait.** List each place your agent waits on the world; label
   its doorbell — machine, human, or clock. Unlabeled waits are where it will
   silently die. *(big idea)*
2. **Find the return address.** Where is the call-id ↔ external-job
   correlation stored? It must be durable and live next to the job. *(01)*
3. **One resume path.** Webhook handler, approval UI, retry script — all of
   them should converge on one `drive()`-shaped helper. *(02)*
4. **Move the gates into the world.** Every "needs approval" must be enforced
   by the system that performs the action, not by model patience. *(02)*
5. **Count, don't believe.** Progress and joins come from driver-side counts
   of external records; the model's "all done!" is narration. *(03)*
6. **Reconcile on a clock.** A scheduled two-way diff between session and
   world, answering both mismatch directions, batching crashed parallel
   turns, skipping human pauses — with a deadline enqueued at submit time. *(04)*
7. **Type your events.** Emit a contract stream from the driver and let a
   robot grade one full episode in CI. *(05)*

If all seven hold, your agent doesn't just *survive* time — it runs on it.

### Where to go next

- **Lab 1 · The Long-Running Agent** — the durable substrate under this lab,
  plus the *fourth* wake-up this lab skipped: the sweeper that re-drives
  crashed runs (Step 7). Two labs, two kinds of resume.
- **The eval labs** — once your agent runs for days unattended, "is it any
  good?" stops being a vibe and becomes a gate.

### Resources

- This repo: [github.com/cuppibla/loop-lab-production](https://github.com/cuppibla/loop-lab-production)
- Lab 1: [github.com/cuppibla/loop-lab-onboarding](https://github.com/cuppibla/loop-lab-onboarding)
- ADK docs: [adk.dev](https://adk.dev) · Gemini key: [aistudio.google.com/apikey](https://aistudio.google.com/apikey)
