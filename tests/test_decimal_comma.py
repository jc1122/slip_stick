from pathlib import Path

import pytest

from slip_stick.ftm10 import load_ftm10_csv

FIXTURE = Path(__file__).parent / "fixtures" / "ftm10_external_head.csv"


def test_decimal_comma_parsing_spec() -> None:
    df_long, metadata = load_ftm10_csv(str(FIXTURE), preview_lines=80)

    assert metadata["decimal"] == ","

    first_rep = metadata["replicate_ids"][0]
    rep_frame = df_long[df_long["replicate_id"] == first_rep]
    assert not rep_frame.empty

    first_force = rep_frame["force_N"].iloc[0]
    assert pytest.approx(first_force, rel=1e-6) == 0.005404154
    assert metadata["replicates"][first_rep]["n_nans"] == 0
