"""Command-line interface for detection and decomposition (scaffold).

Provides band estimation via Welch and a lossless three-way decomposition that writes
NPZ outputs if requested. The CLI can now iterate over all replicates and emit JSON
summaries to feed downstream tooling. Onset detection will be added in a follow-up
iteration.
"""

from __future__ import annotations

import argparse
import json
import logging
import math
from pathlib import Path
from typing import Iterable, List, Sequence

import numpy as np

from . import ftm10
from .detect import (
    DecompositionResult,
    band_estimate_to_summary,
    decompose_complementary,
    decomposition_to_summary,
    estimate_midband_welch,
)

LOGGER = logging.getLogger(__name__)
PACKAGE_VERSION = "0.0.0"  # sync with project version


def main(argv: Iterable[str] | None = None) -> int:
    args = _build_parser().parse_args(list(argv) if argv is not None else None)
    _configure_logging(args)

    df_long, meta = ftm10.load_ftm10_csv(
        args.input,
        preview_lines=args.preview_lines,
        decimal_override="," if args.decimal_comma else "." if args.decimal_dot else None,
        header_rows_override=args.header_rows,
    )

    if args.all_reps and args.rep:
        raise SystemExit("--all-reps cannot be combined with --rep")

    replicate_ids = list(meta.get("replicate_ids", []))
    if not replicate_ids:
        raise SystemExit("no replicates available")

    targets = replicate_ids if args.all_reps else [_select_replicate(meta, args.rep)]
    summaries: List[dict] = []

    for rep_id in targets:
        frame = df_long[df_long["replicate_id"] == rep_id]
        if frame.empty:
            LOGGER.warning("Replicate %s has no samples; skipping", rep_id)
            continue

        y = frame["force_N"].to_numpy()
        fs = _resolve_sampling_rate(meta, rep_id, frame["time_s"].to_numpy())

        f1 = args.f1
        f2 = args.f2
        estimate_summary = None

        if args.estimate_bands or (f1 is None or f2 is None):
            est = estimate_midband_welch(y, fs)
            LOGGER.info(
                "Rep %s | Estimated band: f1=%.2f Hz, f2=%.2f Hz, f_c=%.2f Hz",
                rep_id,
                est.f1,
                est.f2,
                est.f_c,
            )
            estimate_summary = band_estimate_to_summary(est)
            if f1 is None:
                f1 = est.f1
            if f2 is None:
                f2 = est.f2

        if f1 is None or f2 is None:
            raise SystemExit(
                "f1/f2 not provided and estimation disabled; pass both or enable --estimate-bands"
            )

        decomp = decompose_complementary(y, fs, f1, f2)
        if not isinstance(decomp, DecompositionResult):  # pragma: no cover - defensive
            raise SystemExit("unexpected decomposition result type")

        diag = decomposition_to_summary(decomp)
        f1_used = diag.get("f1_used", f1)
        f2_used = diag.get("f2_used", f2)
        energy_mid = diag.get("energy_fraction_mid", float("nan"))

        print(
            (
                "Replicate: {} | Fs={:.2f} Hz | f1={:.2f} Hz f2={:.2f} Hz | "
                "recon_rms={:.2e} | energy_mid_frac={:.2%}"
            ).format(rep_id, fs, f1_used, f2_used, decomp.recon_rms, energy_mid)
        )

        if args.write_npz:
            _write_npz(args.write_npz, rep_id, frame, decomp, y, fs, f1_used, f2_used, diag)

        summary = {
            "replicate_id": rep_id,
            "fs_hz": fs,
            "f1_hz": f1_used,
            "f2_hz": f2_used,
            "recon_rms": decomp.recon_rms,
            "energy_fraction_mid": energy_mid,
            "energy_fraction_low": diag.get("energy_fraction_low", float("nan")),
            "energy_fraction_high": diag.get("energy_fraction_high", float("nan")),
            "band_estimate": (
                estimate_summary
                if estimate_summary is not None
                else _fallback_band_summary(f1_used, f2_used)
            ),
            "decomposition": diag,
        }
        summaries.append(summary)

    if args.write_json:
        processed_ids = [entry["replicate_id"] for entry in summaries]
        _write_json_summary(args.write_json, args.input, summaries, processed_ids)

    if not summaries:
        raise SystemExit("no replicates processed successfully")

    return 0


def _select_replicate(meta: dict, rep_arg: str | None) -> str:
    reps = list(meta.get("replicate_ids", []))
    if not reps:
        raise SystemExit("no replicates available")
    if not rep_arg:
        return reps[0]
    # allow index (1-based) or id
    try:
        idx = int(rep_arg)
        if idx < 1 or idx > len(reps):
            raise ValueError
        return reps[idx - 1]
    except ValueError:
        # treat as id string
        if rep_arg in reps:
            return rep_arg
        raise SystemExit(f"replicate not found: {rep_arg}") from None


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m slip_stick.detect_cli",
        description="Estimate slip–stick bands and decompose a replicate (scaffold).",
    )
    p.add_argument("--input", "-i", required=True, help="Path to the CSV file to parse.")
    p.add_argument("--rep", help="Replicate id or 1-based index to analyze (default: first).")
    p.add_argument("--all-reps", action="store_true", help="Process every replicate sequentially.")
    p.add_argument("--estimate-bands", action="store_true", help="Run Welch-based band estimation.")
    p.add_argument("--f1", type=float, help="Lower band edge (Hz). Overrides estimation if given.")
    p.add_argument("--f2", type=float, help="Upper band edge (Hz). Overrides estimation if given.")
    p.add_argument("--write-npz", help="Write components to <path>.npz (time, low, mid, high).")
    p.add_argument("--write-json", help="Write summary diagnostics to <path>.json.")
    p.add_argument("--preview-lines", type=int, default=ftm10.DEFAULT_PREVIEW_LINES)
    p.add_argument("--header-rows", type=int, default=ftm10.DEFAULT_HEADER_ROWS)
    p.add_argument("--decimal-comma", action="store_true")
    p.add_argument("--decimal-dot", action="store_true")
    p.add_argument("--quiet", action="store_true")
    p.add_argument("--verbose", action="store_true")
    p.add_argument("--version", action="version", version=f"slip_stick {PACKAGE_VERSION}")
    return p


def _configure_logging(args: argparse.Namespace) -> None:
    level = logging.INFO
    if args.quiet:
        level = logging.ERROR
    elif args.verbose:
        level = logging.DEBUG
    logging.basicConfig(level=level, format="%(levelname)s: %(message)s")


def _resolve_sampling_rate(meta: dict, rep_id: str, time_s: np.ndarray) -> float:
    rep_meta = meta.get("replicates", {}).get(rep_id, {}) if isinstance(meta, dict) else {}
    fs = rep_meta.get("Fs")
    if fs is not None:
        try:
            fs_val = float(fs)
        except (TypeError, ValueError):  # pragma: no cover - defensive
            fs_val = math.nan
        if math.isfinite(fs_val) and fs_val > 0:
            return fs_val

    if time_s.size < 2:
        raise SystemExit(f"unable to infer sampling rate for replicate {rep_id}")

    diffs = np.diff(time_s)
    diffs = diffs[np.isfinite(diffs)]
    if diffs.size == 0:
        raise SystemExit(f"replicate {rep_id} has no finite time deltas")

    dt_median = float(np.median(diffs))
    if not math.isfinite(dt_median) or dt_median <= 0:
        raise SystemExit(f"replicate {rep_id} median dt invalid: {dt_median!r}")

    return 1.0 / dt_median


def _write_npz(
    base_path: str,
    rep_id: str,
    frame,
    decomp: DecompositionResult,
    y: np.ndarray,
    fs: float,
    f1: float,
    f2: float,
    diag: dict,
) -> None:
    out_path = Path(base_path)
    if out_path.suffix != ".npz":
        out_path = out_path.with_suffix(".npz")
    if out_path.is_dir():
        out_path = out_path / f"{rep_id}.npz"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    np.savez(
        out_path,
        time=frame["time_s"].to_numpy(),
        low=decomp.low,
        mid=decomp.mid,
        high=decomp.high,
        original=y,
        fs=fs,
        f1=f1,
        f2=f2,
        recon_rms=decomp.recon_rms,
        replicate_id=rep_id,
        diagnostics=diag,
    )
    LOGGER.info("Wrote %s", out_path)


def _fallback_band_summary(f1: float, f2: float) -> dict:
    fc = 0.5 * (f1 + f2)
    return {"f1": f1, "f2": f2, "f_c": fc, "derived": True}


def _write_json_summary(
    base_path: str,
    input_path: str,
    summaries: Sequence[dict],
    processed: Sequence[str],
) -> None:
    out_path = Path(base_path)
    if out_path.suffix != ".json":
        out_path = out_path.with_suffix(".json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "input": str(Path(input_path)),
        "processed_replicates": list(processed),
        "replicates": summaries,
    }
    with out_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
    LOGGER.info("Wrote %s", out_path)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
