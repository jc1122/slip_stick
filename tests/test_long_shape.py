from pathlib import Path

from slip_stick.ftm10 import load_ftm10_csv

FIXTURE = Path(__file__).parent / "fixtures" / "ftm10_external_head.csv"


def test_long_format_shape_spec() -> None:
    df_long, metadata = load_ftm10_csv(str(FIXTURE), preview_lines=80)

    assert list(df_long.columns) == ["replicate_id", "time_s", "force_N", "disp_mm"]

    expected_rows = sum(rep_info["n_samples"] for rep_info in metadata["replicates"].values())
    assert df_long.shape[0] == expected_rows

    assert set(df_long["replicate_id"]) <= set(metadata["replicate_ids"])
