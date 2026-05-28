from strava_climbing.provenance import RouteSource, transition


def test_manual_is_sticky():
    assert transition(RouteSource.MANUAL, RouteSource.AUTO) is RouteSource.MANUAL
    assert transition(RouteSource.MANUAL, RouteSource.UNASSIGNED) is RouteSource.MANUAL


def test_unassigned_can_become_auto_or_manual():
    assert transition(RouteSource.UNASSIGNED, RouteSource.AUTO) is RouteSource.AUTO
    assert transition(RouteSource.UNASSIGNED, RouteSource.MANUAL) is RouteSource.MANUAL


def test_auto_can_be_promoted_to_manual():
    assert transition(RouteSource.AUTO, RouteSource.MANUAL) is RouteSource.MANUAL


def test_strenum_string_compatibility():
    assert RouteSource.MANUAL == "manual"
    assert str(RouteSource.AUTO) == "auto"
