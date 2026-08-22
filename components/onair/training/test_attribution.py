"""Tests for attribution.py (AINOS3-38 per-incident feature attribution)."""
import numpy as np
import pytest

from attribution import (
    aggregate_incident,
    base_field,
    explain_incident,
    load_appid_slot_map,
)

_SLOTS = ["CFE_EVS", "CFE_SB", "CFE_ES", "CFE_TIME", "CFE_TBL", "SCH", "CI", "TO",
          "CI_LAB_APP", "TO_LAB_APP", "CF", "DS", "FM", "LC", "SBN", "SC"]


# ── base_field name normalization ────────────────────────────────────────────
def test_base_field_scalar():
    assert base_field("CFE_EVS.Spare1") == ("CFE_EVS.Spare1", False)


def test_base_field_array_element_collapses_to_parent():
    assert base_field("CFE_EVS_HK.AppData[0_0]") == ("CFE_EVS_HK.AppData", False)


def test_base_field_delta():
    assert base_field("d_ADCS_GNC.Mode") == ("ADCS_GNC.Mode", True)


def test_base_field_delta_of_array():
    assert base_field("d_ADCS_GNC.bvb[0_1]") == ("ADCS_GNC.bvb", True)


# ── aggregate_incident ───────────────────────────────────────────────────────
def _names():
    # two array elements of EPS.Switch, one scalar, and a delta of the scalar
    return [
        "EPS.DeviceHK.Switch[0_0]",
        "EPS.DeviceHK.Switch[0_1]",
        "ADCS_GNC.Mode",
        "d_ADCS_GNC.Mode",
    ]


def test_aggregate_groups_array_elements_and_ranks():
    names = _names()
    shap = np.array([[0.4, 0.4, 0.1, 0.05]])
    out = aggregate_incident(shap, names, top_n=8)  # default agg="max"
    assert [r["field"] for r in out] == ["EPS.DeviceHK.Switch", "ADCS_GNC.Mode"]
    eps, mode = out
    # default "max": EPS score is its strongest element (0.4), not the 0.8 sum
    assert eps["score"] == pytest.approx(0.4)
    assert eps["n_components"] == 2  # two array elements grouped
    # Mode: value part 0.1 > delta part 0.05 → not delta-dominant
    assert mode["delta_dominant"] is False


def test_aggregate_sum_mode_reports_additive_total():
    names = _names()
    shap = np.array([[0.4, 0.4, 0.1, 0.05]])
    out = aggregate_incident(shap, names, top_n=8, agg="sum")
    eps = out[0]
    assert eps["field"] == "EPS.DeviceHK.Switch"
    assert eps["score"] == pytest.approx(0.8)  # 0.4 + 0.4


def test_width_bias_fixed_by_default_max():
    # A wide 8-element array (each 0.1) vs a scalar with one strong value (0.5).
    names = [f"WIDE.arr[0_{i}]" for i in range(8)] + ["NARROW.scalar"]
    shap = np.array([[0.1] * 8 + [0.5]])

    # default "max": the strong scalar wins (bias removed)
    out_max = aggregate_incident(shap, names, top_n=2)
    assert out_max[0]["field"] == "NARROW.scalar"
    assert out_max[0]["score"] == pytest.approx(0.5)

    # "sum": the wide array (0.8) out-ranks the scalar (0.5) — the old bias
    out_sum = aggregate_incident(shap, names, top_n=2, agg="sum")
    assert out_sum[0]["field"] == "WIDE.arr"
    assert out_sum[0]["n_components"] == 8


def test_aggregate_flags_delta_dominant():
    names = ["ADCS_GNC.Mode", "d_ADCS_GNC.Mode"]
    shap = np.array([[0.02, 0.30]])  # the *change* drove it
    out = aggregate_incident(shap, names, top_n=8)
    assert out[0]["field"] == "ADCS_GNC.Mode"
    assert out[0]["delta_dominant"] is True


def test_aggregate_top_n_truncates():
    names = [f"F{i}" for i in range(10)]
    shap = np.abs(np.arange(10, 0, -1)).reshape(1, -1).astype(float)
    out = aggregate_incident(shap, names, top_n=3)
    assert len(out) == 3
    assert [r["field"] for r in out] == ["F0", "F1", "F2"]  # descending by score


def test_aggregate_averages_over_frames():
    names = ["A", "B"]
    # two frames; A mean|shap| = (0.2+0.4)/2 = 0.3 ; B = (0.1+0.1)/2 = 0.1
    shap = np.array([[0.2, 0.1], [-0.4, -0.1]])
    out = aggregate_incident(shap, names, top_n=8)
    assert out[0]["field"] == "A"
    assert out[0]["score"] == pytest.approx(0.3)


def test_aggregate_rejects_shape_mismatch():
    with pytest.raises(ValueError):
        aggregate_incident(np.zeros((1, 3)), ["A", "B"], top_n=2)


# ── end-to-end shap path on a small synthetic HistGB ─────────────────────────
def test_explain_incident_real_shap_path():
    shap = pytest.importorskip("shap")  # noqa: F841
    from sklearn.ensemble import HistGradientBoostingClassifier

    rng = np.random.default_rng(0)
    n_feat = 6
    X = rng.standard_normal((200, n_feat))
    # make class depend mostly on feature 2 so attribution should surface it
    y = (X[:, 2] + 0.1 * rng.standard_normal(200) > 0).astype(int)
    clf = HistGradientBoostingClassifier(max_iter=40, random_state=0).fit(X, y)

    feature_names = ["f0", "f1", "TARGET.field", "f3", "d_TARGET.field", "f5"]
    # explain frames predicted as class 1, w.r.t. class 1
    frames = X[clf.predict(X) == 1][:10]
    out = explain_incident(clf, feature_names, frames, target_class_id=1, top_n=4)

    assert 1 <= len(out) <= 4
    assert all({"field", "score", "frac", "delta_dominant"} <= set(r) for r in out)
    # scores descending
    scores = [r["score"] for r in out]
    assert scores == sorted(scores, reverse=True)
    # the driving field (feature index 2 → "TARGET.field") should rank #1
    assert out[0]["field"] == "TARGET.field"


# ── AINOS3-48: AppData slot->app-name resolution ─────────────────────────────
def test_base_field_appdata_resolves_slot_and_field_with_map():
    # slot 5 = SCH, field 2 = AppEnableStatus
    assert base_field("CFE_EVS_HK.AppData[5_2]", _SLOTS) == (
        "CFE_EVS_HK.AppData[SCH].AppEnableStatus", False)
    # slot 0 = CFE_EVS, field 0 = AppID
    assert base_field("CFE_EVS_HK.AppData[0_0]", _SLOTS) == (
        "CFE_EVS_HK.AppData[CFE_EVS].AppID", False)


def test_base_field_appdata_delta_with_map():
    assert base_field("d_CFE_EVS_HK.AppData[0_1]", _SLOTS) == (
        "CFE_EVS_HK.AppData[CFE_EVS].AppMessageSentCounter", True)


def test_base_field_appdata_falls_back_to_collapse_without_map():
    # no map (default) → unchanged legacy behavior (still one row per array)
    assert base_field("CFE_EVS_HK.AppData[5_2]") == ("CFE_EVS_HK.AppData", False)


def test_base_field_appdata_out_of_range_slot_is_labeled_not_crashed():
    assert base_field("CFE_EVS_HK.AppData[99_2]", _SLOTS) == (
        "CFE_EVS_HK.AppData[slot99].AppEnableStatus", False)


def test_base_field_non_appdata_array_unaffected_by_map():
    # a map must NOT change how other arrays collapse
    assert base_field("ADCS_GNC.bvb[0_1]", _SLOTS) == ("ADCS_GNC.bvb", False)


def test_aggregate_incident_names_appdata_by_app_with_map():
    # Two AppData elements from different slots + a scalar; the map must split
    # them into per-app fields instead of one lumped "CFE_EVS_HK.AppData".
    names = ["CFE_EVS_HK.AppData[5_2]", "CFE_EVS_HK.AppData[10_1]", "EPS.Voltage"]
    shap = np.array([[0.9, 0.4, 0.2]])
    out = aggregate_incident(shap, names, top_n=8, appid_slot_map=_SLOTS)
    fields = {r["field"] for r in out}
    assert "CFE_EVS_HK.AppData[SCH].AppEnableStatus" in fields
    assert "CFE_EVS_HK.AppData[CF].AppMessageSentCounter" in fields
    assert "CFE_EVS_HK.AppData" not in fields  # no opaque lump when resolved
    assert out[0]["field"] == "CFE_EVS_HK.AppData[SCH].AppEnableStatus"  # top


def test_load_appid_slot_map_reads_committed_crosswalk():
    slots = load_appid_slot_map()
    assert slots is not None, "committed cfe_appid_crosswalk.json should load"
    assert len(slots) == 16
    assert slots[0] == "CFE_EVS" and slots[5] == "SCH" and slots[15] == "SC"


def test_load_appid_slot_map_missing_file_returns_none():
    assert load_appid_slot_map("/nonexistent/crosswalk.json") is None
