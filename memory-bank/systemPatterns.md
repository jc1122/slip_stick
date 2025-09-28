# System patterns

## Memory bank architecture
The Memory Bank is a hierarchical documentation system using Markdown files organized
in a dependency structure. It is the source of truth for scope, purpose, design,
technology, active focus, and progress.

## Data analysis workflow pattern
1. Inspect CSV schema and sampling using a small preview (≤100 lines for the agent).
2. Infer time and force/load columns programmatically in the script.
3. Preprocess: de‑NaN, sort by time, and resample to a uniform grid if needed.
4. Separate bands: low‑pass peel trend; band‑pass slip–stick; suppress high‑freq noise.
5. Compute mid‑band energy/envelope and detect onset with adaptive thresholds.
6. Validate on provided CSVs; export onset markers and quick‑look plots.

## Operating constraints
- Agent preview limit: read at most 100 lines from large CSVs to avoid context overflow.
- The processing code is not limited by this preview rule and will operate on full files.
- All data characteristics are derived from the CSV contents (no hard‑coded schema).

## Key technical decisions
- Prefer simple, explainable filters (Butterworth and Savitzky–Golay) before more
  advanced methods. Use Hilbert transform for envelope when appropriate.
- Adaptive thresholds derived from baseline statistics in an early, low‑energy window.
- Hysteresis and minimum‑duration gating to reduce false positives.

## Update triggers
- Update activeContext.md and progress.md after any major decision or parameter change.
- Note assumptions inline and flag unknowns for follow‑up in progress.md.
