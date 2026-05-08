"""Feature engineering for OnAIR security telemetry.

The CSV holds 273 columns of mixed types:
- ~210 numeric scalars (with `[0]` markers for "never received yet")
- ~38 list-valued (1D or 2D arrays of numerics)
- ~16 truly textual (event messages, table names)
- ~9 columns that stay `[0]` for the entire nominal run

Tier 1 strategy is intentionally simple:
1. Coerce numeric scalars; `[0]` and `''` and `'nan'` → 0.
2. Explode list columns into per-element scalar features (fixed shape required).
3. Drop genuine text columns (mark in schema for later iteration).
4. Compute per-column delta against the prior row, masked to 0 across file
   boundaries. Final feature matrix is `[raw, delta]` concatenated.

The schema (column order, list shapes, dropped columns) is captured in a
`FeatureSchema` so the same transformation can be re-applied at inference time.
"""

from __future__ import annotations

import ast
import json
import os
from dataclasses import asdict, dataclass, field
from typing import Iterable

import numpy as np
import pandas as pd

BOOKKEEPING = {"__file_id", "__row_idx", "__scenario", "__time",
               "__attack_id", "__attack_window", "__corruption_window"}


@dataclass
class FeatureSchema:
    scalar_columns: list[str] = field(default_factory=list)
    # col -> {top_shape: [...], paths: [[i0, i1, ...], ...]} where paths captures
    # the actual leaf layout (which can exceed top_shape's product for jagged
    # struct-of-array fields like ADCS_DI.Payload.Css.Sensor).
    list_columns: dict[str, dict] = field(default_factory=dict)
    dropped_text_columns: list[str] = field(default_factory=list)
    dropped_unparseable_columns: list[str] = field(default_factory=list)
    feature_names: list[str] = field(default_factory=list)  # final feature column order

    def save(self, path: str) -> None:
        with open(path, "w") as f:
            json.dump(asdict(self), f, indent=2)

    @classmethod
    def load(cls, path: str) -> "FeatureSchema":
        with open(path) as f:
            data = json.load(f)
        return cls(**data)


def _shape_of(value):
    """Return the shape tuple of a parsed list, recursing through nested lists.

    Scalars return (). Used only for human-readable schema export."""
    if isinstance(value, list):
        if not value:
            return (0,)
        return (len(value),) + _shape_of(value[0])
    return ()


def _flatten_scalars(value, path: tuple[int, ...] = ()):
    """Yield (path, scalar) pairs from a recursively-nested list of numbers.

    Handles struct-of-arrays shapes (e.g. ADCS_DI.Payload.Css.Sensor where each
    of 6 sensor entries is [scalar, scalar, [3-vector]]). The path is a tuple
    of integer indices identifying the leaf, used to build column names.
    """
    if isinstance(value, list):
        for i, item in enumerate(value):
            yield from _flatten_scalars(item, path + (i,))
    else:
        yield path, value


def _scalar_paths(value) -> list[tuple[int, ...]]:
    return [p for p, _ in _flatten_scalars(value)]


def _parse_list(s: str):
    if s == "[0]" or s == "" or s == "nan":
        return None
    try:
        return ast.literal_eval(s)
    except (ValueError, SyntaxError):
        return None


def _classify_columns(df: pd.DataFrame) -> dict[str, str]:
    """Classify each data column as 'numeric', 'list', or 'text'.

    Sampling rule: a column is 'numeric' if every non-empty, non-`[0]` value
    in a sample of 5000 rows parses as a finite or NaN float (after coercion);
    'list' if every such value parses as a Python list; 'text' otherwise.
    """
    out: dict[str, str] = {}
    sample = df.head(5000)
    for col in df.columns:
        if col in BOOKKEEPING:
            continue
        s = sample[col]
        # Mask out the "never received" / empty / 'nan' literal placeholders
        active = s[~s.isin(["[0]", "", "nan"])]
        if active.empty:
            out[col] = "numeric"  # constant 0 — keep as scalar
            continue
        coerced = pd.to_numeric(active, errors="coerce")
        if coerced.notna().all():
            out[col] = "numeric"
            continue
        # Try list parse
        parsed = active.head(50).apply(_parse_list)
        if parsed.notna().all() and parsed.apply(lambda v: isinstance(v, list)).all():
            out[col] = "list"
            continue
        out[col] = "text"
    return out


def _list_layout_for(df: pd.DataFrame, col: str) -> tuple[list[tuple[int, ...]], tuple[int, ...]] | None:
    """Determine the leaf-path layout of a list column.

    Returns (paths, top_shape) where paths is the list of leaf-paths (one per
    scalar) and top_shape is the human-readable shape of the topmost
    homogeneous structure. Returns None if leaf counts vary across rows.
    """
    s = df[col]
    sampled = s[~s.isin(["[0]", "", "nan"])].head(200)
    paths_canon: list[tuple[int, ...]] | None = None
    top_shape: tuple[int, ...] = ()
    for v in sampled:
        parsed = _parse_list(v)
        if parsed is None:
            continue
        paths = _scalar_paths(parsed)
        if paths_canon is None:
            paths_canon = paths
            top_shape = _shape_of(parsed)
        elif paths != paths_canon:
            return None
    if paths_canon is None:
        return None
    return paths_canon, top_shape


def _explode_list_column(df: pd.DataFrame, col: str, paths: list[tuple[int, ...]]) -> pd.DataFrame:
    """Explode a list column into one float column per leaf path."""
    n = len(df)
    flat_size = len(paths)
    path_index = {p: i for i, p in enumerate(paths)}

    arr = np.zeros((n, flat_size), dtype=np.float64)
    for ri, raw in enumerate(df[col].values):
        if raw in ("[0]", "", "nan"):
            continue
        parsed = _parse_list(raw)
        if parsed is None:
            continue
        for p, scalar in _flatten_scalars(parsed):
            i = path_index.get(p)
            if i is None:
                continue
            try:
                arr[ri, i] = float(scalar)
            except (TypeError, ValueError):
                pass

    suffixes = ["_".join(str(i) for i in p) if p else "scalar" for p in paths]
    new_cols = [f"{col}[{s}]" for s in suffixes]
    return pd.DataFrame(arr, columns=new_cols, index=df.index)


def build_features(
    df: pd.DataFrame, *, include_deltas: bool = True
) -> tuple[np.ndarray, FeatureSchema]:
    """Transform the loaded DataFrame into a numeric feature matrix.

    Returns (X, schema) where X has shape (n_rows, n_features) and dtype float64.
    """
    schema = FeatureSchema()
    classification = _classify_columns(df)

    # Two-pass layout to match the inference plugin's invariant:
    #   raw = [all scalars in original CSV order, then all list-col leaves in
    #          original CSV order].
    scalar_pieces: list[pd.DataFrame] = []
    list_pieces: list[pd.DataFrame] = []

    for col, kind in classification.items():
        if kind == "numeric":
            coerced = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
            schema.scalar_columns.append(col)
            scalar_pieces.append(coerced.to_frame(name=col))
        elif kind == "list":
            layout = _list_layout_for(df, col)
            if layout is None:
                schema.dropped_unparseable_columns.append(col)
                continue
            paths, top_shape = layout
            schema.list_columns[col] = {
                "top_shape": list(top_shape),
                "paths": [list(p) for p in paths],
            }
            list_pieces.append(_explode_list_column(df, col, paths))
        else:  # text
            schema.dropped_text_columns.append(col)

    raw = pd.concat(scalar_pieces + list_pieces, axis=1)
    raw_values = raw.to_numpy(dtype=np.float64, copy=False)
    feature_names = list(raw.columns)

    if include_deltas:
        deltas = np.zeros_like(raw_values)
        deltas[1:] = raw_values[1:] - raw_values[:-1]
        # Mask deltas across file boundaries (no carryover between runs).
        if "__file_id" in df.columns:
            file_ids = df["__file_id"].to_numpy()
            boundary = np.empty(len(df), dtype=bool)
            boundary[0] = True
            boundary[1:] = file_ids[1:] != file_ids[:-1]
            deltas[boundary] = 0.0
        feature_matrix = np.concatenate([raw_values, deltas], axis=1)
        feature_names = feature_names + [f"d_{n}" for n in feature_names]
    else:
        feature_matrix = raw_values

    schema.feature_names = feature_names
    return feature_matrix, schema


if __name__ == "__main__":
    import argparse
    from loader import load

    p = argparse.ArgumentParser()
    p.add_argument("--csv-dir", default="data/onair/csv")
    args = p.parse_args()
    df, stats = load(args.csv_dir)
    print(f"loaded {stats.files_kept} files, {df.shape[0]} rows")
    X, schema = build_features(df)
    print(f"feature matrix: {X.shape}")
    print(f"  scalar cols: {len(schema.scalar_columns)}")
    print(f"  list cols (exploded): {len(schema.list_columns)}")
    print(f"  dropped text: {len(schema.dropped_text_columns)}")
    print(f"  dropped unparseable: {len(schema.dropped_unparseable_columns)}")
    print(f"  text cols: {schema.dropped_text_columns[:6]}{'...' if len(schema.dropped_text_columns)>6 else ''}")
    print(f"  list shapes: {dict(list(schema.list_columns.items())[:5])}")
    print(f"  any NaN in X: {np.isnan(X).any()}")
    print(f"  any inf in X: {np.isinf(X).any()}")
    print(f"  X mean: {X.mean():.4f}, std: {X.std():.4f}, min: {X.min()}, max: {X.max()}")
