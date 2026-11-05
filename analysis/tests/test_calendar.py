"""Unit test analysis/calendar.py — semua HTTP di-mock, tanpa network."""

from __future__ import annotations

import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

import analysis.calendar as cal


SAMPLE_FEED = [
    {
        "title": "Non-Farm Employment Change",
        "country": "USD",
        "date": "2026-11-06T13:30:00+00:00",
        "impact": "High",
        "forecast": "180K",
        "previous": "119K",
    },
    {
        "title": "ISM Services PMI",
        "country": "USD",
        "date": "2026-11-05T15:00:00-05:00",  # offset non-UTC
        "impact": "High",
        "forecast": "52.0",
        "previous": "50.2",
    },
    {
        "title": "Core CPI m/m",
        "country": "USD",
        "date": "2026-11-04T13:30:00+00:00",
        "impact": "Medium",  # bukan High -> dibuang
        "forecast": "",
        "previous": "",
    },
    {
        "title": "ECB Press Conference",
        "country": "EUR",  # negara lain -> dibuang
        "date": "2026-11-04T12:45:00+00:00",
        "impact": "High",
        "forecast": "",
        "previous": "",
    },
    {
        "title": "Broken Event",
        "country": "USD",
        "date": "not-a-date",
        "impact": "High",
    },
    {
        "title": "No Date Event",
        "country": "USD",
        "impact": "High",
    },
]


def make_cache(tmp_path: Path, payload=SAMPLE_FEED, age_seconds: float = 0.0) -> Path:
    p = tmp_path / "cache" / "ff.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload), encoding="utf-8")
    if age_seconds:
        old = time.time() - age_seconds
        import os
        os.utime(p, (old, old))
    return p


# ---------- parse_event_date ----------

def test_parse_event_date_with_offset():
    dt = cal.parse_event_date("2026-11-05T15:00:00-05:00")
    assert dt == datetime(2026, 11, 5, 20, 0, tzinfo=timezone.utc)


def test_parse_event_date_naive_treated_as_utc():
    dt = cal.parse_event_date("2026-11-05T15:00:00")
    assert dt.tzinfo is not None
    assert dt.utcoffset() == timedelta(0)


def test_parse_event_date_invalid_returns_none():
    assert cal.parse_event_date("not-a-date") is None
    assert cal.parse_event_date("") is None
    assert cal.parse_event_date(None) is None  # type: ignore[arg-type]


# ---------- filter_red_usd ----------

def test_filter_red_usd_keeps_only_high_usd_sorted():
    out = cal.filter_red_usd(SAMPLE_FEED)
    titles = [e["title"] for e in out]
    assert titles == ["ISM Services PMI", "Non-Farm Employment Change"]  # urut waktu
    for e in out:
        assert e["country"] == "USD"
        assert e["impact"] == "High"
        assert e["time_utc"].endswith("+00:00")


def test_filter_red_usd_impact_case_insensitive():
    feed = [dict(SAMPLE_FEED[0], impact="high")]
    assert len(cal.filter_red_usd(feed)) == 1


def test_filter_red_usd_empty_input():
    assert cal.filter_red_usd([]) == []


# ---------- block_windows ----------

def test_block_windows_iso_and_margin():
    events = cal.filter_red_usd([SAMPLE_FEED[0]])
    ws = cal.block_windows(events, block_minutes=15)
    assert len(ws) == 1
    w = ws[0]
    assert w["event_time_utc"] == "2026-11-06T13:30:00+00:00"
    assert w["block_start_utc"] == "2026-11-06T13:15:00+00:00"
    assert w["block_end_utc"] == "2026-11-06T13:45:00+00:00"


def test_block_windows_custom_minutes():
    events = cal.filter_red_usd([SAMPLE_FEED[0]])
    w = cal.block_windows(events, block_minutes=30)[0]
    assert w["block_start_utc"] == "2026-11-06T13:00:00+00:00"


# ---------- is_blocked ----------

def test_is_blocked_inside_window():
    events = cal.filter_red_usd([SAMPLE_FEED[0]])
    windows = cal.block_windows(events)
    now = datetime(2026, 11, 6, 13, 29, tzinfo=timezone.utc)
    hit = cal.is_blocked(now, windows)
    assert hit is not None and hit["title"] == "Non-Farm Employment Change"


def test_is_blocked_outside_window():
    windows = cal.block_windows(cal.filter_red_usd([SAMPLE_FEED[0]]))
    now = datetime(2026, 11, 6, 14, 0, tzinfo=timezone.utc)
    assert cal.is_blocked(now, windows) is None


def test_is_blocked_empty_windows():
    now = datetime(2026, 11, 6, 13, 30, tzinfo=timezone.utc)
    assert cal.is_blocked(now, []) is None


# ---------- fetch_feed (mock HTTP) ----------

def test_fetch_feed_mock_http(monkeypatch):
    import io

    class FakeResp(io.BytesIO):
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    payload = json.dumps(SAMPLE_FEED).encode()
    monkeypatch.setattr(cal.urllib.request, "urlopen", lambda url, timeout: FakeResp(payload))
    events = cal.fetch_feed()
    assert len(events) == 6


def test_fetch_feed_http_error(monkeypatch):
    def boom(url, timeout):
        raise cal.urllib.error.URLError("network down")

    monkeypatch.setattr(cal.urllib.request, "urlopen", boom)
    with pytest.raises(cal.CalendarError):
        cal.fetch_feed()


def test_fetch_feed_not_a_list(monkeypatch):
    import io

    class FakeResp(io.BytesIO):
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(cal.urllib.request, "urlopen",
                        lambda url, timeout: FakeResp(b'{"oops": true}'))
    with pytest.raises(cal.CalendarError):
        cal.fetch_feed()


# ---------- load_cached ----------

def test_load_cached_fresh_cache_no_network(tmp_path, monkeypatch):
    p = make_cache(tmp_path)

    def fail(url, timeout):
        raise AssertionError("tidak boleh network saat cache segar")

    monkeypatch.setattr(cal.urllib.request, "urlopen", fail)
    events = cal.load_cached(p, ttl_seconds=3600)
    assert len(events) == 6


def test_load_cached_stale_cache_refetches(tmp_path, monkeypatch):
    p = make_cache(tmp_path, age_seconds=7200)
    import io

    class FakeResp(io.BytesIO):
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    fresh = [SAMPLE_FEED[0]]
    monkeypatch.setattr(cal.urllib.request, "urlopen",
                        lambda url, timeout: FakeResp(json.dumps(fresh).encode()))
    events = cal.load_cached(p)
    assert len(events) == 1
    # cache diperbarui
    assert json.loads(p.read_text()) == fresh


def test_load_cached_fetch_fails_falls_back_to_stale(tmp_path, monkeypatch):
    p = make_cache(tmp_path, age_seconds=7200)

    def boom(url, timeout):
        raise cal.urllib.error.URLError("down")

    monkeypatch.setattr(cal.urllib.request, "urlopen", boom)
    events = cal.load_cached(p)
    assert len(events) == 6  # stale cache tetap dipakai


def test_load_cached_no_cache_no_network_raises(tmp_path, monkeypatch):
    def boom(url, timeout):
        raise cal.urllib.error.URLError("down")

    monkeypatch.setattr(cal.urllib.request, "urlopen", boom)
    with pytest.raises(cal.CalendarError):
        cal.load_cached(tmp_path / "nope.json")


# ---------- refresh ----------

def test_refresh_writes_window_file(tmp_path, monkeypatch):
    cache = make_cache(tmp_path)
    out = tmp_path / "analysis" / "news_block_windows.json"

    windows = cal.refresh(cache, out)
    assert out.exists()
    written = json.loads(out.read_text())
    assert written == windows
    assert [w["title"] for w in written] == [
        "ISM Services PMI", "Non-Farm Employment Change"]
    assert all(w["block_start_utc"] < w["event_time_utc"] < w["block_end_utc"]
               for w in written)
