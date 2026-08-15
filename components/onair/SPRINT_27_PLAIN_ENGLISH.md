# Sprint 27 in plain English 🗣️

**Component:** `OnAIR-Security` · **Sprint:** 27 · **Written:** 2026-08-14

A non-technical companion to [`SPRINT_27_PLAN.md`](SPRINT_27_PLAN.md). Same five completed
tickets, no jargon. For the numbers, methods and provenance, see the per-ticket writeups
linked from the sprint plan.

---

## 1. AINOS3-30 — "Would extra data help the AI name attacks better?"

**Why we did it.** Our system does two jobs: spot that *something* is wrong, then say *what
kind* of attack it is. It's good at spotting (93%) and bad at naming (42%). Months ago we
started recording 109 extra streams of spacecraft data — sensor readings, file-system
activity, radio counters — but the AI was never actually taught to use them. The question:
if we fed it that extra data, would the naming get better? We wanted to know *before*
spending weeks retraining.

**What we did.** Ran 17 different simulated attacks against the spacecraft over about
3 hours, choosing attacks the AI is currently worst at, plus a few it's good at for
comparison. Then we trained the AI twice — once without the extra data, once with — and
measured the difference. We split the 109 new streams into five groups so that if something
helped, we'd know which part.

**What we found.** No real improvement. One group looked promising at first (a small gain),
but when we re-ran the test slicing the data at five different points, the "gain" **flipped
to a loss** in two of them. In other words, the apparent improvement was just luck of how we
happened to cut the data, not a genuine effect.

**Bottom line.** Don't retrain — it wouldn't help. But the more useful discovery was *why we
couldn't tell*: we only ran each attack once. With a single recording per attack, the
measurements wobble too much to detect a small improvement. Before asking this question
again, we need a second round of recordings. **The obstacle isn't the AI, it's not having
enough data to measure with.**

---

## 2. AINOS3-77 — "Closing a blind spot an attacker could hide in"

**Why we did it.** The spacecraft has four flight modes (different ways of pointing and
stabilising itself). Our main detector learns what "normal" looks like *per mode* — so
whenever the mode changes, it has to pause and re-learn for about 45 seconds. We noticed the
problem: **an attacker who forces a mode change gets a free 45-second window where the
detector is switched off.** Worse, forcing a mode change is itself a known attack technique.

**What we did.** Added a simple rule that ignores the AI entirely and just watches the mode
setting. If it changes, raise an alert. No cleverness required — a mode changing on its own
is inherently suspicious, and whether a given change was legitimate is a judgement for the
operator.

**What we found.** Two surprises while building it. First, the obvious approach — watching
the spacecraft's "commands received" counter — doesn't work, because that counter ticks
constantly during routine health checks (264,000 times in 7 hours). Second, the mode reading
briefly *flickers* back and forth between old and new values during a switch, which would
have caused 22 false alerts for 4 real changes. We fixed that by requiring the new value to
hold steady for 5 readings before believing it.

**Bottom line.** It works and it's live. Tested against 7 hours of recorded data: 4 alerts
for 4 real mode changes, zero false alarms. Then tested for real on the running spacecraft —
we forced a mode change, the new rule caught it, **and the main AI detector saw absolutely
nothing** across the whole event. That's the blind spot proven and closed in the same test.

---

## 3. AINOS3-80 — "Checking whether we've been flattering ourselves"

**Why we did it.** There's a classic way to fool yourself in this field: test your system on
the same data you built it from. It's like marking your own exam with the answer sheet in
front of you — the score looks great and means nothing. We got caught by exactly this
recently: a headline accuracy figure of 77% turned out to be 42% when measured honestly. So
we went through every other published number looking for the same mistake.

**What we did.** Audited all 18 headline figures in our stakeholder documentation, traced
each one back to the file that produced it, and tagged it with how it was measured.

**What we found.** Most numbers hold up. But two real problems:

- **Our documentation claimed the alarm sensitivity was tuned using fresh, unseen data.** It
  wasn't — it was tuned on the exact same data the detector learned from. We proved it: the
  row counts match precisely in all four flight modes. That's not a coincidence, it's the
  same data.
- **We never wrote down what data the detector was trained on.** No list, no dates, nothing.
  This means several of our published claims **can't be checked by anyone, including us.**
  They're not necessarily wrong — but "trust us" isn't good enough for a security system.

**Bottom line.** Every number now carries a label saying how it was measured, and there's a
rule that an unlabelled number counts as a bug. We also added a subtler lesson learned from
item 1 above: it's not enough for the *number* to be honest — the **margin of error** has to
be honest too, and ours had been calculated the wrong way.

---

## 4. AINOS3-81 — "Does it get twitchy if you leave it running?"

**Why we did it.** An older version of this system had an ugly habit: leave it running for
4–6 hours and it would start raising false alarms constantly. We believed the current version
fixed that, but the newest component had only been live for two weeks and had never been left
running for a long stretch. A security system that cries wolf gets ignored — so this matters.

**What we did.** Started the spacecraft simulation fresh and ran it for **7 hours doing
nothing suspicious at all**. Every single alarm in that window is by definition a false
alarm. We deliberately scheduled things so the longest stretch covered the 4–6 hour window
where the old version used to fall apart.

**What we found.** Two things, one good and one not.

- **The good:** no degradation whatsoever. In fact the detector's confidence *improved* over
  time rather than drifting toward the panic threshold. The old problem is genuinely fixed.
  The supporting detectors raised zero false alarms across 141,000 readings, and the AI never
  once mislabelled normal flight as an attack.
- **The not-good:** one of the four flight modes (INERTIAL) is far noisier than our
  documentation claims. We publish "0.00% false alarms" for it. The real figure is **0.54%**,
  which translates to about **71 false alerts per hour** — against a public promise of *fewer
  than one alert every five hours*.

**Bottom line.** The drift worry is closed for good. But we found a real defect, and it
traces directly back to the audit above: because the alarm threshold was tuned on its own
training data, it's badly set for that one mode. Fixing the tuning problem should fix this
too.

---

## 5. AINOS3-82 — "How do we compare to the published competition?"

**Why we did it.** A university group published a dataset and detector built on the *same*
spacecraft simulator we use — the closest thing to a direct competitor that exists. Their
work reports near-perfect attack detection. Ours reports far more modest numbers. We wanted
to understand the gap honestly, rather than assume we're behind.

**What we did.** Read their paper, downloaded their public dataset, verified it was intact,
and re-ran their problem using our own methods.

**What we found.** Their published data has a structural flaw that makes near-perfect scores
meaningless. **Each type of attack was recorded in one single sitting.** So the computer
doesn't have to learn what the attack looks like — it can just learn what *that afternoon*
looked like. We proved it three ways: the clock alone identifies the attack type 88% of the
time; the computer's memory usage alone gets it 100% right; and five individual columns each
score above 95% on their own. Their own documentation warns against a related problem, but
their suggested fix doesn't address it, because the flaw is baked into how the data was
collected.

We also can't compare scores directly at all: they watch commands going *up* to the
spacecraft, we watch what the spacecraft *does* in response. Almost no overlap.

**Bottom line.** Our lower numbers aren't a sign we're behind — we're measuring a much harder
problem far more strictly. This is strong outside validation of the discipline we've been
enforcing on ourselves. **And there's one genuinely valuable idea to steal:** they easily
catch an attack that we're completely blind to, purely because they're watching from a
different vantage point. That's the best evidence yet that our real limitation is *where
we're looking*, not how clever our AI is.

---

## The sprint in one paragraph

The headline bet — that recording more data would improve attack naming — **failed**, and
failed in a way that tells us the real obstacle is not having enough recorded runs to measure
with. The unglamorous half of the sprint, checking our own work, turned out to be where the
value was: it found that our alarm sensitivity was tuned incorrectly, that one flight mode is
raising 71 false alerts an hour against a documented zero, that we never recorded what our
detector was trained on, and that the leading published competitor's impressive numbers don't
survive scrutiny. **Four real defects, none of which were on the plan.** One fix — retuning
the alarm threshold properly and writing down the training data — addresses the first three
at once.
