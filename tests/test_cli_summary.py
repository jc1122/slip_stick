import os
import subprocess
import sys
from pathlib import Path

FIXTURE = Path(__file__).parent / "fixtures" / "ftm10_external_head.csv"
SRC = Path(__file__).resolve().parents[1] / "src"


def test_cli_summary_spec() -> None:
    env = os.environ.copy()
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = str(SRC) if not existing else str(SRC) + os.pathsep + existing

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "slip_stick.parse_ftm10",
            "--input",
            str(FIXTURE),
            "--summary",
            "--preview-lines",
            "80",
        ],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )

    stdout = result.stdout
    assert "Replicates: 10" in stdout
    assert "Per replicate:" in stdout
    assert "Fs=" in stdout
