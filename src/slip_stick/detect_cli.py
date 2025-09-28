"""Command-line interface for detection and decomposition (scaffold).

Provides band estimation via Welch and a lossless three-way decomposition that writes
NPZ outputs if requested. Onset detection will be added in a follow-up iteration.
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Iterable, Tuple

import numpy as np

from . import ftm10
from .detect import decompose_complementary, estimate_midband_welch

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

    Rep = _select_replicate(meta, args.rep)
    frame = df_long[df_long["replicate_id"] == Rep]
    if frame.empty:
        raise SystemExit(f"replicate not found or empty: {Rep}")

    y = frame["force_N"].to_numpy()
    fs = float(meta["replicates"][Rep]["Fs"]) or 1.0 / float(np.median(np.diff(frame["time_s"])) )

    f1 = args.f1
    f2 = args.f2

    if args.estimate_bands or (f1 is None or f2 is None):
        est = estimate_midband_welch(y, fs)
        LOGGER.info(
            "Estimated band: f1=%.2f Hz, f2=%.2f Hz, f_c=%.2f Hz",
            est.f1,
            est.f2,
            est.f_c,
        )
        if f1 is None:
            f1 = est.f1
        if f2 is None:
            f2 = est.f2

    if f1 is None or f2 is None:
        raise SystemExit("f1/f2 not provided and estimation disabled")

    low, mid, high, recon_rms = decompose_complementary(y, fs, f1, f2)

    print(
        "Replicate: {} | Fs={:.2f} Hz | f1={:.2f} Hz f2={:.2f} Hz | recon_rms={:.2e}".format(
            Rep, fs, f1, f2, recon_rms
        )
    )

    if args.write_npz:
        out_path = Path(args.write_npz)
        if out_path.suffix != ".npz":
            out_path = out_path.with_suffix(".npz")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        np.savez(
            out_path,
            time=frame["time_s"].to_numpy(),
            low=low,
            mid=mid,
            high=high,
            original=y,
            fs=fs,
            f1=f1,
            f2=f2,
            recon_rms=recon_rms,
            replicate_id=Rep,
        )
        LOGGER.info("Wrote %s", out_path)

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
        raise SystemExit(f"replicate not found: {rep_arg}")


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m slip_stick.detect_cli",
        description="Estimate slip–stick bands and decompose a replicate (scaffold).",
    )
    p.add_argument("--input", "-i", required=True, help="Path to the CSV file to parse.")
    p.add_argument("--rep", help="Replicate id or 1-based index to analyze (default: first).")
    p.add_argument("--estimate-bands", action="store_true", help="Run Welch-based band estimation.")
    p.add_argument("--f1", type=float, help="Lower band edge (Hz). Overrides estimation if given.")
    p.add_argument("--f2", type=float, help="Upper band edge (Hz). Overrides estimation if given.")
    p.add_argument("--write-npz", help="Write components to <path>.npz (time, low, mid, high).")
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


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

