# Project brief

## Overview
Slip_stick focuses on FTM 10 data processing to find the onset of the slip–stick
phenomenon from tensile tester CSV files. The repository is documentation‑first and
houses a Python CLI for detection.

## Requirements
- Maintain Memory Bank per .clinerules and keep activeContext/progress current.
- Add an agent operating constraint: preview at most 100 CSV lines in context.
- Infer data characteristics directly from CSV files (schema, units, sampling).
- Separate low‑frequency peel, mid‑frequency slip–stick, and high‑frequency noise.
- Detect onset using a transparent, tunable, and reproducible method.

## Goals
- Deliver a clear plan and then a working script with CLI.
- Provide concise documentation, examples, and defaults that work on provided data.
- Support reproducible analysis and minimal parameter burden for users.

## Scope
Documentation and implementation for slip–stick onset detection from FTM 10 CSVs,
including filtering, detection logic, and export of onset markers and summaries.
