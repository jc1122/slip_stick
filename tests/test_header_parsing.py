from pathlib import Path

from slip_stick import ftm10

FIXTURE = Path(__file__).parent / "fixtures" / "ftm10_external_head.csv"


def test_header_parsing_spec() -> None:
    info = ftm10._sniff_dialect_and_header(str(FIXTURE), preview_lines=80)

    assert info["delimiter"] == ","
    assert info["decimal"] == ","
    assert info["header_rows"] == 3
    assert info["n_columns"] == 30
    assert info["replicate_labels"][0] == "1 _ 1"
    assert info["replicate_labels"][-1] == "1 _ 10"

    first_columns = list(info["columns_multiindex"][:3])
    assert first_columns == [
        ("1 _ 1", "Czas", "sec"),
        ("1 _ 1", "Siła", "N"),
        ("1 _ 1", "Przemieszczenie", "mm"),
    ]
