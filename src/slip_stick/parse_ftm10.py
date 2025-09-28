"""Command-line interface for parsing FTM 10 CSV exports."""

from __future__ import annotations

import argparse
import json
import logging
import math
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, Tuple

from . import ftm10

LOGGER = logging.getLogger(__name__)
PACKAGE_VERSION = "0.0.0"  # synchronised with pyproject version


def main(argv: Iterable[str] | None = None) -> int:
    args = _build_parser().parse_args(list(argv) if argv is not None else None)
    _configure_logging(args)

    if args.decimal_comma and args.decimal_dot:
        raise SystemExit("Choose at most one decimal override option")

    decimal_override = "," if args.decimal_comma else "." if args.decimal_dot else None

    df_long, metadata = ftm10.load_ftm10_csv(
        args.input,
        preview_lines=args.preview_lines,
        decimal_override=decimal_override,
        header_rows_override=args.header_rows,
    )

    if args.summary:
        print(_format_summary(metadata), file=sys.stdout)

    if args.out:
        parquet_path, metadata_path = _resolve_output_paths(args.out)
        parquet_path.parent.mkdir(parents=True, exist_ok=True)
        df_long.to_parquet(parquet_path, index=False)
        with metadata_path.open("w", encoding="utf-8") as fh:
            json.dump(_json_ready(metadata), fh, indent=2, ensure_ascii=False, allow_nan=False)
        LOGGER.info("Wrote %s and %s", parquet_path, metadata_path)

    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m slip_stick.parse_ftm10",
        description="Parse FTM 10 CSV exports into tidy data and metadata outputs.",
    )
    parser.add_argument("--input", "-i", required=True, help="Path to the CSV file to parse.")
    parser.add_argument(
        "--summary",
        action="store_true",
        help="Print a textual summary (replicate count, sampling stats, NaNs).",
    )
    parser.add_argument(
        "--out",
        help=(
            "Base output path (without extension). "
            "Writes <path>.parquet and <path>.metadata.json."
        ),
    )
    parser.add_argument(
        "--preview-lines",
        type=int,
        default=ftm10.DEFAULT_PREVIEW_LINES,
        help="Number of lines to use for dialect sniffing (default: %(default)s).",
    )
    parser.add_argument(
        "--decimal-comma",
        action="store_true",
        help="Force decimal comma handling (overrides detection).",
    )
    parser.add_argument(
        "--decimal-dot",
        action="store_true",
        help="Force decimal dot handling (overrides detection).",
    )
    parser.add_argument(
        "--header-rows",
        type=int,
        default=ftm10.DEFAULT_HEADER_ROWS,
        help="Number of header rows to parse as MultiIndex (default: %(default)s).",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress informational logging (ERROR level only).",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging (DEBUG level).",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"slip_stick {PACKAGE_VERSION}",
    )
    return parser


def _configure_logging(args: argparse.Namespace) -> None:
    level = logging.INFO
    if args.quiet:
        level = logging.ERROR
    elif args.verbose:
        level = logging.DEBUG
    logging.basicConfig(level=level, format="%(levelname)s: %(message)s")


def _resolve_output_paths(out_arg: str) -> Tuple[Path, Path]:
    base = Path(out_arg)
    if base.suffix:
        base = base.with_suffix("")
    parquet_path = base.parent / f"{base.name}.parquet"
    metadata_path = base.parent / f"{base.name}.metadata.json"
    return parquet_path, metadata_path


def _format_summary(metadata: Dict[str, Any]) -> str:
    replicate_ids = metadata.get("replicate_ids", [])
    replicates = metadata.get("replicates", {})
    rows_summary = metadata.get("rows_summary", {})

    lines = [f"File: {metadata.get('file', 'unknown')}"]
    lines.append(f"Replicates: {len(replicate_ids)} ({', '.join(replicate_ids)})")
    if rows_summary:
        lines.append(
            "Rows per replicate: min {min} median {median:.1f} max {max}".format(
                min=rows_summary.get("min", 0),
                median=rows_summary.get("median", 0.0),
                max=rows_summary.get("max", 0),
            )
        )
    lines.append("Per replicate:")
    for rep_id in replicate_ids:
        rep_meta = replicates.get(rep_id, {})
        lines.append(
            "  - {rep}: rows={rows} Fs={fs} Hz dt={dt} s±{dt_std} s n_nans={nans}".format(
                rep=rep_id,
                rows=rep_meta.get("n_samples", 0),
                fs=_fmt_float(rep_meta.get("Fs")),
                dt=_fmt_float(rep_meta.get("dt_median")),
                dt_std=_fmt_float(rep_meta.get("dt_std")),
                nans=rep_meta.get("n_nans", 0),
            )
        )
    return "\n".join(lines)


def _fmt_float(value: Any, precision: int = 4) -> str:
    if value is None:
        return "nan"
    if isinstance(value, float) and math.isnan(value):
        return "nan"
    try:
        return f"{float(value):.{precision}f}"
    except (TypeError, ValueError):
        return "nan"


def _json_ready(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {key: _json_ready(val) for key, val in obj.items()}
    if isinstance(obj, list):
        return [_json_ready(val) for val in obj]
    if isinstance(obj, float) and math.isnan(obj):
        return None
    return obj


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
