# Sprint 27 in plain English 🗣️

**Component:** `OnAIR-Security` · **Sprint:** 27 · **Written:** 2026-08-14 · **Updated:** 2026-08-19

A non-technical companion to [`SPRINT_27_PLAN.md`](SPRINT_27_PLAN.md). Six completed pieces
of work, no jargon, plus what we found afterwards — which turned out to matter more than the
sprint's original plan. Companion doc for the previous sprint:
[`SPRINT_26_PLAIN_ENGLISH.md`](SPRINT_26_PLAIN_ENGLISH.md).

**The short version:** the thing we set out to do returned a null result. Then, checking our
own work, we discovered our test data had been collected in a way that made most of it
unusable — for months — and fixing that changed several things we thought we knew.

---

## 1. `signal-feasibility` — "Would extra data help the AI name attacks better?"

**Why we did it.** Our system does two jobs: spot that *something* is wrong, then say *what
kind* of attack it is. It's good at spotting and weaker at naming. We'd been recording 109
extra streams of spacecraft data that the AI was never taught to use. Would feeding it that
data help?

**What we did.** Ran 17 simulated attacks, collected the data, then trained the AI twice —
with and without the extra streams — and measured the difference.

**What we found.** No real improvement. One group of streams looked promising, but when we
re-ran the test slicing the data differently, the "gain" **flipped to a loss**. It was luck of
the slicing, not a genuine effect.

**Bottom line.** Don't retrain — it wouldn't help. The more useful discovery was *why we
couldn't tell*: we only ran each attack once, and single measurements wobble too much to
detect a small improvement. **The obstacle isn't the AI, it's not having enough data to
measure with.**

*Housekeeping note: this work was originally logged against a ticket that already belonged to
different work. It has been split onto its own ticket so the results can't be confused with
the older ones.*

---

## 2. AINOS3-77 — "Closing a blind spot an attacker could hide in"

**Why we did it.** The spacecraft has four flight modes. Our detector learns what "normal"
looks like *per mode*, so whenever the mode changes it pauses and re-learns for about 45
seconds. **An attacker who forces a mode change gets a free 45-second window where the
detector is switched off** — and forcing a mode change is itself a known attack.

**What we did.** Added a rule that ignores the AI and just watches the mode setting. If it
changes, raise an alert.

**What we found.** Two surprises. The obvious approach — watching the "commands received"
counter — doesn't work, because that counter ticks constantly during routine health checks.
And the mode reading briefly *flickers* during a switch, which would have caused 22 false
alerts for 4 real changes; we fixed that by requiring the new value to hold steady before
believing it.

We also added a second rule for the nastier version of this attack: **an attacker who keeps
flipping modes** every 40 seconds can hold the detector off indefinitely. That's now caught
in about two minutes.

**Bottom line.** Both rules are live and verified on the running spacecraft. When we forced a
mode change, the new rule caught it and **the main AI detector saw nothing at all** — the
blind spot proven and closed in the same test.

---

## 3. AINOS3-80 — "Checking whether we've been flattering ourselves"

**Why we did it.** There's a classic way to fool yourself: test your system on the same data
you built it from. It's like marking your own exam with the answer sheet in front of you. We'd
been caught by this before — a headline figure of 77% turned out to be 42% when measured
honestly — so we checked every other published number.

**What we did.** Audited all 18 headline figures, traced each back to the file that produced
it, and labelled it with how it was measured.

**What we found.** Most hold up. Two real problems:

- **Our documentation claimed the alarm sensitivity was tuned on fresh data.** It wasn't — it
  was tuned on the exact data the detector learned from. We proved it: the row counts match
  precisely in all four flight modes.
- **We never wrote down what data the detector was trained on.** So several published claims
  **can't be checked by anyone, including us.**

**Bottom line.** Every number now carries a label saying how it was measured, and an
unlabelled number counts as a bug. We also learned a subtler lesson: it's not enough for the
*number* to be honest — the **margin of error** has to be honest too, and ours had been
calculated the wrong way.

---

## 4. AINOS3-81 — "Does it get twitchy if you leave it running?"

**Why we did it.** An older version had an ugly habit: leave it running 4–6 hours and it would
start crying wolf. We believed that was fixed but had never tested the current version over a
long stretch.

**What we did.** Ran the simulation for **7 hours doing nothing suspicious**. Every alarm in
that window is by definition a false alarm.

**What we found.**

- **The good:** no degradation at all. The detector's confidence actually *improved* over
  time. The old problem is genuinely fixed.
- **The bad:** one flight mode (INERTIAL) is far noisier than documented. We publish "0.00%
  false alarms". Later measurement put it at **33.6%** — roughly one false alert a minute in
  that mode.

**Bottom line.** The drift worry is closed for good. But INERTIAL is a real, unfixed defect —
now its own ticket, and the number has grown every time we've measured it (0.00% → 7.5% →
33.6%).

---

## 5. AINOS3-82 — "How do we compare to the published competition?"

**Why we did it.** A university group published a dataset and detector built on the *same*
spacecraft simulator, reporting near-perfect results. Ours are more modest. We wanted to
understand the gap honestly.

**What we did.** Read their paper, downloaded their data, and re-ran their problem ourselves.

**What we found.** Their data has a flaw that makes near-perfect scores meaningless: **each
attack type was recorded in one single sitting**, so a computer can identify the attack by
recognising *that recording session* rather than the attack. We proved it three ways — the
clock alone identifies the attack 88% of the time, the computer's memory usage alone gets it
100% right, and five individual columns each score above 95% on their own.

**Bottom line.** Our lower numbers aren't a sign we're behind — we're measuring a much harder
problem far more strictly. **And there's one genuinely valuable idea to borrow:** they easily
catch an attack we're blind to, purely because they watch from a different vantage point.

---

## 6. AINOS3-78 — "Why did the upgrade make one thing worse?"

**Why we did it.** Last sprint's classifier upgrade improved attack-naming overall but made
one group of three near-identical attacks *worse*. We wanted to know whether that was fixable
or a trade worth accepting.

**What we did.** Compared the old and new versions attack-by-attack and mode-by-mode.

**What we found.** The whole loss is in **one flight mode** (INERTIAL again). The suspected
cause — "not enough training examples" — is **wrong**: that mode has more examples than the
ones performing well. The real cause is subtler: those three attacks are so similar to each
other that the AI needs every scrap of evidence to tell them apart, and **specialising the
model to one flight mode throws away the pooled evidence** that was carrying them.

**Bottom line.** There's a cheap fix: specialise only the *other* mode. That recovers almost
the entire loss at a cost of 0.23% overall accuracy — because the upgrade's value was almost
entirely in that other mode anyway. Recommended, not yet deployed.

---

## What we found afterwards — the part that mattered most

None of this was planned. It came out of checking the sprint's own results.

### Our test data had been collected in a way that made most of it unusable

The detector deliberately goes quiet for 45 seconds after each mode change. Our test data
switched modes **every 60 seconds**. Those two designs were set independently, and together
they meant **83% of our attack recordings were taken while the detector was switched off.**

Worse, the reason we cycled modes so quickly was a belief that the spacecraft wouldn't *stay*
in a mode. We tested it: commanded one mode, left it alone for an hour, and it **never
budged** — 17,670 readings, zero drift. The belief was wrong, and our own notes had already
traced it to a data-reading bug years earlier. Nobody revisited the tooling built on it.

**Fixing the collection method took usable data from 17% to 84%.**

### That let us measure things honestly for the first time — with mixed results

- **One attack is caught superbly** (a propulsion attack — the detector flags ~80% of it
  against ~1% false alarms).
- **One attack is caught by nothing at all** — an electrical-power switch toggle, published at
  a 99% catch rate, detected by neither the AI nor any rule. That's now a ticket.
- **Two attacks are caught by the simple rules, not the AI** — which is by design, but our
  documentation had been crediting the AI for them.

### We nearly shipped a change that would have gutted the detector

We noticed all the false alarms happen in a 2-minute window each orbit, when the spacecraft
turns to face the sun. Clean pattern, tidy explanation. We proposed suppressing alarms in that
window — and then checked it against attack data first. **It would have destroyed 67% of our
attack detection**, because that same window is where the detector does most of its real work.
No such rule was built.

### And we withdrew a change we'd already recommended

Earlier in the sprint we proposed a sensitivity adjustment that looked like it would nearly
double detection. Re-tested on the corrected data, it delivers **zero improvement at 2.6× the
false alarms.** The original benefit was an illusion created by the bad test data. Withdrawn.

---

## The sprint in one paragraph

The headline bet — that recording more data would improve attack naming — **failed**, and
failed in a way that told us the real obstacle is not having enough recorded runs to measure
with. The unglamorous half, checking our own work, is where the value was: it found that our
alarm sensitivity was tuned incorrectly, that one flight mode is far noisier than published,
that we never recorded what our detector was trained on, that the leading published competitor's
numbers don't survive scrutiny, and — most consequentially — that **our test data had been
collected in a way that made most of it unusable for months.** Along the way we withdrew one
recommendation and abandoned another before shipping, both because a check we ran at the last
moment showed they'd have made things worse. Eight separate times this sprint, a measurement
turned out to only be capable of giving one answer. **Every one was caught before it reached
anyone outside the team** — several because someone asked an awkward question rather than
because the process caught it automatically. That is the honest summary: the work found real
problems, including in itself.
