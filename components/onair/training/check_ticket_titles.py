#!/usr/bin/env python3
"""Flag sprint-plan ticket headings that diverge from JIRA_CROSSWALK.md.

Why: on 2026-08-19 we found `AINOS3-30` had been reused in Sprint 27 for
materially different work than the key was bound to — different title, different
scope, different estimate — while the Jira issue was still open against the
original. It went unnoticed for ten days because five *cosmetic* title
divergences in the same plan made the substantive one look unremarkable.

The crosswalk is canonical: a key binds to one slug and one scope, permanently.
This check keeps plan headings honest against it so a real reuse cannot hide in
wording noise.

    python3 components/onair/training/check_ticket_titles.py [--sprint 27]

Exit 1 if any heading diverges. Cosmetic differences are reported too — the
point is to keep the noise floor at zero so a substantive divergence stands out.
"""
import argparse, os, re, sys, difflib

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")


def canonical_titles(path):
    out = {}
    for line in open(path, encoding="utf-8"):
        m = re.match(r"\|\s*(AINOS3-\d+)\s*\|\s*([\w-]+)\s*\|\s*(\w+)\s*\|[^|]*\|\s*([^|]+?)\s*\|", line)
        if m and m.group(1) not in out:
            out[m.group(1)] = (m.group(2), m.group(4))
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--sprint", default="27")
    p.add_argument("--threshold", type=float, default=0.72,
                   help="similarity below this is reported as a divergence")
    a = p.parse_args()
    cw = canonical_titles(os.path.join(ROOT, "JIRA_CROSSWALK.md"))
    plan_path = os.path.join(ROOT, f"SPRINT_{a.sprint}_PLAN.md")
    bad = 0
    for line in open(plan_path, encoding="utf-8"):
        m = re.match(r"### (AINOS3-\d+) — (.+?) ·", line)
        if not m:
            continue
        key, title = m.group(1), m.group(2)
        if key not in cw:
            print(f"  {key}: NOT IN CROSSWALK — every key must be registered there")
            bad += 1
            continue
        slug, canon = cw[key]
        r = difflib.SequenceMatcher(None, title.lower(), canon.lower()).ratio()
        if r < a.threshold:
            print(f"  {key} ({slug})  similarity {r:.2f}")
            print(f"      plan:      {title}")
            print(f"      crosswalk: {canon}")
            bad += 1
    if bad:
        print(f"\n{bad} heading(s) diverge from the crosswalk.")
        print("Cosmetic? Align the plan. Substantive? The key may have been REUSED —")
        print("split the new work under its own slug rather than overloading the key.")
        return 1
    print(f"Sprint {a.sprint}: all ticket headings match the crosswalk.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
