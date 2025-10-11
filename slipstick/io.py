from __future__ import annotations

import csv
import locale
import re
import unicodedata
from dataclasses import dataclass, field
from itertools import zip_longest
from pathlib import Path
from typing import Generator, List

import numpy as np

from .models import Replicate


def load_replicates(path: str | Path, *, encoding: str = "cp1250") -> List[Replicate]:
    @dataclass
    class _ReplicateBuilder:
        offset: int
        raw_label: str
        time_vals: list[float] = field(default_factory=list)
        force_vals: list[float] = field(default_factory=list)
        disp_vals: list[float] = field(default_factory=list)

    row_iter = _iter_csv_rows(Path(path), encoding=encoding)
    header_rows: list[List[str]] = []
    for _ in range(3):
        try:
            header_rows.append(next(row_iter))
        except StopIteration:
            break
    if len(header_rows) < 3:
        return []

    columns = list(zip_longest(*header_rows, fillvalue=""))
    try:
        labels_row, names_row, units_row = [
            list(values) for values in zip(*columns)
        ]
    except ValueError:
        return []

    n_cols = len(names_row)
    n_cols -= n_cols % 3  # enforce full triples

    builders: list[_ReplicateBuilder] = []
    current_label = ""

    for offset in range(0, n_cols, 3):
        raw_label = labels_row[offset].strip()
        if raw_label:
            current_label = raw_label

        name_triplet = [names_row[offset + i].strip() for i in range(3)]
        unit_triplet = [units_row[offset + i].strip() for i in range(3)]
        if not _looks_like_replicate(name_triplet, unit_triplet):
            continue

        builders.append(_ReplicateBuilder(offset=offset, raw_label=current_label))

    if not builders:
        return []

    for row in row_iter:
        row_len = len(row)
        for builder in builders:
            if builder.offset + 2 >= row_len:
                continue
            t = _parse_float(row[builder.offset])
            f = _parse_float(row[builder.offset + 1])
            d = _parse_float(row[builder.offset + 2])
            if t is None or f is None or d is None:
                continue
            builder.time_vals.append(t)
            builder.force_vals.append(f)
            builder.disp_vals.append(d)

    replicates: List[Replicate] = []
    current_label = ""
    for builder in builders:
        raw_label = builder.raw_label.strip()
        if raw_label:
            current_label = raw_label
        if not current_label:
            current_label = f"rep_{len(replicates) + 1}"

        if not builder.time_vals:
            continue

        replicates.append(
            Replicate(
                rep_id=_normalise_label(current_label, len(replicates) + 1),
                time_s=np.asarray(builder.time_vals, dtype=float),
                force_n=np.asarray(builder.force_vals, dtype=float),
                disp_mm=np.asarray(builder.disp_vals, dtype=float),
            )
        )

    return replicates


def _iter_csv_rows(path: Path, *, encoding: str) -> Generator[List[str], None, None]:
    with path.open("r", encoding=encoding, newline="") as handle:
        reader = csv.reader(handle, delimiter=",", quotechar='"')
        for row in reader:
            if not row:
                continue
            stripped = [cell.strip() for cell in row]
            if all(not cell for cell in stripped):
                continue
            yield stripped


def _looks_like_replicate(names: List[str], units: List[str]) -> bool:
    if len(names) != 3 or len(units) != 3:
        return False
    expected_names = ["czas", "si", "przemieszczenie"]
    expected_units = ["s", "n", "mm"]
    for name, unit, exp_name, exp_unit in zip(
        names, units, expected_names, expected_units
    ):
        if exp_unit.lower() not in unit.lower():
            return False
        if exp_name not in _ASCII_fold(name):
            return False
    return True


def _ASCII_fold(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    ascii_bytes = normalized.encode("ascii", "ignore")
    return ascii_bytes.decode("ascii").lower()


def _normalise_label(raw: str, fallback_index: int) -> str:
    cleaned = re.sub(r"[^0-9a-zA-Z]+", "_", raw.strip())
    cleaned = cleaned.strip("_")
    return cleaned or f"rep_{fallback_index}"


def _parse_float(text: str) -> float | None:
    value = text.strip()
    if not value:
        return None
    value = value.replace(" ", "")
    try:
        return locale.atof(value)
    except (ValueError, AttributeError):
        fallback = value.replace(",", ".")
        try:
            return float(fallback)
        except ValueError:
            return None
