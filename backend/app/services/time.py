from datetime import datetime, timezone


def as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def elapsed_seconds(later: datetime, earlier: datetime) -> int:
    return int((as_utc(later) - as_utc(earlier)).total_seconds())
