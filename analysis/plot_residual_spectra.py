#!/usr/bin/env python3
"""Compatibility wrapper that forwards to the main slipstick CLI residual spectrum workflow."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

if __package__ is None or __package__ == "":  # pragma: no cover - script entry point
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from slipstick import cli as slipstick_cli


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Generate residual spectrum plots using the slipstick CLI refactored pipeline. "
            "Outputs a multi-panel summary image by default; pass other CLI flags via --extra."
        )
    )
    parser.add_argument("dataset", help="Path to the dataset CSV.")
    parser.add_argument(
        "--output",
        "-o",
        default="plots/residual_spectra.png",
        help="Output image path (default: plots/residual_spectra.png).",
    )
    parser.add_argument(
        "--band-min",
        type=float,
        default=1.8,
        help="Lower bound of the highlighted frequency band (Hz).",
    )
    parser.add_argument(
        "--band-max",
        type=float,
        default=2.4,
        help="Upper bound of the highlighted frequency band (Hz).",
    )
    parser.add_argument(
        "--extra",
        nargs=argparse.REMAINDER,
        help=(
            "Additional arguments forwarded to slipstick.cli (e.g. '--extra --threshold 0.02')."
        ),
    )
    args = parser.parse_args(argv)

    cli_args = [
        "--input",
        str(Path(args.dataset)),
        "--spectra-summary",
        str(Path(args.output)),
        "--spectra-band-min",
        f"{args.band_min}",
        "--spectra-band-max",
        f"{args.band_max}",
    ]
    if args.extra:
        cli_args.extend(args.extra)

    exit_code = slipstick_cli.main(cli_args)
    if exit_code != 0:
        raise SystemExit(exit_code)
    print(f"Wrote {args.output}")


if __name__ == "__main__":  # pragma: no cover - script entry point
    main()
