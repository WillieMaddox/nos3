#!/usr/bin/env python3
"""AINOS3-116 — query the local STIX IOB <-> technique <-> pattern graph.

AINOS3-96 established that SPARTA's full Indicators-of-Behavior graph is already
in the downloaded bundle: 855 `indicator` objects each with a formal `pattern`,
linked to techniques by 855 `indicates` relationships. This exposes that graph so
per-technique IOB coverage is repeatable rather than an ad-hoc pull (the way the
EX-0014.01/EX-0012.12 degeneracy was broken by hand).

Commands:
    stix_iob_index.py --technique EX-0005     # AC1: a technique's IOBs + patterns
    stix_iob_index.py --shared IOB-NAME       # AC2: techniques sharing an IOB
    stix_iob_index.py --args                  # AC2: pattern-argument vocabulary
    stix_iob_index.py --coverage EX-0014.01   # AC3: join IOBs -> mid_stix_map states
    stix_iob_index.py --degeneracy A B ...     # AC4: do these techniques' unique IOBs separate them?
    stix_iob_index.py --provenance            # AC5: bundle sha256 the graph was read from

The coverage join reads `mid_stix_map.json` (AINOS3-115): for each IOB it reports
whether any of its pattern arguments map to a NOS3 observable, and in what state.
It does NOT judge whether a script implements the IOB — that stays a human/attack
call (the AINOS3-96 subjectivity lesson); it reports the *observability*, which is
objective.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
STIX = os.path.join(ROOT, "data/sparta/sparta_stix_latest.json")
MAP = os.path.join(ROOT, "components/onair/mid_stix_map.json")

_ARG = re.compile(r"([a-z][\w-]*):([\w.\[\]-]+)")


def load():
    d = json.load(open(STIX))
    byid = {o["id"]: o for o in d["objects"]}
    eid2id, id2eid = {}, {}
    for o in d["objects"]:
        if o.get("type") == "attack-pattern":
            e = next((r["external_id"] for r in o.get("external_references", [])
                      if r.get("external_id")), None)
            if e:
                eid2id[e] = o["id"]
                id2eid[o["id"]] = e
    # technique external_id -> [indicator objects]
    iobs = collections.defaultdict(list)
    for o in d["objects"]:
        if o.get("type") == "relationship" and o.get("relationship_type") == "indicates":
            src, tgt = byid.get(o.get("source_ref", "")), o.get("target_ref")
            if src and src.get("type") == "indicator" and tgt in id2eid:
                iobs[id2eid[tgt]].append(src)
    return d, iobs, eid2id


def args_of(pattern):
    return sorted({f"{m.group(1)}:{m.group(2)}" for m in _ARG.finditer(pattern or "")})


def cmd_technique(iobs, tid):
    ins = iobs.get(tid, [])
    print(f"{tid}: {len(ins)} IOB(s)\n")
    for i in sorted(ins, key=lambda x: x.get("name", "")):
        print(f"  {i.get('name','')}")
        print(f"    {i.get('pattern','')}")
    return 0


def cmd_shared(iobs, name):
    nl = name.lower()
    hits = collections.defaultdict(list)
    for tid, ins in iobs.items():
        for i in ins:
            if nl in i.get("name", "").lower():
                hits[i.get("name")].append(tid)
    if not hits:
        print(f"no IOB name matches {name!r}")
        return 1
    for iob, tids in sorted(hits.items()):
        print(f"{iob}\n    shared by: {', '.join(sorted(tids))}")
    return 0


def cmd_args(iobs):
    c = collections.Counter()
    for ins in iobs.values():
        for i in ins:
            for a in args_of(i.get("pattern")):
                c[a] += 1
    for a, n in c.most_common():
        print(f"{n:4d}  {a}")
    print(f"\n{len(c)} distinct arguments", file=sys.stderr)
    return 0


def cmd_coverage(iobs, tid):
    """AC3: for each of the technique's IOBs, can we observe it? Join to the map."""
    rows = json.load(open(MAP))["rows"] if os.path.exists(MAP) else []
    # object -> best-known state from the map (verified > unverified > cannot > none)
    rank = {"verified": 3, "unverified": 2, "field-cannot-represent-value": 1}
    obj_state = {}
    for r in rows:
        st = ("no-observable" if r.get("mid") is None
              else "field-cannot-represent-value" if r.get("representable") is False
              else r.get("status", "unverified"))
        o = r["stix_object"]
        if rank.get(st, 0) >= rank.get(obj_state.get(o, ""), 0):
            obj_state[o] = st
    ins = iobs.get(tid, [])
    print(f"{tid}: {len(ins)} IOB(s) — observability join to mid_stix_map.json\n")
    for i in sorted(ins, key=lambda x: x.get("name", "")):
        objs = {a.split(":")[0] for a in args_of(i.get("pattern"))}
        states = {obj_state.get(o, "unmapped") for o in objs}
        # An IOB needs ALL its arguments observable to fire, so its observability is
        # the WEAKEST of them, not the best. (Under-counts OR-patterns — noted below;
        # distinguishing AND/OR needs pattern-logic parsing, deferred.)
        worst = next((s for s in ("unmapped", "no-observable",
                                  "field-cannot-represent-value", "unverified", "verified")
                      if s in states), "unmapped")
        print(f"  [{worst:26s}] {i.get('name','')}")
        print(f"        objects: {', '.join(sorted(objs))}")
    return 0


def cmd_degeneracy(iobs, tids):
    """AC4: are these techniques separable by their UNIQUE IOBs?"""
    sets = {t: {i.get("name") for i in iobs.get(t, [])} for t in tids}
    shared = set.intersection(*sets.values()) if sets else set()
    print(f"comparing {', '.join(tids)}")
    print(f"  shared IOBs ({len(shared)}): {', '.join(sorted(shared)) or 'none'}\n")
    separable = True
    for t in tids:
        uniq = sets[t] - shared
        print(f"  {t} unique IOBs ({len(uniq)}): {', '.join(sorted(uniq)) or 'NONE'}")
        if not uniq:
            separable = False
    print(f"\n  → {'SEPARABLE — each has a distinguishing IOB (script limitation, not degeneracy)' if separable else 'NOT separable by IOB — genuinely degenerate at this granularity'}")
    return 0


def cmd_provenance():
    sha = hashlib.sha256(open(STIX, "rb").read()).hexdigest()
    d = json.load(open(STIX))
    n_ap = sum(1 for o in d["objects"] if o.get("type") == "attack-pattern")
    n_ind = sum(1 for o in d["objects"] if o.get("type") == "indicator")
    print(f"bundle: {os.path.relpath(STIX, ROOT)}")
    print(f"sha256: {sha}")
    print(f"contents: {n_ap} attack-patterns, {n_ind} indicators")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--technique", metavar="ID")
    ap.add_argument("--shared", metavar="IOB")
    ap.add_argument("--args", action="store_true")
    ap.add_argument("--coverage", metavar="ID")
    ap.add_argument("--degeneracy", nargs="+", metavar="ID")
    ap.add_argument("--provenance", action="store_true")
    a = ap.parse_args(argv)
    if a.provenance:
        return cmd_provenance()
    _, iobs, _ = load()
    if a.technique:
        return cmd_technique(iobs, a.technique)
    if a.shared:
        return cmd_shared(iobs, a.shared)
    if a.args:
        return cmd_args(iobs)
    if a.coverage:
        return cmd_coverage(iobs, a.coverage)
    if a.degeneracy:
        return cmd_degeneracy(iobs, a.degeneracy)
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
