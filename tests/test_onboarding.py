from datetime import time

import pytest

from worddays.services.onboarding import normalize_phone, parse_delivery_time, validate_timezone


@pytest.mark.parametrize(
    ("text", "expected"),
    [("08:30", time(8, 30)), ("8:30", time(8, 30)), ("21.05", time(21, 5)), (" 0:00 ", time(0, 0))],
)
def test_parse_time_ok(text, expected):
    assert parse_delivery_time(text) == expected


@pytest.mark.parametrize("text", ["24:00", "8", "12:60", "abc", "", "8:5"])
def test_parse_time_bad(text):
    assert parse_delivery_time(text) is None


def test_timezone():
    assert validate_timezone("Asia/Tashkent") == "Asia/Tashkent"
    assert validate_timezone("  Europe/Moscow ") == "Europe/Moscow"
    assert validate_timezone("Mars/Olympus") is None
    assert validate_timezone("UTC") is None  # только Region/City
    assert validate_timezone("../etc/passwd") is None


def test_phone():
    assert normalize_phone("998901234567") == "+998901234567"
    assert normalize_phone("+998 (90) 123-45-67") == "+998901234567"
    assert normalize_phone("12345") is None
