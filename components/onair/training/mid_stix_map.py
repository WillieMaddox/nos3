#!/usr/bin/env python3
"""AINOS3-115 — NOS3/OnAIR MID field <-> STIX IOB pattern-argument map.

The 855 STIX IOB patterns (`data/sparta/sparta_stix_latest.json`) express what
each technique should produce as machine-comparable observables. This is the
translation from those pattern arguments to NOS3 telemetry, so pattern-based
coverage checks and attack generation (AINOS3-116/118) have a substrate.

⚠ It is NOT complete and is not meant to be (AC5). It is a seed that grows; an
unmappable argument is a finding, not a gap in this file. The four states a row
can be in — all present in the seed:

  * mapped + verified   — the field moves as the argument requires, demonstrated
                          live, evidence cited.
  * mapped + unverified — a plausible field, not yet exercised. The default.
  * representable=false  — a field exists but cannot hold the argument's value
                          (e.g. file:hashes -> a uint16 CRC computed once at boot).
  * no-observable        — mid=null; nothing in NOS3 can carry it (e.g.
                          network-traffic:src on an anonymous bus).

Three commands:
    mid_stix_map.py --check      # AC2: fail if a mapped field is not in the schema
    mid_stix_map.py --report     # AC3/AC5: state counts + the observability-gap metric
    mid_stix_map.py --lookup X   # AC4: X is a STIX object/arg substring OR a MID/field
    mid_stix_map.py --args       # dump the full STIX argument vocabulary from the bundle
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
MAP = os.path.join(ROOT, "components/onair/mid_stix_map.json")
SCHEMA = os.path.join(ROOT, "components/onair/nos3_security_tlm.json")
STIX = os.path.join(ROOT, "data/sparta/sparta_stix_latest.json")


def load_map():
    return json.load(open(MAP))["rows"]


def schema_fields():
    d = json.load(open(SCHEMA))
    return set(d["order"]), set(d["channels"])


def stix_args():
    """Every distinct (object:property) comparison term across all IOB patterns."""
    pats = [o["pattern"] for o in json.load(open(STIX))["objects"]
            if o.get("type") == "indicator" and o.get("pattern")]
    args = collections.Counter()
    for p in pats:
        for m in re.finditer(r"([a-z][\w-]*):([\w.\[\]-]+)", p):
            args[f"{m.group(1)}:{m.group(2)}"] += 1
    return args


def check(rows):
    """AC2: a mapped field must exist in the schema, unless the row is a
    no-observable (mid=null) gap. A drifted field is an error."""
    order, channels = schema_fields()
    problems = []
    for r in rows:
        mid, field = r.get("mid"), r.get("field")
        if mid is None and field is None:
            if r.get("status") != "no-observable":
                problems.append(f"{r['stix_object']}:{r['stix_property']}: null mid "
                                f"but status={r.get('status')!r} (expected no-observable)")
            continue
        if mid not in channels:
            problems.append(f"{r['stix_object']}:{r['stix_property']}: MID {mid} "
                            f"not subscribed in nos3_security_tlm.json")
        if field not in order:
            problems.append(f"{r['stix_object']}:{r['stix_property']}: field {field!r} "
                            f"not in schema `order` (drifted or unsubscribed)")
        if r.get("status") == "verified" and not r.get("evidence"):
            problems.append(f"{r['stix_object']}:{r['stix_property']}: verified with no evidence")
    for p in problems:
        print(f"  ERROR: {p}")
    print(f"\n{len(rows)} rows checked · {len(problems)} error(s)")
    return 1 if problems else 0


def report(rows):
    """AC3/AC5: the four states, and the observability-gap metric."""
    by = collections.Counter()
    for r in rows:
        if r.get("mid") is None:
            by["no-observable"] += 1
        elif r.get("representable") is False:
            by["field-cannot-represent-value"] += 1
        else:
            by[r.get("status", "unverified")] += 1
    print("mapping states:")
    for k in ("verified", "unverified", "field-cannot-represent-value", "no-observable"):
        print(f"   {by.get(k, 0):4d}  {k}")

    args = stix_args()
    mapped_objs = {r["stix_object"] for r in rows}
    covered = sum(n for a, n in args.items() if a.split(":")[0] in mapped_objs)
    total = sum(args.values())
    print(f"\nSTIX argument vocabulary: {len(args)} distinct arguments "
          f"across {len({a.split(':')[0] for a in args})} object types")
    print(f"seed touches {len(mapped_objs)} object types "
          f"({covered}/{total} argument-occurrences)")
    print(f"⚠ observability-gap metric: {len(args) - len([r for r in rows if r.get('mid')])} "
          f"of {len(args)} STIX arguments have no verified NOS3 observable yet "
          f"(seed is intentionally partial — AC5)")
    return 0


def lookup(rows, q):
    ql = q.lower()
    hits = [r for r in rows
            if ql in f"{r['stix_object']}:{r['stix_property']}".lower()
            or (r.get("mid") and ql in str(r["mid"]).lower())
            or (r.get("field") and ql in str(r["field"]).lower())]
    if not hits:
        print(f"no rows match {q!r}")
        return 1
    for r in hits:
        arrow = f"{r.get('mid') or '(no MID)'} / {r.get('field') or '—'}"
        rep = "" if r.get("representable", True) else "  [not-representable]"
        print(f"\n{r['stix_object']}:{r['stix_property']}  →  {arrow}   [{r.get('status')}]{rep}")
        if r.get("evidence"):
            print(f"   evidence: {r['evidence']}")
        if r.get("notes"):
            print(f"   notes:    {r['notes']}")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--lookup", metavar="X")
    ap.add_argument("--args", action="store_true")
    a = ap.parse_args(argv)
    rows = load_map()
    if a.check:
        return check(rows)
    if a.report:
        return report(rows)
    if a.lookup:
        return lookup(rows, a.lookup)
    if a.args:
        for arg, n in stix_args().most_common():
            print(f"{n:4d}  {arg}")
        return 0
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
