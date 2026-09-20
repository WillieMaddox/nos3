#!/usr/bin/env python3
"""Tests for footprint_reproducibility — the AINOS3-101 AC1 measurement.

These pin the failures that would corrupt the measurement silently rather than
crash it. Both were hit for real while building the tool:

  1. **A single glitch frame.** `ADCS_GNC.DT` reads 1.5e284 in 6 frames of
     413,472. Under mean/std that makes the nominal variance infinite, which
     turns every z-score in the affected fold into 0 — and the class is then
     reported as irreproducible with no warning. The statistic must be immune.
  2. **A feature that is constant in nominal.** Its scale is 0, so a naive
     divide sends its z to infinity and that one axis owns the cosine. These are
     precisely the static-in-nominal counters the rule gate keys on, so they must
     count as "moved" without swamping everything else.
"""
import importlib.util
import os
import sys

import numpy as np
import pytest

_MOD = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                    "footprint_reproducibility.py")
_spec = importlib.util.spec_from_file_location("footprint_reproducibility", _MOD)
fr = importlib.util.module_from_spec(_spec)
sys.modules["footprint_reproducibility"] = fr
_spec.loader.exec_module(fr)


def _fold(tmp_path, name, X, y, modes=None):
    """Write a fold in the on-disk layout: `<name>_X.npy` + `<name>_meta.npz`."""
    p = os.path.join(tmp_path, f"{name}_X.npy")
    n = len(y)
    np.save(p, np.asarray(X, dtype=np.float64))
    np.savez(os.path.join(tmp_path, f"{name}_meta.npz"), y=np.array(y, dtype=str),
             meta_adcs_mode=np.array(modes if modes is not None
                                     else ["MODE_SUNSAFE"] * n, dtype=str),
             meta_file_id=np.array(["f"] * n, dtype=str),
             meta_row_idx=np.arange(n, dtype=np.int64),
             meta_in_corruption=np.zeros(n, dtype=bool),
             meta_attack_id=np.array([""] * n, dtype=str))
    return p


def _corpus(rng, n_nom=60, n_atk=40, n_feat=6, shift=None, noise=1.0):
    """A fold where `shift` names the per-feature displacement of the attack."""
    shift = shift if shift is not None else [0.0] * n_feat
    nom = rng.normal(0, noise, size=(n_nom, n_feat))
    atk = rng.normal(0, noise, size=(n_atk, n_feat)) + np.asarray(shift)
    X = np.vstack([nom, atk])
    y = ["nominal"] * n_nom + ["ATK"] * n_atk
    return X, y


# ─────────────────────── the glitch-frame regression ────────────────────────

def test_single_glitch_frame_does_not_destroy_the_measurement(tmp_path):
    """One 1.5e284 frame in nominal must not change the verdict.

    This is the ADCS_GNC.DT case. Under mean/std the fold's scale goes infinite
    and the class reads as irreproducible; the robust statistic must not move.
    """
    rng = np.random.default_rng(0)
    shift = [8.0, 0, 0, 0, 0, 0]
    paths_clean, paths_glitched = [], []
    for i in range(2):
        X, y = _corpus(np.random.default_rng(i), shift=shift)
        paths_clean.append(_fold(tmp_path, f"clean{i}", X, y))
        Xg = X.copy()
        Xg[3, 5] = 1.5e284          # one nominal frame, one feature
        paths_glitched.append(_fold(tmp_path, f"glitch{i}", Xg, y))

    clean = [fr.fold_signatures(p, 5)[0]["ATK"] for p in paths_clean]
    dirty = [fr.fold_signatures(p, 5)[0]["ATK"] for p in paths_glitched]

    r_clean = fr.jaccard(clean[0][0], clean[1][0])
    r_dirty = fr.jaccard(dirty[0][0], dirty[1][0])
    assert r_clean == pytest.approx(r_dirty), (
        f"a single glitch frame moved reproducibility {r_clean} -> {r_dirty}")
    assert np.isfinite(dirty[0][1]).all(), "clipped z must stay finite"
    _ = rng  # the per-fold generators above are what seed the data


def test_constant_nominal_feature_counts_as_moved_without_owning_the_cosine(tmp_path):
    """A static-in-nominal counter has scale 0. It must register as moved, and
    the clipped z must keep it from dominating the similarity."""
    rng = np.random.default_rng(7)
    n_nom, n_atk = 60, 40
    X = np.vstack([rng.normal(0, 1, (n_nom, 3)), rng.normal(0, 1, (n_atk, 3))])
    X[:, 2] = 0.0                       # constant in nominal …
    X[n_nom:, 2] = 5.0                  # … and moved by the attack
    y = ["nominal"] * n_nom + ["ATK"] * n_atk
    sigs, _ = fr.fold_signatures(_fold(tmp_path, "c", X, y), 5)
    moved, z = sigs["ATK"]
    assert (2, 1) in moved, "constant-in-nominal feature must register as moved"
    assert abs(z[2]) <= fr.Z_CLIP
    assert np.isfinite(z).all()


# ──────────────────────────── the core measure ──────────────────────────────

def test_identical_footprints_are_fully_reproducible(tmp_path):
    shift = [9.0, -9.0, 0, 0, 0, 0]
    s = [fr.fold_signatures(
            _fold(tmp_path, f"id{i}", *_corpus(np.random.default_rng(i), shift=shift)),
            5)[0]["ATK"] for i in range(3)]
    assert fr.jaccard(s[0][0], s[1][0]) == 1.0
    assert fr.cos(s[0][1], s[1][1]) > 0.99


def test_disjoint_footprints_score_zero(tmp_path):
    a = fr.fold_signatures(_fold(tmp_path, "a", *_corpus(
        np.random.default_rng(1), shift=[9, 0, 0, 0, 0, 0])), 5)[0]["ATK"]
    b = fr.fold_signatures(_fold(tmp_path, "b", *_corpus(
        np.random.default_rng(2), shift=[0, 0, 0, 0, 0, 9])), 5)[0]["ATK"]
    assert fr.jaccard(a[0], b[0]) == 0.0


def test_opposite_sign_is_not_the_same_footprint(tmp_path):
    """Two runs that move the same feature in OPPOSITE directions have not
    reproduced a footprint — the signed set is what makes that visible."""
    a = fr.fold_signatures(_fold(tmp_path, "up", *_corpus(
        np.random.default_rng(3), shift=[9, 0, 0, 0, 0, 0])), 5)[0]["ATK"]
    b = fr.fold_signatures(_fold(tmp_path, "dn", *_corpus(
        np.random.default_rng(4), shift=[-9, 0, 0, 0, 0, 0])), 5)[0]["ATK"]
    assert fr.jaccard(a[0], b[0]) == 0.0


def test_partial_overlap_is_a_ratio(tmp_path):
    """{f0,f1} vs {f1,f2} -> intersection 1, union 3."""
    a = fr.fold_signatures(_fold(tmp_path, "p1", *_corpus(
        np.random.default_rng(5), shift=[9, 9, 0, 0, 0, 0])), 5)[0]["ATK"]
    b = fr.fold_signatures(_fold(tmp_path, "p2", *_corpus(
        np.random.default_rng(6), shift=[0, 9, 9, 0, 0, 0])), 5)[0]["ATK"]
    assert fr.jaccard(a[0], b[0]) == pytest.approx(1 / 3)


def test_noise_alone_moves_nothing(tmp_path):
    """An attack that displaces nothing must produce an empty footprint, not a
    footprint of whichever features happened to drift."""
    sigs, _ = fr.fold_signatures(_fold(tmp_path, "n", *_corpus(
        np.random.default_rng(11), n_nom=400, n_atk=300)), 5)
    assert len(sigs["ATK"][0]) == 0


# ─────────────────────────────── plumbing ───────────────────────────────────

def test_mode_filter_selects_rows(tmp_path):
    rng = np.random.default_rng(12)
    X = rng.normal(0, 1, (40, 3))
    # Rows 0-9 / 10-19 are SUNSAFE nominal / attack; 20-29 / 30-39 the same for
    # INERTIAL. Only the INERTIAL ATTACK rows are displaced, so f0 must show up
    # in the INERTIAL footprint and be absent from the SUNSAFE one.
    X[30:40, 0] += 9.0
    y = (["nominal"] * 10 + ["ATK"] * 10) * 2
    modes = ["MODE_SUNSAFE"] * 20 + ["MODE_INERTIAL"] * 20
    p = _fold(tmp_path, "m", X, y, modes=modes)
    sun, _ = fr.fold_signatures(p, 5, mode_filter="MODE_SUNSAFE")
    ine, _ = fr.fold_signatures(p, 5, mode_filter="MODE_INERTIAL")
    assert (0, 1) not in sun["ATK"][0]
    assert (0, 1) in ine["ATK"][0]


def test_classes_below_min_frames_are_skipped(tmp_path):
    X = np.vstack([np.zeros((40, 3)), np.ones((3, 3))])
    y = ["nominal"] * 40 + ["RARE"] * 3
    sigs, counts = fr.fold_signatures(_fold(tmp_path, "r", X, y), min_frames=20)
    assert "RARE" not in sigs and "RARE" not in counts


def test_spearman_matches_known_values():
    assert fr.spearman([1, 2, 3, 4], [1, 2, 3, 4]) == pytest.approx(1.0)
    assert fr.spearman([1, 2, 3, 4], [4, 3, 2, 1]) == pytest.approx(-1.0)
    assert fr.spearman([1, 1, 1, 1], [1, 2, 3, 4]) == 0.0     # no variance -> 0


def test_jaccard_of_two_empty_footprints_is_one():
    """Two runs that both moved nothing agree perfectly. Returning 0 here would
    report a silent no-op attack as maximally irreproducible."""
    assert fr.jaccard(frozenset(), frozenset()) == 1.0
