"""AINOS3-38 validation — run attribution on real attacks from the frozen v3
corpus and print the top telemetry fields per attack, so they can be checked
against each attack's known SPARTA footprint.

    python3 validate_attribution.py            # default: ROBUST-tier attacks
    python3 validate_attribution.py EX-0012.07 DE-0003.02
"""
import os
import pickle
import sys

import numpy as np

import attribution as A
import eval_classifier_clusters as E

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "../../.."))
MODEL = os.path.join(ROOT, "data/onair/models/xgb_attack_classifier_v3.pkl")
CSV_DIR = os.path.join(ROOT, "data/onair/csv_corpus_v3stage")
MAN_DIR = os.path.join(ROOT, "data/onair/scenarios")

# ROBUST tier — cleanest-classified, strongest footprint check (V5 §4).
DEFAULT_TARGETS = ["EX-0008.02", "DE-0003.01", "IMP-0005", "DE-0003.10"]


def main(targets):
    art = pickle.load(open(MODEL, "rb"))
    clf, labels, schema = art["clf"], art["labels"], art["schema"]
    feat_names = schema["feature_names"]
    # clf.classes_ are integer class IDs; map attack label -> shap class column.
    label_to_id = art["label_to_id"]
    col_of_id = {c: i for i, c in enumerate(clf.classes_)}
    cls_index = {lbl: col_of_id[label_to_id[lbl]]
                 for lbl in labels if label_to_id[lbl] in col_of_id}

    insts = E.discover_instances(MAN_DIR)
    print(f"instances: {len(insts)}; loading instance 0 ({len(insts[0])} manifests) ...",
          flush=True)
    X, y, meta = E.load_instance(CSV_DIR, insts[0], schema, allowed_labels=set(labels))
    print(f"loaded X={X.shape}", flush=True)
    aid, incorr = meta["attack_id"], meta["in_corruption"]
    present = sorted(set(aid[incorr]) - {""})
    print(f"{len(present)} attacks have corruption frames in instance 0\n", flush=True)

    explainer = A.build_explainer(clf)
    for atk in targets:
        if atk not in cls_index:
            print(f"{atk}: not a classifier label — skip\n"); continue
        if atk not in present:
            print(f"{atk}: no corruption frames in instance 0 — skip\n"); continue
        sel = incorr & (aid == atk)
        top = A.explain_incident(clf, feat_names, X[sel],
                                 target_class_id=cls_index[atk],
                                 explainer=explainer, top_n=6)
        print(f"{atk}  ({int(sel.sum())} corruption frames)  top fields:")
        for r in top:
            d = " (Δ)" if r["delta_dominant"] else ""
            print(f"   {r['frac']*100:5.1f}%  {r['field']}{d}")
        print(flush=True)


if __name__ == "__main__":
    main(sys.argv[1:] or DEFAULT_TARGETS)
