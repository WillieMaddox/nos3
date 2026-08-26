#!/usr/bin/env python3
"""Behavioural half of AINOS3-96: does each attack script DO what its STIX technique DEFINES?

`map_scripts_to_stix.py` is the MECHANICAL check — claimed ID resolves, filename
and docstring agree, title matches. It cannot see behaviour, and reports it as
`NEEDS-REVIEW`. This is that review, made repeatable so the verdict is not a
one-off human read buried in a ticket.

For each technique it prints, side by side:
  - the STIX definition (name + description), and
  - what the script actually sends — command MIDs, raw hex MIDs, and every
    `_send(...)` action label, which is where the scripts describe their own steps.

The VERDICT per script (`implements-as-claimed` / `mislabelled` /
`partially-implements` / `undecidable-from-STIX`) is a judgement and stays in the
ticket log — this tool assembles the evidence for it, it does not decide.

Scope: defaults to the classifier's own classes (from classifier_tiers.json) plus
any id passed on the command line, because a mislabel only corrupts training if
the mislabelled technique is a *class*. `--all` widens to every claimed id.

Run:
    python3 components/onair/training/audit_script_vs_stix.py [--all] [IDS...]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import textwrap

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, HERE)
import map_scripts_to_stix as M  # noqa: E402

STIX = os.path.join(ROOT, "data/sparta/sparta_stix_latest.json")
TIERS = os.path.join(ROOT, "data/onair/models/classifier_tiers.json")
SCRIPTS = os.path.join(ROOT, "gsw/attack_scripts/sparta")

# f-string labels contain {...}; the earlier pattern stopped at the first quote and
# dropped f"CFE_TBL LOAD {self.filename}" entirely — the LOAD/ACTIVATE actions that
# distinguish the EX-0012.03/04/05 cluster. Allow an optional f prefix and match the
# whole quoted label including braces.
_SEND = re.compile(r'_send\(\s*(?:f?"[^"]*",\s*)?f?"([^"]{1,140})"')
_MIDNAME = re.compile(r'CMD_MIDS\["([A-Z_0-9]+)"\]')
_HEX = re.compile(r'0x1[0-9A-Fa-f]{3}')
_FC = re.compile(r'\bFC\s*=?\s*(\d+)|fc\s*=\s*(\d+)')


def stix_defs():
    d = {}
    for o in json.load(open(STIX))["objects"]:
        if o.get("type") != "attack-pattern":
            continue
        for ref in o.get("external_references", []):
            if ref.get("external_id"):
                d[ref["external_id"]] = (o.get("name", ""), o.get("description", ""))
    return d


def scripts_by_id():
    out = {}
    for r, _, fs in os.walk(SCRIPTS):
        for fn in sorted(fs):
            if not fn.endswith(".py"):
                continue
            p = os.path.join(r, fn)
            cid, _ = M.claimed_from_docstring(p)
            cid = cid or M.claimed_from_filename(fn)
            if cid:
                out.setdefault(cid, []).append(p)
    return out


def behaviour(path):
    txt = open(path, errors="replace").read()
    acts = _SEND.findall(txt)
    mids = sorted(set(_MIDNAME.findall(txt)))
    hexm = sorted(set(_HEX.findall(txt)))
    return acts, mids, hexm


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("ids", nargs="*", help="technique ids; default = classifier classes")
    ap.add_argument("--all", action="store_true", help="every claimed id, not just classes")
    args = ap.parse_args(argv)

    defs = stix_defs()
    byid = scripts_by_id()
    if args.ids:
        ids = args.ids
    elif args.all:
        ids = sorted(byid)
    else:
        cls = json.load(open(TIERS)).get("classes") or {}
        ids = sorted({c.replace(" [prereq]", "") for c in cls if c != "nominal"})

    print(f"{len(ids)} technique(s); STIX v4.0\n")
    for t in ids:
        print("=" * 100)
        if t not in defs:
            print(f"##### {t}  ⚠ NOT IN STIX v4.0 — claimed id does not resolve")
            continue
        name, d = defs[t]
        print(f"##### {t} — {name}")
        print("STIX: " + textwrap.shorten(" ".join(d.split()), 600))
        src = [p for p in byid.get(t, []) if not p.endswith("_cosmos.py")] or byid.get(t, [])
        if not src:
            print("  ⚠ NO SCRIPT")
            continue
        for p in src:
            acts, mids, hexm = behaviour(p)
            print(f"\n  {os.path.relpath(p, ROOT)}")
            print(f"    MIDs: {', '.join(mids) or '—'}   raw: {', '.join(hexm) or '—'}")
            for a in acts[:10]:
                print(f"      · {a}")
            if len(acts) > 10:
                print(f"      · … {len(acts) - 10} more send actions")
    return 0


if __name__ == "__main__":
    sys.exit(main())
