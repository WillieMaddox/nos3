#!/usr/bin/env python3
"""Tests for retrain_clean_corpus — the AINOS3-101 retrain harness.

The load-and-fit path needs a real corpus, so what is pinned here is everything
that decides *what gets compared to what*. A defect in any of these produces a
plausible number rather than an error, which is the failure mode this ticket
exists to avoid:

  1. **Recipe parity with v3.** v3's pickled schema suppresses the raw values of
     22 absolute-time / orbital columns so the model cannot learn the sim epoch
     and TLE. `eval_classifier_clusters.py` inherits them by passing v3's schema
     to `build_features`; this script derives a FRESH schema (schema-v1 is 470
     columns, v3's corpus was 360) and so must re-apply the mask by hand. It did
     not, at first — and a retrain that reads absolute time differs from v3 in
     RECIPE as well as data, which is the confound AC3 exists to exclude.
  2. **Fold membership.** Folds set the `min` that sets the tier. They must come
     from the declared (mode, instance) in the corpus manifest.
  3. **Mode scope.** The AC3 control is exactly "same scope, different data", so
     the filter has to select rows and nothing else.
"""
import importlib.util
import json
import os
import pickle
import sys

import numpy as np
import pandas as pd
import pytest

THIS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(THIS)))
sys.path.insert(0, THIS)

_spec = importlib.util.spec_from_file_location(
    "retrain_clean_corpus", os.path.join(THIS, "retrain_clean_corpus.py"))
rc = importlib.util.module_from_spec(_spec)
sys.modules["retrain_clean_corpus"] = rc
_spec.loader.exec_module(rc)

from features import V5_DELTA_ONLY_COLUMNS, build_features  # noqa: E402

V3_PKL = os.path.join(ROOT, "data/onair/models/xgb_attack_classifier_v3.pkl")


# ───────────────────── 1. recipe parity with the v3 model ─────────────────────

@pytest.mark.skipif(not os.path.exists(V3_PKL), reason="v3 pickle not present")
def test_v5_preset_matches_the_deployed_v3_schema():
    """The mask this script applies must be the mask v3 was trained under.

    If these ever diverge, a 'data-only' comparison silently becomes a
    recipe-and-data comparison.
    """
    with open(V3_PKL, "rb") as f:
        v3 = pickle.load(f)
    assert sorted(v3["schema"]["delta_only_columns"]) == sorted(V5_DELTA_ONLY_COLUMNS)


def test_delta_only_suppresses_raw_and_keeps_the_delta():
    """The contract the retrain depends on: a masked column contributes its
    delta and NOT its absolute value."""
    col = V5_DELTA_ONLY_COLUMNS[0]
    df = pd.DataFrame({
        "__file_id": ["f"] * 4,
        col: [100.0, 101.0, 102.0, 103.0],
        "KEEP": [1.0, 2.0, 3.0, 4.0],
    })
    X, sch = build_features(df, include_deltas=True,
                            delta_only=list(V5_DELTA_ONLY_COLUMNS))
    assert col not in sch.feature_names, "absolute value must be masked"
    assert f"d_{col}" in sch.feature_names, "its delta must survive"
    assert "KEEP" in sch.feature_names and "d_KEEP" in sch.feature_names
    assert sch.delta_only_columns, "the schema must record the mask it was built with"
    # and the surviving delta is the actual rate
    d = X[:, sch.feature_names.index(f"d_{col}")]
    assert list(d) == [0.0, 1.0, 1.0, 1.0]


def test_default_preset_is_v5_not_none():
    """A default of 'none' would quietly let the model read the sim epoch, and
    every cell run without the flag would be the wrong recipe."""
    assert rc.build_parser().get_default("delta_only_preset") == "v5"


# ────────────────────────── 2. fold membership ────────────────────────────────

def _manifest(tmp_path, runs):
    d = tmp_path / "corpus"
    d.mkdir()
    (d / "corpus_manifest.json").write_text(json.dumps({"runs": runs}))
    return str(d)


def _run(tech, mode, inst, csv, man):
    return {"technique": tech, "mode": mode, "instance": inst,
            "csv": csv, "manifest": man}


def test_folds_come_from_the_declared_instance(tmp_path):
    runs = [
        _run("A", "SUNSAFE", 1, "a1.csv", "m_a1.json"),
        _run("B", "SUNSAFE", 1, "b1.csv", "m_b1.json"),
        _run("A", "SUNSAFE", 2, "a2.csv", "m_a2.json"),
        _run("A", "INERTIAL", 1, "ai.csv", "m_ai.json"),
    ]
    folds = rc.rebuild_instances(_manifest(tmp_path, runs), "SUNSAFE", [1, 2])
    assert [n for n, _, _ in folds] == ["SUNSAFE_i1", "SUNSAFE_i2"]
    assert len(folds[0][2]) == 2 and len(folds[1][2]) == 1
    # the INERTIAL run must not leak into a SUNSAFE fold
    assert all("m_ai.json" not in m for _, _, mans in folds for m in mans)


def test_fold_order_follows_the_requested_instances(tmp_path):
    runs = [_run("A", "SUNSAFE", i, f"a{i}.csv", f"m{i}.json") for i in (1, 2, 3)]
    folds = rc.rebuild_instances(_manifest(tmp_path, runs), "SUNSAFE", [3, 1])
    assert [n for n, _, _ in folds] == ["SUNSAFE_i3", "SUNSAFE_i1"]


def test_missing_instance_is_an_error_not_an_empty_fold(tmp_path):
    """An empty fold would still produce a tier table — one built on fewer folds
    than reported, which is exactly the kind of quiet drift AC4 guards."""
    runs = [_run("A", "SUNSAFE", 1, "a1.csv", "m1.json")]
    with pytest.raises(SystemExit):
        rc.rebuild_instances(_manifest(tmp_path, runs), "SUNSAFE", [1, 2])


def test_symlink_view_is_built_per_instance(tmp_path):
    runs = [_run("A", "SUNSAFE", 1, "a1.csv", "m1.json"),
            _run("A", "SUNSAFE", 2, "a2.csv", "m2.json")]
    corpus = _manifest(tmp_path, runs)
    folds = rc.rebuild_instances(corpus, "SUNSAFE", [1, 2])
    for name, csv_dir, _ in folds:
        assert os.path.basename(csv_dir) == name
        links = os.listdir(csv_dir)
        assert len(links) == 1, "a fold's view must hold only that fold's CSVs"
    # idempotent: a second call over existing links must not raise
    rc.rebuild_instances(corpus, "SUNSAFE", [1, 2])


# ─────────────────────────── 3. mode scope ────────────────────────────────────

def _meta(modes):
    n = len(modes)
    return {"file_id": np.array(["f"] * n), "row_idx": np.arange(n),
            "adcs_mode": np.array(modes), "in_corruption": np.zeros(n, bool),
            "attack_id": np.array([""] * n)}


def test_mode_filter_selects_rows_across_X_y_and_meta():
    X = np.arange(12, dtype=float).reshape(6, 2)
    y = np.array(["nominal", "A", "B", "A", "nominal", "B"], dtype=object)
    modes = ["MODE_SUNSAFE", "MODE_SUNSAFE", "MODE_INERTIAL",
             "MODE_SUNSAFE", "MODE_INERTIAL", "MODE_INERTIAL"]
    Xf, yf, mf = rc.apply_mode_filter(X, y, _meta(modes), "MODE_SUNSAFE")
    assert Xf.shape == (3, 2)
    assert list(yf) == ["nominal", "A", "A"]
    assert list(mf["adcs_mode"]) == ["MODE_SUNSAFE"] * 3
    assert list(mf["row_idx"]) == [0, 1, 3], "meta must stay row-aligned to X"


def test_no_mode_filter_is_a_passthrough():
    X = np.zeros((3, 2))
    y = np.array(["a", "b", "c"], dtype=object)
    m = _meta(["MODE_SUNSAFE"] * 3)
    Xf, yf, mf = rc.apply_mode_filter(X, y, m, None)
    assert Xf is X and yf is y and mf is m


# ───────────────────── 4. schema alignment across folds ───────────────────────

def test_absent_schema_column_is_zero_filled_not_dropped():
    """An app that never emitted during one session would otherwise KeyError, or
    — worse, if handled by dropping the fold — silently change the fold count."""
    schema = {"scalar_columns": ["A", "B"], "list_columns": {}}
    df = pd.DataFrame({"A": [1.0, 2.0]})
    out = rc._align_to_schema(df, schema)
    assert "B" in out.columns
    assert list(out["B"]) == [0.0, 0.0]
    assert list(out["A"]) == [1.0, 2.0], "present columns must be untouched"


def test_align_keeps_list_columns_in_scope():
    schema = {"scalar_columns": ["A"], "list_columns": {"L": {}}}
    out = rc._align_to_schema(pd.DataFrame({"A": [1.0]}), schema)
    assert "L" in out.columns


# ───────────────────── 5. the float32 cache cast ──────────────────────────────

def test_out_of_range_value_is_clamped_not_turned_into_inf():
    """The ADCS_GNC.DT case. A plain `.astype(np.float32)` turns 1.5e284 into
    `inf`, which poisons the whole feature column; clamping keeps it as the
    largest representable value, which bins identically."""
    X = np.array([[1.0, 1.5e284], [2.0, -1.5e284]], dtype=np.float64)
    out = rc._to_float32(X)
    assert out.dtype == np.float32
    assert np.isfinite(out).all()
    assert out[0, 1] == np.finfo(np.float32).max
    assert out[1, 1] == -np.finfo(np.float32).max
    assert out[0, 0] == 1.0 and out[1, 0] == 2.0


def test_clamping_preserves_rank_order():
    """HistGradientBoosting bins by rank, so the clamp is only safe if it does
    not reorder values."""
    X = np.array([[1.0], [1e300], [5.0], [-1e300], [0.0]], dtype=np.float64)
    out = rc._to_float32(X)
    assert list(np.argsort(X[:, 0])) == list(np.argsort(out[:, 0]))


def test_stack_folds_excludes_the_held_out_fold_and_preserves_order():
    folds = []
    for i in range(3):
        X = np.full((2, 4), float(i), dtype=np.float32)
        y = np.array([f"c{i}", f"c{i}"], dtype=object)
        folds.append((X, y, None))
    Xtr, ytr = rc.stack_folds(folds, exclude=1)
    # float64 on purpose: HistGradientBoosting's X_DTYPE is float64, so handing
    # it float32 would make it allocate a second, larger copy.
    assert Xtr.shape == (4, 4) and Xtr.dtype == np.float64
    assert list(Xtr[:, 0]) == [0.0, 0.0, 2.0, 2.0]
    assert list(ytr) == ["c0", "c0", "c2", "c2"]


def test_stack_folds_with_no_exclusion_takes_everything():
    folds = [(np.full((2, 3), float(i), dtype=np.float32),
              np.array(["a", "b"], dtype=object), None) for i in range(3)]
    Xtr, ytr = rc.stack_folds(folds)
    assert Xtr.shape == (6, 3) and len(ytr) == 6


# ─────────────────── 6. the resumable fit must be the same fit ────────────────

def _toy(n=600, seed=0):
    rng = np.random.default_rng(seed)
    X = rng.normal(size=(n, 10))
    y = np.array(["a", "b", "c"])[(X[:, 0] > 0).astype(int) + (X[:, 1] > 0).astype(int)]
    return X, y


_HP = dict(max_iter=30, learning_rate=0.1, max_depth=4, max_leaf_nodes=31,
           min_samples_leaf=20, l2_regularization=0.0, max_bins=255)


def test_block_fitting_is_identical_to_one_fit(tmp_path):
    """The whole justification for resuming mid-fold: boosting is sequential, so
    warm-starting in blocks must give the SAME trees as fitting once. If this
    ever drifts, every checkpointed fold is a different model from the one the
    tier table claims to describe."""
    from eval_classifier_clusters import make_clf
    X, y = _toy()
    once = make_clf(_HP)
    once.fit(X, y)
    blocks = rc.fit_resumable(_HP, X, y, str(tmp_path / "c.pkl"), step=7)
    assert list(once.classes_) == list(blocks.classes_)
    assert once.n_iter_ == blocks.n_iter_ == _HP["max_iter"]
    assert np.abs(once.predict_proba(X) - blocks.predict_proba(X)).max() == 0.0


def test_fit_resumes_from_the_checkpoint_rather_than_restarting(tmp_path):
    X, y = _toy()
    ckpt = str(tmp_path / "c.pkl")
    partial = dict(_HP, max_iter=14)
    rc.fit_resumable(partial, X, y, ckpt, step=7)
    with open(ckpt, "rb") as f:
        _, done = pickle.load(f)
    assert done == 14, "the checkpoint must record how far training got"
    full = rc.fit_resumable(_HP, X, y, ckpt, step=7)
    assert full.n_iter_ == _HP["max_iter"], "resuming must continue, not restart"


def test_checkpoint_write_is_atomic(tmp_path):
    """A kill during the pickle write must not leave a truncated checkpoint that
    a later resume would load as if it were valid."""
    X, y = _toy()
    ckpt = str(tmp_path / "c.pkl")
    rc.fit_resumable(_HP, X, y, ckpt, step=10)
    assert os.path.exists(ckpt)
    assert not os.path.exists(ckpt + ".tmp"), "the temp file must not survive"
