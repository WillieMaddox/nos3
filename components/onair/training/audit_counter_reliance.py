#!/usr/bin/env python3
"""AINOS3-39 — audit v3's reliance on generic activity counters.

AINOS3-38 SHAP attribution showed v3 keys heavily on generic high-traffic
core-app counters (`CFE_EVS_HK.AppData[*]`, `CFE_ES.CommandCounter`,
`CFE_TBL.*`, `CFE_SB.*`, EVS `MessageSendCounter`). The AppData 16 slots are
ALL cFE core / C&DH apps (no subsystem app), so for a *subsystem* attack those
features can only reflect generic bus/event activity — a possible activity-level
shortcut rather than the attacked subsystem's own telemetry.

Sharp test: DROP the generic-activity feature block, re-run the EXACT v3
3-instance LOIO, and compare overall accuracy + per-class F1 to the baseline.
- accuracy holds  → the generics were REDUNDANT (a shortcut; other features
  already carry the signal).
- accuracy drops  → they carried genuine discriminative signal for those classes.
Per-class F1 deltas localise WHICH techniques actually depend on them.

Reuses the deployed-recipe LOIO machinery from eval_classifier_clusters.py
(same instances, same 894-feature build, same hyper-params from the pickle).
Read-only: writes a JSON report to --out-dir, touches no deployed artifact.
"""
import argparse
import json
import os
import pickle
import re
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from eval_classifier_clusters import (  # noqa: E402
    discover_instances, load_instance, make_clf, per_class_f1)

# Generic core / C&DH bus-activity counters (raw + `d_` delta). REFINED: only
# the AppData slots for the six cFE CORE apps (0=CFE_EVS 1=CFE_SB 2=CFE_ES
# 3=CFE_TIME 4=CFE_TBL 5=SCH) — a subsystem attack can only ever move these as
# generic activity — plus the scalar bus/event counters. The per-app AppData
# slots 6-15 (CI/TO/CI_LAB/TO_LAB/CF/DS/FM/LC/SBN/SC) are KEPT: they are a
# genuine per-app event stream (EX-0008 ATS/RTS keys on AppData[SC], IMP-0006
# theft on AppData[TO]), not a generic shortcut. CFE_TIME's *scalar* counter is
# kept too (genuine target of the clock attacks); only its AppData slot is generic.
GENERIC_RE = re.compile(
    r"^(d_)?(CFE_EVS_HK\.AppData\[[0-5]_\d+\]"
    r"|CFE_EVS_HK\.MessageSendCounter|CFE_EVS_HK\.CommandCounter"
    r"|CFE_ES\.CommandCounter|CFE_TBL\.|CFE_SB\.)")


def loio(data, hp, keep_mask, labels):
    """Run leave-one-instance-out over `data`, restricting to columns keep_mask.
    Returns (overall_accuracy, per_class_f1_dict)."""
    from sklearn.metrics import accuracy_score
    all_true, all_pred = [], []
    for held in range(len(data)):
        Xtr = np.vstack([data[j][0][:, keep_mask] for j in range(len(data)) if j != held])
        ytr = np.concatenate([data[j][1] for j in range(len(data)) if j != held])
        Xte, yte = data[held][0][:, keep_mask], data[held][1]
        clf = make_clf(hp)
        clf.fit(Xtr, ytr)
        ypred = clf.classes_[clf.predict_proba(Xte).argmax(axis=1)]
        all_true.append(yte)
        all_pred.append(ypred)
    yt = np.concatenate(all_true)
    yp = np.concatenate(all_pred)
    f1 = per_class_f1(yt, yp, labels)
    return accuracy_score(yt, yp), f1


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--csv-dir", default="data/onair/csv_corpus_v3stage",
                   help="FROZEN v3 corpus (AINOS3 v3 regen uses this, not live csv)")
    p.add_argument("--manifest-dir", default="data/onair/csv_corpus_v3stage")
    p.add_argument("--classifier", default="data/onair/models/xgb_attack_classifier_v3.pkl")
    p.add_argument("--out-dir", default="/tmp/ainos3_39")
    p.add_argument("--max-iter", type=int, default=0,
                   help="override HistGB max_iter for a faster RELATIVE audit "
                        "(0 = use the deployed v3 value, 300). The baseline-vs-drop "
                        "delta is stable under a lighter fit; absolute acc is lower.")
    args = p.parse_args()

    t0 = time.time()
    os.makedirs(args.out_dir, exist_ok=True)
    with open(args.classifier, "rb") as f:
        v3 = pickle.load(f)
    schema = v3["schema"]
    hp = v3["clf"].get_params()
    if args.max_iter:
        hp["max_iter"] = args.max_iter
        print(f"[audit] max_iter overridden to {args.max_iter} for a fast relative run")
    allowed = set(v3["labels"])
    fn = schema["feature_names"]
    n_feat = len(fn)

    generic_idx = [i for i, name in enumerate(fn) if GENERIC_RE.search(name)]
    keep_all = np.ones(n_feat, dtype=bool)
    keep_drop = keep_all.copy()
    keep_drop[generic_idx] = False
    print(f"v3 recipe: {n_feat} features; generic-activity block = "
          f"{len(generic_idx)} features ({len(generic_idx)*100//n_feat}%) dropped in the test arm")

    instances = discover_instances(args.manifest_dir)
    print(f"discovered {len(instances)} instances: {[len(m) for m in instances]} manifests each")
    data = []
    for i, manifests in enumerate(instances):
        X, y, meta = load_instance(args.csv_dir, manifests, schema, allowed)
        assert X.shape[1] == n_feat, f"feature mismatch {X.shape[1]} != {n_feat}"
        data.append((X, y, meta))
        print(f"  instance {i}: X={X.shape} classes={len(set(y))}")
    labels = sorted(set().union(*[set(y) for _, y, _ in data]))

    print("\n=== LOIO baseline (all features) ===")
    acc_base, f1_base = loio(data, hp, keep_all, labels)
    print(f"overall accuracy = {acc_base:.4f}")
    print("\n=== LOIO drop generic-activity block ===")
    acc_drop, f1_drop = loio(data, hp, keep_drop, labels)
    print(f"overall accuracy = {acc_drop:.4f}   (Δ {acc_drop-acc_base:+.4f})")

    # per-class F1 deltas, most-negative (most reliant) first
    rows = []
    for lbl in labels:
        b, d = f1_base.get(lbl, 0.0), f1_drop.get(lbl, 0.0)
        rows.append((lbl, b, d, d - b))
    rows.sort(key=lambda r: r[3])
    print("\nper-class F1 (baseline -> drop, Δ), most-reliant first:")
    for lbl, b, d, delta in rows:
        flag = "  <== relies on generics" if delta <= -0.05 else ""
        print(f"  {lbl:20s} {b:.3f} -> {d:.3f}  ({delta:+.3f}){flag}")

    report = {
        "overall": {"baseline": acc_base, "drop_generic": acc_drop,
                    "delta": acc_drop - acc_base},
        "n_generic_dropped": len(generic_idx),
        "generic_features": [fn[i] for i in generic_idx],
        "per_class_f1": [{"label": l, "baseline": b, "drop": d, "delta": dl}
                         for l, b, d, dl in rows],
        "elapsed_s": time.time() - t0,
    }
    out = os.path.join(args.out_dir, "counter_reliance_audit.json")
    with open(out, "w") as f:
        json.dump(report, f, indent=2)
    print(f"\nwrote {out}  ({report['elapsed_s']:.0f}s)")


if __name__ == "__main__":
    main()
