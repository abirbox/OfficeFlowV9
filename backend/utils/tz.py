"""Timezone helpers. Default org timezone = Asia/Dhaka (UTC+6) unless overridden in app_settings."""
from datetime import datetime, timezone, timedelta, date
from zoneinfo import ZoneInfo
from typing import Optional

DEFAULT_TZ = "Asia/Dhaka"
DEFAULT_OFFSET_HOURS = 6.0
DHAKA_TZ = ZoneInfo(DEFAULT_TZ)


def dhaka_now() -> datetime:
    """Current wall-clock time in Asia/Dhaka (tz-aware)."""
    return datetime.now(timezone.utc).astimezone(DHAKA_TZ)


def dhaka_today() -> date:
    """Today's calendar date in Asia/Dhaka (never in UTC/browser tz)."""
    return dhaka_now().date()


def dhaka_today_iso() -> str:
    """ISO date string (YYYY-MM-DD) for today in Asia/Dhaka."""
    return dhaka_today().isoformat()


async def get_org_timezone(db) -> tuple[str, float]:
    """Read timezone code + offset hours from app_settings singleton."""
    try:
        doc = await db.app_settings.find_one({"key": "app_settings_singleton"}, {"_id": 0})
        if doc:
            return doc.get("timezone", DEFAULT_TZ), float(doc.get("tz_offset_hours", DEFAULT_OFFSET_HOURS))
    except Exception:
        pass
    return DEFAULT_TZ, DEFAULT_OFFSET_HOURS


def to_local(dt: datetime, tz_code: str = DEFAULT_TZ, offset_hours: float = DEFAULT_OFFSET_HOURS) -> datetime:
    """Convert a UTC (or naive UTC) datetime to org local time."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    try:
        return dt.astimezone(ZoneInfo(tz_code))
    except Exception:
        # Fallback to fixed offset
        return dt.astimezone(timezone(timedelta(hours=offset_hours)))


def local_now(tz_code: str = DEFAULT_TZ, offset_hours: float = DEFAULT_OFFSET_HOURS) -> datetime:
    return to_local(datetime.now(timezone.utc), tz_code, offset_hours)


def local_minutes_of_day(dt: datetime, tz_code: str = DEFAULT_TZ, offset_hours: float = DEFAULT_OFFSET_HOURS) -> int:
    local = to_local(dt, tz_code, offset_hours)
    return local.hour * 60 + local.minute


def local_date_iso(dt: Optional[datetime] = None, tz_code: str = DEFAULT_TZ, offset_hours: float = DEFAULT_OFFSET_HOURS) -> str:
    d = to_local(dt or datetime.now(timezone.utc), tz_code, offset_hours)
    return d.date().isoformat()
