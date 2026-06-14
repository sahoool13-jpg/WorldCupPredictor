from datetime import datetime, timezone

from wcpredictor.data.model import parse_iso_utc, parse_offset_time, slugify


def test_slugify_folds():
    assert slugify("Türkiye") == "turkiye"
    assert slugify("Bosnia & Herzegovina") == "bosnia herzegovina"
    assert slugify("Bosnia and Herzegovina") == "bosnia herzegovina"
    assert slugify("Côte d'Ivoire") == "cote d ivoire"


def test_parse_offset_time_to_utc():
    # 21:00 at UTC-7 -> 04:00 UTC the next day
    dt = parse_offset_time("2026-06-13", "21:00 UTC-7")
    assert dt == datetime(2026, 6, 14, 4, 0, tzinfo=timezone.utc)


def test_parse_offset_time_missing_time():
    dt = parse_offset_time("2026-06-13", None)
    assert dt == datetime(2026, 6, 13, 0, 0, tzinfo=timezone.utc)


def test_parse_iso_utc():
    assert parse_iso_utc("2026-06-14T04:00Z") == datetime(2026, 6, 14, 4, 0, tzinfo=timezone.utc)
