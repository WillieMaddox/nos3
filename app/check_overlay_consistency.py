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
    Incident recall SHOULD sit above frame catch — that is what incident
    aggregation is for. A large positive gap is normal.
  - different scope: `Catch` is SUNSAFE-only, while incidents are scored over a
    corpus whose attack windows span every mode. An attack invisible in SUNSAFE
    can still raise an incident off another mode's frames.

So the checks below look for gaps that those two explanations do NOT cover.

  IMPOSSIBLE       catch == 0 yet incidents were raised. Not literally
                   impossible (see scope, above) but it means every incident
                   came from a mode outside the published figure — and one of
                   those modes, INERTIAL, currently has a 33.6 % false-alarm
                   rate, so "detected" there may be noise. Always worth a look.
  INVERTED         incident recall BELOW frame catch by more than --margin.
                   Backwards: frames were flagged but no incident formed.
                   Suggests hysteresis or aggregation is dropping real signal.
  NEVER-NAMED      high incident recall with zero correct labels. Reads as
                   "solved" on screen while the classifier never once got it
                   right.
  WIDE             a gap larger than --margin in the expected direction. Not a
                   defect; listed so nobody is surprised by it mid-demo.

Usage:
    python3 app/check_overlay_consistency.py [--margin 0.25] [--quiet]

Exit status is 1 if any IMPOSSIBLE / INVERTED / NEVER-NAMED panel is found, so
this can gate a rollout the way check_ticket_titles.py gates a sprint plan.
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
                tid=tid, kind="IMPOSSIBLE", catch=catch, recall=recall,
                label_ok=label_ok,
                note="zero frames flagged in SUNSAFE yet incidents raised — "
                     "every incident came from another mode"))
        elif gap < -margin:
            findings.append(dict(
                tid=tid, kind="INVERTED", catch=catch, recall=recall,
                label_ok=label_ok,
                note=f"incident recall {recall:.0%} is {abs(gap):.0%} BELOW "
                     f"frame catch — frames flagged but no incident formed"))
        elif gap > margin:
            findings.append(dict(
                tid=tid, kind="WIDE", catch=catch, recall=recall,
                label_ok=label_ok,
                note=f"incident recall exceeds frame catch by {gap:.0%} "
                     f"(expected direction; aggregation working)"))

        if recall >= 0.99 and label_ok == 0:
            findings.append(dict(
                tid=tid, kind="NEVER-NAMED", catch=catch, recall=recall,
                label_ok=label_ok,
                note="every incident detected, none ever named correctly — "
                     "reads as 'solved' on screen"))
    return findings


BLOCKING = {"IMPOSSIBLE", "INVERTED", "NEVER-NAMED"}


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--coverage", default=COVERAGE_JS)
    p.add_argument("--margin", type=float, default=0.25,
                   help="gap between incident recall and frame catch that counts "
                        "as notable (default 0.25)")
    p.add_argument("--quiet", action="store_true",
                   help="suppress the WIDE (expected-direction) rows")
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
        order = {"IMPOSSIBLE": 0, "INVERTED": 1, "NEVER-NAMED": 2, "WIDE": 3}
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
