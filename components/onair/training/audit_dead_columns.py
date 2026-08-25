#!/usr/bin/env python3
"""Find telemetry columns that never carry information (AINOS3-91, generalised).

Motivation: `ST_DEV.*` sat at the never-received sentinel `[0]` for the entire
corpus and nobody noticed, which hid the fact that the star tracker was disabled
and therefore that INERTIAL mode performed no closed-loop control (AINOS3-86).
That was found by accident. This finds the rest on purpose.

Three verdicts, in descending severity:

  NEVER_RECEIVED  every row is the `[0]` sentinel — the MID never arrived at
                  OnAIR at all. An entire packet in this state means a device or
                  app is silent, not that a field is boring.
  ALL_ZERO        received, but every sample is zero (scalar 0, or an array of
                  zeros). A device reporting, but reporting nothing.
  CONSTANT        received and non-zero, but never changes. Often legitimate
                  (mounting quaternions, table sizes, config); flagged because
                  a *feature* built on one contributes nothing to a model.

⚠ A column is dead only if it never varies across the WHOLE corpus — every
session, every ADCS mode, nominal AND attack. Auditing a single nominal session
does not answer the question: it cannot distinguish a genuinely inert field from
a counter that is static in nominal and moves under attack. The latter is not
dead, it is the most useful kind of column there is — `static-in-nominal` is
exactly the precondition rule-gate R6-R13 are built on. So the default is to
pool every `csv_out_*.csv`, and a single `--csv` is the narrow case.

Schemas grew over time (359 -> 382 columns), so columns are unioned across files
and each result records how many files actually contained it. Once a column is
shown to vary anywhere it is dropped from the read set, so later files get
progressively cheaper.

Run:
    python3 components/onair/training/audit_dead_columns.py \\
        [--glob "data/onair/csv/csv_out_*.csv"] [--json out.json] \\
        [--chunksize 100000] [--max-rows N]

With neither --glob nor --csv, pools every csv_out_*.csv in data/onair/csv.
"""
from __future__ import annotations

import argparse
import collections
import glob
import json
import sys

import pandas as pd

# OnAIR writes this when a MID has never been received (see the double-buffer
# note in reference_runbooks): the field keeps its one-element init value.
NEVER_RECEIVED = "[0]"

# A column counts as dead when one value dominates at least this fraction of
# rows. Strict uniqueness is NOT enough: the OnAIR double buffer emits rare
# misaligned frames, and a SINGLE such frame gave every THRUSTER column a second
# distinct value — hiding a device that was disabled in 1,742,103 of 1,742,104
# rows. Dominance finds it; uniqueness does not.
DEFAULT_DOMINANCE = 0.999

# Values that count as "zero" for ALL_ZERO once the sentinel is excluded.
_ZERO_STRINGS = {"0", "0.0", "-0.0", "0.00000", "b''", "", "nan"}


def _is_zeroish(v: str) -> bool:
    if v in _ZERO_STRINGS:
        return True
    if v.startswith("[") and v.endswith("]"):
        inner = v[1:-1].strip()
        if not inner:
            return True
        return all(p.strip() in _ZERO_STRINGS for p in inner.split(","))
    return False


def audit(paths, chunksize: int = 100_000, max_rows: int | None = None,
          value_cap: int = 64, dominance: float = DEFAULT_DOMINANCE,
          verbose: bool = True) -> dict:
    """Pool every file in `paths` and report the columns that never vary.

    Verdicts are decided on the DOMINANT value's share of rows, not on distinct
    counts, so a handful of misaligned double-buffer frames cannot disguise a
    dead column as a live one — a single shifted THRUSTER frame in 1.74M rows
    did exactly that under a uniqueness test.
    """
    if isinstance(paths, str):
        paths = [paths]
    counts: dict[str, collections.Counter] = collections.defaultdict(
        collections.Counter)
    alive: set[str] = set()
    files_with_col: collections.Counter = collections.Counter()
    n_rows = 0
    files_read = 0

    for fi, path in enumerate(paths):
        try:
            file_cols = list(pd.read_csv(path, nrows=0).columns)
        except Exception as exc:
            if verbose:
                print(f"  [skip] {path}: {exc}", file=sys.stderr)
            continue
        for c in file_cols:
            files_with_col[c] += 1
        # Anything already shown to vary somewhere needs no further reading.
        usecols = [c for c in file_cols if c not in alive]
        files_read += 1
        if not usecols:
            continue
        rows_this = 0
        try:
            for chunk in pd.read_csv(path, chunksize=chunksize, usecols=usecols,
                                     low_memory=False, dtype=str,
                                     keep_default_na=False):
                for col in chunk.columns:
                    if col in alive:
                        continue
                    c = counts[col]
                    c.update(chunk[col].to_numpy().tolist())
                    if len(c) > value_cap:
                        alive.add(col)
                        counts.pop(col, None)
                rows_this += len(chunk)
                if max_rows and rows_this >= max_rows:
                    break
        except Exception as exc:
            if verbose:
                print(f"  [partial] {path}: {exc}", file=sys.stderr)
        n_rows += rows_this
        if verbose:
            print(f"  [{fi + 1}/{len(paths)}] {path.split('/')[-1][:46]:48s} "
                  f"rows={rows_this:>8} still-tracked={len(counts)}",
                  file=sys.stderr, flush=True)

    results = {}
    for col, c in counts.items():
        if col in alive or not c:
            continue                                    # varies somewhere
        total = sum(c.values())
        # The sentinel is an absence of data, not a value: a column that is the
        # sentinel early and one constant afterwards is still constant.
        real = collections.Counter({k: v for k, v in c.items()
                                    if k != NEVER_RECEIVED})
        if not real:
            verdict, dom, share = "NEVER_RECEIVED", NEVER_RECEIVED, 1.0
        else:
            dom, dom_n = real.most_common(1)[0]
            share = dom_n / sum(real.values())
            if share < dominance:
                continue                                # genuinely varying
            verdict = "ALL_ZERO" if _is_zeroish(dom) else "CONSTANT"
        results[col] = {
            "verdict": verdict,
            "dominant": dom[:80],
            "dominant_share": round(share, 6),
            "n_distinct": len(c),
            "n_outlier_rows": (total - c[dom]) if dom in c else 0,
            "sentinel_present": NEVER_RECEIVED in c,
            "files_containing_column": files_with_col[col],
        }

    packets: dict[str, dict] = {}
    all_cols = sorted(set(counts) | alive)
    for col in all_cols:
        pkt = col.split(".")[0]
        p = packets.setdefault(pkt, {"total": 0, "NEVER_RECEIVED": 0,
                                     "ALL_ZERO": 0, "CONSTANT": 0})
        p["total"] += 1
        if col in results:
            p[results[col]["verdict"]] += 1
    for pkt, p in packets.items():
        dead = p["NEVER_RECEIVED"] + p["ALL_ZERO"] + p["CONSTANT"]
        p["dead"] = dead
        p["fully_dead"] = dead == p["total"]
        p["fully_never_received"] = p["NEVER_RECEIVED"] == p["total"]

    return {"files": list(paths), "files_read": files_read,
            "rows_scanned": n_rows, "n_columns": len(all_cols),
            "columns": results, "packets": packets}


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--csv", default=None,
                   help="audit a SINGLE session (narrow case — see the warning "
                        "in the module docstring)")
    p.add_argument("--glob", default=None,
                   help="shell glob of sessions to pool (default: every "
                        "csv_out_*.csv under data/onair/csv)")
    p.add_argument("--chunksize", type=int, default=100_000)
    p.add_argument("--max-rows", type=int, default=None)
    p.add_argument("--dominance", type=float, default=DEFAULT_DOMINANCE,
                   help="a column is dead when one value holds at least this "
                        "share of non-sentinel rows (default %(default)s)")
    p.add_argument("--json", default=None)
    args = p.parse_args()

    if args.csv:
        paths = [args.csv]
    else:
        paths = sorted(glob.glob(args.glob or "data/onair/csv/csv_out_*.csv"))
    if not paths:
        sys.exit("no csv_out_*.csv found")

    r = audit(paths, args.chunksize, args.max_rows, dominance=args.dominance)
    cols, pkts = r["columns"], r["packets"]
    scope = (paths[0] if len(paths) == 1
             else f"{r['files_read']} sessions pooled (nominal + attack, all modes)")
    print(f"{scope}\n{r['rows_scanned']} rows x {r['n_columns']} columns\n")

    order = ["NEVER_RECEIVED", "ALL_ZERO", "CONSTANT"]
    counts = collections.Counter(c["verdict"] for c in cols.values())
    print("summary: " + "  ".join(f"{v}={counts.get(v, 0)}" for v in order)
          + f"  alive={r['n_columns'] - len(cols)}")

    dead_pkts = sorted(k for k, v in pkts.items() if v["fully_dead"])
    if dead_pkts:
        print(f"\n⚠ FULLY DEAD PACKETS ({len(dead_pkts)}) — every column carries "
              f"no information:")
        for k in dead_pkts:
            v = pkts[k]
            tag = ("never received" if v["fully_never_received"]
                   else f"NR={v['NEVER_RECEIVED']} ZERO={v['ALL_ZERO']} "
                        f"CONST={v['CONSTANT']}")
            print(f"    {k:16s} {v['total']:3d} cols — {tag}")

    for verdict in order:
        hits = {k: v for k, v in cols.items() if v["verdict"] == verdict}
        if not hits:
            continue
        print(f"\n── {verdict} ({len(hits)}) " + "─" * 40)
        for k in sorted(hits):
            h = hits[k]
            odd = (f"  ({h['n_outlier_rows']} outlier row(s))"
                   if h["n_outlier_rows"] else "")
            print(f"    {k:46s} {h['dominant'][:44]}{odd}")

    if args.json:
        with open(args.json, "w") as f:
            json.dump(r, f, indent=2)
        print(f"\nwrote {args.json}")


if __name__ == "__main__":
    main()
