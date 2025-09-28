from pathlib import Path

import pytest

from slip_stick.ftm10 import load_ftm10_csv

FIXTURE = Path(__file__).parent / "fixtures" / "ftm10_external_head.csv"


def test_timebase_stats_spec() -> None:
    _, metadata = load_ftm10_csv(str(FIXTURE), preview_lines=80)

    for rep_meta in metadata["replicates"].values():
        assert rep_meta["n_samples"] > 0
        assert rep_meta["dt_median"] is not None
        assert rep_meta["dt_median"] == pytest.approx(0.01, rel=5e-3)
        assert rep_meta["dt_std"] >= 0
        assert rep_meta["Fs"] == pytest.approx(100.0, rel=5e-3)
