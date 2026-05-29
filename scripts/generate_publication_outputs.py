#!/usr/bin/env python3
"""Regenerate publication tables and release-curve figures.

The script is intentionally manifest-driven. Dataset inclusion decisions live in
publication/dataset_manifest.csv, not in ad hoc notebook state.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

import numpy as np

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from slipstick.core import (
    _analyse_replicate,
    _find_spikes,
    estimate_instrumental_noise,
    process_replicates,
)
from slipstick.io import load_replicates
from slipstick.models import Replicate


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = REPO_ROOT / "publication" / "dataset_manifest.csv"
DEFAULT_RESIDUAL_PANELS = REPO_ROOT / "publication" / "main_residual_profiles.csv"
DEFAULT_DATASETS_DIR = REPO_ROOT / "datasets"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "publication" / "generated"
CSV_WRITE_KWARGS = {"lineterminator": "\n"}

SEALANT_ORDER = ["C1E", "U2E", "T1E", "T2E", "C1EN", "T1EN", "T2EN"]
LINER_ORDER = ["dolpap", "rossella", "crosil42"]
PLOT_SIDE_ORDER = ["external", "internal"]
TABLE_SIDE_ORDER = ["internal", "external"]

FORCE_UNIT = "cN/25 mm"
DEFAULT_NOISE_FORCE_ONSET_N = 0.2
NORMAL_RELEASE_Y_MIN_CN = 0.0
NORMAL_RELEASE_Y_MAX_CN = 30.0
SEVERE_RELEASE_ABOVE_NORMAL_FRACTION = 0.05
DEFAULT_THRESHOLD_SENSITIVITY_CN = [0.5, 1.0, 1.4, 2.0, 3.0]


@dataclass(frozen=True)
class ManifestRow:
    figure: int
    liner: str
    liner_label: str
    sealant: str
    side: str
    side_label: str
    dataset_file: str

    @property
    def key(self) -> tuple[str, str, str]:
        return (self.liner, self.sealant, self.side)


@dataclass(frozen=True)
class TraceMetric:
    figure: int
    liner: str
    liner_label: str
    sealant: str
    side: str
    side_label: str
    dataset_file: str
    replicate: str
    total_replicates_in_file: int
    valid_release_window: bool
    mean_release_cN_25mm: float
    sd_trace_cN_25mm: float
    n_samples_50_200mm: int
    disp_min_used_mm: float
    disp_max_used_mm: float
    peak_count_1p4cN: int | None
    max_abs_residual_cN_25mm: float
    noise_std_cN_25mm: float
    noise_max_abs_cN_25mm: float
    noise_samples: int | None
    instrument_peak_hz: float | None
    filter_cutoff_hz: float | None
    threshold_peak_counts: dict[float, int]


@dataclass(frozen=True)
class ConfigurationSummary:
    figure: int
    liner: str
    liner_label: str
    sealant: str
    side: str
    side_label: str
    dataset_file: str
    total_replicates_in_file: int
    n_replicates: int
    mean_release_cN_25mm_mean: float
    mean_release_cN_25mm_sd: float
    mean_release_cN_25mm_median: float
    trace_samples_min: int | None
    trace_samples_max: int | None
    peak_count_1p4cN_mean: float
    peak_count_1p4cN_sd: float
    peak_count_1p4cN_sum: int | None
    noise_std_cN_25mm_median: float
    noise_max_abs_cN_25mm_max: float
    instrument_peak_hz_median: float
    filter_cutoff_hz_median: float


@dataclass(frozen=True)
class ResidualPanel:
    panel: str
    dataset_file: str
    replicate: str
    label: str


def finite_or_blank(value: float | int | None, digits: int | None = None) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and not math.isfinite(value):
        return ""
    if digits is None:
        return str(value)
    return f"{float(value):.{digits}f}"


def threshold_token(threshold_cN: float) -> str:
    return f"{threshold_cN:g}".replace(".", "p")


def sample_sd(values: Sequence[float]) -> float:
    if len(values) < 2:
        return 0.0
    return float(np.std(np.asarray(values, dtype=float), ddof=1))


def safe_mean(values: Sequence[float]) -> float:
    return float(np.mean(np.asarray(values, dtype=float))) if values else math.nan


def safe_median(values: Sequence[float]) -> float:
    return float(np.median(np.asarray(values, dtype=float))) if values else math.nan


def read_manifest(path: Path, datasets_dir: Path) -> list[ManifestRow]:
    required = {
        "figure",
        "liner",
        "liner_label",
        "sealant",
        "side",
        "side_label",
        "dataset_file",
    }
    rows: list[ManifestRow] = []
    with path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        missing = required.difference(reader.fieldnames or [])
        if missing:
            raise ValueError(f"manifest missing columns: {sorted(missing)}")
        for raw in reader:
            row = ManifestRow(
                figure=int(raw["figure"]),
                liner=raw["liner"].strip(),
                liner_label=raw["liner_label"].strip(),
                sealant=raw["sealant"].strip(),
                side=raw["side"].strip(),
                side_label=raw["side_label"].strip(),
                dataset_file=raw["dataset_file"].strip(),
            )
            if row.sealant not in SEALANT_ORDER:
                raise ValueError(f"unexpected sealant in manifest: {row.sealant}")
            if row.liner not in LINER_ORDER:
                raise ValueError(f"unexpected liner in manifest: {row.liner}")
            if row.side not in {"internal", "external"}:
                raise ValueError(f"unexpected side in manifest: {row.side}")
            if not (datasets_dir / row.dataset_file).exists():
                raise FileNotFoundError(f"manifest dataset missing: {row.dataset_file}")
            rows.append(row)
    validate_manifest(rows)
    return rows


def validate_manifest(rows: list[ManifestRow]) -> None:
    keys: set[tuple[str, str, str]] = set()
    figures: dict[int, list[ManifestRow]] = {}
    for row in rows:
        if row.key in keys:
            raise ValueError(f"duplicate manifest key: {row.key}")
        keys.add(row.key)
        figures.setdefault(row.figure, []).append(row)

    expected_keys = {
        (liner, sealant, side)
        for liner in LINER_ORDER
        for sealant in SEALANT_ORDER
        for side in ("external", "internal")
    }
    missing = expected_keys.difference(keys)
    extra = keys.difference(expected_keys)
    if missing or extra:
        raise ValueError(f"manifest matrix mismatch; missing={sorted(missing)}, extra={sorted(extra)}")

    for figure, figure_rows in figures.items():
        sides = sorted(row.side for row in figure_rows)
        if sides != ["external", "internal"]:
            raise ValueError(f"figure {figure} must contain one external and one internal row")
        liners = {row.liner for row in figure_rows}
        sealants = {row.sealant for row in figure_rows}
        if len(liners) != 1 or len(sealants) != 1:
            raise ValueError(f"figure {figure} mixes liner/sealant combinations")


def read_residual_panels(path: Path, datasets_dir: Path) -> list[ResidualPanel]:
    required = {"panel", "dataset_file", "replicate", "label"}
    panels: list[ResidualPanel] = []
    with path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        missing = required.difference(reader.fieldnames or [])
        if missing:
            raise ValueError(f"residual panel file missing columns: {sorted(missing)}")
        for raw in reader:
            panel = ResidualPanel(
                panel=raw["panel"].strip().lower(),
                dataset_file=raw["dataset_file"].strip(),
                replicate=raw["replicate"].strip(),
                label=raw["label"].strip(),
            )
            if not (datasets_dir / panel.dataset_file).exists():
                raise FileNotFoundError(f"residual panel dataset missing: {panel.dataset_file}")
            panels.append(panel)
    expected = ["a", "b", "c"]
    actual = [panel.panel for panel in panels]
    if actual != expected:
        raise ValueError(f"residual panels must be ordered {expected}, got {actual}")
    return panels


def scaled_replicate(rep: Replicate, force_scale: float) -> Replicate:
    return Replicate(
        rep_id=rep.rep_id,
        time_s=np.asarray(rep.time_s, dtype=float),
        force_n=np.asarray(rep.force_n, dtype=float) * force_scale,
        disp_mm=np.asarray(rep.disp_mm, dtype=float),
    )


def release_window_stats(
    rep: Replicate,
    *,
    disp_min: float,
    disp_max: float,
) -> tuple[bool, float, float, int, float, float]:
    disp = np.asarray(rep.disp_mm, dtype=float)
    force_cN = np.asarray(rep.force_n, dtype=float) * 100.0
    mask = (
        np.isfinite(disp)
        & np.isfinite(force_cN)
        & (disp >= disp_min)
        & (disp <= disp_max)
    )
    if np.count_nonzero(mask) < 2:
        return False, math.nan, math.nan, 0, math.nan, math.nan

    window_force = force_cN[mask]
    window_disp = disp[mask]
    return (
        True,
        float(np.mean(window_force)),
        sample_sd([float(value) for value in window_force]),
        int(window_force.size),
        float(np.min(window_disp)),
        float(np.max(window_disp)),
    )


def analyse_dataset(
    row: ManifestRow,
    *,
    datasets_dir: Path,
    collection_width_mm: float,
    report_width_mm: float,
    disp_min: float,
    disp_max: float,
    threshold_cN: float,
    polyorder: int,
    window_seconds: float | None,
    noise_disp_min: float,
    noise_disp_max: float,
    noise_min_samples: int,
    instrument_cutoff_factor: float,
    apply_filter: bool,
    thresholds_cN: Sequence[float] | None = None,
) -> list[TraceMetric]:
    dataset_path = datasets_dir / row.dataset_file
    raw_replicates = load_replicates(dataset_path)
    if not raw_replicates:
        raise ValueError(f"no replicates found in {dataset_path}")

    force_scale = report_width_mm / collection_width_mm
    scaled_reps = [scaled_replicate(rep, force_scale) for rep in raw_replicates]
    noise_force_onset_n = DEFAULT_NOISE_FORCE_ONSET_N * force_scale

    noise_by_id = {}
    for rep in scaled_reps:
        noise_by_id[rep.rep_id] = estimate_instrumental_noise(
            rep,
            disp_min=noise_disp_min,
            disp_max=noise_disp_max,
            force_abs_max=None,
            min_samples=noise_min_samples,
            force_onset=noise_force_onset_n,
        )

    peak_values = [
        estimate.noise_peak_hz
        for estimate in noise_by_id.values()
        if estimate is not None and estimate.noise_peak_hz is not None
    ]
    instrument_peak_hz = safe_median([float(value) for value in peak_values])
    filter_cutoff_hz = (
        instrument_peak_hz * instrument_cutoff_factor
        if apply_filter and math.isfinite(instrument_peak_hz)
        else None
    )

    processed_reps = process_replicates(
        scaled_reps,
        force_scale=1.0,
        cutoff_hz=filter_cutoff_hz,
    )
    processed_by_id = {rep.rep_id: rep for rep in processed_reps}
    threshold_n = threshold_cN / 100.0
    threshold_counts_to_compute = (
        [threshold_cN] if thresholds_cN is None else list(thresholds_cN)
    )

    metrics: list[TraceMetric] = []
    for rep in scaled_reps:
        valid, mean_release, sd_trace, sample_count, disp_min_used, disp_max_used = (
            release_window_stats(rep, disp_min=disp_min, disp_max=disp_max)
        )

        result = _analyse_replicate(
            processed_by_id.get(rep.rep_id, rep),
            displacement_window=(disp_min, disp_max),
            window_seconds=window_seconds,
            polyorder=polyorder,
            threshold=threshold_n,
        )
        threshold_peak_counts: dict[float, int] = {}
        if result is not None:
            for candidate_threshold_cN in threshold_counts_to_compute:
                threshold_peak_counts[candidate_threshold_cN] = len(
                    _find_spikes(
                        result.time,
                        result.disp,
                        result.residual,
                        candidate_threshold_cN / 100.0,
                    )
                )
        peak_count = threshold_peak_counts.get(threshold_cN) if result is not None else None
        max_abs_residual = (
            float(np.max(np.abs(result.residual)) * 100.0)
            if result is not None and result.residual.size
            else math.nan
        )

        noise = noise_by_id.get(rep.rep_id)
        metrics.append(
            TraceMetric(
                figure=row.figure,
                liner=row.liner,
                liner_label=row.liner_label,
                sealant=row.sealant,
                side=row.side,
                side_label=row.side_label,
                dataset_file=row.dataset_file,
                replicate=rep.rep_id,
                total_replicates_in_file=len(raw_replicates),
                valid_release_window=valid,
                mean_release_cN_25mm=mean_release,
                sd_trace_cN_25mm=sd_trace,
                n_samples_50_200mm=sample_count,
                disp_min_used_mm=disp_min_used,
                disp_max_used_mm=disp_max_used,
                peak_count_1p4cN=peak_count,
                max_abs_residual_cN_25mm=max_abs_residual,
                noise_std_cN_25mm=(
                    noise.std_n * 100.0 if noise is not None else math.nan
                ),
                noise_max_abs_cN_25mm=(
                    noise.max_abs_n * 100.0 if noise is not None else math.nan
                ),
                noise_samples=noise.sample_count if noise is not None else None,
                instrument_peak_hz=instrument_peak_hz,
                filter_cutoff_hz=filter_cutoff_hz,
                threshold_peak_counts=threshold_peak_counts,
            )
        )
    return metrics


def summarize_configuration(row: ManifestRow, metrics: list[TraceMetric]) -> ConfigurationSummary:
    valid_metrics = [metric for metric in metrics if metric.valid_release_window]
    release_values = [metric.mean_release_cN_25mm for metric in valid_metrics]
    peak_values = [
        float(metric.peak_count_1p4cN)
        for metric in metrics
        if metric.peak_count_1p4cN is not None
    ]
    noise_std = [
        metric.noise_std_cN_25mm
        for metric in metrics
        if math.isfinite(metric.noise_std_cN_25mm)
    ]
    noise_max_abs = [
        metric.noise_max_abs_cN_25mm
        for metric in metrics
        if math.isfinite(metric.noise_max_abs_cN_25mm)
    ]
    instrument_peaks = [
        metric.instrument_peak_hz
        for metric in metrics
        if metric.instrument_peak_hz is not None and math.isfinite(metric.instrument_peak_hz)
    ]
    cutoffs = [
        metric.filter_cutoff_hz
        for metric in metrics
        if metric.filter_cutoff_hz is not None and math.isfinite(metric.filter_cutoff_hz)
    ]
    sample_counts = [metric.n_samples_50_200mm for metric in valid_metrics]

    return ConfigurationSummary(
        figure=row.figure,
        liner=row.liner,
        liner_label=row.liner_label,
        sealant=row.sealant,
        side=row.side,
        side_label=row.side_label,
        dataset_file=row.dataset_file,
        total_replicates_in_file=metrics[0].total_replicates_in_file if metrics else 0,
        n_replicates=len(valid_metrics),
        mean_release_cN_25mm_mean=safe_mean(release_values),
        mean_release_cN_25mm_sd=sample_sd(release_values),
        mean_release_cN_25mm_median=safe_median(release_values),
        trace_samples_min=min(sample_counts) if sample_counts else None,
        trace_samples_max=max(sample_counts) if sample_counts else None,
        peak_count_1p4cN_mean=safe_mean(peak_values),
        peak_count_1p4cN_sd=sample_sd(peak_values),
        peak_count_1p4cN_sum=int(sum(peak_values)) if peak_values else None,
        noise_std_cN_25mm_median=safe_median(noise_std),
        noise_max_abs_cN_25mm_max=max(noise_max_abs) if noise_max_abs else math.nan,
        instrument_peak_hz_median=safe_median(instrument_peaks),
        filter_cutoff_hz_median=safe_median(cutoffs),
    )


def write_replicate_metrics(path: Path, rows: list[TraceMetric]) -> None:
    fieldnames = [
        "figure",
        "liner",
        "liner_label",
        "sealant",
        "side",
        "side_label",
        "dataset_file",
        "replicate",
        "total_replicates_in_file",
        "valid_release_window",
        "mean_release_cN_25mm",
        "sd_trace_cN_25mm",
        "n_samples_50_200mm",
        "disp_min_used_mm",
        "disp_max_used_mm",
        "peak_count_1p4cN",
        "max_abs_residual_cN_25mm",
        "noise_std_cN_25mm",
        "noise_max_abs_cN_25mm",
        "noise_samples",
        "instrument_peak_hz",
        "filter_cutoff_hz",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, **CSV_WRITE_KWARGS)
        writer.writeheader()
        for metric in rows:
            writer.writerow(
                {
                    "figure": metric.figure,
                    "liner": metric.liner,
                    "liner_label": metric.liner_label,
                    "sealant": metric.sealant,
                    "side": metric.side,
                    "side_label": metric.side_label,
                    "dataset_file": metric.dataset_file,
                    "replicate": metric.replicate,
                    "total_replicates_in_file": metric.total_replicates_in_file,
                    "valid_release_window": int(metric.valid_release_window),
                    "mean_release_cN_25mm": finite_or_blank(metric.mean_release_cN_25mm, 6),
                    "sd_trace_cN_25mm": finite_or_blank(metric.sd_trace_cN_25mm, 6),
                    "n_samples_50_200mm": metric.n_samples_50_200mm,
                    "disp_min_used_mm": finite_or_blank(metric.disp_min_used_mm, 6),
                    "disp_max_used_mm": finite_or_blank(metric.disp_max_used_mm, 6),
                    "peak_count_1p4cN": (
                        "" if metric.peak_count_1p4cN is None else metric.peak_count_1p4cN
                    ),
                    "max_abs_residual_cN_25mm": finite_or_blank(
                        metric.max_abs_residual_cN_25mm, 6
                    ),
                    "noise_std_cN_25mm": finite_or_blank(metric.noise_std_cN_25mm, 6),
                    "noise_max_abs_cN_25mm": finite_or_blank(
                        metric.noise_max_abs_cN_25mm, 6
                    ),
                    "noise_samples": (
                        "" if metric.noise_samples is None else metric.noise_samples
                    ),
                    "instrument_peak_hz": finite_or_blank(metric.instrument_peak_hz, 6),
                    "filter_cutoff_hz": finite_or_blank(metric.filter_cutoff_hz, 6),
                }
            )


def write_configuration_summary(path: Path, rows: list[ConfigurationSummary]) -> None:
    fieldnames = [
        "figure",
        "liner",
        "liner_label",
        "sealant",
        "side",
        "side_label",
        "dataset_file",
        "total_replicates_in_file",
        "n_replicates",
        "mean_release_cN_25mm_mean",
        "mean_release_cN_25mm_sd",
        "mean_release_cN_25mm_median",
        "trace_samples_min",
        "trace_samples_max",
        "peak_count_1p4cN_mean",
        "peak_count_1p4cN_sd",
        "peak_count_1p4cN_sum",
        "noise_std_cN_25mm_median",
        "noise_max_abs_cN_25mm_max",
        "instrument_peak_hz_median",
        "filter_cutoff_hz_median",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, **CSV_WRITE_KWARGS)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "figure": row.figure,
                    "liner": row.liner,
                    "liner_label": row.liner_label,
                    "sealant": row.sealant,
                    "side": row.side,
                    "side_label": row.side_label,
                    "dataset_file": row.dataset_file,
                    "total_replicates_in_file": row.total_replicates_in_file,
                    "n_replicates": row.n_replicates,
                    "mean_release_cN_25mm_mean": finite_or_blank(
                        row.mean_release_cN_25mm_mean, 6
                    ),
                    "mean_release_cN_25mm_sd": finite_or_blank(
                        row.mean_release_cN_25mm_sd, 6
                    ),
                    "mean_release_cN_25mm_median": finite_or_blank(
                        row.mean_release_cN_25mm_median, 6
                    ),
                    "trace_samples_min": (
                        "" if row.trace_samples_min is None else row.trace_samples_min
                    ),
                    "trace_samples_max": (
                        "" if row.trace_samples_max is None else row.trace_samples_max
                    ),
                    "peak_count_1p4cN_mean": finite_or_blank(
                        row.peak_count_1p4cN_mean, 6
                    ),
                    "peak_count_1p4cN_sd": finite_or_blank(row.peak_count_1p4cN_sd, 6),
                    "peak_count_1p4cN_sum": (
                        "" if row.peak_count_1p4cN_sum is None else row.peak_count_1p4cN_sum
                    ),
                    "noise_std_cN_25mm_median": finite_or_blank(
                        row.noise_std_cN_25mm_median, 6
                    ),
                    "noise_max_abs_cN_25mm_max": finite_or_blank(
                        row.noise_max_abs_cN_25mm_max, 6
                    ),
                    "instrument_peak_hz_median": finite_or_blank(
                        row.instrument_peak_hz_median, 6
                    ),
                    "filter_cutoff_hz_median": finite_or_blank(
                        row.filter_cutoff_hz_median, 6
                    ),
                }
            )


def summary_lookup(rows: list[ConfigurationSummary]) -> dict[tuple[str, str, str], ConfigurationSummary]:
    return {(row.liner, row.sealant, row.side): row for row in rows}


def format_mean_sd(row: ConfigurationSummary | None) -> str:
    if row is None or not math.isfinite(row.mean_release_cN_25mm_mean):
        return ""
    return f"{row.mean_release_cN_25mm_mean:.1f} +/- {row.mean_release_cN_25mm_sd:.1f}"


def ratio_display(inner: ConfigurationSummary | None, outer: ConfigurationSummary | None) -> str:
    if (
        inner is None
        or outer is None
        or inner.mean_release_cN_25mm_mean <= 0
        or outer.mean_release_cN_25mm_mean <= 0
        or not math.isfinite(inner.mean_release_cN_25mm_mean)
        or not math.isfinite(outer.mean_release_cN_25mm_mean)
    ):
        return ""
    ratio = inner.mean_release_cN_25mm_mean / outer.mean_release_cN_25mm_mean
    if ratio >= 1.0:
        rounded = int(round(ratio))
        return "1:1" if rounded <= 1 else f"{rounded}:1"
    rounded = int(round(1.0 / ratio))
    return "1:1" if rounded <= 1 else f"1:{rounded}"


def markdown_table(headers: list[str], rows: list[list[str]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def write_release_tables(output_dir: Path, summaries: list[ConfigurationSummary]) -> None:
    lookup = summary_lookup(summaries)
    table_rows: list[list[str]] = []
    numeric_rows: list[dict[str, object]] = []

    for liner in LINER_ORDER:
        liner_label = next(row.liner_label for row in summaries if row.liner == liner)
        for side in TABLE_SIDE_ORDER:
            side_label = "inner" if side == "internal" else "outer"
            table_rows.append(
                [liner_label, side_label]
                + [
                    format_mean_sd(lookup.get((liner, sealant, side)))
                    for sealant in SEALANT_ORDER
                ]
            )
        ratio_row = [liner_label, "force ratio (inner : outer)"]
        for sealant in SEALANT_ORDER:
            ratio_row.append(
                ratio_display(
                    lookup.get((liner, sealant, "internal")),
                    lookup.get((liner, sealant, "external")),
                )
            )
        table_rows.append(ratio_row)

        for sealant in SEALANT_ORDER:
            inner = lookup[(liner, sealant, "internal")]
            outer = lookup[(liner, sealant, "external")]
            numeric_rows.append(
                {
                    "liner": liner_label,
                    "sealant": sealant,
                    "inner_file": inner.dataset_file,
                    "outer_file": outer.dataset_file,
                    "inner_n": inner.n_replicates,
                    "outer_n": outer.n_replicates,
                    "inner_mean_cN_25mm": finite_or_blank(
                        inner.mean_release_cN_25mm_mean, 6
                    ),
                    "inner_sd_cN_25mm": finite_or_blank(inner.mean_release_cN_25mm_sd, 6),
                    "outer_mean_cN_25mm": finite_or_blank(
                        outer.mean_release_cN_25mm_mean, 6
                    ),
                    "outer_sd_cN_25mm": finite_or_blank(outer.mean_release_cN_25mm_sd, 6),
                    "inner_outer_ratio_numeric": finite_or_blank(
                        inner.mean_release_cN_25mm_mean / outer.mean_release_cN_25mm_mean,
                        6,
                    )
                    if outer.mean_release_cN_25mm_mean > 0
                    else "",
                    "ratio_display": ratio_display(inner, outer),
                }
            )

    headers = ["Liner", "Side"] + SEALANT_ORDER
    tables_dir = output_dir / "tables"
    tables_dir.mkdir(parents=True, exist_ok=True)
    (tables_dir / "release_force_table.md").write_text(
        "\n".join(
            [
                "# Release-Force Table",
                "",
                f"Values are mean +/- sample SD in {FORCE_UNIT}.",
                "The calculation uses per-replicate mean force over 50-200 mm.",
                "",
                markdown_table(headers, table_rows),
                "",
            ]
        ),
        encoding="utf-8",
    )

    with (tables_dir / "release_force_table.csv").open(
        "w", newline="", encoding="utf-8"
    ) as handle:
        writer = csv.writer(handle, **CSV_WRITE_KWARGS)
        writer.writerow(headers)
        writer.writerows(table_rows)

    numeric_path = tables_dir / "release_force_table_numeric.csv"
    with numeric_path.open("w", newline="", encoding="utf-8") as handle:
        fieldnames = list(numeric_rows[0].keys())
        writer = csv.DictWriter(handle, fieldnames=fieldnames, **CSV_WRITE_KWARGS)
        writer.writeheader()
        writer.writerows(numeric_rows)


def write_warnings(output_dir: Path, summaries: list[ConfigurationSummary]) -> None:
    rows: list[dict[str, object]] = []
    for row in summaries:
        if row.n_replicates != 10:
            rows.append(
                {
                    "severity": "review",
                    "liner": row.liner_label,
                    "sealant": row.sealant,
                    "side": row.side_label,
                    "dataset_file": row.dataset_file,
                    "message": f"valid 50-200 mm replicate count is {row.n_replicates}, not 10",
                }
            )
        if row.total_replicates_in_file != row.n_replicates:
            rows.append(
                {
                    "severity": "info",
                    "liner": row.liner_label,
                    "sealant": row.sealant,
                    "side": row.side_label,
                    "dataset_file": row.dataset_file,
                    "message": (
                        f"{row.total_replicates_in_file} traces in file; "
                        f"{row.n_replicates} have at least two samples in the 50-200 mm window"
                    ),
                }
            )

    path = output_dir / "data" / "warnings.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        fieldnames = ["severity", "liner", "sealant", "side", "dataset_file", "message"]
        writer = csv.DictWriter(handle, fieldnames=fieldnames, **CSV_WRITE_KWARGS)
        writer.writeheader()
        writer.writerows(rows)


def threshold_values(default_threshold_cN: float) -> list[float]:
    values = list(DEFAULT_THRESHOLD_SENSITIVITY_CN)
    if not any(math.isclose(default_threshold_cN, value) for value in values):
        values.append(default_threshold_cN)
    return sorted(values)


def summarize_configuration_for_threshold(
    row: ManifestRow,
    metrics: list[TraceMetric],
    *,
    threshold_cN: float,
) -> ConfigurationSummary:
    valid_metrics = [metric for metric in metrics if metric.valid_release_window]
    release_values = [metric.mean_release_cN_25mm for metric in valid_metrics]
    peak_values = [
        float(metric.threshold_peak_counts[threshold_cN])
        for metric in metrics
        if threshold_cN in metric.threshold_peak_counts
    ]
    noise_std = [
        metric.noise_std_cN_25mm
        for metric in metrics
        if math.isfinite(metric.noise_std_cN_25mm)
    ]
    noise_max_abs = [
        metric.noise_max_abs_cN_25mm
        for metric in metrics
        if math.isfinite(metric.noise_max_abs_cN_25mm)
    ]
    instrument_peaks = [
        metric.instrument_peak_hz
        for metric in metrics
        if metric.instrument_peak_hz is not None and math.isfinite(metric.instrument_peak_hz)
    ]
    cutoffs = [
        metric.filter_cutoff_hz
        for metric in metrics
        if metric.filter_cutoff_hz is not None and math.isfinite(metric.filter_cutoff_hz)
    ]
    sample_counts = [metric.n_samples_50_200mm for metric in valid_metrics]

    return ConfigurationSummary(
        figure=row.figure,
        liner=row.liner,
        liner_label=row.liner_label,
        sealant=row.sealant,
        side=row.side,
        side_label=row.side_label,
        dataset_file=row.dataset_file,
        total_replicates_in_file=metrics[0].total_replicates_in_file if metrics else 0,
        n_replicates=len(valid_metrics),
        mean_release_cN_25mm_mean=safe_mean(release_values),
        mean_release_cN_25mm_sd=sample_sd(release_values),
        mean_release_cN_25mm_median=safe_median(release_values),
        trace_samples_min=min(sample_counts) if sample_counts else None,
        trace_samples_max=max(sample_counts) if sample_counts else None,
        peak_count_1p4cN_mean=safe_mean(peak_values),
        peak_count_1p4cN_sd=sample_sd(peak_values),
        peak_count_1p4cN_sum=int(sum(peak_values)) if peak_values else None,
        noise_std_cN_25mm_median=safe_median(noise_std),
        noise_max_abs_cN_25mm_max=max(noise_max_abs) if noise_max_abs else math.nan,
        instrument_peak_hz_median=safe_median(instrument_peaks),
        filter_cutoff_hz_median=safe_median(cutoffs),
    )


def compute_threshold_summary_sets(
    manifest_rows: list[ManifestRow],
    *,
    metrics: list[TraceMetric],
    default_summaries: list[ConfigurationSummary],
    default_threshold_cN: float,
) -> dict[float, list[ConfigurationSummary]]:
    metrics_by_key: dict[tuple[str, str, str], list[TraceMetric]] = {}
    for metric in metrics:
        metrics_by_key.setdefault((metric.liner, metric.sealant, metric.side), []).append(
            metric
        )

    summary_sets: dict[float, list[ConfigurationSummary]] = {}
    for threshold_cN in threshold_values(default_threshold_cN):
        if math.isclose(threshold_cN, default_threshold_cN):
            summary_sets[threshold_cN] = default_summaries
            continue

        summary_sets[threshold_cN] = [
            summarize_configuration_for_threshold(
                row,
                metrics_by_key[row.key],
                threshold_cN=threshold_cN,
            )
            for row in manifest_rows
        ]
    return summary_sets


def spearman_vs_default(
    values: Sequence[float],
    default_values: Sequence[float],
    *,
    same_threshold: bool,
) -> tuple[float, float]:
    if same_threshold:
        return 1.0, 0.0
    try:
        from scipy.stats import spearmanr
    except ModuleNotFoundError as exc:
        raise SystemExit(
            "scipy is required for threshold robustness tables. Install the "
            "repository requirements."
        ) from exc

    result = spearmanr(values, default_values)
    return float(result.statistic), float(result.pvalue)


def write_threshold_robustness(
    path: Path,
    *,
    summary_sets: dict[float, list[ConfigurationSummary]],
    default_threshold_cN: float,
) -> list[dict[str, object]]:
    default_rows = summary_sets[default_threshold_cN]
    default_values = [row.peak_count_1p4cN_mean for row in default_rows]
    rows: list[dict[str, object]] = []

    for threshold_cN, summaries in sorted(summary_sets.items()):
        values = [row.peak_count_1p4cN_mean for row in summaries]
        rho, p_value = spearman_vs_default(
            values,
            default_values,
            same_threshold=math.isclose(threshold_cN, default_threshold_cN),
        )
        total_peaks = sum(
            row.peak_count_1p4cN_sum or 0
            for row in summaries
            if row.peak_count_1p4cN_sum is not None
        )
        rows.append(
            {
                "threshold_cN": threshold_cN,
                "spearman_rho_vs_default": rho,
                "spearman_p_value": p_value,
                "total_peaks": total_peaks,
                "configurations_mean_ge_1_peak": sum(
                    1 for row in summaries if row.peak_count_1p4cN_mean >= 1.0
                ),
                "configurations_mean_ge_5_peaks": sum(
                    1 for row in summaries if row.peak_count_1p4cN_mean >= 5.0
                ),
            }
        )

    fieldnames = [
        "threshold_cN",
        "spearman_rho_vs_default",
        "spearman_p_value",
        "total_peaks",
        "configurations_mean_ge_1_peak",
        "configurations_mean_ge_5_peaks",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, **CSV_WRITE_KWARGS)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "threshold_cN": finite_or_blank(row["threshold_cN"], 3),
                    "spearman_rho_vs_default": finite_or_blank(
                        row["spearman_rho_vs_default"], 6
                    ),
                    "spearman_p_value": finite_or_blank(row["spearman_p_value"], 12),
                    "total_peaks": row["total_peaks"],
                    "configurations_mean_ge_1_peak": row[
                        "configurations_mean_ge_1_peak"
                    ],
                    "configurations_mean_ge_5_peaks": row[
                        "configurations_mean_ge_5_peaks"
                    ],
                }
            )
    return rows


def write_threshold_noise_summary(
    path: Path,
    *,
    metrics: list[TraceMetric],
    summaries: list[ConfigurationSummary],
    default_threshold_cN: float,
) -> dict[str, object]:
    noise_std = [
        metric.noise_std_cN_25mm
        for metric in metrics
        if math.isfinite(metric.noise_std_cN_25mm)
    ]
    noise_max_abs = [
        metric.noise_max_abs_cN_25mm
        for metric in metrics
        if math.isfinite(metric.noise_max_abs_cN_25mm)
    ]
    summary = {
        "replicate_traces": len(metrics),
        "configurations": len(summaries),
        "default_threshold_cN": default_threshold_cN,
        "median_noise_std_cN_25mm": safe_median(noise_std),
        "p95_noise_std_cN_25mm": float(np.percentile(noise_std, 95)) if noise_std else math.nan,
        "max_noise_std_cN_25mm": max(noise_std) if noise_std else math.nan,
        "median_noise_max_abs_cN_25mm": safe_median(noise_max_abs),
        "p95_noise_max_abs_cN_25mm": (
            float(np.percentile(noise_max_abs, 95)) if noise_max_abs else math.nan
        ),
        "max_noise_max_abs_cN_25mm": max(noise_max_abs) if noise_max_abs else math.nan,
    }
    median_std = float(summary["median_noise_std_cN_25mm"])
    p95_std = float(summary["p95_noise_std_cN_25mm"])
    summary["threshold_to_median_noise_std_ratio"] = (
        default_threshold_cN / median_std if median_std > 0 else math.nan
    )
    summary["threshold_to_p95_noise_std_ratio"] = (
        default_threshold_cN / p95_std if p95_std > 0 else math.nan
    )

    rows = [
        ("replicate_traces", summary["replicate_traces"], ""),
        ("configurations", summary["configurations"], ""),
        ("default_threshold_cN", summary["default_threshold_cN"], "cN/25 mm"),
        ("median_noise_std_cN_25mm", summary["median_noise_std_cN_25mm"], "cN/25 mm"),
        ("p95_noise_std_cN_25mm", summary["p95_noise_std_cN_25mm"], "cN/25 mm"),
        ("max_noise_std_cN_25mm", summary["max_noise_std_cN_25mm"], "cN/25 mm"),
        (
            "median_noise_max_abs_cN_25mm",
            summary["median_noise_max_abs_cN_25mm"],
            "cN/25 mm",
        ),
        (
            "p95_noise_max_abs_cN_25mm",
            summary["p95_noise_max_abs_cN_25mm"],
            "cN/25 mm",
        ),
        (
            "max_noise_max_abs_cN_25mm",
            summary["max_noise_max_abs_cN_25mm"],
            "cN/25 mm",
        ),
        (
            "threshold_to_median_noise_std_ratio",
            summary["threshold_to_median_noise_std_ratio"],
            "x",
        ),
        (
            "threshold_to_p95_noise_std_ratio",
            summary["threshold_to_p95_noise_std_ratio"],
            "x",
        ),
    ]

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=["metric", "value", "unit"], **CSV_WRITE_KWARGS
        )
        writer.writeheader()
        for metric, value, unit in rows:
            writer.writerow(
                {
                    "metric": metric,
                    "value": (
                        value
                        if isinstance(value, int)
                        else finite_or_blank(float(value), 6)
                    ),
                    "unit": unit,
                }
            )
    return summary


def write_top_peak_configs(
    path: Path,
    *,
    summary_sets: dict[float, list[ConfigurationSummary]],
    default_threshold_cN: float,
    limit: int = 10,
) -> list[dict[str, object]]:
    default_rows = sorted(
        summary_sets[default_threshold_cN],
        key=lambda row: row.peak_count_1p4cN_mean,
        reverse=True,
    )[:limit]
    set_lookup = {
        threshold_cN: {
            (row.liner, row.sealant, row.side): row
            for row in summaries
        }
        for threshold_cN, summaries in summary_sets.items()
    }
    threshold_columns = []
    for threshold_cN in sorted(summary_sets):
        token = threshold_token(threshold_cN)
        threshold_columns.extend(
            [f"peak_count_{token}cN_mean", f"peak_count_{token}cN_sum"]
        )

    fieldnames = [
        "figure",
        "sealant",
        "liner_label",
        "side_label",
        "dataset_file",
        "n_replicates",
        "mean_release_cN_25mm_mean",
        "mean_release_cN_25mm_sd",
        "noise_std_cN_25mm_median",
        "noise_max_abs_cN_25mm_max",
        *threshold_columns,
    ]

    rows: list[dict[str, object]] = []
    for row in default_rows:
        key = (row.liner, row.sealant, row.side)
        out: dict[str, object] = {
            "figure": row.figure,
            "sealant": row.sealant,
            "liner_label": row.liner_label,
            "side_label": row.side_label,
            "dataset_file": row.dataset_file,
            "n_replicates": row.n_replicates,
            "mean_release_cN_25mm_mean": row.mean_release_cN_25mm_mean,
            "mean_release_cN_25mm_sd": row.mean_release_cN_25mm_sd,
            "noise_std_cN_25mm_median": row.noise_std_cN_25mm_median,
            "noise_max_abs_cN_25mm_max": row.noise_max_abs_cN_25mm_max,
        }
        for threshold_cN in sorted(summary_sets):
            threshold_row = set_lookup[threshold_cN][key]
            token = threshold_token(threshold_cN)
            out[f"peak_count_{token}cN_mean"] = threshold_row.peak_count_1p4cN_mean
            out[f"peak_count_{token}cN_sum"] = threshold_row.peak_count_1p4cN_sum
        rows.append(out)

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, **CSV_WRITE_KWARGS)
        writer.writeheader()
        for row in rows:
            formatted = row.copy()
            for name, value in formatted.items():
                if isinstance(value, float):
                    formatted[name] = finite_or_blank(value, 6)
            writer.writerow(formatted)
    return rows


def write_threshold_summary_json(
    path: Path,
    *,
    threshold_rows: list[dict[str, object]],
    noise_summary: dict[str, object],
    top_configs: list[dict[str, object]],
) -> None:
    def clean(value):
        if isinstance(value, float) and not math.isfinite(value):
            return None
        if isinstance(value, dict):
            return {key: clean(item) for key, item in value.items()}
        if isinstance(value, list):
            return [clean(item) for item in value]
        return value

    payload = {
        "noise_summary": noise_summary,
        "threshold_robustness": threshold_rows,
        "top_peak_configurations": top_configs,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(clean(payload), indent=2), encoding="utf-8")


def p_value_display(value: object) -> str:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return ""
    if not math.isfinite(numeric):
        return ""
    if numeric < 0.001:
        return "<0.001"
    return f"{numeric:.3f}"


def write_threshold_supplement_markdown(
    path: Path,
    *,
    threshold_rows: list[dict[str, object]],
    noise_summary: dict[str, object],
    top_configs: list[dict[str, object]],
) -> None:
    default_threshold = float(noise_summary["default_threshold_cN"])
    median_noise = float(noise_summary["median_noise_std_cN_25mm"])
    p95_noise = float(noise_summary["p95_noise_std_cN_25mm"])
    median_ratio = float(noise_summary["threshold_to_median_noise_std_ratio"])
    p95_ratio = float(noise_summary["threshold_to_p95_noise_std_ratio"])

    lines = [
        "# Supplementary Methodological Background",
        "",
        "## Threshold Robustness of Slip-Stick Peak Detection",
        "",
        "This supplementary note supports the operational residual-force threshold "
        f"of {default_threshold:.1f} cN/25 mm used for slip-stick peak detection. "
        "The threshold is not treated as a universal material constant; it is a "
        "reproducible detection criterion applied to all traces in the manuscript "
        "matrix.",
        "",
        "The values below are generated by `python scripts/generate_publication_outputs.py` "
        "from the publication dataset manifest.",
        "",
        "### S1. Dataset Scope",
        "",
        f"- Replicate traces: {int(noise_summary['replicate_traces'])}",
        f"- Liner-sealant-side configurations: {int(noise_summary['configurations'])}",
        "- Analysis window: 50-200 mm displacement.",
        "- Force normalization: cN/25 mm from the 90 mm collection width.",
        "- Peak definition: one contiguous positive residual excursion above the "
        "threshold is counted as one event.",
        "",
        "### S2. Noise Margin",
        "",
        "| Metric | Value |",
        "|---|---:|",
        f"| Median baseline noise SD | {median_noise:.3f} cN/25 mm |",
        f"| 95th percentile baseline noise SD | {p95_noise:.3f} cN/25 mm |",
        f"| Maximum baseline noise SD | {float(noise_summary['max_noise_std_cN_25mm']):.3f} cN/25 mm |",
        f"| Median baseline maximum absolute noise | {float(noise_summary['median_noise_max_abs_cN_25mm']):.3f} cN/25 mm |",
        f"| 95th percentile baseline maximum absolute noise | {float(noise_summary['p95_noise_max_abs_cN_25mm']):.3f} cN/25 mm |",
        f"| Maximum baseline maximum absolute noise | {float(noise_summary['max_noise_max_abs_cN_25mm']):.3f} cN/25 mm |",
        f"| Threshold / median noise SD | {median_ratio:.1f}x |",
        f"| Threshold / 95th percentile noise SD | {p95_ratio:.1f}x |",
        "",
        f"The {default_threshold:.1f} cN/25 mm threshold is therefore well above the "
        "measured baseline noise floor.",
        "",
        "### S3. Threshold Sensitivity",
        "",
        "Peak counts were recalculated at nearby residual-force thresholds. Spearman "
        "rho was computed across configuration-level mean peak counts relative to "
        f"the default {default_threshold:.1f} cN/25 mm threshold.",
        "",
        "| Threshold [cN/25 mm] | Spearman rho vs default | p value | Total peaks | Configs mean >= 1 peak | Configs mean >= 5 peaks |",
        "|---:|---:|---:|---:|---:|---:|",
    ]

    for row in threshold_rows:
        p_display = (
            "reference"
            if math.isclose(float(row["threshold_cN"]), default_threshold)
            else p_value_display(row["spearman_p_value"])
        )
        lines.append(
            f"| {float(row['threshold_cN']):.1f} "
            f"| {float(row['spearman_rho_vs_default']):.3f} "
            f"| {p_display} "
            f"| {int(row['total_peaks'])} "
            f"| {int(row['configurations_mean_ge_1_peak'])} "
            f"| {int(row['configurations_mean_ge_5_peaks'])} |"
        )

    threshold_lookup = {float(row["threshold_cN"]): row for row in threshold_rows}
    low_row = threshold_lookup.get(1.0)
    high_row = threshold_lookup.get(2.0)
    stability_sentence = ""
    if low_row is not None and high_row is not None:
        stability_sentence = (
            " The configuration-level rankings remained strongly correlated with "
            "the default analysis at 1.0 cN/25 mm "
            f"(rho = {float(low_row['spearman_rho_vs_default']):.3f}) and "
            "2.0 cN/25 mm "
            f"(rho = {float(high_row['spearman_rho_vs_default']):.3f})."
        )

    lines.extend(
        [
            "",
            "The absolute number of detected peaks decreases as the threshold "
            "increases, as expected."
            + stability_sentence,
            "This supports using 1.4 cN/25 mm as an operational threshold rather "
            "than indicating that the slip-stick ranking depends on a single "
            "arbitrary value.",
            "",
            "### S4. Highest Peak-Count Configurations",
            "",
            "The configurations below had the highest mean peak counts at the "
            f"default {default_threshold:.1f} cN/25 mm threshold.",
            "",
            "| Sealant | Liner | Side | n | Mean peaks 1.0 | Mean peaks 1.4 | Mean peaks 2.0 | Mean force [cN/25 mm] | Median noise SD |",
            "|---|---|---|---:|---:|---:|---:|---:|---:|",
        ]
    )

    for row in top_configs:
        lines.append(
            f"| {row['sealant']} "
            f"| {row['liner_label']} "
            f"| {row['side_label']} "
            f"| {int(row['n_replicates'])} "
            f"| {float(row['peak_count_1cN_mean']):.1f} "
            f"| {float(row['peak_count_1p4cN_mean']):.1f} "
            f"| {float(row['peak_count_2cN_mean']):.1f} "
            f"| {float(row['mean_release_cN_25mm_mean']):.1f} "
            f"| {float(row['noise_std_cN_25mm_median']):.3f} |"
        )

    lines.extend(
        [
            "",
            "High peak count should not be read as identical to high mean release "
            "force. It describes instability of the residual force trace after "
            "baseline correction.",
            "",
            "### S5. Machine-Readable Data",
            "",
            "- `publication/generated/data/threshold_noise_summary.csv`",
            "- `publication/generated/data/threshold_robustness.csv`",
            "- `publication/generated/data/top_peak_configs.csv`",
            "- `publication/generated/data/threshold_robustness_summary.json`",
            "- `publication/generated/data/configuration_summary.csv`",
            "- `publication/generated/data/replicate_metrics.csv`",
            "",
        ]
    )

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def require_matplotlib():
    os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ModuleNotFoundError as exc:
        raise SystemExit(
            "matplotlib is required for plot generation. Install the repository "
            "requirements or run with --tables-only."
        ) from exc
    return plt


def save_figure(
    fig,
    output_dir: Path,
    stem: str,
    image_formats: list[str],
    *,
    dpi: int,
    subdir: str = "main",
) -> dict[str, str]:
    paths: dict[str, str] = {}
    for suffix in image_formats:
        out_path = output_dir / "figures" / subdir / suffix / f"{stem}.{suffix}"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        save_kwargs = {"dpi": dpi} if suffix.lower() in {"png", "jpg", "jpeg"} else {}
        fig.savefig(out_path, **save_kwargs)
        paths[f"{suffix}_path"] = str(out_path.relative_to(output_dir))
    return paths


def set_main_plot_style(plt) -> None:
    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["DejaVu Sans", "Arial", "Helvetica"],
            "font.size": 12,
            "axes.labelsize": 13,
            "axes.titlesize": 15,
            "axes.titleweight": "bold",
            "xtick.labelsize": 12,
            "ytick.labelsize": 12,
            "legend.fontsize": 10,
            "axes.linewidth": 0.9,
            "savefig.bbox": "tight",
        }
    )


def configuration_matrix(
    summaries: list[ConfigurationSummary],
    *,
    side: str,
    field: str,
) -> np.ndarray:
    lookup = summary_lookup(summaries)
    matrix = np.full((len(LINER_ORDER), len(SEALANT_ORDER)), np.nan, dtype=float)
    for i, liner in enumerate(LINER_ORDER):
        for j, sealant in enumerate(SEALANT_ORDER):
            summary = lookup.get((liner, sealant, side))
            if summary is not None:
                matrix[i, j] = float(getattr(summary, field))
    return matrix


def annotate_heatmap(ax, data: np.ndarray, *, vmax: float, mark_outliers: bool) -> None:
    for i in range(data.shape[0]):
        for j in range(data.shape[1]):
            value = data[i, j]
            if not math.isfinite(float(value)):
                continue
            normalized = min(max(float(value) / vmax, 0.0), 1.0) if vmax > 0 else 0.0
            text_color = "black" if normalized > 0.62 else "white"
            text = f"{value:.1f}"
            if mark_outliers and value > vmax:
                text = f"{value:.1f}\noutlier"
                text_color = "black"
            ax.text(
                j,
                i,
                text,
                ha="center",
                va="center",
                color=text_color,
                fontweight="bold",
                fontsize=12 if "\n" in text else 14,
            )


def plot_two_panel_heatmap(
    summaries: list[ConfigurationSummary],
    *,
    field: str,
    title: str,
    colorbar_label: str,
    vmax: float,
    mark_outliers: bool,
    plt,
):
    fig, axes = plt.subplots(2, 1, figsize=(8.4, 6.2))
    fig.suptitle(title, fontsize=18, fontweight="bold", y=0.98)
    fig.add_artist(
        plt.Line2D([0.19, 0.81], [0.935, 0.935], transform=fig.transFigure, color="#2878C7", linewidth=1.1)
    )

    image = None
    for ax, side, panel, subtitle in zip(
        axes,
        ["external", "internal"],
        ["(a)", "(b)"],
        ["External side", "Internal side"],
    ):
        data = configuration_matrix(summaries, side=side, field=field)
        image = ax.imshow(data, cmap="viridis", vmin=0.0, vmax=vmax, aspect="auto")
        ax.set_title(subtitle, pad=8)
        ax.set_xticks(np.arange(len(SEALANT_ORDER)))
        ax.set_xticklabels(SEALANT_ORDER, fontweight="bold")
        ax.set_yticks(np.arange(len(LINER_ORDER)))
        ax.set_yticklabels(
            [next(row.liner_label for row in summaries if row.liner == liner) for liner in LINER_ORDER],
            fontweight="bold",
        )
        ax.set_xticks(np.arange(-0.5, len(SEALANT_ORDER), 1), minor=True)
        ax.set_yticks(np.arange(-0.5, len(LINER_ORDER), 1), minor=True)
        ax.grid(which="minor", color="white", linestyle="-", linewidth=1.0)
        ax.tick_params(which="minor", bottom=False, left=False)
        annotate_heatmap(ax, data, vmax=vmax, mark_outliers=mark_outliers)
        ax.text(
            0.5,
            -0.23,
            panel,
            transform=ax.transAxes,
            ha="center",
            va="center",
            fontsize=14,
            fontweight="bold",
        )

    fig.subplots_adjust(left=0.13, right=0.86, top=0.88, bottom=0.08, hspace=0.62)
    if image is not None:
        cbar_ax = fig.add_axes([0.895, 0.14, 0.035, 0.70])
        cbar = fig.colorbar(image, cax=cbar_ax)
        cbar.set_label(colorbar_label, fontweight="bold")
    return fig


def generate_release_force_heatmap(
    summaries: list[ConfigurationSummary],
    *,
    output_dir: Path,
    image_formats: list[str],
    dpi: int,
    plt,
) -> dict[str, object]:
    fig = plot_two_panel_heatmap(
        summaries,
        field="mean_release_cN_25mm_mean",
        title="Mean release force values",
        colorbar_label="Mean release force [cN / 25 mm]",
        vmax=25.0,
        mark_outliers=True,
        plt=plt,
    )
    paths = save_figure(
        fig,
        output_dir,
        "figure2_release_force_heatmap",
        image_formats,
        dpi=dpi,
    )
    plt.close(fig)
    return {
        "figure": "Figure 2",
        "description": "Mean release-force heatmap generated from configuration_summary.csv",
        **paths,
    }


def generate_peak_count_heatmap(
    summaries: list[ConfigurationSummary],
    *,
    output_dir: Path,
    image_formats: list[str],
    dpi: int,
    plt,
) -> dict[str, object]:
    max_value = max(
        row.peak_count_1p4cN_mean
        for row in summaries
        if math.isfinite(row.peak_count_1p4cN_mean)
    )
    vmax = max(10.0, math.ceil(max_value / 10.0) * 10.0)
    fig = plot_two_panel_heatmap(
        summaries,
        field="peak_count_1p4cN_mean",
        title="Average number of slip-stick spikes",
        colorbar_label="Average number of spikes",
        vmax=vmax,
        mark_outliers=False,
        plt=plt,
    )
    paths = save_figure(
        fig,
        output_dir,
        "figure8_peak_count_heatmap",
        image_formats,
        dpi=dpi,
    )
    plt.close(fig)
    return {
        "figure": "Figure 8",
        "description": "Mean slip-stick peak-count heatmap generated from configuration_summary.csv",
        **paths,
    }


def analyse_residual_panel(
    panel: ResidualPanel,
    *,
    datasets_dir: Path,
    collection_width_mm: float,
    report_width_mm: float,
    disp_min: float,
    disp_max: float,
    threshold_cN: float,
    polyorder: int,
    window_seconds: float | None,
    noise_disp_min: float,
    noise_disp_max: float,
    noise_min_samples: int,
    instrument_cutoff_factor: float,
    apply_filter: bool,
):
    reps = load_replicates(datasets_dir / panel.dataset_file)
    if not reps:
        raise ValueError(f"no replicates found in {panel.dataset_file}")
    force_scale = report_width_mm / collection_width_mm
    scaled_reps = [scaled_replicate(rep, force_scale) for rep in reps]
    noise_force_onset_n = DEFAULT_NOISE_FORCE_ONSET_N * force_scale
    peak_values = []
    for rep in scaled_reps:
        estimate = estimate_instrumental_noise(
            rep,
            disp_min=noise_disp_min,
            disp_max=noise_disp_max,
            force_abs_max=None,
            min_samples=noise_min_samples,
            force_onset=noise_force_onset_n,
        )
        if estimate is not None and estimate.noise_peak_hz is not None:
            peak_values.append(float(estimate.noise_peak_hz))
    cutoff = (
        safe_median(peak_values) * instrument_cutoff_factor
        if apply_filter and peak_values
        else None
    )
    processed = process_replicates(scaled_reps, force_scale=1.0, cutoff_hz=cutoff)
    replicate = next((rep for rep in processed if rep.rep_id == panel.replicate), None)
    if replicate is None:
        raise ValueError(f"replicate {panel.replicate} not found in {panel.dataset_file}")
    result = _analyse_replicate(
        replicate,
        displacement_window=(disp_min, disp_max),
        window_seconds=window_seconds,
        polyorder=polyorder,
        threshold=threshold_cN / 100.0,
    )
    if result is None:
        raise ValueError(
            f"replicate {panel.replicate} in {panel.dataset_file} has no valid residual profile"
        )
    return result


def generate_residual_profile_figure(
    panels: list[ResidualPanel],
    *,
    datasets_dir: Path,
    output_dir: Path,
    collection_width_mm: float,
    report_width_mm: float,
    disp_min: float,
    disp_max: float,
    threshold_cN: float,
    polyorder: int,
    window_seconds: float | None,
    noise_disp_min: float,
    noise_disp_max: float,
    noise_min_samples: int,
    instrument_cutoff_factor: float,
    apply_filter: bool,
    image_formats: list[str],
    dpi: int,
    plt,
) -> dict[str, object]:
    results = [
        analyse_residual_panel(
            panel,
            datasets_dir=datasets_dir,
            collection_width_mm=collection_width_mm,
            report_width_mm=report_width_mm,
            disp_min=disp_min,
            disp_max=disp_max,
            threshold_cN=threshold_cN,
            polyorder=polyorder,
            window_seconds=window_seconds,
            noise_disp_min=noise_disp_min,
            noise_disp_max=noise_disp_max,
            noise_min_samples=noise_min_samples,
            instrument_cutoff_factor=instrument_cutoff_factor,
            apply_filter=apply_filter,
        )
        for panel in panels
    ]
    max_abs = max(float(np.max(np.abs(result.residual)) * 100.0) for result in results)
    y_max = max(15.0, math.ceil((max_abs + 1.0) / 5.0) * 5.0)
    y_min = -5.0

    fig, axes = plt.subplots(3, 1, figsize=(7.8, 9.8), sharex=True)
    for ax, panel, result in zip(axes, panels, results):
        residual_cN = result.residual * 100.0
        ax.plot(result.disp, residual_cN, color="#1f77b4", linewidth=1.2, label="residual")
        ax.axhline(threshold_cN, color="#1f77b4", linestyle="--", linewidth=1.0, label="threshold")
        if result.spikes:
            spike_idx = [spike.index for spike in result.spikes]
            ax.scatter(
                result.disp[spike_idx],
                residual_cN[spike_idx],
                marker="x",
                s=36,
                color="#1f77b4",
                linewidths=1.5,
                label="spikes",
                zorder=3,
            )
        ax.set_xlim(disp_min, disp_max)
        ax.set_ylim(y_min, y_max)
        ax.set_ylabel(f"Residual ({FORCE_UNIT})")
        ax.grid(True, color="#cccccc", alpha=0.45)
        ax.legend(loc="upper left", frameon=True)
        ax.text(
            0.5,
            -0.32,
            f"({panel.panel})",
            transform=ax.transAxes,
            ha="center",
            va="center",
            fontsize=13,
            fontweight="bold",
        )
    axes[-1].set_xlabel("Displacement (mm)")
    fig.tight_layout(h_pad=2.2)
    paths = save_figure(
        fig,
        output_dir,
        "figure5_residual_profiles",
        image_formats,
        dpi=dpi,
    )
    plt.close(fig)
    return {
        "figure": "Figure 5",
        "description": "Representative residual force profiles generated from main_residual_profiles.csv",
        "panels": "; ".join(
            f"{panel.panel}:{panel.dataset_file}:{panel.replicate}:{panel.label}"
            for panel in panels
        ),
        **paths,
    }


def write_main_figure_manifest(output_dir: Path, rows: list[dict[str, object]]) -> None:
    path = output_dir / "figures" / "main_figure_manifest.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = sorted({key for row in rows for key in row})
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, **CSV_WRITE_KWARGS)
        writer.writeheader()
        writer.writerows(rows)

    caption_lines = [
        "# Main Manuscript Data Figures",
        "",
        "These files regenerate the data-derived plots used in the main manuscript.",
        "Photographs and static schematic artwork are not generated by this script.",
        "",
        "## Figure 2",
        "",
        f"Heatmap of mean release force values [{FORCE_UNIT}] for all liner-sealant combinations. "
        "The color scale is capped at 25 cN/25 mm for readability.",
        "",
        "## Figure 5",
        "",
        "Representative residual force profiles selected in publication/main_residual_profiles.csv. "
        "The residual signal is the force minus the Savitzky-Golay baseline after the same "
        "normalization and filtering rules used for peak counting. Markers indicate positive "
        "residual excursions above the threshold; negative excursions are shown but not counted "
        "as slip-stick peak events.",
        "",
        "## Figure 8",
        "",
        "Heatmap of the mean number of detected slip-stick peak events per replicate at the "
        "configured residual threshold. Each contiguous positive residual excursion "
        "above threshold is counted as one event.",
        "",
    ]
    (output_dir / "figures" / "main_figure_captions.md").write_text(
        "\n".join(caption_lines),
        encoding="utf-8",
    )


def generate_main_figures(
    summaries: list[ConfigurationSummary],
    residual_panels: list[ResidualPanel],
    *,
    datasets_dir: Path,
    output_dir: Path,
    collection_width_mm: float,
    report_width_mm: float,
    disp_min: float,
    disp_max: float,
    threshold_cN: float,
    polyorder: int,
    window_seconds: float | None,
    noise_disp_min: float,
    noise_disp_max: float,
    noise_min_samples: int,
    instrument_cutoff_factor: float,
    apply_filter: bool,
    image_formats: list[str],
    dpi: int,
    plt,
) -> None:
    set_main_plot_style(plt)
    rows = [
        generate_release_force_heatmap(
            summaries,
            output_dir=output_dir,
            image_formats=image_formats,
            dpi=dpi,
            plt=plt,
        ),
        generate_residual_profile_figure(
            residual_panels,
            datasets_dir=datasets_dir,
            output_dir=output_dir,
            collection_width_mm=collection_width_mm,
            report_width_mm=report_width_mm,
            disp_min=disp_min,
            disp_max=disp_max,
            threshold_cN=threshold_cN,
            polyorder=polyorder,
            window_seconds=window_seconds,
            noise_disp_min=noise_disp_min,
            noise_disp_max=noise_disp_max,
            noise_min_samples=noise_min_samples,
            instrument_cutoff_factor=instrument_cutoff_factor,
            apply_filter=apply_filter,
            image_formats=image_formats,
            dpi=dpi,
            plt=plt,
        ),
        generate_peak_count_heatmap(
            summaries,
            output_dir=output_dir,
            image_formats=image_formats,
            dpi=dpi,
            plt=plt,
        ),
    ]
    write_main_figure_manifest(output_dir, rows)


def scaled_trace(rep: Replicate, force_scale: float) -> tuple[np.ndarray, np.ndarray]:
    disp = np.asarray(rep.disp_mm, dtype=float)
    force = np.asarray(rep.force_n, dtype=float) * force_scale * 100.0
    order = np.argsort(disp)
    return disp[order], force[order]


def mean_trace(
    traces: list[tuple[np.ndarray, np.ndarray]],
    *,
    disp_min: float,
    disp_max: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    grid = np.linspace(disp_min, disp_max, 1001)
    interpolated = []
    for disp, force in traces:
        mask = (disp >= disp_min) & (disp <= disp_max)
        if np.count_nonzero(mask) < 2:
            continue
        d = disp[mask]
        f = force[mask]
        values = np.full_like(grid, np.nan, dtype=float)
        in_range = (grid >= d.min()) & (grid <= d.max())
        values[in_range] = np.interp(grid[in_range], d, f)
        interpolated.append(values)
    if not interpolated:
        return grid, np.full_like(grid, np.nan), np.zeros_like(grid)
    stack = np.vstack(interpolated)
    count = np.sum(~np.isnan(stack), axis=0)
    mean_values = np.full_like(grid, np.nan, dtype=float)
    populated = count > 0
    mean_values[populated] = np.nanmean(stack[:, populated], axis=0)
    min_count = max(2, int(np.ceil(0.4 * len(traces))))
    mean_values[count < min_count] = np.nan
    return grid, mean_values, count


def release_curve_force_values(
    traces: list[tuple[np.ndarray, np.ndarray]],
    *,
    disp_min: float,
    disp_max: float,
) -> np.ndarray:
    values = []
    for disp, force in traces:
        mask = (
            (disp >= disp_min)
            & (disp <= disp_max)
            & np.isfinite(force)
        )
        if np.any(mask):
            values.append(force[mask])
    if not values:
        return np.asarray([], dtype=float)
    finite = np.concatenate(values)
    return finite[np.isfinite(finite)]


def release_curve_axis_metadata(
    traces: list[tuple[np.ndarray, np.ndarray]],
    *,
    disp_min: float,
    disp_max: float,
) -> tuple[float, float, str, float, float]:
    finite = release_curve_force_values(traces, disp_min=disp_min, disp_max=disp_max)
    if finite.size == 0:
        return (
            NORMAL_RELEASE_Y_MIN_CN,
            NORMAL_RELEASE_Y_MAX_CN,
            "shared_normal_0_30",
            math.nan,
            math.nan,
        )

    y_min_observed = float(np.nanmin(finite))
    y_max_observed = float(np.nanmax(finite))
    y_min = min(NORMAL_RELEASE_Y_MIN_CN, math.floor(y_min_observed))
    y_max = math.ceil((y_max_observed * 1.05) / 10.0) * 10.0
    y_max = max(y_max, NORMAL_RELEASE_Y_MAX_CN)
    if y_max_observed <= NORMAL_RELEASE_Y_MAX_CN:
        return (
            NORMAL_RELEASE_Y_MIN_CN,
            NORMAL_RELEASE_Y_MAX_CN,
            "shared_normal_0_30",
            y_min_observed,
            y_max_observed,
        )

    return (
        y_min,
        y_max,
        "shared_0_30_with_full_range_panels",
        y_min_observed,
        y_max_observed,
    )


def side_full_range_axis_limits(
    observed_min: float,
    observed_max: float,
) -> tuple[float, float]:
    if not math.isfinite(observed_min) or not math.isfinite(observed_max):
        return NORMAL_RELEASE_Y_MIN_CN, NORMAL_RELEASE_Y_MAX_CN
    if observed_max <= NORMAL_RELEASE_Y_MAX_CN:
        return NORMAL_RELEASE_Y_MIN_CN, NORMAL_RELEASE_Y_MAX_CN
    y_min = min(NORMAL_RELEASE_Y_MIN_CN, math.floor(observed_min))
    y_max = math.ceil((observed_max * 1.05) / 10.0) * 10.0
    return y_min, max(y_max, NORMAL_RELEASE_Y_MAX_CN)


def release_curve_fraction_above_normal(
    traces: list[tuple[np.ndarray, np.ndarray]],
    *,
    disp_min: float,
    disp_max: float,
) -> float:
    finite = release_curve_force_values(traces, disp_min=disp_min, disp_max=disp_max)
    if finite.size == 0:
        return 0.0
    return float(np.mean(finite > NORMAL_RELEASE_Y_MAX_CN))


def release_curve_display_mode(observed_max: float, fraction_above_normal: float) -> str:
    if not math.isfinite(observed_max) or observed_max <= NORMAL_RELEASE_Y_MAX_CN:
        return "comparison_only"
    if fraction_above_normal >= SEVERE_RELEASE_ABOVE_NORMAL_FRACTION:
        return "full_range_only"
    return "comparison_and_full_range"


def display_mode_description(mode: str) -> str:
    if mode == "full_range_only":
        return "one full-range panel"
    if mode == "comparison_and_full_range":
        return "paired 0-30 comparison and full-range panels"
    return "one 0-30 comparison panel"


def plot_release_panel(
    ax,
    traces: list[tuple[np.ndarray, np.ndarray]],
    *,
    disp_min: float,
    disp_max: float,
    y_min: float,
    y_max: float,
    title: str,
    plt,
    hide_above: float | None = None,
    show_legend: bool = False,
) -> None:
    for disp, force in traces:
        mask = (disp >= disp_min) & (disp <= disp_max)
        if np.count_nonzero(mask) >= 2:
            plot_force = np.asarray(force[mask], dtype=float)
            if hide_above is not None:
                plot_force = np.where(plot_force <= hide_above, plot_force, np.nan)
            ax.plot(
                disp[mask],
                plot_force,
                color="#4C78A8",
                linewidth=0.8,
                alpha=0.32,
            )

    grid, mean_values, _ = mean_trace(traces, disp_min=disp_min, disp_max=disp_max)
    if np.any(np.isfinite(mean_values)):
        plot_mean = np.asarray(mean_values, dtype=float)
        if hide_above is not None:
            plot_mean = np.where(plot_mean <= hide_above, plot_mean, np.nan)
        ax.plot(
            grid,
            plot_mean,
            color="#0B3C5D",
            linewidth=2.2,
            label="mean",
            zorder=3,
        )

    ax.set_xlim(disp_min, disp_max)
    ax.set_ylim(y_min, y_max)
    ax.set_ylabel(f"Release force ({FORCE_UNIT})")
    ax.set_title(title)
    if show_legend:
        replicate_proxy = plt.Line2D(
            [0],
            [0],
            color="#4C78A8",
            linewidth=1.0,
            alpha=0.55,
            label="replicates",
        )
        mean_proxy = plt.Line2D(
            [0],
            [0],
            color="#0B3C5D",
            linewidth=2.2,
            label="mean",
        )
        ax.legend(handles=[replicate_proxy, mean_proxy], loc="upper right", frameon=True)


def plot_figure(
    figure_rows: list[ManifestRow],
    *,
    datasets_dir: Path,
    output_dir: Path,
    collection_width_mm: float,
    report_width_mm: float,
    disp_min: float,
    disp_max: float,
    image_formats: list[str],
    dpi: int,
    plt,
) -> dict[str, object]:
    by_side = {row.side: row for row in figure_rows}
    entry = figure_rows[0]
    force_scale = report_width_mm / collection_width_mm

    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["DejaVu Sans", "Arial", "Helvetica"],
            "font.size": 10,
            "axes.labelsize": 11,
            "axes.titlesize": 12,
            "axes.titleweight": "bold",
            "xtick.labelsize": 10,
            "ytick.labelsize": 10,
            "legend.fontsize": 9,
            "axes.grid": True,
            "grid.color": "#d9d9d9",
            "grid.linewidth": 0.6,
            "grid.alpha": 0.65,
            "axes.linewidth": 0.9,
            "savefig.bbox": "tight",
        }
    )

    side_counts: dict[str, dict[str, int]] = {}
    side_data: dict[str, dict[str, object]] = {}
    paths: dict[str, str] = {}

    for side in PLOT_SIDE_ORDER:
        row = by_side[side]
        reps = load_replicates(datasets_dir / row.dataset_file)
        traces = [scaled_trace(rep, force_scale) for rep in reps]
        side_data[side] = {"row": row, "traces": traces}
        side_counts[side] = {
            "total": len(traces),
            "shown": sum(
                np.count_nonzero((disp >= disp_min) & (disp <= disp_max)) >= 2
                for disp, _ in traces
            ),
            "ended_before_window": sum(float(disp.max()) < disp_min for disp, _ in traces),
            "truncated_in_window": sum(
                disp_min <= float(disp.max()) < disp_max for disp, _ in traces
            ),
        }

    side_observed_max: dict[str, float] = {}
    side_observed_min: dict[str, float] = {}
    side_fraction_above_normal: dict[str, float] = {}
    side_display_modes: dict[str, str] = {}
    for side in PLOT_SIDE_ORDER:
        finite = release_curve_force_values(
            side_data[side]["traces"],
            disp_min=disp_min,
            disp_max=disp_max,
        )
        side_observed_max[side] = float(np.nanmax(finite)) if finite.size else math.nan
        side_observed_min[side] = float(np.nanmin(finite)) if finite.size else math.nan
        side_fraction_above_normal[side] = release_curve_fraction_above_normal(
            side_data[side]["traces"],
            disp_min=disp_min,
            disp_max=disp_max,
        )
        side_display_modes[side] = release_curve_display_mode(
            side_observed_max[side],
            side_fraction_above_normal[side],
        )

    all_traces = [
        trace
        for side in PLOT_SIDE_ORDER
        for trace in side_data[side]["traces"]
    ]
    full_y_min, full_y_max, y_axis_mode, observed_min, observed_max = release_curve_axis_metadata(
        all_traces,
        disp_min=disp_min,
        disp_max=disp_max,
    )
    main_y_min = NORMAL_RELEASE_Y_MIN_CN
    main_y_max = NORMAL_RELEASE_Y_MAX_CN

    if y_axis_mode == "shared_normal_0_30":
        fig, axes = plt.subplots(2, 1, figsize=(7.5, 6.8), sharex=True)
        for ax, side, panel in zip(axes, PLOT_SIDE_ORDER, ["(a)", "(b)"]):
            row = side_data[side]["row"]
            plot_release_panel(
                ax,
                side_data[side]["traces"],
                disp_min=disp_min,
                disp_max=disp_max,
                y_min=main_y_min,
                y_max=main_y_max,
                title=f"{panel} {row.side_label} side",
                plt=plt,
                show_legend=True,
            )
        axes[-1].set_xlabel("Displacement (mm)")
    else:
        fig = plt.figure(figsize=(7.5, 6.8))
        grid = fig.add_gridspec(2, 2, hspace=0.50, wspace=0.34)
        shared_x = None
        top_row_axes = []
        bottom_row_axes = []
        panel_index = 0
        for row_index, side in enumerate(PLOT_SIDE_ORDER):
            row = side_data[side]["row"]
            traces = side_data[side]["traces"]
            mode = side_display_modes[side]
            side_full_y_min, side_full_y_max = side_full_range_axis_limits(
                side_observed_min[side],
                side_observed_max[side],
            )

            if mode == "comparison_and_full_range":
                ax_comparison = fig.add_subplot(
                    grid[row_index, 0],
                    sharex=shared_x,
                )
                if shared_x is None:
                    shared_x = ax_comparison
                panel_index += 1
                plot_release_panel(
                    ax_comparison,
                    traces,
                    disp_min=disp_min,
                    disp_max=disp_max,
                    y_min=main_y_min,
                    y_max=main_y_max,
                    title=(
                        f"({chr(ord('a') + panel_index - 1)}) "
                        f"{row.side_label} side, 0-30 comparison"
                    ),
                    plt=plt,
                    hide_above=NORMAL_RELEASE_Y_MAX_CN,
                    show_legend=panel_index == 1,
                )

                ax_full = fig.add_subplot(
                    grid[row_index, 1],
                    sharex=shared_x,
                )
                panel_index += 1
                plot_release_panel(
                    ax_full,
                    traces,
                    disp_min=disp_min,
                    disp_max=disp_max,
                    y_min=side_full_y_min,
                    y_max=side_full_y_max,
                    title=(
                        f"({chr(ord('a') + panel_index - 1)}) "
                        f"{row.side_label} side, full range"
                    ),
                    plt=plt,
                    show_legend=False,
                )
                axes_for_row = [ax_comparison, ax_full]
                max_label_axis = ax_full
            elif mode == "full_range_only":
                ax_full = fig.add_subplot(
                    grid[row_index, :],
                    sharex=shared_x,
                )
                if shared_x is None:
                    shared_x = ax_full
                panel_index += 1
                plot_release_panel(
                    ax_full,
                    traces,
                    disp_min=disp_min,
                    disp_max=disp_max,
                    y_min=side_full_y_min,
                    y_max=side_full_y_max,
                    title=(
                        f"({chr(ord('a') + panel_index - 1)}) "
                        f"{row.side_label} side, full range"
                    ),
                    plt=plt,
                    show_legend=panel_index == 1,
                )
                axes_for_row = [ax_full]
                max_label_axis = ax_full
            else:
                ax_comparison = fig.add_subplot(
                    grid[row_index, :],
                    sharex=shared_x,
                )
                if shared_x is None:
                    shared_x = ax_comparison
                panel_index += 1
                plot_release_panel(
                    ax_comparison,
                    traces,
                    disp_min=disp_min,
                    disp_max=disp_max,
                    y_min=main_y_min,
                    y_max=main_y_max,
                    title=(
                        f"({chr(ord('a') + panel_index - 1)}) "
                        f"{row.side_label} side, 0-30 comparison"
                    ),
                    plt=plt,
                    show_legend=panel_index == 1,
                )
                axes_for_row = [ax_comparison]
                max_label_axis = None

            if row_index == 0:
                top_row_axes.extend(axes_for_row)
            else:
                bottom_row_axes.extend(axes_for_row)

            if max_label_axis is not None and side_observed_max[side] > NORMAL_RELEASE_Y_MAX_CN:
                max_label_axis.text(
                    0.02,
                    0.96,
                    f"max {side_observed_max[side]:.1f} cN",
                    transform=max_label_axis.transAxes,
                    ha="left",
                    va="top",
                    fontsize=8.5,
                    color="#4F5B62",
                    bbox={
                        "facecolor": "white",
                        "edgecolor": "#B0BEC5",
                        "alpha": 0.75,
                        "pad": 2.5,
                    },
                )
        for ax in top_row_axes:
            ax.tick_params(labelbottom=False)
        for ax in bottom_row_axes:
            ax.set_xlabel("Displacement (mm)")
    fig.suptitle(
        f"Figure S{entry.figure}. {entry.liner_label} / {entry.sealant}",
        fontsize=15,
        fontweight="bold",
        y=0.99,
    )
    if y_axis_mode == "shared_normal_0_30":
        fig.tight_layout(rect=[0, 0, 1, 0.97])
    else:
        fig.subplots_adjust(
            left=0.11,
            right=0.98,
            bottom=0.08,
            top=0.88,
            hspace=0.55,
            wspace=0.34,
        )

    stem = f"S{entry.figure:02d}_{entry.liner}_{entry.sealant}_release_curves"
    for suffix in image_formats:
        out_path = output_dir / "figures" / "release_curves" / suffix / f"{stem}.{suffix}"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        save_kwargs = {"dpi": dpi} if suffix.lower() in {"png", "jpg", "jpeg"} else {}
        fig.savefig(out_path, **save_kwargs)
        paths[suffix] = str(out_path.relative_to(output_dir))
    plt.close(fig)

    return {
        "figure": entry.figure,
        "liner": entry.liner_label,
        "sealant": entry.sealant,
        "external_file": by_side["external"].dataset_file,
        "internal_file": by_side["internal"].dataset_file,
        "external_total_n": side_counts["external"]["total"],
        "internal_total_n": side_counts["internal"]["total"],
        "external_shown_n": side_counts["external"]["shown"],
        "internal_shown_n": side_counts["internal"]["shown"],
        "external_ended_before_50mm": side_counts["external"]["ended_before_window"],
        "internal_ended_before_50mm": side_counts["internal"]["ended_before_window"],
        "external_truncated_before_200mm": side_counts["external"]["truncated_in_window"],
        "internal_truncated_before_200mm": side_counts["internal"]["truncated_in_window"],
        "y_axis_mode": y_axis_mode,
        "y_axis_min_cN_25mm": finite_or_blank(main_y_min, 3),
        "y_axis_max_cN_25mm": finite_or_blank(main_y_max, 3),
        "full_range_y_axis_min_cN_25mm": finite_or_blank(full_y_min, 3),
        "full_range_y_axis_max_cN_25mm": finite_or_blank(full_y_max, 3),
        "observed_min_cN_25mm": finite_or_blank(observed_min, 3),
        "observed_max_cN_25mm": finite_or_blank(observed_max, 3),
        "external_observed_min_cN_25mm": finite_or_blank(side_observed_min["external"], 3),
        "external_observed_max_cN_25mm": finite_or_blank(side_observed_max["external"], 3),
        "internal_observed_min_cN_25mm": finite_or_blank(side_observed_min["internal"], 3),
        "internal_observed_max_cN_25mm": finite_or_blank(side_observed_max["internal"], 3),
        "external_fraction_above_30cN": finite_or_blank(
            side_fraction_above_normal["external"],
            6,
        ),
        "internal_fraction_above_30cN": finite_or_blank(
            side_fraction_above_normal["internal"],
            6,
        ),
        "external_display_mode": side_display_modes["external"],
        "internal_display_mode": side_display_modes["internal"],
        "outlier_sides": "; ".join(
            side
            for side in PLOT_SIDE_ORDER
            if side_observed_max[side] > NORMAL_RELEASE_Y_MAX_CN
        ),
        **{f"{suffix}_path": path for suffix, path in paths.items()},
    }


def trace_count_note(count: object, side: str, event: str) -> str:
    count_int = int(count)
    noun = "trace" if count_int == 1 else "traces"
    return f"{count_int} {side} {noun} {event}"


def caption(row: dict[str, object]) -> str:
    notes = []
    if int(row["external_ended_before_50mm"]):
        notes.append(
            trace_count_note(
                row["external_ended_before_50mm"],
                "external",
                "ended before 50 mm",
            )
        )
    if int(row["internal_ended_before_50mm"]):
        notes.append(
            trace_count_note(
                row["internal_ended_before_50mm"],
                "internal",
                "ended before 50 mm",
            )
        )
    if int(row["external_truncated_before_200mm"]):
        notes.append(
            trace_count_note(
                row["external_truncated_before_200mm"],
                "external",
                "ended within 50-200 mm",
            )
        )
    if int(row["internal_truncated_before_200mm"]):
        notes.append(
            trace_count_note(
                row["internal_truncated_before_200mm"],
                "internal",
                "ended within 50-200 mm",
            )
        )
    note_text = f" {'; '.join(notes)}." if notes else ""
    if row["y_axis_mode"] == "shared_0_30_with_full_range_panels":
        axis_text = (
            f"Panels marked as 0-{NORMAL_RELEASE_Y_MAX_CN:.0f} comparison use a "
            f"shared 0-{NORMAL_RELEASE_Y_MAX_CN:.0f} cN/25 mm y-axis, with values "
            "above this range omitted from that comparison view. Full-range "
            "panels retain all above-range values. Sides with more than "
            f"{SEVERE_RELEASE_ABOVE_NORMAL_FRACTION:.0%} of samples above "
            f"{NORMAL_RELEASE_Y_MAX_CN:.0f} cN/25 mm are shown only at full range "
            f"(figure maximum {float(row['observed_max_cN_25mm']):.1f} cN/25 mm)."
        )
    else:
        axis_text = (
            f"Both panels use the shared 0-{NORMAL_RELEASE_Y_MAX_CN:.0f} cN/25 mm "
            "comparison y-axis."
        )
    if row["y_axis_mode"] == "shared_0_30_with_full_range_panels":
        panel_text = (
            f"The external liner side "
            f"(n = {row['external_shown_n']} shown from {row['external_total_n']} "
            f"traces) is shown as {display_mode_description(str(row['external_display_mode']))}; "
            f"the internal liner side "
            f"(n = {row['internal_shown_n']} shown from {row['internal_total_n']} "
            f"traces) is shown as {display_mode_description(str(row['internal_display_mode']))}."
        )
    else:
        panel_text = (
            f"Panel (a) shows the external liner side "
            f"(n = {row['external_shown_n']} shown from {row['external_total_n']} "
            f"traces); panel (b) shows the internal liner side "
            f"(n = {row['internal_shown_n']} shown from {row['internal_total_n']} "
            "traces)."
        )
    return (
        f"Figure S{row['figure']}. Force-displacement release curves for "
        f"{row['liner']} liner tested with {row['sealant']} butyl sealant. "
        f"{panel_text} Thin blue lines show individual "
        f"replicates and the dark blue line shows the mean curve where replicate "
        f"coverage was sufficient. Forces are normalized to {FORCE_UNIT}; the "
        f"displayed range corresponds to the 50-200 mm analysis interval. "
        f"{axis_text}{note_text}"
    )


def write_figure_manifest(output_dir: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        return
    manifest_path = output_dir / "figures" / "figure_manifest.csv"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys())
    with manifest_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, **CSV_WRITE_KWARGS)
        writer.writeheader()
        writer.writerows(rows)

    lines = [
        "# Supplementary Release-Curve Figures",
        "",
        "The figures are regenerated from publication/dataset_manifest.csv.",
        "",
    ]
    for row in rows:
        lines.extend(
            [
                f"## Figure S{row['figure']}. {row['liner']} / {row['sealant']}",
                "",
                caption(row),
                "",
            ]
        )
    (output_dir / "figures" / "release_curve_captions.md").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )


def generate_release_curve_figures(
    manifest_rows: list[ManifestRow],
    *,
    datasets_dir: Path,
    output_dir: Path,
    collection_width_mm: float,
    report_width_mm: float,
    disp_min: float,
    disp_max: float,
    image_formats: list[str],
    dpi: int,
) -> None:
    plt = require_matplotlib()
    by_figure: dict[int, list[ManifestRow]] = {}
    for row in manifest_rows:
        by_figure.setdefault(row.figure, []).append(row)

    manifest = [
        plot_figure(
            sorted(rows, key=lambda row: PLOT_SIDE_ORDER.index(row.side)),
            datasets_dir=datasets_dir,
            output_dir=output_dir,
            collection_width_mm=collection_width_mm,
            report_width_mm=report_width_mm,
            disp_min=disp_min,
            disp_max=disp_max,
            image_formats=image_formats,
            dpi=dpi,
            plt=plt,
        )
        for _, rows in sorted(by_figure.items())
    ]
    write_figure_manifest(output_dir, manifest)


def write_run_readme(
    output_dir: Path,
    *,
    manifest_path: Path,
    metrics_count: int,
    summary_count: int,
    plots_generated: bool,
) -> None:
    try:
        manifest_display = manifest_path.resolve().relative_to(REPO_ROOT)
    except ValueError:
        manifest_display = manifest_path

    lines = [
        "# Generated Publication Outputs",
        "",
        f"Manifest: `{manifest_display}`",
        f"Replicate-level rows: {metrics_count}",
        f"Configuration rows: {summary_count}",
        f"Publication plots generated: {'yes' if plots_generated else 'no'}",
        "",
        "## Rules",
        "",
        "- Dataset inclusion follows the manifest exactly.",
        "- Release force is the per-replicate mean over 50-200 mm.",
        "- Forces are normalized from 90 mm collection width to 25 mm report width and reported as cN/25 mm.",
        "- Configuration SD is the sample SD across replicate mean-release values.",
        "- Slip-stick peak counts use one contiguous positive residual excursion above threshold as one event.",
        "- Threshold-robustness outputs repeat the peak-count analysis across nearby thresholds from the same manifest.",
        "- No replicate-level outlier exclusions are applied by this generator.",
    ]
    lines.append("")
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "README.md").write_text("\n".join(lines), encoding="utf-8")


def parse_image_formats(raw: str) -> list[str]:
    formats = [item.strip().lower().lstrip(".") for item in raw.split(",") if item.strip()]
    if not formats:
        raise ValueError("at least one image format is required")
    allowed = {"png", "pdf", "svg"}
    unsupported = set(formats).difference(allowed)
    if unsupported:
        raise ValueError(f"unsupported image formats: {sorted(unsupported)}")
    return formats


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--residual-panels", type=Path, default=DEFAULT_RESIDUAL_PANELS)
    parser.add_argument("--datasets-dir", type=Path, default=DEFAULT_DATASETS_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--collection-width-mm", type=float, default=90.0)
    parser.add_argument("--report-width-mm", type=float, default=25.0)
    parser.add_argument("--disp-min", type=float, default=50.0)
    parser.add_argument("--disp-max", type=float, default=200.0)
    parser.add_argument("--threshold-cN", type=float, default=1.4)
    parser.add_argument("--polyorder", type=int, default=3)
    parser.add_argument("--window-seconds", type=float, default=None)
    parser.add_argument("--noise-disp-min", type=float, default=1.0)
    parser.add_argument("--noise-disp-max", type=float, default=5.0)
    parser.add_argument("--noise-min-samples", type=int, default=40)
    parser.add_argument("--instrument-cutoff-factor", type=float, default=0.8)
    parser.add_argument("--no-filter", action="store_true")
    parser.add_argument("--image-formats", default="png,pdf")
    parser.add_argument("--dpi", type=int, default=300)
    parser.add_argument("--tables-only", action="store_true")
    parser.add_argument("--plots-only", action="store_true")
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    if args.tables_only and args.plots_only:
        parser.error("--tables-only and --plots-only cannot be used together")
    if args.disp_max <= args.disp_min:
        parser.error("--disp-max must be greater than --disp-min")
    if args.collection_width_mm <= 0 or args.report_width_mm <= 0:
        parser.error("widths must be positive")

    manifest_rows = read_manifest(args.manifest, args.datasets_dir)
    residual_panels = read_residual_panels(args.residual_panels, args.datasets_dir)
    thresholds_for_publication = threshold_values(args.threshold_cN)

    all_metrics: list[TraceMetric] = []
    summaries: list[ConfigurationSummary] = []
    for row in manifest_rows:
        metrics = analyse_dataset(
            row,
            datasets_dir=args.datasets_dir,
            collection_width_mm=args.collection_width_mm,
            report_width_mm=args.report_width_mm,
            disp_min=args.disp_min,
            disp_max=args.disp_max,
            threshold_cN=args.threshold_cN,
            polyorder=args.polyorder,
            window_seconds=args.window_seconds,
            noise_disp_min=args.noise_disp_min,
            noise_disp_max=args.noise_disp_max,
            noise_min_samples=args.noise_min_samples,
            instrument_cutoff_factor=args.instrument_cutoff_factor,
            apply_filter=not args.no_filter,
            thresholds_cN=thresholds_for_publication,
        )
        all_metrics.extend(metrics)
        summaries.append(summarize_configuration(row, metrics))

    if not args.plots_only:
        threshold_summary_sets = compute_threshold_summary_sets(
            manifest_rows,
            metrics=all_metrics,
            default_summaries=summaries,
            default_threshold_cN=args.threshold_cN,
        )
        write_replicate_metrics(args.output_dir / "data" / "replicate_metrics.csv", all_metrics)
        write_configuration_summary(
            args.output_dir / "data" / "configuration_summary.csv", summaries
        )
        threshold_rows = write_threshold_robustness(
            args.output_dir / "data" / "threshold_robustness.csv",
            summary_sets=threshold_summary_sets,
            default_threshold_cN=args.threshold_cN,
        )
        noise_summary = write_threshold_noise_summary(
            args.output_dir / "data" / "threshold_noise_summary.csv",
            metrics=all_metrics,
            summaries=summaries,
            default_threshold_cN=args.threshold_cN,
        )
        top_configs = write_top_peak_configs(
            args.output_dir / "data" / "top_peak_configs.csv",
            summary_sets=threshold_summary_sets,
            default_threshold_cN=args.threshold_cN,
        )
        write_threshold_summary_json(
            args.output_dir / "data" / "threshold_robustness_summary.json",
            threshold_rows=threshold_rows,
            noise_summary=noise_summary,
            top_configs=top_configs,
        )
        write_threshold_supplement_markdown(
            args.output_dir / "tables" / "threshold_sensitivity_supplement.md",
            threshold_rows=threshold_rows,
            noise_summary=noise_summary,
            top_configs=top_configs,
        )
        write_release_tables(args.output_dir, summaries)
        write_warnings(args.output_dir, summaries)

    plots_generated = False
    if not args.tables_only:
        image_formats = parse_image_formats(args.image_formats)
        plt = require_matplotlib()
        generate_main_figures(
            summaries,
            residual_panels,
            datasets_dir=args.datasets_dir,
            output_dir=args.output_dir,
            collection_width_mm=args.collection_width_mm,
            report_width_mm=args.report_width_mm,
            disp_min=args.disp_min,
            disp_max=args.disp_max,
            threshold_cN=args.threshold_cN,
            polyorder=args.polyorder,
            window_seconds=args.window_seconds,
            noise_disp_min=args.noise_disp_min,
            noise_disp_max=args.noise_disp_max,
            noise_min_samples=args.noise_min_samples,
            instrument_cutoff_factor=args.instrument_cutoff_factor,
            apply_filter=not args.no_filter,
            image_formats=image_formats,
            dpi=args.dpi,
            plt=plt,
        )
        generate_release_curve_figures(
            manifest_rows,
            datasets_dir=args.datasets_dir,
            output_dir=args.output_dir,
            collection_width_mm=args.collection_width_mm,
            report_width_mm=args.report_width_mm,
            disp_min=args.disp_min,
            disp_max=args.disp_max,
            image_formats=image_formats,
            dpi=args.dpi,
        )
        plots_generated = True

    write_run_readme(
        args.output_dir,
        manifest_path=args.manifest,
        metrics_count=len(all_metrics),
        summary_count=len(summaries),
        plots_generated=plots_generated
        or (args.output_dir / "figures" / "figure_manifest.csv").exists(),
    )

    print(f"Analysed {len(summaries)} configurations and {len(all_metrics)} traces")
    if not args.plots_only:
        print(f"Tables: {args.output_dir / 'tables'}")
        print(f"Data: {args.output_dir / 'data'}")
    if plots_generated:
        print(f"Figures: {args.output_dir / 'figures'}")
    elif args.tables_only:
        print("Figures skipped (--tables-only)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
