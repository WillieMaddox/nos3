"""Unit tests for the IncidentAggregator (NOS3-201).

The aggregator ships inside the xgb_classifier plugin package; add it to the
path so these run from the training/ test suite.
"""
import os
import sys

import pytest

PLUGIN_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "fsw", "plugins", "xgb_classifier")
sys.path.insert(0, PLUGIN_DIR)

from incident import Incident, IncidentAggregator, cluster_map_from_taxonomy  # noqa: E402


def feed(agg, frames):
    """frames: list of (is_anomaly, cluster, conf). Returns closed incidents."""
    out = []
    for i, (is_anom, cluster, conf) in enumerate(frames):
        inc = agg.update(i, is_anom, mode="MODE_SUNSAFE",
                         cluster=cluster, sub_technique=cluster, confidence=conf)
        if inc:
            out.append(inc)
    return out


def test_simple_incident_confirms_and_closes():
    agg = IncidentAggregator(alert_hysteresis=3, clear_hysteresis=2)
    frames = [(True, "A", 0.9)] * 5 + [(False, "", 0.0)] * 2
    closed = feed(agg, frames)
    assert len(closed) == 1
    inc = closed[0]
    assert inc.frame_start == 0
    assert inc.frame_end == 4          # last anomalous frame
    assert inc.n_anomaly_frames == 5
    assert inc.cluster == "A"
    assert inc.agreement == 1.0
    assert inc.confidence == pytest.approx(0.9)
    assert inc.peak_confidence == pytest.approx(0.9)


def test_building_run_dies_before_confirmation():
    agg = IncidentAggregator(alert_hysteresis=3, clear_hysteresis=2)
    # only 2 consecutive anomalies, never reaches alert_hyst=3
    frames = [(True, "A", 0.9), (True, "A", 0.9), (False, "", 0.0),
              (False, "", 0.0), (False, "", 0.0)]
    closed = feed(agg, frames)
    assert closed == []
    assert agg.flush() is None


def test_internal_gap_below_clear_hyst_stays_one_incident():
    agg = IncidentAggregator(alert_hysteresis=2, clear_hysteresis=3)
    # confirm, one short nominal gap (<3), more anomaly, then clear
    frames = ([(True, "A", 0.8)] * 3 + [(False, "", 0.0)] * 2 +
              [(True, "A", 0.8)] * 3 + [(False, "", 0.0)] * 3)
    closed = feed(agg, frames)
    assert len(closed) == 1
    inc = closed[0]
    assert inc.frame_start == 0
    assert inc.frame_end == 7          # last anomaly before the closing gap
    assert inc.n_anomaly_frames == 6


def test_two_incidents_separated_by_clear_gap():
    agg = IncidentAggregator(alert_hysteresis=2, clear_hysteresis=2)
    frames = ([(True, "A", 0.9)] * 3 + [(False, "", 0.0)] * 2 +
              [(True, "B", 0.7)] * 3 + [(False, "", 0.0)] * 2)
    closed = feed(agg, frames)
    assert len(closed) == 2
    assert closed[0].cluster == "A"
    assert closed[1].cluster == "B"
    assert closed[1].frame_start == 5


def test_winning_cluster_by_summed_probability_and_agreement():
    agg = IncidentAggregator(alert_hysteresis=2, clear_hysteresis=2)
    # 3 frames vote A (0.6 each = 1.8), 2 frames vote B (0.95 each = 1.9)
    frames = [(True, "A", 0.6), (True, "A", 0.6), (True, "B", 0.95),
              (True, "B", 0.95), (True, "A", 0.6)] + [(False, "", 0.0)] * 2
    closed = feed(agg, frames)
    assert len(closed) == 1
    inc = closed[0]
    # A: sum 1.8 over 3 frames; B: sum 1.9 over 2 frames -> B wins on summed prob
    assert inc.cluster == "B"
    assert inc.n_anomaly_frames == 5
    assert inc.agreement == pytest.approx(2 / 5)
    assert inc.confidence == pytest.approx(0.95)


def test_flush_emits_open_incident():
    agg = IncidentAggregator(alert_hysteresis=2, clear_hysteresis=5)
    feed(agg, [(True, "A", 0.9)] * 4)   # confirmed, never cleared
    inc = agg.flush()
    assert inc is not None
    assert inc.cluster == "A"
    assert inc.n_anomaly_frames == 4
    # second flush is idempotent
    assert agg.flush() is None


def test_min_anomaly_frames_filters_tiny_incidents():
    agg = IncidentAggregator(alert_hysteresis=1, clear_hysteresis=1,
                             min_anomaly_frames=3)
    frames = [(True, "A", 0.9), (False, "", 0.0)]   # 1 anomaly, below min 3
    closed = feed(agg, frames)
    assert closed == []


def test_cluster_map_from_taxonomy():
    tax = {"clusters": {
        "EX-0012.{03,04,05}": ["EX-0012.03", "EX-0012.04", "EX-0012.05"],
        "IMP-0005": ["IMP-0005"],
    }}
    m = cluster_map_from_taxonomy(tax)
    assert m["EX-0012.04"] == "EX-0012.{03,04,05}"
    assert m["IMP-0005"] == "IMP-0005"
    assert "nominal" not in m
