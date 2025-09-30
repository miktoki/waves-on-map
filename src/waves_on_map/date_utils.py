from datetime import datetime, timezone
from zoneinfo import ZoneInfo

TIME_TZ_LABEL = "Europe/Oslo"
OSLO_TZ = ZoneInfo(TIME_TZ_LABEL)
UTC = timezone.utc


def to_oslo(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(OSLO_TZ)
