#!/usr/bin/env python3
"""Rebuild the per-class explanation catalog against the DEPLOYED selective
per-mode hybrid (AINOS3-37), not the v3 global model.

Why this exists as a separate script: `build_explanation_catalog.py` explains one
model. The deployed classifier is three — a global head plus per-mode heads for
INERTIAL and SUNSAFE — and which one scores a frame depends on that frame's ADCS
mode. Explaining the whole corpus with the global head describes a model that is
not running for routed frames.

Routing is mirrored exactly: a frame in a routed mode is explained by that mode's
head, every other frame by the global head. Per-frame SHAP matrices from the
different heads are concatenated before ranking, so a class that spans modes gets
one attribution weighted naturally by how many of its frames each head scored.

Two details that matter:
  - Each head has its own `classes_`, so the target column is resolved PER HEAD.
    A class the routed head never saw falls back to the global head for those
    frames (recorded in `heads_used`), because a head cannot explain a class it
    cannot predict.
  - SHAP values are per-head, but the ranking normalises to fractions of summed
    mean-|SHAP|, so cross-head concatenation is comparable in the way the column
    is actually read ("share of the model's attention").

Usage:
    python3 build_explanation_catalog_hybrid.py \\
        --out ../../../data/onair/models/explanation_catalog.json
"""
from __future__ import annotations

import argparse
import json
import os
import pickle

import numpy as np

try:
    from label_set import training_excludes as _ls_excludes
except Exception:  # label_set.json absent -> backward-compatible no-op
    _ls_excludes = lambda: []

import attribution as A
import eval_classifier_clusters as E
from incident_attribution import format_top_features

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "../../.."))
MODEL = os.path.join(ROOT, "data/onair/models/xgb_attack_classifier_v3_hybrid.pkl")
CSV_DIR = os.path.join(ROOT, "data/onair/csv_corpus_v3stage")
MAN_DIR = os.path.join(ROOT, "data/onair/scenarios")


def col_map(clf, label_to_id):
    """label -> column index in this head's predict_proba output.

    ⚠ The deployed hybrid encodes classes INCONSISTENTLY across its heads: the
    global head's ``classes_`` holds integer label ids (dtype int64) while the
    per-mode heads' hold label strings (dtype object) — an artifact of the two
    being fitted through different paths. Handle both, and raise rather than
    return an empty map: an empty map silently routes every frame to the
    fallback head, which produces a "hybrid" catalog byte-identical to the
    global-only one and looks like a successful run.
    """
    classes = list(clf.classes_)
    if classes and isinstance(classes[0], (str, bytes, np.str_)):
        m = {str(c): i for i, c in enumerate(classes)}
    else:
        id_to_label = {v: k for k, v in label_to_id.items()}
        m = {id_to_label[c]: i for i, c in enumerate(classes) if c in id_to_label}
    if not m:
        raise ValueError(
            f"empty column map for a head with {len(classes)} classes "
            f"(dtype {getattr(clf.classes_, 'dtype', '?')}) — unrecognised "
            f"classes_ representation; refusing to fall back silently")
    return m


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--model", default=MODEL)
    p.add_argument("--out", default=os.path.join(
        ROOT, "data/onair/models/explanation_catalog.json"))
    p.add_argument("--top-n", type=int, default=6)
    p.add_argument("--max-frames", type=int, default=400,
                   help="cap frames per class (SHAP mean is stable at a few hundred)")
    p.add_argument("--instance", type=int, default=0)
    args = p.parse_args()

    art = pickle.load(open(args.model, "rb"))
    global_clf = art["clf"]
    labels, schema = art["labels"], art["schema"]
    feat_names = schema["feature_names"]
    label_to_id = art["label_to_id"]
    mode_heads = art.get("mode_heads", {}) or {}
    route_modes = list(art.get("route_modes", []) or [])
    version = art["config"].get("version", "xgb_v3_hybrid")

    print(f"model      : {os.path.basename(args.model)}  ({version})")
    print(f"route modes: {route_modes or '(none — global only)'}")

    # One explainer + column map per head. Built lazily: TreeExplainer on a
    # HistGB is not free and a head may score no frames in this instance.
    heads = {"__global__": global_clf}
    for m, h in mode_heads.items():
        heads[m] = h
    explainers: dict[str, object] = {}
    colmaps = {name: col_map(clf, label_to_id) for name, clf in heads.items()}

    insts = E.discover_instances(MAN_DIR)
    print(f"loading instance {args.instance} ({len(insts[args.instance])} manifests) ...",
          flush=True)
    X, y, meta = E.load_instance(CSV_DIR, insts[args.instance], schema,
                                 allowed_labels=set(labels) - set(_ls_excludes()))  # AINOS3-122 AC7
    aid, incorr = meta["attack_id"], meta["in_corruption"]
    modes = meta["adcs_mode"]
    print(f"loaded X={X.shape}  modes={sorted(set(modes))}", flush=True)

    slot_map = A.load_appid_slot_map()
    print(f"AppData slot map: {'loaded ' + str(len(slot_map)) + ' slots' if slot_map else 'ABSENT'}",
          flush=True)

    def head_for(mode: str) -> str:
        return mode if (mode in mode_heads and mode in route_modes) else "__global__"

    present = sorted(a for a in set(aid[incorr]) - {""}
                     if a in colmaps["__global__"])
    classes = {}
    for atk in present:
        rows = np.where(incorr & (aid == atk))[0]
        n_all = int(len(rows))
        if n_all > args.max_frames:
            rows = rows[:: max(1, n_all // args.max_frames)][:args.max_frames]

        # Group this class's frames by the head that would score them live.
        by_head: dict[str, list[int]] = {}
        fellback: dict[str, int] = {}
        for r in rows:
            hname = head_for(str(modes[r]))
            # A routed head that never saw this class cannot explain it. Count
            # these — a silent fallback is how a global-only catalog once passed
            # for a hybrid one.
            if hname != "__global__" and atk not in colmaps[hname]:
                fellback[hname] = fellback.get(hname, 0) + 1
                hname = "__global__"
            by_head.setdefault(hname, []).append(int(r))
        for hn, cnt in sorted(fellback.items()):
            print(f"    ! {atk}: {cnt} frames fell back from {hn} "
                  f"(head does not predict this class)", flush=True)

        shap_parts, used = [], {}
        for hname, idx in sorted(by_head.items()):
            clf = heads[hname]
            if hname not in explainers:
                explainers[hname] = A.build_explainer(clf)
            cid = colmaps[hname][atk]
            sf = A.frame_class_shap(explainers[hname], X[idx],
                                    np.full(len(idx), cid, dtype=int))
            shap_parts.append(np.atleast_2d(sf))
            used[hname] = len(idx)

        top = A.aggregate_incident(np.vstack(shap_parts), feat_names,
                                   top_n=args.top_n, appid_slot_map=slot_map)
        classes[atk] = {
            "n_frames": n_all,
            "heads_used": used,
            "top_features": top,
            "top_features_str": format_top_features(top),
        }
        hs = "+".join(f"{k.replace('MODE_', '').replace('__global__', 'global')}:{v}"
                      for k, v in sorted(used.items()))
        print(f"  {atk:14s} [{hs}] {classes[atk]['top_features_str']}", flush=True)

    catalog = {
        "meta": {
            "model": version,
            "model_file": os.path.basename(args.model),
            "route_modes": route_modes,
            "routing": "per-frame: a frame in a routed mode is explained by that "
                       "mode's head, all others by the global head; a class a "
                       "routed head never saw falls back to global (see "
                       "classes[*].heads_used).",
            "corpus": os.path.basename(CSV_DIR),
            "instance": args.instance,
            "agg": "max",
            "top_n": args.top_n,
            "max_frames": args.max_frames,
            "appdata_resolved": slot_map is not None,
            "note": "faithful ranking; generic activity counters may top the list "
                    "(AINOS3-38). Attack-specific field is within top-N. "
                    "AINOS3-48: CFE_EVS_HK.AppData resolved to AppData[<app>].<field> "
                    "via cfe_appid_crosswalk.json (per-app-per-field, so a widely-"
                    "distributed EVS signal may occupy several top-N slots). "
                    "Percentages are each field's share of summed mean-|SHAP| over "
                    "ALL fields, so the displayed top-N need not total 100%.",
        },
        "classes": classes,
    }
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w") as f:
        json.dump(catalog, f, indent=2)
    print(f"\nwrote {len(classes)} classes -> {args.out}", flush=True)


if __name__ == "__main__":
    main()
