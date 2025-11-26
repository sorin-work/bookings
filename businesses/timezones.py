from functools import lru_cache
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError, available_timezones

from django.core.exceptions import ValidationError


@lru_cache(maxsize=1)
def timezone_choices():
    """(name, label) pairs for a select, skipping the legacy aliases like "US/Eastern"."""
    names = sorted(
        name
        for name in available_timezones()
        if "/" in name and not name.startswith(("Etc/", "SystemV/", "US/", "posix/", "right/"))
    )
    return [("UTC", "UTC")] + [(name, name.replace("_", " ")) for name in names]


def validate_timezone(value):
    try:
        ZoneInfo(value)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ValidationError(f"{value!r} is not a time zone we know.") from exc
