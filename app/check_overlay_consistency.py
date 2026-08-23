#!/usr/bin/env python3
"""Pre-flight check for the coverage overlay: find panels whose own numbers
disagree with each other, before a stakeholder does.

WHY
---
The overlay's columns do not share a provenance. `Catch` and `Incidents` both
trace to the pre-correction corpus (mode-cycled every 60 s, so 83 % of attack
frames landed inside the detector's blind window), while `tier`, `Top fields`
and `cluster` were re-derived against the deployed hybrid. When a correction
lands on one column and not the other, a panel can end up asserting two
incompatible things — `EX-0012.09` currently shows "detected by nothing" beside
an incident recall of 3/3. That was found by eye. This finds the rest.

WHAT "DISAGREE" MEANS HERE
--------------------------
`Catch` and `Incidents` are NOT the same measurement, so a raw difference is the
wrong test — most of the gap between them is expected and healthy:

  - different granularity: `Catch` is the fraction of attack FRAMES flagged;
    `Incidents` is the fraction of attacks that raised AT LEAST ONE alert.
  - different scope, and this one is absolute: `Catch` is SUNSAFE-only, while
    every incident is attributed to its attack's FIRST corruption frame's mode.
    Attacks start where the FSW boots, so the corpus holds 91 PASSIVE, 23
    INERTIAL, 1 BDOT and **zero SUNSAFE** incidents. The two columns therefore
    describe populations that never overlap, and NO arithmetic between them is
    meaningful — not a difference, not a ratio, not a direction.

So the checks below avoid cross-column arithmetic as evidence. What they look
for is a panel that READS as self-contradictory to someone seeing it for the
first time, plus one finding (NEVER-NAMED) that holds within a single column.

  SAYS-BOTH        the panel asserts "caught nothing" and "caught everything"
                   at once: catch == 0 with incidents raised. Given the scope
                   note above this is not a contradiction in the data, but it
                   IS one on screen — and the incidents came from modes
                   including INERTIAL, which currently runs a 33.6 %
                   false-alarm rate, so "detected" there may be noise.
  NEVER-NAMED      high incident recall with zero correct labels. Reads as
                   "solved" on screen while the classifier never once got it
                   right. The strongest finding this check produces, because it
                   needs no cross-column comparison to hold.
  WIDE             a gap larger than --margin. Reported ONLY so nobody is
                   surprised mid-demo — see the scope note: the gap is not
                   evidence of anything.

Usage:
    python3 app/check_overlay_consistency.py [--margin 0.25] [--quiet]

Exit status is 1 if any SAYS-BOTH / NEVER-NAMED panel is found, so this can
gate a rollout the way check_ticket_titles.py gates a sprint plan.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
COVERAGE_JS = os.path.join(HERE, "nos3_coverage.js")
SENTINEL = "window.NOS3_COVERAGE = "


def load_coverage(path: str) -> dict:
    """Extract the NOS3_COVERAGE object literal from the generated JS."""
    s = open(path, encoding="utf-8").read()
    i = s.index(SENTINEL) + len(SENTINEL)
    depth = 0
    for j in range(i, len(s)):
        if s[j] == "{":
            depth += 1
        elif s[j] == "}":
            depth -= 1
            if depth == 0:
                return json.loads(s[i:j + 1])
    raise ValueError(f"unterminated {SENTINEL} object in {path}")


def audit(cov: dict, margin: float) -> list[dict]:
    findings = []
    for tid, v in sorted(cov.items()):
        det, tot = v.get("incident_detected"), v.get("incident_total")
        catch = v.get("frame_rate")
        if det is None or not tot:
            continue                      # no incident measurement to compare
        recall = det / tot
        label_ok = v.get("label_ok")

        if catch is None:
            # Catch is suppressed below 25% as "not meaningful"; a high incident
            # recall against a suppressed catch rate is still worth a glance.
            if recall >= 0.99:
                findings.append(dict(
                    tid=tid, kind="WIDE", catch=catch, recall=recall,
                    label_ok=label_ok,
                    note="catch suppressed (<25%, 'not meaningful') but every "
                         "incident was detected"))
            continue

        gap = recall - catch
        if catch == 0.0 and recall > 0:
            findings.append(dict(
                tid=tid, kind="SAYS-BOTH", catch=catch, recall=recall,
                label_ok=label_ok,
                note="panel shows 0% caught beside 100% of incidents "
                     "detected; those incidents are all non-SUNSAFE"))
        # NO "INVERTED" CHECK. An earlier version flagged incident recall
        # falling below frame catch as backwards ("frames flagged but no
        # incident formed") and fired on EX-0012.08. That test was invalid: it
        # assumed both figures cover the same attacks. They cover DISJOINT
        # populations — Catch is SUNSAFE-only, and because incidents are
        # attributed to an attack's FIRST corruption frame's mode (attacks start
        # in PASSIVE, where the FSW boots) the corpus contains ZERO SUNSAFE
        # incidents. A gap in either direction is therefore uninformative about
        # aggregation, and the check must not imply otherwise.
        elif gap > margin:
            findings.append(dict(
                tid=tid, kind="WIDE", catch=catch, recall=recall,
                label_ok=label_ok,
                note=f"incident recall exceeds frame catch by {gap:.0%} "
                     f"(populations do not overlap — not evidence)"))

        if recall >= 0.99 and label_ok == 0:
            findings.append(dict(
                tid=tid, kind="NEVER-NAMED", catch=catch, recall=recall,
                label_ok=label_ok,
                note="every incident detected, none ever named correctly — "
                     "reads as 'solved' on screen"))
    return findings


BLOCKING = {"SAYS-BOTH", "NEVER-NAMED"}


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--coverage", default=COVERAGE_JS)
    p.add_argument("--margin", type=float, default=0.25,
                   help="gap between incident recall and frame catch that counts "
                        "as notable (default 0.25)")
    p.add_argument("--quiet", action="store_true",
                   help="suppress the WIDE (informational) rows")
    a = p.parse_args()

    cov = load_coverage(a.coverage)
    findings = audit(cov, a.margin)
    shown = [f for f in findings if not (a.quiet and f["kind"] == "WIDE")]
    blockers = [f for f in findings if f["kind"] in BLOCKING]

    scored = sum(1 for v in cov.values()
                 if v.get("incident_total") and v.get("incident_detected") is not None)
    print(f"{scored} panels carry both an Incidents and a Catch figure; "
          f"margin {a.margin:.0%}\n")
    if not shown:
        print("No disagreements.")
    else:
        print(f"{'technique':<14}{'kind':<13}{'catch':>7}{'incid':>8}{'lbl':>5}  note")
        print("-" * 110)
        order = {"SAYS-BOTH": 0, "NEVER-NAMED": 1, "WIDE": 2}
        for f in sorted(shown, key=lambda f: (order[f["kind"]], f["tid"])):
            c = "—" if f["catch"] is None else f"{f['catch']:.0%}"
            print(f"{f['tid']:<14}{f['kind']:<13}{c:>7}{f['recall']:>7.0%}"
                  f"{str(f['label_ok']):>5}  {f['note']}")

    print(f"\n{len(blockers)} panel(s) need an answer before presenting; "
          f"{len(findings) - len(blockers)} informational.")
    if blockers:
        print("Both Catch and Incidents trace to the pre-correction corpus "
              "(AINOS3-89 owns re-measuring them).")
    return 1 if blockers else 0


if __name__ == "__main__":
    sys.exit(main())
