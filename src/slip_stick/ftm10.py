"""FTM 10 CSV parsing utilities.

This module provides a ``load_ftm10_csv`` helper alongside the internal building
blocks needed to parse the vendor CSV export format.  The file format is
quirky:

* Each row is wrapped in double quotes, so we strip the outer quotes before
  passing the content to the CSV reader.
* Decimal commas appear inside quoted numeric strings.  After removing the outer
  quotes we convert doubled quotes (``""``) back to single quotes so the csv
  module can treat ``","`` as a decimal separator inside the field.
* Replicate headers occupy three rows: replicate label, measurement name,
  measurement unit.  The label row uses sparsely populated cells, so we forward
  fill empty cells to reconstruct contiguous three-column replicate blocks.

The parsing pipeline mirrors the actionable tasks captured in the Memory Bank:

1. Sniff dialect information (delimiter, decimal separator, header rows,
   encoding) from a preview slice limited to ``preview_lines``.
2. Collect replicate blocks and normalise measurement metadata.
3. Coerce strings to numeric values, reshape the data into a tidy long-format
   table, and compute per-replicate statistics.
4. Expose ``load_ftm10_csv`` as the public entry point; the CLI reuses the same
   functions.
"""

from __future__ import annotations

import csv
import logging
import math
import os
import re
import unicodedata
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

LOGGER = logging.getLogger(__name__)

DEFAULT_PREVIEW_LINES = 100
DEFAULT_HEADER_ROWS = 3
ENCODING_CANDIDATES = ("utf-8", "utf-8-sig", "cp1250")
DELIMITER_CANDIDATES = ",;\t"
DECIMAL_PLACEHOLDER = "__DEC_COMMA__"

_DECIMAL_SUB_RE = re.compile(r"(?<=\d),(?=\d)")

CANONICAL_FIELDS = {
    "time": "time_s",
    "force": "force_N",
    "disp": "disp_mm",
}
CANONICAL_UNITS = {"time": "s", "force": "N", "disp": "mm"}

TIME_NAME_TOKENS = {
    "czas",
    "time",
    "czas s",
    "czas [s]",
    "czas (s)",
}
FORCE_NAME_TOKENS = {
    "siła",
    "sila",
    "force",
}
DISP_NAME_TOKENS = {
    "przemieszczenie",
    "displacement",
    "disp",
    "przemieszczenie mm",
}

TIME_UNIT_TOKENS = {"s", "sec", "second", "seconds"}
FORCE_UNIT_TOKENS = {"n", "kn", "gf"}
DISP_UNIT_TOKENS = {"mm", "µm", "um", "micrometre", "micrometer", "m"}

UNIT_CONVERSIONS = {
    ("force", "kn"): ("N", 1000.0),
    ("force", "gf"): ("N", 0.00980665),
    ("disp", "µm"): ("mm", 0.001),
    ("disp", "um"): ("mm", 0.001),
    ("disp", "m"): ("mm", 1000.0),
    ("time", "ms"): ("s", 0.001),
}

__all__ = ["load_ftm10_csv"]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load_ftm10_csv(
    path: str,
    preview_lines: int = DEFAULT_PREVIEW_LINES,
    *,
    decimal_override: Optional[str] = None,
    header_rows_override: Optional[int] = None,
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """Load an FTM 10 CSV and return a tidy DataFrame plus metadata.

    Parameters
    ----------
    path:
        Path to the CSV file.
    preview_lines:
        Number of lines to use when sniffing the dialect (defaults to 100 in
        line with the Memory Bank constraint).
    decimal_override:
        Optional override for the decimal separator ("," or ".").
    header_rows_override:
        Optional override for the number of header rows (defaults to three).

    Returns
    -------
    (df_long, metadata)
        ``df_long`` columns: ``replicate_id``, ``time_s``, ``force_N``,
        ``disp_mm``.  ``metadata`` aggregates dialect details and per-replicate
        statistics.
    """

    csv_path = Path(path)
    if not csv_path.exists():  # pragma: no cover - defensive guard
        raise FileNotFoundError(path)

    sniff_info = _sniff_dialect_and_header(
        path,
        preview_lines=preview_lines,
        header_rows=header_rows_override or DEFAULT_HEADER_ROWS,
        decimal_override=decimal_override,
    )

    delimiter: str = sniff_info["delimiter"]
    decimal: str = sniff_info["decimal"]
    encoding: str = sniff_info["encoding"]
    header_rows: int = sniff_info["header_rows"]

    rows = list(
        _iter_csv_rows(
            path,
            encoding=encoding,
            delimiter=delimiter,
        )
    )
    if len(rows) < header_rows:
        raise ValueError(
            f"Expected at least {header_rows} header rows, found {len(rows)} in {path}"
        )

    header_slice = rows[:header_rows]
    data_rows = rows[header_rows:]

    columns_mi, replicate_labels, name_unit_map = _build_columns_from_header(header_slice)
    if columns_mi.empty:
        raise ValueError("Failed to derive multi-level header from CSV preview")

    df_raw = pd.DataFrame(data_rows)
    df_raw = df_raw.iloc[:, : len(columns_mi)]
    df_raw.columns = columns_mi
    df_raw.replace({"": pd.NA}, inplace=True)

    numeric_df = _coerce_numeric(df_raw, decimal)
    numeric_df.dropna(axis=0, how="all", inplace=True)

    blocks = _collect_replicate_blocks(numeric_df.columns)
    df_long = _build_long_frame(numeric_df, blocks)
    stats = _compute_stats(df_long)

    replicate_meta: Dict[str, Dict[str, Any]] = {}
    for block in blocks:
        rep_id = block["replicate_id"]
        col_meta = {
            field: {
                "original_unit": block["columns"][field]["original_unit"],
                "canonical_unit": block["columns"][field]["canonical_unit"],
                "scale_applied": block["columns"][field]["scale"],
                "name": block["columns"][field]["name"],
            }
            for field in ("time", "force", "disp")
        }
        metrics = {
            "rows_initial": block["metrics"]["rows_initial"],
            "rows_after_time_drop": block["metrics"]["rows_after_time_drop"],
            "rows_after_monotonic": block["metrics"]["rows_after_monotonic"],
            "dropped_time_na": block["metrics"]["dropped_time_na"],
            "dropped_non_monotonic": block["metrics"]["dropped_non_monotonic"],
            "source_label": block["replicate_label"],
            "position": block["index"],
        }
        combined = {
            **col_meta,
            **metrics,
            **stats["replicates"].get(rep_id, {}),
        }
        replicate_meta[rep_id] = _coerce_metadata_scalars(combined)

    metadata = {
        "file": str(csv_path.resolve()),
        "delimiter": delimiter,
        "decimal": decimal,
        "encoding": encoding,
        "header_rows": header_rows,
        "column_count": len(columns_mi),
        "row_count": int(df_long.shape[0]),
        "replicate_ids": [block["replicate_id"] for block in blocks],
        "replicate_labels": replicate_labels,
        "name_unit_map": name_unit_map,
        "replicates": replicate_meta,
        "rows_summary": stats.get("rows_summary"),
        "preview_lines": preview_lines,
    }

    return df_long, _coerce_metadata_scalars(metadata)


# ---------------------------------------------------------------------------
# Dialect sniffing helpers
# ---------------------------------------------------------------------------


def _sniff_dialect_and_header(
    path: str,
    *,
    preview_lines: int = DEFAULT_PREVIEW_LINES,
    header_rows: int = DEFAULT_HEADER_ROWS,
    decimal_override: Optional[str] = None,
) -> Dict[str, Any]:
    """Inspect a limited preview of the CSV to detect dialect information."""

    preview_raw_lines, encoding = _read_preview_lines(path, preview_lines)
    if not preview_raw_lines:
        raise ValueError(f"CSV appears empty: {path}")

    cleaned_preview_lines = [_normalise_line(line) for line in preview_raw_lines]
    sample_text = "\n".join(cleaned_preview_lines)

    try:
        dialect = csv.Sniffer().sniff(sample_text, delimiters=DELIMITER_CANDIDATES)
        delimiter = dialect.delimiter
    except csv.Error:
        delimiter = ","
        LOGGER.debug("Falling back to default delimiter ',' for %s", path)

    reader = csv.reader(
        cleaned_preview_lines[:preview_lines],
        delimiter=delimiter,
        quotechar='"',
        doublequote=True,
    )
    rows = [_restore_decimal_placeholders(row) for row in reader]
    if len(rows) < header_rows:
        raise ValueError(
            f"Expected at least {header_rows} header rows, found {len(rows)} in preview"
        )

    header_slice = rows[:header_rows]
    data_rows = rows[header_rows:]

    columns_mi, replicate_labels, name_unit_map = _build_columns_from_header(header_slice)

    decimal = decimal_override or _detect_decimal_separator(data_rows)

    return {
        "delimiter": delimiter,
        "decimal": decimal,
        "encoding": encoding,
        "header_rows": header_rows,
        "columns_multiindex": columns_mi,
        "replicate_labels": replicate_labels,
        "name_unit_map": name_unit_map,
        "n_columns": len(columns_mi),
    }


def _read_preview_lines(path: str, preview_lines: int) -> Tuple[List[str], str]:
    """Read up to ``preview_lines`` lines, trying multiple encodings."""

    errors: List[UnicodeDecodeError] = []
    for encoding in ENCODING_CANDIDATES:
        try:
            lines: List[str] = []
            with Path(path).open("r", encoding=encoding) as fh:
                for _, line in zip(range(preview_lines), fh):
                    lines.append(line.rstrip("\r\n"))
            return lines, encoding
        except UnicodeDecodeError as exc:  # pragma: no cover - depends on file
            errors.append(exc)
            continue
    if errors:  # pragma: no cover - defensive
        raise errors[-1]
    return [], "utf-8"


def _iter_csv_rows(path: str, *, encoding: str, delimiter: str) -> Iterable[List[str]]:
    """Yield parsed CSV rows after normalising quoting quirks."""

    with Path(path).open("r", encoding=encoding) as fh:
        normalised_lines = (_normalise_line(line.rstrip("\r\n")) for line in fh)
        reader = csv.reader(
            normalised_lines,
            delimiter=delimiter,
            quotechar='"',
            doublequote=True,
        )
        for row in reader:
            yield [cell.replace(DECIMAL_PLACEHOLDER, ",").strip() for cell in row]


def _normalise_line(line: str) -> str:
    """Strip outer quotes and collapse doubled quotes within a CSV line."""

    if line and line[0] == '"' and line[-1] == '"':
        line = line[1:-1]
    line = line.replace('""', '"')
    return _DECIMAL_SUB_RE.sub(DECIMAL_PLACEHOLDER, line)


def _restore_decimal_placeholders(row: Iterable[str]) -> List[str]:
    return [cell.replace(DECIMAL_PLACEHOLDER, ",") for cell in row]


def _build_columns_from_header(
    header_rows: Sequence[Sequence[str]],
) -> Tuple[pd.MultiIndex, List[str], List[Dict[str, Any]]]:
    if len(header_rows) < 3:
        raise ValueError("Expected three header rows (label, name, unit)")

    max_len = max(len(row) for row in header_rows)
    padded_rows = [
        list(row) + [""] * (max_len - len(row))
        for row in header_rows[:3]
    ]
    replicate_row, name_row, unit_row = padded_rows

    replicate_series = pd.Series(replicate_row, dtype="object")
    replicate_series = replicate_series.fillna("").astype(str).str.strip()
    replicate_series = replicate_series.replace("", pd.NA).ffill().fillna("")

    name_series = pd.Series(name_row, dtype="object").fillna("").astype(str).str.strip()
    unit_series = pd.Series(unit_row, dtype="object").fillna("").astype(str).str.strip()

    tuples: List[Tuple[str, str, str]] = []
    replicate_labels: List[str] = []
    name_unit_map: List[Dict[str, Any]] = []

    for idx in range(max_len):
        rep = replicate_series.iat[idx]
        name = name_series.iat[idx]
        unit = unit_series.iat[idx]
        if not (rep or name or unit):
            continue
        if not rep:
            rep = tuples[-1][0] if tuples else f"rep{len(tuples)+1:02d}"
        tuples.append((rep, name, unit))
        name_unit_map.append(
            {
                "column_index": idx,
                "replicate_label": rep,
                "name": name,
                "unit": unit,
            }
        )
        if not replicate_labels or replicate_labels[-1] != rep:
            replicate_labels.append(rep)

    columns_mi = pd.MultiIndex.from_tuples(
        tuples,
        names=["replicate", "name", "unit"],
    )
    return columns_mi, replicate_labels, name_unit_map


def _detect_decimal_separator(data_rows: Sequence[Sequence[str]]) -> str:
    comma_count = 0
    dot_count = 0
    for row in data_rows:
        for value in row:
            if value is None or value == "":
                continue
            if "," in value:
                comma_count += 1
            if "." in value:
                dot_count += 1
    if comma_count and not dot_count:
        return ","
    if dot_count and not comma_count:
        return "."
    if comma_count >= dot_count:
        return ","
    return "."


# ---------------------------------------------------------------------------
# Replicate block helpers
# ---------------------------------------------------------------------------


def _collect_replicate_blocks(columns_mi: pd.MultiIndex) -> List[Dict[str, Any]]:
    if not isinstance(columns_mi, pd.MultiIndex):
        raise TypeError("columns_mi must be a pandas MultiIndex")

    blocks: List[Dict[str, Any]] = []
    seen_ids: set[str] = set()

    current_label: Optional[str] = None
    current_columns: List[Tuple[str, str, str]] = []
    current_indices: List[int] = []

    for idx, column in enumerate(columns_mi):
        replicate_label = str(column[0]).strip()
        if not replicate_label:
            continue
        if current_label is None:
            current_label = replicate_label
        if replicate_label != current_label:
            if current_columns:
                blocks.append(
                    _finalise_block(
                        current_label,
                        current_columns,
                        current_indices,
                        len(blocks),
                        seen_ids,
                    )
                )
            current_label = replicate_label
            current_columns = []
            current_indices = []
        current_columns.append(column)
        current_indices.append(idx)

    if current_columns:
        blocks.append(
            _finalise_block(
                current_label or "rep0",
                current_columns,
                current_indices,
                len(blocks),
                seen_ids,
            )
        )

    return blocks


def _finalise_block(
    replicate_label: str,
    columns: Sequence[Tuple[str, str, str]],
    indices: Sequence[int],
    position: int,
    seen_ids: set[str],
) -> Dict[str, Any]:
    measurement_map: Dict[str, Dict[str, Any]] = {}

    for column, absolute_idx in zip(columns, indices):
        _, raw_name, raw_unit = column
        info = _classify_measurement(raw_name, raw_unit)
        if info is None:
            continue
        field = info["field"]
        if field in measurement_map:
            continue
        measurement_map[field] = {
            "column_key": column,
            "original_unit": info["original_unit"],
            "canonical_unit": info["canonical_unit"],
            "scale": info["scale"],
            "name": info["name"],
            "column_index": absolute_idx,
        }

    missing = {"time", "force", "disp"} - set(measurement_map)
    if missing:
        raise ValueError(
            f"Replicate '{replicate_label}' missing columns: {', '.join(sorted(missing))}"
        )

    replicate_id = _normalize_replicate_label(replicate_label, position, seen_ids)

    return {
        "replicate_label": replicate_label,
        "replicate_id": replicate_id,
        "columns": measurement_map,
        "index": position,
        "metrics": {
            "rows_initial": 0,
            "rows_after_time_drop": 0,
            "rows_after_monotonic": 0,
            "dropped_time_na": 0,
            "dropped_non_monotonic": 0,
        },
    }


def _classify_measurement(name: str, unit: str) -> Optional[Dict[str, Any]]:
    norm_name = _normalize_token(name)
    norm_unit = _normalize_token(unit)

    if norm_name == "":
        norm_name = norm_unit

    if norm_name in TIME_NAME_TOKENS or norm_unit in TIME_UNIT_TOKENS:
        field = "time"
    elif norm_name in FORCE_NAME_TOKENS or norm_unit in FORCE_UNIT_TOKENS:
        field = "force"
    elif norm_name in DISP_NAME_TOKENS or norm_unit in DISP_UNIT_TOKENS:
        field = "disp"
    else:
        LOGGER.debug("Unclassified measurement name=%s unit=%s", name, unit)
        return None

    canonical_unit = CANONICAL_UNITS[field]
    scale = 1.0

    conversion = UNIT_CONVERSIONS.get((field, norm_unit))
    if conversion:
        canonical_unit, scale = conversion

    return {
        "field": field,
        "name": name,
        "original_unit": unit,
        "canonical_unit": canonical_unit,
        "scale": scale,
    }


def _normalize_replicate_label(label: str, index: int, seen_ids: set[str]) -> str:
    clean = _normalize_token(label)
    clean = re.sub(r"[^0-9a-z_]+", "_", clean)
    clean = clean.strip("_")
    clean = re.sub(r"_+", "_", clean)
    if not clean:
        clean = f"rep{index+1}"
    if clean[0].isdigit():
        clean = f"rep{clean}"
    base = clean
    suffix = 1
    while base in seen_ids:
        suffix += 1
        base = f"{clean}_{suffix}"
    seen_ids.add(base)
    return base


# ---------------------------------------------------------------------------
# Data coercion helpers
# ---------------------------------------------------------------------------


def _coerce_numeric(df: pd.DataFrame, decimal: str) -> pd.DataFrame:
    numeric_df = df.copy()
    decimal = decimal or "."

    for column in numeric_df.columns:
        series = numeric_df[column]
        if pd.api.types.is_numeric_dtype(series):
            continue
        series = series.astype("string")
        series = series.str.strip()
        series = series.mask(series == "", pd.NA)
        if decimal == ",":
            series = series.str.replace(" ", "", regex=False)
            series = series.str.replace("\u00a0", "", regex=False)
            series = series.str.replace(",", ".", regex=False)
        else:
            series = series.str.replace(" ", "", regex=False)
            series = series.str.replace("\u00a0", "", regex=False)
        numeric_df[column] = pd.to_numeric(series, errors="coerce")

    return numeric_df


def _build_long_frame(df: pd.DataFrame, blocks: List[Dict[str, Any]]) -> pd.DataFrame:
    frames: List[pd.DataFrame] = []

    for block in blocks:
        cols = block["columns"]
        subset = df[[
            cols["time"]["column_key"],
            cols["force"]["column_key"],
            cols["disp"]["column_key"],
        ]].copy()
        subset.columns = [CANONICAL_FIELDS["time"], CANONICAL_FIELDS["force"], CANONICAL_FIELDS["disp"]]

        block_metrics = block.setdefault("metrics", {})
        block_metrics["rows_initial"] = int(subset.shape[0])

        for field in ("time", "force", "disp"):
            scale = cols[field]["scale"]
            if scale != 1.0:
                subset[CANONICAL_FIELDS[field]] = subset[CANONICAL_FIELDS[field]] * scale

        subset.dropna(subset=[CANONICAL_FIELDS["time"]], inplace=True)
        block_metrics["rows_after_time_drop"] = int(subset.shape[0])
        block_metrics["dropped_time_na"] = block_metrics["rows_initial"] - block_metrics["rows_after_time_drop"]

        diffs = subset[CANONICAL_FIELDS["time"]].diff()
        non_monotonic_mask = diffs < 0
        dropped_non_monotonic = int(non_monotonic_mask.sum())
        if dropped_non_monotonic:
            subset = subset.loc[~non_monotonic_mask]
        block_metrics["rows_after_monotonic"] = int(subset.shape[0])
        block_metrics["dropped_non_monotonic"] = dropped_non_monotonic

        subset["replicate_id"] = block["replicate_id"]
        frames.append(subset[["replicate_id", CANONICAL_FIELDS["time"], CANONICAL_FIELDS["force"], CANONICAL_FIELDS["disp"]]])

    if not frames:
        return pd.DataFrame(columns=["replicate_id", *CANONICAL_FIELDS.values()])

    df_long = pd.concat(frames, axis=0, ignore_index=True)
    df_long = df_long[["replicate_id", *CANONICAL_FIELDS.values()]]
    return df_long


def _compute_stats(df_long: pd.DataFrame) -> Dict[str, Any]:
    if df_long.empty:
        return {
            "replicates": {},
            "row_count": 0,
            "rows_summary": {"min": 0, "median": 0, "max": 0},
        }

    replicate_groups = df_long.groupby("replicate_id", sort=False)
    replicates: Dict[str, Dict[str, Any]] = {}
    row_counts: List[int] = []

    for rep_id, frame in replicate_groups:
        row_count = int(frame.shape[0])
        row_counts.append(row_count)

        dt = frame[CANONICAL_FIELDS["time"]].diff().dropna()
        dt_median = float(dt.median()) if not dt.empty else math.nan
        dt_std = float(dt.std(ddof=1)) if len(dt) > 1 else 0.0
        sampling_rate = float(1.0 / dt_median) if dt_median and not math.isnan(dt_median) and dt_median != 0 else math.nan
        n_nans = int(frame[[CANONICAL_FIELDS["force"], CANONICAL_FIELDS["disp"]]].isna().sum().sum())

        replicates[rep_id] = {
            "n_samples": row_count,
            "n_nans": n_nans,
            "dt_median": dt_median,
            "dt_std": dt_std,
            "Fs": sampling_rate,
            "time_min": float(frame[CANONICAL_FIELDS["time"]].min()) if row_count else math.nan,
            "time_max": float(frame[CANONICAL_FIELDS["time"]].max()) if row_count else math.nan,
        }

    row_counts_arr = np.array(row_counts, dtype=float)
    rows_summary = {
        "min": int(np.nanmin(row_counts_arr)),
        "median": float(np.nanmedian(row_counts_arr)),
        "max": int(np.nanmax(row_counts_arr)),
    }

    return {
        "replicates": replicates,
        "row_count": int(df_long.shape[0]),
        "rows_summary": rows_summary,
    }


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------


def _normalize_token(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip().strip('"').lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"\s+", " ", text)
    return text


def _coerce_metadata_scalars(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: _coerce_metadata_scalars(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_coerce_metadata_scalars(v) for v in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if pd.isna(obj):
        return math.nan
    return obj
