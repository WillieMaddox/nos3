"""Tests for incident_attribution.py (AINOS3-38 incident-record wiring)."""
import os
import sys
from types import SimpleNamespace

import numpy as np
import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
# the IncidentAggregator lives in the fsw submodule, same path the offline
# re-score (eval_incident_rescore.py) uses.
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "fsw", "plugins", "xgb_classifier"))

from incident_attribution import (  # noqa: E402
    attribute_incident,
    enrich_incident_record,
    format_top_features,
    incident_feature_rows,
)


def test_format_top_features_compact():
    top = [
        {"field": "NOVATEL_HK.CommandCount", "frac": 0.81, "delta_dominant": False},
        {"field": "NOVATEL.ECEFX", "frac": 0.10, "delta_dominant": True},
    ]
    assert format_top_features(top) == "NOVATEL_HK.CommandCount:81%|NOVATEL.ECEFXΔ:10%"


def test_incident_feature_rows_maps_span_and_skips_missing():
    inc = SimpleNamespace(frame_start=5, frame_end=8)
    f2r = {5: 0, 6: 1, 8: 2}  # frame 7 absent
    assert incident_feature_rows(inc, f2r) == [0, 1, 2]


def test_attribute_incident_empty_when_no_rows():
    inc = SimpleNamespace(frame_start=5, frame_end=8, sub_technique="X", cluster="X")
    assert attribute_incident(inc, np.zeros((3, 4)), {}, None, ["a"] * 4, {}) == []


def test_enrich_real_incident_carries_top_features():
    pytest.importorskip("shap")
    from sklearn.ensemble import HistGradientBoostingClassifier

    from incident import IncidentAggregator

    rng = np.random.default_rng(0)
    n_feat = 6
    X = rng.standard_normal((300, n_feat))
    y = (X[:, 2] + 0.1 * rng.standard_normal(300) > 0).astype(int)  # class depends on f2
    clf = HistGradientBoostingClassifier(max_iter=40, random_state=0).fit(X, y)
    feat_names = ["f0", "f1", "TARGET.field", "f3", "d_TARGET.field", "f5"]

    # Build a genuine Incident from the real aggregator over class-1 frames.
    agg = IncidentAggregator(alert_hysteresis=3, clear_hysteresis=2)
    rows1 = np.where(clf.predict(X) == 1)[0][:10]
    frame_to_row, closed, fidx = {}, None, 0
    for r in rows1:
        c = agg.update(fidx, True, mode="MODE_X", cluster="ATK",
                       sub_technique="ATK", confidence=0.9)
        frame_to_row[fidx] = int(r)
        closed = c or closed
        fidx += 1
    for _ in range(3):  # nominal frames close the incident
        closed = agg.update(fidx, False) or closed
        fidx += 1
    inc = closed or agg.flush()
    assert inc is not None and inc.sub_technique == "ATK"

    rec = enrich_incident_record(inc, X, frame_to_row, clf, feat_names,
                                 {"ATK": 1}, top_n=4)
    # the incident record now carries the ranked fields (criterion 1)
    assert {"top_features", "top_features_str"} <= set(rec)
    assert rec["top_features"][0]["field"] == "TARGET.field"  # the driver surfaces
    assert "TARGET.field" in rec["top_features_str"]
    # base incident fields are preserved
    assert rec["cluster"] == "ATK" and rec["n_anomaly_frames"] >= 3
