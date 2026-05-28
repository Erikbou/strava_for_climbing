from strava_climbing.boundary_detection import find_attempts


def test_send_climb_detects_single_attempt(successful_climb, frame_h):
    xy, conf, com_xy = successful_climb
    attempts = find_attempts(com_xy, xy, conf, frame_h)
    assert len(attempts) == 1
    a = attempts[0]
    assert a.start_frame < a.end_frame
    assert a.top_frame is not None
    assert a.send is True


def test_failed_climb_no_top(failed_climb, frame_h):
    xy, conf, com_xy = failed_climb
    attempts = find_attempts(com_xy, xy, conf, frame_h)
    # The climber gets on the wall (ankles cross the threshold) but never tops.
    if attempts:
        a = attempts[0]
        assert a.send is False
        assert a.top_frame is None


def test_empty_track_yields_no_attempts(frame_h):
    import numpy as np
    com = np.zeros((0, 2), dtype="float32")
    xy = np.zeros((0, 17, 2), dtype="float32")
    conf = np.zeros((0, 17), dtype="float32")
    assert find_attempts(com, xy, conf, frame_h) == []
