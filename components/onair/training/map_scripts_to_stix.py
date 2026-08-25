#!/usr/bin/env python3
"""Map our SPARTA attack scripts onto STIX technique objects (AINOS3-96).

Our attack scripts *assert* which SPARTA technique they implement, in a docstring
line of the form `SPARTA EX-0010.01 - <title>`, and again in their filename. Those
assertions are the classifier's class labels, so a wrong one is a mislabelled
class that propagates into every downstream artifact — the `EX-0012` wave-1
failure mode that cost a full re-derivation.

This is the MECHANICAL half of the check: does the claimed ID exist in the STIX
bundle, do the filename and docstring agree, and does the claimed title match the
authoritative one. Behavioural agreement (does the script do what the technique
*describes*) needs a human read of the STIX description and is reported as
`NEEDS-REVIEW` here rather than guessed.

Run:
    python3 components/onair/training/map_scripts_to_stix.py \\
        [--stix data/sparta/sparta_stix_latest.json] \\
        [--scripts-root gsw/attack_scripts/sparta] [--json out.json]
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import re
import sys

# `SPARTA EX-0010.01 - Malicious Code: Ransomware`, tolerating - / -- / em dash.
_DOC_RE = re.compile(r"SPARTA\s+([A-Z]{2,3}-\d{4}(?:\.\d{2})?)\s*[-–—:]*\s*(.*)")
# `ex_0010_01_ransomware.py` -> EX-0010.01 ; `de_0005_subvert.py` -> DE-0005
_FILE_RE = re.compile(r"^([a-z]{2,3})_(\d{4})(?:_(\d{2}))?_")


def claimed_from_filename(name: str):
    m = _FILE_RE.match(name)
    if not m:
        return None
    tac, num, sub = m.groups()
    return f"{tac.upper()}-{num}" + (f".{sub}" if sub else "")


def claimed_from_docstring(path: str):
    """First `SPARTA <ID>` in the module docstring region (first 40 lines)."""
    try:
        with open(path, errors="replace") as f:
            head = "".join(f.readline() for _ in range(40))
    except OSError:
        return None, None
    m = _DOC_RE.search(head)
    return (m.group(1), m.group(2).strip()) if m else (None, None)


def load_stix(path: str):
    d = json.load(open(path))
    by_id, names = {}, {}
    for o in d["objects"]:
        if o.get("type") != "attack-pattern":
            continue
        for r in o.get("external_references", []):
            if r.get("source_name", "").lower().startswith("sparta"):
                eid = r.get("external_id")
                by_id[eid] = o
                names[eid] = o.get("name", "")
                break
    version = next((o.get("x_sparta_version") for o in d["objects"]
                    if o.get("type") == "x-sparta-collection"), "?")
    return by_id, names, version


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--stix", default="data/sparta/sparta_stix_latest.json")
    p.add_argument("--scripts-root", default="gsw/attack_scripts/sparta")
    p.add_argument("--json", default=None)
    args = p.parse_args()

    if not os.path.exists(args.stix):
        sys.exit(f"no STIX bundle at {args.stix} — run fetch_sparta_stix.py first")
    by_id, names, version = load_stix(args.stix)

    rows = []
    for dirpath, _dirs, files in os.walk(args.scripts_root):
        for fn in sorted(files):
            if not fn.endswith(".py") or fn.endswith("_cosmos.py"):
                continue
            path = os.path.join(dirpath, fn)
            f_id = claimed_from_filename(fn)
            d_id, d_title = claimed_from_docstring(path)
            claimed = d_id or f_id
            flags = []
            if not claimed:
                flags.append("NO-CLAIM")
            else:
                if f_id and d_id and f_id != d_id:
                    flags.append(f"FILENAME-DOCSTRING-DISAGREE({f_id}!={d_id})")
                if claimed not in by_id:
                    parent = claimed.split(".")[0]
                    flags.append("NOT-IN-STIX"
                                 + ("(parent exists)" if parent in by_id else "(parent missing)"))
            rows.append({"script": os.path.relpath(path), "filename_id": f_id,
                         "docstring_id": d_id, "docstring_title": d_title,
                         "claimed": claimed,
                         "stix_name": names.get(claimed),
                         "flags": flags,
                         "verdict": "FLAGGED" if flags else "NEEDS-REVIEW"})

    claimed_ids = {r["claimed"] for r in rows if r["claimed"]}
    in_stix = {c for c in claimed_ids if c in by_id}
    never = sorted(set(by_id) - claimed_ids)

    print(f"STIX {version}: {len(by_id)} techniques   |   "
          f"{len(rows)} scripts, {len(claimed_ids)} distinct claimed IDs\n")
    flagged = [r for r in rows if r["flags"]]
    print(f"mechanically OK (claim resolves): {len(rows) - len(flagged)}")
    print(f"FLAGGED:                          {len(flagged)}")
    for r in flagged:
        print(f"    {r['script']:72s} {','.join(r['flags'])}")

    print(f"\ntechniques covered by >=1 script: {len(in_stix)} / {len(by_id)}")
    print(f"techniques with NO script:        {len(never)}")
    bytac = collections.Counter(t.split("-")[0] for t in never)
    print("   never-attempted by tactic:", dict(sorted(bytac.items())))

    if args.json:
        json.dump({"stix_version": version, "n_techniques": len(by_id),
                   "scripts": rows, "covered": sorted(in_stix),
                   "never_attempted": never}, open(args.json, "w"), indent=2)
        print(f"\nwrote {args.json}")


if __name__ == "__main__":
    main()
