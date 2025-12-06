"""Helpers shared by the tests."""

from datetime import datetime
from zoneinfo import ZoneInfo

LONDON = ZoneInfo("Europe/London")


def at(day, hour, minute=0, tz=LONDON):
    """An aware datetime on `day` at hour:minute in `tz`."""
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=tz)
