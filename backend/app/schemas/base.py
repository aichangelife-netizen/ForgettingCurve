from datetime import datetime, timezone

from pydantic import BaseModel, field_serializer


def utc_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


class APIModel(BaseModel):
    @field_serializer("*", when_used="json", check_fields=False)
    def serialize_utc_datetimes(self, value):
        if isinstance(value, datetime):
            return utc_datetime(value).isoformat().replace("+00:00", "Z")
        return value
