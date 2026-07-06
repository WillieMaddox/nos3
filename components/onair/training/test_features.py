# GSC-19165-1, "The On-Board Artificial Intelligence Research (OnAIR) Platform"
# Licensed under the NASA Open Source Agreement version 1.3

"""Tests for `build_features`, focusing on the delta_only mask path.

The delta_only mechanism makes the IF invariant to absolute time + the
deterministic NOS3 orbit while preserving the rate-of-change signal that
matters for time/PNT spoof detection. The mask must:

1. drop the named TLM columns from the raw half but keep their deltas
2. expand list-column names to every exploded leaf
3. survive a schema round-trip so the inference plugin reproduces the
   exact training-time feature layout
4. error cleanly when include_deltas is False (no representation otherwise)
"""

from __future__ import annotations

from dataclasses import asdict

import numpy as np
import pandas as pd
import pytest

from features import V5_DELTA_ONLY_COLUMNS, FeatureSchema, build_features


def _toy_df() -> pd.DataFrame:
    """3 rows, 1 scalar TLM col + 1 list TLM col + 1 plain scalar."""
    return pd.DataFrame({
        "__file_id": ["A", "A", "A"],
        "CFE_TIME.SecondsMET": ["100", "200", "400"],   # monotonic abs time
        "ADCS_DI.Payload.Mag.bvb": ["[1.0, 2.0, 3.0]",
                                      "[1.1, 2.2, 3.3]",
                                      "[1.5, 2.5, 3.5]"],
        "CFE_EVS_HK.CommandCounter": ["10", "11", "12"],  # ordinary counter
    })


def test_delta_only_drops_scalar_raw_keeps_delta():
    df = _toy_df()
    X, schema = build_features(df, delta_only=["CFE_TIME.SecondsMET"])

    # All three TLM cols contribute features (3 leaves for the list col, 1
    # each for the two scalars). delta_only suppresses 1 raw slot.
    n_raw_full = 1 + 3 + 1   # scalar1 + list_leaves(3) + scalar2
    n_raw_kept = n_raw_full - 1
    assert X.shape == (3, n_raw_kept + n_raw_full)

    # Schema records the suppression
    assert schema.delta_only_columns == ["CFE_TIME.SecondsMET"]

    # The raw-half feature names no longer contain SecondsMET, but the
    # delta-half does ("d_CFE_TIME.SecondsMET").
    raw_names = schema.feature_names[:n_raw_kept]
    delta_names = schema.feature_names[n_raw_kept:]
    assert "CFE_TIME.SecondsMET" not in raw_names
    assert "d_CFE_TIME.SecondsMET" in delta_names

    # The delta values for SecondsMET should be 0, 100, 200 (file-boundary
    # gives 0 at row 0, then 200-100=100, 400-200=200).
    di = delta_names.index("d_CFE_TIME.SecondsMET")
    np.testing.assert_array_equal(X[:, n_raw_kept + di], [0.0, 100.0, 200.0])


def test_delta_only_list_column_suppresses_all_leaves():
    """Naming a list TLM column suppresses every exploded leaf in the raw
    half but keeps every leaf in the delta half."""
    df = _toy_df()
    X, schema = build_features(df, delta_only=["ADCS_DI.Payload.Mag.bvb"])

    n_raw_full = 5
    n_raw_kept = n_raw_full - 3   # 3 list leaves suppressed
    assert X.shape == (3, n_raw_kept + n_raw_full)

    raw_names = schema.feature_names[:n_raw_kept]
    delta_names = schema.feature_names[n_raw_kept:]

    # No bvb leaf in raw half
    assert not any(n.startswith("ADCS_DI.Payload.Mag.bvb") for n in raw_names)
    # All three bvb leaves in delta half
    bvb_deltas = [n for n in delta_names if n.startswith("d_ADCS_DI.Payload.Mag.bvb")]
    assert len(bvb_deltas) == 3


def test_no_delta_only_matches_legacy_behaviour():
    """When delta_only is empty/None, output shape and naming exactly match
    the pre-change behaviour: [raw, delta] of equal width."""
    df = _toy_df()
    X, schema = build_features(df)

    n_raw_full = 5
    assert X.shape == (3, 2 * n_raw_full)
    assert schema.delta_only_columns == []
    # Symmetric naming: every raw name has a matching d_<name>
    raw_names = schema.feature_names[:n_raw_full]
    delta_names = schema.feature_names[n_raw_full:]
    assert delta_names == [f"d_{n}" for n in raw_names]


def test_delta_only_without_deltas_raises():
    df = _toy_df()
    with pytest.raises(ValueError, match="delta_only requires include_deltas"):
        build_features(df, include_deltas=False,
                       delta_only=["CFE_TIME.SecondsMET"])


def test_schema_roundtrip_preserves_delta_only():
    """Train-time schema serializes via asdict, deserializes through
    build_features(schema=...), and produces the same feature layout — the
    inference-time invariant the plugin relies on."""
    df = _toy_df()
    X_train, schema_train = build_features(df, delta_only=["CFE_TIME.SecondsMET"])

    # Round-trip the schema through dict (matches the pickle format).
    schema_dict = asdict(schema_train)
    X_infer, schema_infer = build_features(df, schema=schema_dict)

    np.testing.assert_array_equal(X_train, X_infer)
    assert schema_infer.feature_names == schema_train.feature_names
    assert schema_infer.delta_only_columns == ["CFE_TIME.SecondsMET"]


def test_schema_roundtrip_with_kwarg_does_not_double_apply():
    """If a saved schema already carries delta_only_columns AND the caller
    also passes delta_only=, the schema's record wins — guards against an
    inference caller accidentally widening the mask."""
    df = _toy_df()
    _, schema_train = build_features(df, delta_only=["CFE_TIME.SecondsMET"])

    X_infer, schema_infer = build_features(
        df,
        schema=asdict(schema_train),
        delta_only=["ADCS_DI.Payload.Mag.bvb"],  # ignored by the schema path
    )
    assert schema_infer.delta_only_columns == ["CFE_TIME.SecondsMET"]
    # Shape matches the schema's mask (1 scalar dropped), not the kwarg's
    # (3 list leaves dropped).
    assert X_infer.shape == (3, (5 - 1) + 5)


def test_v5_preset_columns_are_well_formed():
    """Sanity: the canonical v5 list contains only TLM-style names and no
    list-leaf bracket suffixes (the mask logic expands list parents on its
    own, so leaf-suffixed names would be a configuration bug)."""
    for c in V5_DELTA_ONLY_COLUMNS:
        assert "[" not in c, f"V5 preset entry {c!r} looks like a leaf, not a parent"
        assert "." in c, f"V5 preset entry {c!r} is not a dotted TLM path"
    # No duplicates
    assert len(V5_DELTA_ONLY_COLUMNS) == len(set(V5_DELTA_ONLY_COLUMNS))
