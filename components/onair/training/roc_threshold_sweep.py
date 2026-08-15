#!/usr/bin/env python3
"""Per-mode detection-vs-false-alarm curve for the IF alarm threshold.

Why this exists
---------------
`recalibrate_heldout.py` showed the deployed INERTIAL threshold produces a
**6.88 %** false-alarm rate on held-out nominal flight (vs 0.00–0.23 % in the
other three modes), and that re-picking it at any target <= 0.1 % drives that to
**0.00 %**. That looks like a free win — and it is exactly the shape of result
that should not be trusted on its own.

Tightening a threshold ALWAYS reduces false alarms. A threshold of -inf scores a
perfect 0.00 % in every mode and detects nothing, ever. So a false-alarm sweep
measured on quiet data cannot choose an operating point; it only ever tells you
which end of the dial is quieter.

This script supplies the missing half: at each candidate threshold it also
measures how much of a real attack the detector still flags. Only the pair
(false-alarm rate, detection rate) identifies an operating point.

Data, and which half is held out from what
------------------------------------------
- **False alarms** come from the AINOS3-81 7 h nominal soak, split exactly as in
  `recalibrate_heldout.py`: thresholds are picked on part A, false alarms are
  measured on part B. Part B chose nothing.
- **Detection** comes from the AINOS3-30 weak-class attack corpus (17 attacks,
  2026-08-11) — corruption-window frames only, as marked by the run manifests.
  The IF trains on nominal only, so no attack frame was ever fitted.

Detection is reported frame-level (the fraction of an attack's corruption frames
that flag), matching the "catch rate" column in `V5_DETECTOR_COVERAGE.md`. Note
the operational metric is *incident*-level, which is far more forgiving — an
attack counts as caught if it raises even one alert — so the frame-level numbers
here are a conservative lower bound on operational impact.

Caveat worth carrying: this corpus was deliberately biased toward the attacks the
classifier is WORST at, so the absolute detection rates are pessimistic relative
to the full SPARTA set. The comparison ACROSS thresholds is the deliverable; the
absolute level is not comparable to the published per-technique catch rates.

Usage
-----
    ~/.virtualenvs/nos3/bin/python \\
        components/onair/training/roc_threshold_sweep.py \\
        --out-json data/onair/models/roc_threshold_sweep.json
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import pickle
import shutil
import sys
import tempfile

import numpy as np
import pandas as pd

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, THIS_DIR)
from features import build_features                   # noqa: E402
from loader import load, load_with_labels             # noqa: E402

DEFAULT_MODEL = "data/onair/models/iforest_per_mode_v5_invariant_bolstered.pkl"
CODE_TO_MODE = {0: "MODE_PASSIVE", 1: "MODE_BDOT",
                2: "MODE_SUNSAFE", 3: "MODE_INERTIAL"}


def add_mode(df: pd.DataFrame, col: str = "__adcs_mode") -> np.ndarray:
    if col in df.columns:
        return df[col].to_numpy()
    codes = pd.to_numeric(df["ADCS_GNC.Mode"], errors="coerce")
    return codes.map(CODE_TO_MODE).fillna("MODE_UNKNOWN").to_numpy()


def score(df: pd.DataFrame, models: dict, schema: dict, modes: np.ndarray) -> np.ndarray:
    drop = [c for c in df.columns if c.startswith("__")]
    X, _ = build_features(df.drop(columns=drop), include_deltas=True, schema=schema)
    out = np.full(len(df), np.nan)
    for scn, mdl in models.items():
        m = (modes == scn)
        if m.any():
            out[m] = mdl.decision_function(X[m])
    return out


def main() -> None:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--model", default=DEFAULT_MODEL)
    p.add_argument("--soak-glob", default="csv_out_2026-08-11T06-05-26*.csv")
    p.add_argument("--soak-dir", default="data/onair/csv")
    p.add_argument("--attack-csv-dir", default="data/onair/csv_ainos3_30_s27")
    p.add_argument("--attack-manifest-dir", default="data/onair/scenarios_ainos3_30_s27")
    p.add_argument("--calib-frac", type=float, default=0.6)
    p.add_argument("--mode-entry-skip", type=int, default=700)
    p.add_argument("--targets", default="0.0001,0.0005,0.001,0.005,0.01")
    p.add_argument("--only-mode", default="",
                   help="Restrict to one mode (e.g. MODE_SUNSAFE) for a fine sweep.")
    p.add_argument("--per-technique", action="store_true",
                   help="Also break detection down per attack technique. The "
                        "aggregate frame rate can be carried by one or two "
                        "long-dwell attacks; this shows whether an operating "
                        "point's gain is broad or concentrated.")
    p.add_argument("--out-json", default="data/onair/models/roc_threshold_sweep.json")
    args = p.parse_args()

    with open(args.model, "rb") as f:
        bundle = pickle.load(f)
    models, schema = bundle["models"], bundle["schema"]
    deployed = json.load(open(os.path.splitext(args.model)[0] + ".calibration.json"))

    # ── nominal (soak) ──────────────────────────────────────────────────
    paths = sorted(glob.glob(os.path.join(args.soak_dir, args.soak_glob)))
    tmp = tempfile.mkdtemp(prefix="roc_")
    try:
        for s in paths:
            os.symlink(os.path.abspath(s), os.path.join(tmp, os.path.basename(s)))
        soak, _ = load(csv_dir=tmp, skip_warmup_rows=30)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    soak_modes = add_mode(soak)
    soak_scores = score(soak, models, schema, soak_modes)
    print(f"soak: {len(soak)} frames")

    # ── attack corpus ───────────────────────────────────────────────────
    mans = sorted(glob.glob(os.path.join(args.attack_manifest_dir, "manifest_*.json")))
    atk, _ = load_with_labels(csv_dir=args.attack_csv_dir, manifest=mans,
                              drop_unlabeled=True, skip_warmup_rows=30)
    atk_modes = add_mode(atk)
    atk_ids = atk["__attack_id"].astype(str).to_numpy()
    is_attack = (atk_ids != "")
    atk_scores = score(atk, models, schema, atk_modes)
    print(f"attack corpus: {len(atk)} frames, {int(is_attack.sum())} corruption-window frames")

    targets = [float(t) for t in args.targets.split(",") if t.strip()]
    result = {
        "provenance": "false alarms = held-out part B of the AINOS3-81 nominal "
                      "soak (chose nothing); detection = corruption-window frames "
                      "of the AINOS3-30 attack corpus (never fitted — the IF "
                      "trains on nominal only). Detection is frame-level; the "
                      "operational metric is incident-level and more forgiving.",
        "caveat": "the attack corpus is biased toward the weakest-detected "
                  "techniques, so absolute detection is pessimistic; compare "
                  "ACROSS thresholds, not against published catch rates.",
        "modes": {},
    }

    wanted = [args.only_mode] if args.only_mode else sorted(models)
    for scn in wanted:
        sm = (soak_modes == scn)
        idx = np.flatnonzero(sm)
        if len(idx) > args.mode_entry_skip * 2:
            idx = idx[args.mode_entry_skip:]
        s_all = soak_scores[idx]
        cut = int(len(s_all) * args.calib_frac)
        part_a, part_b = s_all[:cut], s_all[cut:]

        am = (atk_modes == scn) & is_attack
        a_scores = atk_scores[am]
        a_ids = atk_ids[am]
        # Techniques with enough frames in this mode for a per-technique rate
        # to mean anything.
        techs = [t for t in sorted(set(a_ids.tolist()))
                 if int((a_ids == t).sum()) >= 30]

        rows = []
        cand = [("deployed", deployed["thresholds"].get(scn))]
        for t in targets:
            s = np.sort(part_a)
            k = max(1, min(len(s), int(round(t * len(s)))))
            cand.append((f"target {t:g}", float(s[k - 1])))

        for name, thr in cand:
            if thr is None:
                continue
            fp = float((part_b < thr).mean()) if len(part_b) else float("nan")
            det = float((a_scores < thr).mean()) if len(a_scores) else float("nan")
            row = {"label": name, "threshold": thr,
                   "heldout_fp": round(fp, 5),
                   "attack_detection": round(det, 5)}
            if args.per_technique and techs:
                per = {t: round(float((a_scores[a_ids == t] < thr).mean()), 4)
                       for t in techs}
                row["per_technique"] = per
                # How many techniques clear a 50 % frame rate — a breadth measure
                # the aggregate hides, since one long-dwell attack can carry it.
                row["n_tech_over_50pct"] = sum(1 for v in per.values() if v >= 0.5)
                row["n_tech_total"] = len(per)
            rows.append(row)

        result["modes"][scn] = {
            "n_soak_partA": int(len(part_a)), "n_soak_partB": int(len(part_b)),
            "n_attack_frames": int(len(a_scores)), "rows": rows,
        }

        print(f"\n=== {scn}  (nominal partB={len(part_b)}, attack frames={len(a_scores)}) ===")
        hdr = f"{'threshold source':>18}{'value':>12}{'false alarms':>14}{'detection':>12}"
        if args.per_technique and techs:
            hdr += f"{'techs>=50%':>12}"
        print(hdr)
        for r in rows:
            line = (f"{r['label']:>18}{r['threshold']:>12.2e}"
                    f"{r['heldout_fp']*100:>13.4f}%{r['attack_detection']:>11.4f}")
            if "n_tech_over_50pct" in r:
                line += f"{r['n_tech_over_50pct']:>7}/{r['n_tech_total']:<4}"
            print(line)
        if args.per_technique and techs:
            print(f"\n  per-technique detection ({len(techs)} techniques with >=30 "
                  f"frames in {scn}):")
            width = max(len(t) for t in techs)
            print(f"    {'technique':<{width}}" + "".join(
                f"{r['label'].replace('target ',''):>10}" for r in rows if "per_technique" in r))
            for t in techs:
                print(f"    {t:<{width}}" + "".join(
                    f"{r['per_technique'][t]:>10.3f}" for r in rows if "per_technique" in r))

    os.makedirs(os.path.dirname(args.out_json), exist_ok=True)
    with open(args.out_json, "w") as f:
        json.dump(result, f, indent=2)
    print(f"\nwrote {args.out_json}")


if __name__ == "__main__":
    main()
