import math

import numpy as np

from strava_climbing.boundary_detection import find_attempts
from strava_climbing.metrics import (
    compute_metrics,
    compute_route_percentiles,
    current_config_hash,
)


def test_metrics_on_synthetic_send(successful_climb, frame_h):
    xy, conf, com_xy = successful_climb
    attempts = find_attempts(com_xy, xy, conf, frame_h)
    assert attempts, "expected at least one attempt from the synthetic send"
    m = compute_metrics(attempts[0], com_xy, fps=30.0)
    assert m.send is True
    assert m.time_seconds > 0
    # Synthetic climb is linear — jerk should be finite and small.
    assert math.isfinite(m.smoothness_raw)


def test_percentiles_low_jerk_ranks_high():
    raws = [0.1, 0.5, 1.0, 5.0]
    pcts = compute_route_percentiles(raws)
    assert pcts[0] is not None and pcts[-1] is not None
    assert pcts[0] > pcts[-1], "lower raw jerk should map to higher percentile"
    assert 0.0 <= min(p for p in pcts if p is not None)
    assert max(p for p in pcts if p is not None) <= 100.0


def test_percentiles_below_threshold_returns_none():
    raws = [0.1]  # below SMOOTHNESS_MIN_ATTEMPTS_FOR_PERCENTILE
    assert compute_route_percentiles(raws) == [None]


def test_frozen_baseline_keeps_old_scores_stable():
    baseline = [1.0, 2.0, 3.0, 4.0]
    first_run = compute_route_percentiles(baseline)
    # Add a new "fast" attempt. With a frozen baseline, the previously-computed
    # percentiles for the original four don't change.
    new_attempts = baseline + [0.5]
    rerun = compute_route_percentiles(new_attempts, frozen_baseline=baseline)
    assert rerun[:4] == first_run


def test_config_hash_is_stable_across_calls():
    a = current_config_hash()
    b = current_config_hash()
    assert a == b
    assert len(a) == 64  # sha256 hex
