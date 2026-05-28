from enum import StrEnum


class RouteSource(StrEnum):
    MANUAL = "manual"
    AUTO = "auto"
    UNASSIGNED = "unassigned"


def transition(current: RouteSource, proposed: RouteSource) -> RouteSource:
    """Apply the manual-is-sticky invariant for route-source provenance.

    Why: Stage 2 (auto clustering) must never overwrite a human-confirmed
    route assignment, even if the cluster confidence is high. The DB has a
    TRIGGER as a second line of defense (see db.py); this function is the
    application-level guard so callers don't depend on catching IntegrityError.
    """
    if current is RouteSource.MANUAL:
        return RouteSource.MANUAL
    return proposed
