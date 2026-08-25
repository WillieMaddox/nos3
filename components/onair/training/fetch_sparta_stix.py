#!/usr/bin/env python3
"""Fetch the SPARTA knowledge base as a STIX 2.1 bundle (AINOS3-96).

SPARTA publishes STIX as the most granular form of its knowledge base; every
other view — including the HTML matrix our coverage overlay was built from — is
derived from it. Per the SPARTA "Working With SPARTA" page the documented
scriptable endpoint is:

    https://sparta.aerospace.org/download/STIX?f=latest

⚠ Only `f=latest` works. The site lists older bundles (sparta_data_v3.2.json and
back to v1.0), but requesting them through `f=` returns the site's HTML page with
a 200 status and a multi-MB body — it looks like a successful download and is
not. That is why this script validates the payload rather than trusting the
status code. Older versions appear to be browser-download only.

The bundle is pinned by sha256 in a `.meta.json` sidecar next to it, mirroring
the CSV schema-sidecar convention, so a later run can prove whether upstream
changed under us.

Run:
    python3 components/onair/training/fetch_sparta_stix.py [--out-dir data/sparta]
    python3 components/onair/training/fetch_sparta_stix.py --check   # verify only
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import sys
import urllib.request

ENDPOINT = "https://sparta.aerospace.org/download/STIX?f=latest"
DEFAULT_OUT = "data/sparta"
BUNDLE_NAME = "sparta_stix_latest.json"
TIMEOUT_S = 120


def validate(raw: bytes) -> dict:
    """Parse and sanity-check the payload. Raises on anything that is not a
    SPARTA STIX bundle — including the HTML page the server returns with 200."""
    head = raw.lstrip()[:64].lower()
    if head.startswith(b"<!doctype") or head.startswith(b"<html"):
        raise ValueError(
            "server returned HTML, not JSON — this is the silent failure mode "
            "for any `f=` value other than 'latest'")
    try:
        d = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"payload is not JSON: {exc}") from None
    if d.get("type") != "bundle" or "objects" not in d:
        raise ValueError(f"not a STIX bundle (top-level type={d.get('type')!r})")
    coll = [o for o in d["objects"] if o.get("type") == "x-sparta-collection"]
    if not coll:
        raise ValueError("no x-sparta-collection object — not a SPARTA bundle")
    return d


def summarise(d: dict) -> dict:
    objs = d["objects"]
    coll = next(o for o in objs if o["type"] == "x-sparta-collection")
    types: dict[str, int] = {}
    for o in objs:
        types[o["type"]] = types.get(o["type"], 0) + 1
    ids = []
    for o in objs:
        if o["type"] != "attack-pattern":
            continue
        for r in o.get("external_references", []):
            if r.get("source_name", "").lower().startswith("sparta"):
                ids.append(r.get("external_id"))
                break
    return {
        "sparta_version": coll.get("x_sparta_version"),
        "collection_modified": coll.get("modified"),
        "n_objects": len(objs),
        "object_types": dict(sorted(types.items(), key=lambda kv: -kv[1])),
        "n_attack_patterns": len(ids),
        "n_parent_techniques": sum(1 for i in ids if i and "." not in i),
        "n_sub_techniques": sum(1 for i in ids if i and "." in i),
    }


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--out-dir", default=DEFAULT_OUT)
    p.add_argument("--check", action="store_true",
                   help="validate the bundle already on disk against its "
                        "sidecar; do not download")
    args = p.parse_args()

    bundle = os.path.join(args.out_dir, BUNDLE_NAME)
    meta_path = bundle + ".meta.json"

    if args.check:
        if not os.path.exists(bundle):
            sys.exit(f"no bundle at {bundle} — run without --check first")
        raw = open(bundle, "rb").read()
        got = hashlib.sha256(raw).hexdigest()
        meta = json.load(open(meta_path))
        ok = got == meta["sha256"]
        print(f"{bundle}\n  sha256 on disk {got}\n  sha256 recorded {meta['sha256']}"
              f"\n  {'OK — unchanged' if ok else 'MISMATCH — bundle differs from its sidecar'}")
        sys.exit(0 if ok else 1)

    print(f"GET {ENDPOINT}")
    with urllib.request.urlopen(ENDPOINT, timeout=TIMEOUT_S) as resp:
        raw = resp.read()
    d = validate(raw)
    summary = summarise(d)

    os.makedirs(args.out_dir, exist_ok=True)
    with open(bundle, "wb") as f:
        f.write(raw)
    meta = {
        "source": ENDPOINT,
        "fetched_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "ticket": "AINOS3-96",
        **summary,
    }
    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2)

    print(f"wrote {bundle} ({len(raw):,} bytes)")
    print(f"wrote {meta_path}")
    print(f"\nSPARTA {summary['sparta_version']} "
          f"(collection modified {summary['collection_modified']})")
    print(f"  {summary['n_objects']:,} objects: {summary['object_types']}")
    print(f"  {summary['n_attack_patterns']} attack-patterns "
          f"= {summary['n_parent_techniques']} parent "
          f"+ {summary['n_sub_techniques']} sub-techniques")


if __name__ == "__main__":
    main()
