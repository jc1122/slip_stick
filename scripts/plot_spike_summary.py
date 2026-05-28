#!/usr/bin/env python3
"""Create a summary plot of the number of spikes for each material/film/side combination."""

import csv
import re
from pathlib import Path
from typing import List, Dict, Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from mpl_toolkits.axes_grid1 import make_axes_locatable

SUMMARIES_DIR = Path(__file__).resolve().parents[1] / "summaries"
OUTPUT_DIR = Path(__file__).resolve().parents[1]
MANIFEST_PATH = Path(__file__).resolve().parents[1] / "publication" / "dataset_manifest.csv"


def manifest_summary_stems(manifest_path: Path = MANIFEST_PATH) -> set[str]:
    """Return dataset stems that belong to the publication manifest."""
    if not manifest_path.exists():
        return set()
    with manifest_path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        return {Path(row["dataset_file"]).stem for row in reader}


def parse_summary_data(summaries_dir: Path) -> pd.DataFrame:
    """Parse the summary files and return a DataFrame with the data.

    Args:
        summaries_dir: The directory containing the summary files.

    Returns:
        A DataFrame with the parsed data.
    """
    data: List[Dict[str, Any]] = []
    allowed_stems = manifest_summary_stems()
    summary_files = sorted(
        summary_file
        for summary_file in summaries_dir.glob("*.txt")
        if not allowed_stems or summary_file.stem in allowed_stems
    )

    for summary_file in summary_files:
        match = re.match(
            r"(\d+)_([A-Z0-9]+)_([a-z0-9]+)_(internal|external)", summary_file.name
        )
        if not match:
            continue

        date, material_type, film_type, side = match.groups()

        try:
            with open(summary_file, "r") as f:
                content = f.read()
                spike_counts = [
                    int(c) for c in re.findall(r"  \S+: (\d+) spikes", content)
                ]
                if spike_counts:
                    average_spikes = np.mean(spike_counts)
                    data.append(
                        {
                            "material_type": material_type,
                            "film_type": film_type,
                            "side": side,
                            "total_spikes": average_spikes,
                        }
                    )
        except FileNotFoundError:
            print(f"Warning: Could not find file {summary_file}")
        except Exception as e:
            print(f"Warning: Could not parse file {summary_file}: {e}")

    return pd.DataFrame(data)


def create_pivot_table(df: pd.DataFrame, side: str) -> pd.DataFrame:
    """Create a pivot table for a given side.

    Args:
        df: The DataFrame with the summary data.
        side: The side to create the pivot table for ('internal' or 'external').

    Returns:
        A pivot table with the average number of spikes.
    """
    side_df = df[df["side"] == side]
    return side_df.pivot_table(
        index="film_type",
        columns="material_type",
        values="total_spikes",
        aggfunc="mean",
    )


def plot_heatmap(pivot_table: pd.DataFrame, side: str) -> None:
    """Generate and save a heatmap plot for a given pivot table.

    Args:
        pivot_table: The pivot table to plot.
        side: The side the plot is for ('internal' or 'external').
    """
    fig, ax = plt.subplots(figsize=(10, 6))
    cax = ax.matshow(pivot_table, cmap="viridis")

    divider = make_axes_locatable(ax)
    cax_cb = divider.append_axes("right", size="5%", pad=0.05)
    cbar = fig.colorbar(cax, cax=cax_cb)
    cbar.set_label("Average number of spikes")

    ax.set_xticks(np.arange(len(pivot_table.columns)))
    ax.set_yticks(np.arange(len(pivot_table.index)))

    ax.set_xticklabels(pivot_table.columns)
    ax.set_yticklabels(pivot_table.index)

    plt.setp(ax.get_xticklabels(), rotation=45, ha="left", rotation_mode="anchor")

    # Add text annotations with adaptive color
    for (i, j), val in np.ndenumerate(pivot_table):
        if not np.isnan(val):
            # Normalize value to 0-1 range for color mapping
            normalized_val = (val - pivot_table.min().min()) / (
                pivot_table.max().max() - pivot_table.min().min()
            )
            # Use black text for light backgrounds, white for dark
            text_color = "black" if normalized_val > 0.5 else "white"
            ax.text(j, i, f"{val:.1f}", ha="center", va="center", color=text_color)

    ax.set_title(f"Average Number of Spikes ({side.capitalize()})")
    fig.tight_layout()
    plt.savefig(OUTPUT_DIR / f"spike_summary_{side}.png")
    plt.show()


def main():
    """Main function."""
    df = parse_summary_data(SUMMARIES_DIR)

    if df.empty:
        print("No data found to plot.")
        return

    for side in ["internal", "external"]:
        pivot_table = create_pivot_table(df, side)
        print(f"--- {side.capitalize()} ---")
        print(pivot_table)
        plot_heatmap(pivot_table, side)


if __name__ == "__main__":
    main()
