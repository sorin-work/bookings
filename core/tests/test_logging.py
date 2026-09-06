import json
import logging
import sys

from core.logging import JsonFormatter


def make_record(**extra):
    record = logging.makeLogRecord(
        {"name": "bookings", "levelno": logging.WARNING, "levelname": "WARNING", "msg": "Hi %s"}
    )
    record.args = ("there",)
    for key, value in extra.items():
        setattr(record, key, value)
    return record


def test_json_formatter_writes_one_object():
    payload = json.loads(JsonFormatter().format(make_record()))

    assert payload["level"] == "WARNING"
    assert payload["logger"] == "bookings"
    assert payload["message"] == "Hi there"
    assert payload["time"].endswith("+00:00")


def test_json_formatter_keeps_extra_fields():
    payload = json.loads(JsonFormatter().format(make_record(booking="ABC123", attempts=2)))

    assert payload["booking"] == "ABC123"
    assert payload["attempts"] == 2


def test_json_formatter_includes_exceptions():
    try:
        raise ValueError("nope")
    except ValueError:
        record = make_record()
        record.exc_info = sys.exc_info()

    payload = json.loads(JsonFormatter().format(record))

    assert "ValueError: nope" in payload["exception"]
