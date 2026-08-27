#!/usr/bin/env python3
"""AINOS3-121 — offline IF-audit harness: is an IF null trustworthy for design use?

An isolation-forest 0-anomaly result ("the detector didn't flag this") only backs an
OPERATIONAL coverage statement on its own. Before it can back a DESIGN/mechanistic claim
("this attack is fundamentally undetectable", "because feature X ..."), the model must be
shown to be a trustworthy oracle for that judgement. This tool is that check.

It runs three things against a **golden capture** — the exact per-frame feature vectors the
deployed plugin scored, saved to an .npz by the isolation_forest plugin's `GoldenCaptureEvery`
(set it >0 in the ini, restart OnAIR, capture, set back to 0):

  AC1 reproduce : offline `decision_function(features)` must match the live score to ~0.
                  If it doesn't, nothing else here is trustworthy — the feature pipeline is
                  not reproduced (do NOT reconstruct from CSV; use the captured vector).
  AC2 respond   : per feature (or feature group) a null rests on, hold each mode's nominal
                  baselines and perturb only that group; report the % pushed anomalous. A
                  responsive-but-still-0% group => a TRUE coverage gap. Also a positive
                  control (+1e6 on the mode's top-N split features) that MUST be high, else
                  the model/threshold is inert and every null in that mode is meaningless.
  AC3 calibrate : per mode, the detection margin (median nominal score - threshold) and the
                  post-warmup live FP, cross-checked against the calibration diagnostics. A
                  mode with a huge margin + tiny calibration sample is inert (flag it).

Standing rule (AC5): an IF null backs an OPERATIONAL claim immediately; it backs a
DESIGN/mechanistic claim only after AC1 reproduces and AC2 shows the feature is responsive
AND the mode's positive control is high. Cite this tool's output when you do.

Run:
    python3 components/onair/training/if_audit.py --golden <iforest_golden_*.npz> \
        [--model <pkl>] [--warmup 30]

Groups probed by default mirror the AINOS3-118 gaps (position / MAG / IMU); add your own
with --group NAME=col1,col2,...=value .
"""
from __future__ import annotations
import argparse, collections, glob, json, os, pickle, sys
import numpy as np

DEF_MODEL = "data/onair/models/iforest_per_mode_v5_invariant_bolstered.pkl"
DEF_GROUPS = {  # name -> (feature-name templates, spoof value)
    "POSITION": ([f"d_NOVATEL.Novatel_oem615.ECEF{a}" for a in "XYZ"], 5e6),
    "MAG": ([f"ADCS_DI.Payload.Mag.bvb[{a}]" for a in range(3)]
            + [f"d_ADCS_DI.Payload.Mag.bvb[{a}]" for a in range(3)], 0.05),
    "IMU": ([f"ADCS_DI.Payload.Imu.wbn[{a}]" for a in range(3)]
            + [f"d_ADCS_DI.Payload.Imu.wbn[{a}]" for a in range(3)], 100.0),
}


def load_golden(path):
    # savez overwrites in place; retry to dodge a mid-write read.
    import shutil, time
    for _ in range(15):
        try:
            tmp = path + ".read"
            shutil.copy(path, tmp)
            d = np.load(tmp, allow_pickle=True)
            _ = d["features"].shape
            return d
        except Exception:
            time.sleep(2)
    raise SystemExit(f"could not read {path} cleanly (still being written?)")


def top_features(model, k):
    c = collections.Counter()
    for t in model.estimators_:
        for f in t.tree_.feature:
            if f >= 0:
                c[f] += 1
    return [f for f, _ in c.most_common(k)]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--golden", help="iforest_golden_*.npz (default: newest under data/onair/csv)")
    ap.add_argument("--model", default=DEF_MODEL)
    ap.add_argument("--warmup", type=int, default=30)
    ap.add_argument("--topn", type=int, default=100)
    ap.add_argument("--group", action="append", default=[],
                    help="extra NAME=col1,col2=value")
    args = ap.parse_args(argv)

    gpath = args.golden or max(glob.glob("data/onair/csv/iforest_golden_*.npz"),
                               key=os.path.getmtime, default=None)
    if not gpath:
        raise SystemExit("no golden capture found — enable GoldenCaptureEvery and restart OnAIR")
    d = load_golden(gpath)
    obj = pickle.load(open(args.model, "rb"))
    models = obj["models"]
    feats, scn, live, thr_arr = d["features"], d["scenario"], d["score"], d["threshold"]
    fidx = d["frame_idx"]
    fn = list(d["feature_names"]); idx = {f: i for i, f in enumerate(fn)}
    cal = None
    calp = args.model + ".calibration.json"
    if os.path.exists(calp):
        cal = json.load(open(calp))

    groups = dict(DEF_GROUPS)
    for g in args.group:
        name, cols, val = g.split("=")
        groups[name] = ([c.strip() for c in cols.split(",")], float(val))

    print(f"golden: {gpath}\nframes: {len(scn)}  by mode: {dict(collections.Counter(scn.tolist()))}\n")

    # AC1
    err = max(abs(float(models[str(scn[i])].decision_function(feats[i].reshape(1, -1))[0]) - live[i])
              for i in range(len(scn)))
    print(f"AC1 reproduce: max |offline-live| = {err:.2e}  -> {'PASS' if err < 1e-6 else 'FAIL'}\n")

    # AC2 + AC3 per mode
    hdr = f"{'mode':11}{'n':>4}{'margin':>8}{'liveFP':>7}{'posctl':>7}  " + \
          "".join(f"{g:>9}" for g in groups)
    print(hdr)
    verdicts = {}
    for mode in sorted(set(scn.tolist())):
        m = models[mode]
        th = cal["thresholds"][mode] if cal else float(thr_arr[scn == mode][0])
        mask = (scn == mode) & (fidx >= args.warmup)
        rows = feats[mask]
        if len(rows) == 0:
            continue
        dfun = lambda x: float(m.decision_function(x.reshape(1, -1))[0])
        nom = [r for r in rows if dfun(r) >= th]
        margin = float(np.median([dfun(r) for r in rows]) - th)
        liveFP = 100.0 * np.mean([s < th for s in live[mask]])
        top = top_features(m, args.topn)
        def frac(mut):
            if not nom:
                return float("nan")
            return 100.0 * sum(1 for r in nom if dfun(mut(r.copy())) < th) / len(nom)
        def add_top(x):
            for i in top:
                x[i] += 1e6
            return x
        pc = frac(add_top)
        gvals = {}
        for gname, (cols, val) in groups.items():
            ci = [idx[c] for c in cols if c in idx]
            def setg(x, ci=ci, val=val):
                for i in ci:
                    x[i] = val
                return x
            gvals[gname] = frac(setg) if ci else float("nan")
        row = f"{mode.replace('MODE_',''):11}{len(rows):>4}{margin:>+8.3f}{liveFP:>6.1f}%{pc:>6.0f}%  " + \
              "".join(f"{gvals[g]:>8.0f}%" for g in groups)
        print(row)
        verdicts[mode] = dict(margin=margin, posctl=pc, groups=gvals, n=len(rows))

    print("\nmargin=median nominal score - threshold; liveFP=post-warmup; posctl=+1e6 on top-N "
          "(harness sanity, want high); group cols = % of nominal baselines the spoof crosses.")
    print("Interpretation: posctl low (<~20%) => mode inert, its nulls are NOT trustworthy. "
          "posctl high + group 0% => a TRUE coverage gap (feature responsive, attack missed).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
