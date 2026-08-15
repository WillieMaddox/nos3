# Sprint 26 in plain English 🗣️

**Component:** `OnAIR-Security` · **Sprint:** 26 · **Written:** 2026-08-14

A non-technical companion to [`SPRINT_26_PLAN.md`](SPRINT_26_PLAN.md). Eight completed
tickets, no jargon. Companion doc for the following sprint:
[`SPRINT_27_PLAIN_ENGLISH.md`](SPRINT_27_PLAIN_ENGLISH.md).

**The sprint in one line:** we taught the system to see five new kinds of attack it had been
blind to, and shipped an upgrade that made attack-naming more accurate in the two modes where
naming was already working.

---

## 1. AINOS3-70 — "Start recording the data we weren't listening to"

**Why we did it.** The spacecraft broadcasts status reports from dozens of internal programs
— the file manager, the radio, the safety monitor, the sensors. Our monitor was only
listening to a fraction of them. Any attack whose only visible trace was in an unmonitored
report was invisible to us by construction, no matter how good the AI was.

**What we did.** Subscribed to **16 additional data streams** and raised the internal limit on
how many the monitor can listen to at once (32 → 48). The recorded data grew from roughly 250
columns to 383.

**What we found.** Straightforward plumbing job, and it unblocked everything else in the
sprint — every detection ticket below reads a field this pass added.

**Bottom line.** Important to be clear about scope: this only **records** the new data. It
doesn't make the AI use it. Turning recordings into actual detection was the rest of the
sprint's work, and the question of whether the AI could benefit from them was still open a
sprint later (Sprint 27 answered it: no, not measurably).

*Footnote: two of the sixteen were pointed at the wrong program — an idle stand-in rather
than the real one. Caught and corrected in AINOS3-72 below.*

---

## 2. AINOS3-71 — "Catching ransomware and data-wiping"

**Why we did it.** Two of the nastiest things an attacker can do to a spacecraft are destroy
its stored files (a wiper) or encrypt them and hold them hostage (ransomware). We had no way
to see either.

**What we did.** Wrote realistic simulated versions of both attacks and ran them against the
live spacecraft to find out what they actually look like in telemetry — then built a detector
around the trace they leave.

**What we found.** Our initial theory was wrong. We assumed we'd spot it by watching the
*data-storage* counter — but that counter climbs constantly during normal operations, so
building on it would have produced endless false alarms. The reliable signal turned out to be
the **file manager's command counter**, which sits at exactly zero in normal flight and jumps
to 24 during a wipe and 71 during ransomware. A number that's normally frozen at zero is a
much better alarm than one that's always moving.

**Bottom line.** Detector built and verified live. It can't tell wiper from ransomware — both
look like "a burst of file operations" — so it reports the category and the specific commands
tell you which. That's an honest limit, not a defect.

---

## 3. AINOS3-72 — "Catching someone stealing our downlink"

**Why we did it.** An attacker who redirects the spacecraft's radio downlink can quietly copy
mission data to their own ground station. We wanted to catch that.

**What we did.** Investigated where the real radio link is controlled, then built detectors on
it.

**What we found.** The ticket's assumption was **wrong twice over**, and fixing that was most
of the work. We had been monitoring a *stand-in* version of the radio program — a
development placeholder that sits idle and never reports anything. It had also been sending
us nothing at all for weeks without anyone noticing. The spacecraft actually runs a **second,
full version** of that program, and that's the one that owns the real ground link and knows
which downlink routes are switched on.

**Bottom line.** Repointed the monitor at the real program — a configuration change, no
flight-software rebuild needed. Then built two detectors: one watching for commands to the
radio program, one watching for changes to the downlink routing. Both verified live. A useful
side effect: this also gave us our first real visibility into the command-*ingest* path.

*The general lesson, worth remembering: a data stream that reports nothing looks identical to
a data stream reporting "all quiet." We had been reassured by silence.*

---

## 4. AINOS3-73 — "Catching someone switching off the safety monitors"

**Why we did it.** Spacecraft carry watchdogs that check whether values are in safe ranges. A
sophisticated attacker disables those first, so their later actions don't trip anything. We
wanted that covered.

**What we did.** Ran the attack and checked what it looks like.

**What we found.** **No new detector was needed.** Switching off the safety monitors produces
exactly the same trace as two attacks we already caught — the safety monitor's status changes
from ACTIVE to DISABLED, and that's it. All three attacks are indistinguishable from each
other in telemetry.

**Bottom line.** Free coverage. We report it as "someone disabled fault management" rather
than pretending to identify which of the three specific techniques it was — because the data
genuinely cannot tell them apart. Also fixed two bugs in the attack scripts found along the
way.

---

## 5. AINOS3-74 — "Is there a watchdog timer to attack?"

**Why we did it.** Two known attack techniques target a spacecraft's watchdog timer — the
component that reboots things when they hang. We needed to know whether ours was exposed.

**What we did.** Went looking for the watchdog and any status it reports.

**What we found.** **There isn't one.** In this simulator the watchdog is an empty
placeholder that does nothing, there's no health-monitoring program running, and the one thing
named "WDT" turned out to be an unrelated configuration table with a confusingly similar
acronym.

**Bottom line.** Both techniques marked out-of-scope — you cannot attack, or defend, a
component that doesn't exist. A two-hour check that correctly closed two tickets without
building anything. Worth noting the *reason*, though: it's out of scope because of a
simulator limitation, not because real spacecraft are safe from it.

---

## 6. AINOS3-75 — "Three maybes, resolved"

**Why we did it.** Three attack techniques were sitting in an "unclear" pile — nobody had
determined whether we could detect them or not. Unresolved items like this quietly
misrepresent your coverage.

**What we did.** Checked each one properly.

**What we found.** One is **detectable** (modifying the approved-command whitelist — it shows
up as command activity we already watch). One is **out of scope** (replaying internal bus
traffic — there's no way for an attacker to inject onto that internal bus from outside). One
is **not applicable** (exploiting firmware design flaws — our simulator models behaviour, not
the chip-level layer that technique targets).

**Bottom line.** The "unclear" pile is now empty. Every one of the 177 attack techniques in
the catalogue has a definite status. That matters more than it sounds — it's the difference
between "we don't know our coverage" and "we know exactly what we do and don't cover."

---

## 7. AINOS3-39 — "Is the AI cheating?"

**Why we did it.** A worry had been building: our attack-naming AI leaned heavily on generic
"how busy is the spacecraft" counters. That's a classic shortcut — it can look like the model
understands attacks when really it's just noticing activity. If so, it would fall apart on any
attack that isn't noisy.

**What we did.** Two-part audit — inspected which measurements the model actually relies on,
then retrained with the suspect ones removed to see what breaks.

**What we found.** **It's a mix, not a uniform cheat**, and the nuance matters:

- **Genuine** in many cases — when the attack's actual target *is* the spacecraft's core
  computer, watching core-computer counters isn't a shortcut, it's the correct signal.
- **A fragile shortcut** for a few attacks defined by their *outcome* rather than their
  mechanism (e.g. "deception"), which have no dedicated telemetry of their own. Remove the
  activity counters and those collapse to zero — but that's an information limit, not a bug.
- **Actively harmful** in a handful of cases, which was the surprise. For some attacks the
  generic counters *masked* the real signal — GPS-spoofing detection actually **improved**
  when we took them away.

**Bottom line.** Recommendation was **leave the model alone** — dropping everything costs only
about 4 points overall, and much of the reliance is legitimate. But the harmful subset is
flagged for removal at the next retrain, as a small free gain.

---

## 8. AINOS3-37 — "Specialists for the modes that have enough signal"

**Why we did it.** The spacecraft flies in four modes, and attack-naming accuracy varied a lot
between them. An earlier experiment gave every mode its own specialist model — which helped
two modes and *hurt* the other two, so it was shelved.

**What we did.** The obvious compromise nobody had tried: **use the specialists only where
they help.** Two modes route to their own dedicated model; the other two keep the general one.

**What we found.** Overall naming accuracy improved from 0.627 to 0.645, with the two
specialist modes gaining about 6 points each and the most-reliable attack types gaining 10.
The two modes kept on the general model were **unchanged by construction** — they're running
exactly the same code as before, so they can't regress.

We also fixed a related problem: the model's confidence scores didn't mean the same thing
across different modes. "80% confident" from one meant something different than from another.
Now they're calibrated to be comparable.

**Bottom line.** Deployed and verified live. Rolling back is a one-line change. Honest caveat
worth carrying: the improvement (+0.018) is **smaller than the natural variation between
measurement runs** (±0.036), so while the comparison is valid — both models were tested on
identical data — the gain shouldn't be oversold.

---

## What Sprint 26 changed overall

Five previously-invisible attack types became detectable, and the "we're not sure" pile went
to zero — so for the first time we could state our coverage precisely: **42 attack techniques
detected, 26 out of scope, 109 not applicable to this spacecraft, 0 unknown.**

The recurring theme, and it shows up in three separate tickets: **most of the work was
discovering that an assumption was wrong.** The file-storage counter was the wrong signal. The
radio program we monitored was a placeholder sending nothing. The watchdog didn't exist. In
each case the fix was cheap once the misconception was cleared, and the misconception was
only found by running the attack against a live spacecraft and looking at what actually
happened.

One thing did *not* get done: presenting the results to stakeholders. The materials were
prepared but the readout slipped — and then slipped again in Sprint 27.
