"""NOS3-311 — per-incident feature attribution for the v3 attack classifier.

Offline SHAP attribution. Given the deployed HistGradientBoostingClassifier and
the frames belonging to one incident, compute which *telemetry fields* drove the
classification, as an operator-readable ranked list ("EPS.DeviceHK.Switch,
ADCS_GNC.Mode, ...") rather than feature indices.

Why offline first (NOS3-311 vs the live-plugin work in NOS3-312): this satisfies
both acceptance criteria — "each incident carries a ranked top-N contributing
fields" and "attributions validated against >=3 known attacks" — without adding
shap to the OnAIR flight runtime. `shap.TreeExplainer` supports HistGradientBoosting
as of shap >= 0.49 and is path-dependent (no predict_proba sampling), so it is
cheap enough to lift into the plugin later if NOS3-312 wants live explanations.

Feature-name convention in `schema["feature_names"]` (894 entries):
  - scalar          : "CFE_EVS.Spare1"
  - array-exploded  : "CFE_EVS_HK.AppData[0_0]"   (indices joined by '_')
  - per-row delta   : "d_" prefix on either of the above
`base_field()` collapses a feature column back to its telemetry field so the
operator sees one row per field, not one per array element / raw-vs-delta split.
"""
from __future__ import annotations

import re

import numpy as np

_ARRAY_SUFFIX = re.compile(r"\[[0-9_]+\]$")


def base_field(feature_name: str) -> tuple[str, bool]:
    """Map a feature-column name to (telemetry_field, is_delta).

    Strips the ``d_`` delta prefix and any ``[i_j]`` array-index suffix.
    >>> base_field("d_ADCS_GNC.bvb[0_1]")
    ('ADCS_GNC.bvb', True)
    """
    is_delta = feature_name.startswith("d_")
    name = feature_name[2:] if is_delta else feature_name
    name = _ARRAY_SUFFIX.sub("", name)
    return name, is_delta


def build_explainer(clf):
    """TreeExplainer over the classifier. Imported lazily so the module loads
    without shap (e.g. for `base_field`/`aggregate_incident` unit tests)."""
    import shap

    return shap.TreeExplainer(clf)


def frame_class_shap(explainer, X: np.ndarray, class_ids: np.ndarray) -> np.ndarray:
    """Per-frame SHAP for each frame's own target class.

    X: (n, n_features). class_ids: (n,) integer indices into ``clf.classes_``.
    Returns (n, n_features) — the SHAP row for each frame's class.
    """
    sv = np.asarray(explainer.shap_values(X))
    # Multiclass (e.g. the 26-class v3 model) → (n, n_features, n_classes):
    # select each frame's target-class row. Binary → (n, n_features): a single
    # array for the positive class; the sign flips for class 0 but downstream
    # aggregation uses |SHAP|, so it is returned as-is.
    if sv.ndim == 3:
        n = X.shape[0]
        return sv[np.arange(n), :, class_ids]
    if sv.ndim == 2:
        return sv
    raise ValueError(f"unexpected shap_values ndim {sv.ndim} (shape {sv.shape})")


def _field_score(vals: list[float], agg: str) -> float:
    if not vals:
        return 0.0
    if agg == "max":
        return float(max(vals))
    if agg == "mean":
        return float(sum(vals) / len(vals))
    if agg == "sum":
        return float(sum(vals))
    raise ValueError(f"unknown agg {agg!r} (use 'max', 'mean', or 'sum')")


def aggregate_incident(
    per_frame_shap: np.ndarray,
    feature_names: list[str],
    top_n: int = 8,
    group_arrays: bool = True,
    agg: str = "max",
) -> list[dict]:
    """Rank telemetry fields by per-frame mean-|SHAP| over an incident.

    A field's columns (array elements + raw + delta) are combined per ``agg``:
      - ``"max"`` (default): the field's strongest single telemetry component.
        Scale-comparable to scalars, so a wide array does not out-rank a scalar
        just by having more elements.
      - ``"mean"``: width-normalized (average per element).
      - ``"sum"``: total contribution (theoretically the field's additive SHAP
        share, but biases toward wide arrays — see below).

    Returns top-N dicts: {field, score, frac, delta_dominant, n_components},
    where ``frac`` is the field's share of summed scores, ``delta_dominant``
    flags fields whose *change* (delta) drove the call more than the value, and
    ``n_components`` is how many feature columns the field spans (1 = scalar).

    ARRAY-WIDTH NOTE: ``"sum"`` over-ranks wide arrays (CFE_EVS_HK.AppData has 64
    elements), so EVS app-data tops nearly every alert even when the
    discriminating field is a subsystem scalar. The default ``"max"`` removes
    that bias; ``"sum"`` is kept for callers that want true additive shares.
    """
    per_frame_shap = np.atleast_2d(np.asarray(per_frame_shap, dtype=float))
    if per_frame_shap.shape[1] != len(feature_names):
        raise ValueError(
            f"feature count mismatch: shap {per_frame_shap.shape[1]} "
            f"vs names {len(feature_names)}"
        )
    mean_abs = np.abs(per_frame_shap).mean(axis=0)  # (n_features,)

    cols: dict[str, dict[str, list[float]]] = {}  # field -> {all, value, delta}
    for j, fname in enumerate(feature_names):
        if group_arrays:
            field, is_delta = base_field(fname)
        else:
            field, is_delta = fname, fname.startswith("d_")
        slot = cols.setdefault(field, {"all": [], "value": [], "delta": []})
        slot["all"].append(mean_abs[j])
        slot["delta" if is_delta else "value"].append(mean_abs[j])

    scored = {
        field: (
            _field_score(c["all"], agg),
            _field_score(c["value"], agg),
            _field_score(c["delta"], agg),
            len(c["all"]),
        )
        for field, c in cols.items()
    }
    total = sum(s[0] for s in scored.values()) or 1.0
    ranked = sorted(scored.items(), key=lambda kv: kv[1][0], reverse=True)[:top_n]
    return [
        {
            "field": field,
            "score": float(tot),
            "frac": float(tot / total),
            "delta_dominant": bool(dlt > val),
            "n_components": int(ncomp),
        }
        for field, (tot, val, dlt, ncomp) in ranked
    ]


def explain_incident(
    clf,
    feature_names: list[str],
    X_frames: np.ndarray,
    target_class_id: int | None = None,
    explainer=None,
    top_n: int = 8,
) -> list[dict]:
    """End-to-end attribution for one incident's frames.

    ``target_class_id`` — if given, explain every frame w.r.t. that class (the
    incident's winning label, what the operator sees). If None, explain each
    frame's own argmax class. ``explainer`` may be reused across incidents.
    """
    X_frames = np.atleast_2d(np.asarray(X_frames, dtype=float))
    if explainer is None:
        explainer = build_explainer(clf)
    n = X_frames.shape[0]
    if target_class_id is None:
        class_ids = clf.predict_proba(X_frames).argmax(axis=1)
    else:
        class_ids = np.full(n, int(target_class_id), dtype=int)
    shap_frames = frame_class_shap(explainer, X_frames, class_ids)
    return aggregate_incident(shap_frames, feature_names, top_n=top_n)
