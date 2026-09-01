#!/usr/bin/env python3
"""AINOS3-122 AC6 — the explicit, frozen class label set.

Single source of truth for the classifier's classes, replacing the implicit
`sorted(df[label_column].unique())`: the class list, the footprint-based names,
the v4 mechanism cross-refs, and — the operational half — which labels are
`excluded` from training (dropped + probe-only deferred) vs `trained`.

The three derived artifacts (classifier_tiers.json, cluster_taxonomy.json,
explanation_catalog.json) are regenerated AGAINST this; they reflect it, they do
not own it. `deferred` rows are the deferred register (each with a trigger +
gating ticket); a re-freeze must resolve or re-confirm every one.

    from label_set import load_label_set, training_excludes, trained_classes
    excl = training_excludes()      # -> ['DE-0003.03', ..., 'IMP-0001', ...]

Run:  python3 components/onair/training/label_set.py            # summary
      python3 components/onair/training/label_set.py --check    # validate vs a corpus
"""
from __future__ import annotations
import argparse, json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
PATH = os.path.join(ROOT, "data/onair/models/label_set.json")


def load_label_set(path: str = PATH) -> dict:
    with open(path) as f:
        return json.load(f)


def _rows(path=PATH):
    return load_label_set(path)["classes"]


def training_excludes(path=PATH) -> list[str]:
    """Labels to pass to train/classifier exclude_labels: status dropped, plus
    probe-only deferred. Derived from the `training` field so it can't drift."""
    return sorted(c["id"] for c in _rows(path) if c["training"] == "excluded")


def trained_classes(path=PATH) -> list[str]:
    """Labels the model is trained on (training == 'trained')."""
    return sorted(c["id"] for c in _rows(path) if c["training"] == "trained")


def deferred(path=PATH) -> list[dict]:
    return [c for c in _rows(path) if c["status"] == "deferred"]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", metavar="NPZ", nargs="?", const="",
                    help="validate label_set ids exactly match a corpus label set "
                         "(default: the deployed OOF labels array)")
    args = ap.parse_args(argv)
    d = load_label_set()
    print(f"{d['counts']} | excludes {len(training_excludes())} | frozen {d['frozen_at']} ({d['source_ticket']})")
    if args.check is not None:
        import numpy as np
        npz = args.check or os.path.join(
            ROOT, "data/onair/models/cluster_rescore/loio_predictions_oof_v3hybrid_full.npz")
        corpus = set(map(str, np.load(npz, allow_pickle=True)["labels"]))
        ids = {c["id"] for c in _rows()}
        extra, missing = sorted(ids - corpus), sorted(corpus - ids)
        if extra or missing:
            print(f"  MISMATCH  in-set-not-corpus={extra}  in-corpus-not-set={missing}")
            return 1
        print(f"  OK — {len(ids)} ids match the corpus label set")
    return 0


if __name__ == "__main__":
    sys.exit(main())
