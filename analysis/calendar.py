"""Kalender ekonomi ForexFactory — fetch + cache + filter news merah USD.

Sumber: feed resmi mingguan https://nfs.faireconomy.media/ff_calendar_thisweek.json
Diverifikasi riset S2-T4: tanpa auth, schema
  title / country / date (ISO offset) / impact / forecast / previous.
Feed hanya mencakup minggu berjalan dan TIDAK memuat nilai actual.
ToS ForexFactory melarang redistribution database — feed ini untuk
konsumsi internal pipeline/EA (bukan untuk dipublikasikan ulang).

Output: daftar window blokir news (+/- NEWS_BLOCK_MINUTES menit di
sekitar event High-impact USD), JSON yang bisa dikonsumsi pipeline
dan EA (ea/AgenticTrade.mq5 membaca file format yang sama).

Tanpa klaim performa apa pun — modul ini hanya pencegah trading di
sekitar news, bukan alpha.
"""

from __future__ import annotations

import json
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

FEED_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
CACHE_TTL_SECONDS = 3600  # poll maksimum 1x/jam (rekomendasi riset S2-T4)
NEWS_BLOCK_MINUTES = 15   # blokir +/- 15 menit di sekitar rilis
HIGH_IMPACT_COUNTRIES = {"USD"}   # diperluas nanti (EUR, GBP) via konfigurasi
HIGH_IMPACT_LABELS = {"high", "high impact"}  # variasi kapitalisasi feed


class CalendarError(RuntimeError):
    """Kegagalan fetch/parse kalender — jangan pernah jadi alasan blokir total."""


def fetch_feed(url: str = FEED_URL, timeout: float = 15.0) -> list[dict[str, Any]]:
    """Ambil feed JSON dari jaringan. Melempar CalendarError jika gagal."""
    # CDN di depan feed menolak user-agent default python-urllib (403) —
    # kirim UA browser generik. Feed tetap publik tanpa auth.
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36",
        "Accept": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status != 200:
                raise CalendarError(f"HTTP {resp.status} dari feed kalender")
            data = json.loads(resp.read().decode("utf-8"))
    except CalendarError:
        raise
    except Exception as exc:  # urllib / JSON errors
        raise CalendarError(f"gagal fetch feed kalender: {exc}") from exc
    if not isinstance(data, list):
        raise CalendarError("feed kalender bukan list JSON")
    return data


def load_cached(cache_path: str | Path, url: str = FEED_URL,
                ttl_seconds: int = CACHE_TTL_SECONDS) -> list[dict[str, Any]]:
    """Fetch dengan cache file TTL.

    - cache segar (< ttl) -> pakai cache, tidak ada network call.
    - cache kedaluwarsa/hilang -> fetch, tulis cache baru.
    - fetch gagal tapi ada cache lama -> pakai cache lama (stale ok).
    - fetch gagal tanpa cache -> CalendarError.
    """
    path = Path(cache_path)
    now = time.time()
    if path.exists():
        try:
            age = now - path.stat().st_mtime
            if age < ttl_seconds:
                return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            pass  # cache korup = anggap hilang
    try:
        events = fetch_feed(url)
    except CalendarError:
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except ValueError as exc:
                raise CalendarError(f"cache korup & fetch gagal: {exc}") from exc
        raise
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(events), encoding="utf-8")
    tmp.replace(path)
    return events


def parse_event_date(raw: str) -> datetime | None:
    """Parse kolom 'date' feed (ISO offset) -> datetime aware UTC.

    Return None jika field hilang/tidak valid (event dilewati, bukan error fatal).
    """
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if dt.tzinfo is None:
        # Feed normalnya selalu offset; kalau naive, anggap UTC dan WARN via None? —
        # lebih aman diperlakukan UTC eksplisit agar window tetap deterministik.
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def filter_red_usd(events: list[dict[str, Any]],
                   countries: set[str] | None = None) -> list[dict[str, Any]]:
    """Filter event High-impact untuk daftar negara mata uang (default USD).

    Event dengan date tidak valid atau impact bukan 'High' dibuang.
    Output diurutkan berdasarkan waktu rilis UTC.
    """
    countries = countries or HIGH_IMPACT_COUNTRIES
    out: list[dict[str, Any]] = []
    for ev in events:
        impact = str(ev.get("impact", "")).strip().lower()
        country = str(ev.get("country", "")).strip().upper()
        if country not in countries:
            continue
        if impact not in HIGH_IMPACT_LABELS:
            continue
        dt = parse_event_date(str(ev.get("date", "")))
        if dt is None:
            continue
        out.append({
            "title": str(ev.get("title", "")).strip(),
            "country": country,
            "impact": "High",
            "time_utc": dt.isoformat(),
            "forecast": ev.get("forecast"),
            "previous": ev.get("previous"),
        })
    out.sort(key=lambda e: e["time_utc"])
    return out


def block_windows(events: list[dict[str, Any]],
                  block_minutes: int = NEWS_BLOCK_MINUTES) -> list[dict[str, Any]]:
    """Konversi event ke window blokir (+/- block_minutes).

    Format output (kontrak lintas pipeline & EA):
      {"title", "country", "event_time_utc", "block_start_utc", "block_end_utc"}
    Semua ISO-8601 UTC, urut berdasarkan block_start.
    """
    delta = timedelta(minutes=block_minutes)
    windows: list[dict[str, Any]] = []
    for ev in events:
        dt = parse_event_date(ev.get("time_utc", ""))
        if dt is None:
            continue
        windows.append({
            "title": ev.get("title", ""),
            "country": ev.get("country", ""),
            "event_time_utc": dt.isoformat(),
            "block_start_utc": (dt - delta).isoformat(),
            "block_end_utc": (dt + delta).isoformat(),
        })
    windows.sort(key=lambda w: w["block_start_utc"])
    return windows


def is_blocked(now_utc: datetime, windows: list[dict[str, Any]]) -> dict[str, Any] | None:
    """True-window check: return window yang memblokir now_utc, atau None."""
    for w in windows:
        start = parse_event_date(w.get("block_start_utc", ""))
        end = parse_event_date(w.get("block_end_utc", ""))
        if start is None or end is None:
            continue
        if start <= now_utc <= end:
            return w
    return None


def refresh(cache_path: str | Path, out_path: str | Path,
            url: str = FEED_URL, block_minutes: int = NEWS_BLOCK_MINUTES,
            countries: set[str] | None = None) -> list[dict[str, Any]]:
    """Entri pipeline: fetch/cache -> filter merah USD -> tulis file window.

    File output adalah JSON list window blokir — format yang sama
    yang dibaca ea/AgenticTrade.mq5 (news guard). Return windows.
    """
    events = load_cached(cache_path, url=url)
    windows = block_windows(filter_red_usd(events, countries=countries),
                            block_minutes=block_minutes)
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(out.suffix + ".tmp")
    tmp.write_text(json.dumps(windows, indent=2), encoding="utf-8")
    tmp.replace(out)
    return windows


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="Refresh window blokir news merah USD")
    ap.add_argument("--cache", default="cache/ff_calendar.json")
    ap.add_argument("--out", default="analysis/news_block_windows.json")
    ap.add_argument("--minutes", type=int, default=NEWS_BLOCK_MINUTES)
    args = ap.parse_args()
    ws = refresh(args.cache, args.out, block_minutes=args.minutes)
    print(f"{len(ws)} window blokir ditulis ke {args.out}")
