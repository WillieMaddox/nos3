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



_PHANTOM = re.compile(r"^[a-z_][a-z0-9_]*$")


def _footprint(txt):
    """The objective on-wire signature: the set of (MID-token, FC-token) sent.
    A bare lower-case MID token (mid, tgt, fc) is a helper-definition parameter or
    loop variable from the `build_ccsds_cmd(mid, fc)` DEF, not an actual send;
    capturing it invents a phantom ('mid','fc') pair shared by every script with
    such a helper, which over-merges once boilerplate is stripped. Excluded here."""
    pairs = ((m.group(1), m.group(2)) for m in re.finditer(
        r"build_ccsds_cmd\(\s*([A-Za-z_0-9\[\]\"\'.]+)\s*,\s*([A-Za-z_0-9]+)", txt))
    return frozenset((mid, fc) for mid, fc in pairs if not _PHANTOM.match(mid))


# Boilerplate function codes: connectivity probes (NOOP), evidence resets
# (RESET / RST_COUNTERS / RESET_COUNTERS), baseline reads (REQ_HK / SEND_HK /
# SEND_DIAG), and the literal 0. These scaffold nearly every script and say nothing
# about *which* attack it is; stripping them yields the DISCRIMINATING action.
# AINOS3-122 AC2: the full-footprint grouping is a lower bound because two scripts
# sharing the attack command but differing in this scaffold do not group (the
# IMP-0001 == EX-0012.09 EPS-switch case AINOS3-96 missed).
_BOILER = re.compile(r"NOOP|RST_COUNTERS|RESET|REQ_HK|SEND_HK|SEND_DIAG", re.I)


def _discriminating(txt):
    """The footprint with boilerplate FCs stripped -- the attack command(s) only."""
    return frozenset((mid, fc) for mid, fc in _footprint(txt)
                     if fc != "0" and not _BOILER.search(fc))


def structural(defs, byid):
    """Machine facts only — deliberately NO implements/partial judgement, because
    that half proved subjective (see AINOS3-96) and belongs to pattern analysis."""
    import collections
    src = {}
    for cid, ps in byid.items():
        for p in ps:
            if not p.endswith("_cosmos.py"):
                src[cid] = p
                break
        else:
            src[cid] = ps[0]

    dep = sorted(c for c in src if "[DEPRECATED]" in (defs.get(c, ("", ))[0]))
    notin = sorted(c for c in src if c not in defs)
    sigs = collections.defaultdict(set)
    dsigs = collections.defaultdict(set)
    probe = []
    for cid, p in src.items():
        txt = open(p, errors="replace").read()
        sig = _footprint(txt)
        if sig:
            sigs[sig].add(cid)
        dsig = _discriminating(txt)
        if dsig:
            dsigs[dsig].add(cid)
        fcs = {fc for _, fc in sig}
        if fcs and all("NOOP" in fc.upper() or fc == "0" for fc in fcs):
            probe.append(cid)
    deg = [ids for ids in sigs.values() if len(ids) > 1]
    ddeg = [ids for ids in dsigs.values() if len(ids) > 1]

    print(f"{len(src)} source scripts (cosmos duplicates folded)\n")
    print(f"[deprecated in STIX v4.0] {len(dep)}: {', '.join(dep) or 'none'}")
    print(f"[claimed id not in v4.0]  {len(notin)}: {', '.join(notin) or 'none'}")
    print(f"[probe-only (NOOP-only)]  {len(probe)}: {', '.join(sorted(probe)) or 'none'}")
    print(f"\n[identical-footprint groups spanning >1 technique] {len(deg)} "
          f"(distinct techniques, same commands -> IOB patterns decide if genuinely "
          f"distinct or degenerate):")
    for ids in sorted(deg, key=lambda x: (-len(x), sorted(x))):
        allprobe = all(i in probe for i in ids)
        print(f"    {sorted(ids)}{'  [all probe-only, trivial]' if allprobe else ''}")

    seen = {frozenset(g) for g in deg}
    new_only = [ids for ids in ddeg if frozenset(ids) not in seen]
    print(f"\n[discriminating-action groups (boilerplate stripped)] {len(ddeg)} -- "
          f"{len(new_only)} NOT visible in the full-footprint list above "
          f"(collisions the scaffold was hiding):")
    for ids in sorted(ddeg, key=lambda x: (-len(x), sorted(x))):
        allprobe = all(i in probe for i in ids)
        flag = "  <-- NEW" if frozenset(ids) in {frozenset(g) for g in new_only} else ""
        print(f"    {sorted(ids)}{'  [all probe-only]' if allprobe else ''}{flag}")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("ids", nargs="*", help="technique ids; default = classifier classes")
    ap.add_argument("--all", action="store_true", help="every claimed id, not just classes")
    ap.add_argument("--structural", action="store_true",
                    help="objective corpus-wide facts (deprecated / not-in-v4 / "
                         "identical-footprint degeneracy / probe-only), no verdicts")
    args = ap.parse_args(argv)

    defs = stix_defs()
    byid = scripts_by_id()
    if args.structural:
        return structural(defs, byid)
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
