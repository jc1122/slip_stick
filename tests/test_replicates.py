from pathlib import Path

from slip_stick.ftm10 import load_ftm10_csv

FIXTURE = Path(__file__).parent / "fixtures" / "ftm10_external_head.csv"


def test_replicates_count_spec() -> None:
    df_long, metadata = load_ftm10_csv(str(FIXTURE), preview_lines=80)

    replicate_ids = metadata["replicate_ids"]
    assert len(replicate_ids) == 10
    assert len(set(replicate_ids)) == len(replicate_ids)

    for rep_id in replicate_ids:
        subset = df_long[df_long["replicate_id"] == rep_id]
        assert not subset.empty
        assert metadata["replicates"][rep_id]["source_label"].startswith("1 _")
