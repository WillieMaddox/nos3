"""AINOS3-38 — attach per-incident SHAP attribution to Incident records (offline).

Bridges `attribution.py` (per-frame SHAP) to the `IncidentAggregator`'s output
so every incident carries a ranked top-N of the telemetry fields that drove its
classification — acceptance criterion 1.

Why offline / why not in the live plugin: the OnAIR flight runtime has no shap,
and the `Incident` dataclass lives in the `components/onair/fsw` submodule. This
module therefore enriches incidents in the training tree without modifying the
live emit path or the dataclass. Surfacing these explanations in the live
incident side-file + demo app is the separate ticket AINOS3-40.
"""
from __future__ import annotations

import numpy as np

from attribution import explain_incident


def incident_feature_rows(incident, frame_to_row: dict[int, int]) -> list[int]:
    """X-row indices for the frames spanned by an incident (present frames only).

    ``frame_to_row`` maps an aggregator ``frame_idx`` to its row in the feature
    matrix X. Frames with no row (e.g. dropped) are skipped.
    """
    return [
        frame_to_row[f]
        for f in range(incident.frame_start, incident.frame_end + 1)
        if f in frame_to_row
    ]


def attribute_incident(
    incident,
    X: np.ndarray,
    frame_to_row: dict[int, int],
    clf,
    feature_names: list[str],
    class_col_of_label: dict[str, int],
    explainer=None,
    top_n: int = 6,
) -> list[dict]:
    """Ranked top-N telemetry fields for one incident.

    Explains the incident's winning ``sub_technique`` (falling back to its
    ``cluster``, then to each frame's own argmax if neither maps to a class).
    """
    rows = incident_feature_rows(incident, frame_to_row)
    if not rows:
        return []
    target = class_col_of_label.get(incident.sub_technique)
    if target is None:
        target = class_col_of_label.get(incident.cluster)  # may stay None → argmax
    return explain_incident(
        clf, feature_names, X[rows],
        target_class_id=target, explainer=explainer, top_n=top_n,
    )


def format_top_features(top: list[dict], max_fields: int | None = None) -> str:
    """Compact one-line rendering for an incident-record column, e.g.
    ``"NOVATEL_HK.CommandCount:81%|CFE_SB.MsgSendErrorCounter:15%"``.
    A trailing ``Δ`` marks a delta-dominant field.
    """
    items = top if max_fields is None else top[:max_fields]
    return "|".join(
        f"{r['field']}{'Δ' if r['delta_dominant'] else ''}:{round(r['frac'] * 100)}%"
        for r in items
    )


def enrich_incident_record(
    incident,
    X: np.ndarray,
    frame_to_row: dict[int, int],
    clf,
    feature_names: list[str],
    class_col_of_label: dict[str, int],
    explainer=None,
    top_n: int = 6,
) -> dict:
    """``incident.to_dict()`` augmented with ``top_features`` (list of dicts) and
    ``top_features_str`` (the compact one-line form). This is the enriched
    incident record AINOS3-40 will surface live."""
    top = attribute_incident(
        incident, X, frame_to_row, clf, feature_names,
        class_col_of_label, explainer=explainer, top_n=top_n,
    )
    rec = incident.to_dict()
    rec["top_features"] = top
    rec["top_features_str"] = format_top_features(top)
    return rec
