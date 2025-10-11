from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

import numpy as np


@dataclass
class Replicate:
    rep_id: str
    time_s: np.ndarray
    force_n: np.ndarray
    disp_mm: np.ndarray


@dataclass
class Spike:
    index: int
    time_s: float
    disp_mm: float
    residual_n: float


@dataclass
class DetectionResult:
    time: np.ndarray
    disp: np.ndarray
    force: np.ndarray
    baseline: np.ndarray
    residual: np.ndarray
    spikes: List[Spike]
    residual_freqs: np.ndarray | None = field(default=None, repr=False)
    residual_power: np.ndarray | None = field(default=None, repr=False)
    peak_freq_hz: float | None = field(default=None, repr=False)


@dataclass
class NoiseEstimate:
    std_n: float
    dc_offset_n: float
    max_abs_n: float
    sample_count: int
    disp_max_mm: float
    time_span_s: float
    sample_rate_hz: float | None
    noise_peak_hz: float | None
    raw_force: np.ndarray | None = field(default=None, repr=False)
    baseline_force: np.ndarray | None = field(default=None, repr=False)
    residual_force: np.ndarray | None = field(default=None, repr=False)
    time_s: np.ndarray | None = field(default=None, repr=False)
    disp_mm: np.ndarray | None = field(default=None, repr=False)
