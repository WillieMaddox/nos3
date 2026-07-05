"""NOS3-312 — build the per-class explanation catalog (offline).

The live OnAIR plugin runtime has no shap, so per-incident SHAP can't run live.
Instead we precompute, per classifier class, the top-N telemetry fields that
drive that class (SHAP over the class's corruption frames in the frozen corpus)
and ship it as a JSON artifact. The plugin/demo then look up the predicted
class's explanation — no shap dependency in flight software.

    python3 build_explanation_catalog.py \
        --out ../../../data/onair/models/explanation_catalog.json

Faithful-ranking caveat (see NOS3-311): entries reflect the model's real drivers,
which are often generic activity counters with the attack-specific field beneath.
"""
import argparse
import json
import os
import pickle

import numpy as np

import attribution as A
import eval_classifier_clusters as E
from incident_attribution import format_top_features

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "../../.."))
MODEL = os.path.join(ROOT, "data/onair/models/xgb_attack_classifier_v3.pkl")
CSV_DIR = os.path.join(ROOT, "data/onair/csv_corpus_v3stage")
MAN_DIR = os.path.join(ROOT, "data/onair/scenarios")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", default=os.path.join(
        ROOT, "data/onair/models/explanation_catalog.json"))
    p.add_argument("--top-n", type=int, default=6)
    p.add_argument("--max-frames", type=int, default=400,
                   help="cap frames per class (SHAP mean is stable at a few hundred)")
    p.add_argument("--instance", type=int, default=0)
    args = p.parse_args()

    art = pickle.load(open(MODEL, "rb"))
    clf, labels, schema = art["clf"], art["labels"], art["schema"]
    feat_names = schema["feature_names"]
    label_to_id = art["label_to_id"]
    col_of_id = {c: i for i, c in enumerate(clf.classes_)}
    cls_col = {lbl: col_of_id[label_to_id[lbl]] for lbl in labels
               if label_to_id[lbl] in col_of_id}

    insts = E.discover_instances(MAN_DIR)
    print(f"loading instance {args.instance} ({len(insts[args.instance])} manifests) ...",
          flush=True)
    X, y, meta = E.load_instance(CSV_DIR, insts[args.instance], schema,
                                 allowed_labels=set(labels))
    print(f"loaded X={X.shape}", flush=True)
    aid, incorr = meta["attack_id"], meta["in_corruption"]
    present = sorted(a for a in set(aid[incorr]) - {""} if a in cls_col)

    explainer = A.build_explainer(clf)
    classes = {}
    for atk in present:
        rows = np.where(incorr & (aid == atk))[0]
        n_all = int(len(rows))
        if n_all > args.max_frames:
            rows = rows[:: max(1, n_all // args.max_frames)][:args.max_frames]
        top = A.explain_incident(clf, feat_names, X[rows],
                                 target_class_id=cls_col[atk],
                                 explainer=explainer, top_n=args.top_n)
        classes[atk] = {
            "n_frames": n_all,
            "top_features": top,
            "top_features_str": format_top_features(top),
        }
        print(f"  {atk:14s} {classes[atk]['top_features_str']}", flush=True)

    catalog = {
        "meta": {
            "model": art["config"].get("version", "xgb_v3"),
            "corpus": os.path.basename(CSV_DIR),
            "instance": args.instance,
            "agg": "max",
            "top_n": args.top_n,
            "max_frames": args.max_frames,
            "note": "faithful ranking; generic activity counters may top the list "
                    "(NOS3-311). Attack-specific field is within top-N.",
        },
        "classes": classes,
    }
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w") as f:
        json.dump(catalog, f, indent=2)
    print(f"\nwrote {len(classes)} classes -> {args.out}", flush=True)


if __name__ == "__main__":
    main()
