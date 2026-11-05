"""Struktur analisa pasar SMC/ICT — pure functions, testable.

Semua fungsi menerima data OHLC sederhana (list of dicts atau tuples)
dan mengembalikan struktur data murni. Tanpa I/O, tanpa state, tanpa
dependensi eksternal. TIDAK ADA klaim performa — ini alat analisa,
bukan prediksi profit.

Konvensi candle: {"open": o, "high": h, "low": l, "close": c}
atau tuple (open, high, low, close). Index = urutan waktu (0 terlama).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

Candle = dict  # {"open","high","low","close"}


@dataclass(frozen=True)
class Swing:
    index: int       # indeks candle puncak/lembah
    price: float
    kind: str        # "high" | "low"


@dataclass(frozen=True)
class OrderBlock:
    index: int       # indeks candle OB
    direction: str   # "bullish" | "bearish"
    top: float
    bottom: float


@dataclass(frozen=True)
class FVG:
    index: int       # indeks candle tengah (candle ke-2 dari 3)
    direction: str   # "bullish" | "bearish"
    top: float
    bottom: float


@dataclass(frozen=True)
class MSS:
    index: int       # indeks candle yang menembus struktur
    direction: str   # "bullish" (break ke atas) | "bearish"
    level: float     # level swing yang ditembus
    broke_swing: Swing


def _candle(c: Candle | Sequence[float]) -> tuple[float, float, float, float]:
    if isinstance(c, dict):
        return float(c["open"]), float(c["high"]), float(c["low"]), float(c["close"])
    o, h, l, cl = c
    return float(o), float(h), float(l), float(cl)


def find_swing_points(
    candles: Sequence[Candle | Sequence[float]], left: int = 2, right: int = 2
) -> list[Swing]:
    """Swing high/low fraktal: candle dengan `left` candle lebih rendah/tinggi
    di kiri dan `right` di kanan. Strict inequality di kedua sisi."""
    if left < 1 or right < 1:
        raise ValueError("left/right harus >= 1")
    swings: list[Swing] = []
    for i in range(left, len(candles) - right):
        _, h, l, _ = _candle(candles[i])
        is_high = True
        is_low = True
        for j in range(i - left, i + right + 1):
            if j == i:
                continue
            _, hj, lj, _ = _candle(candles[j])
            if hj >= h:
                is_high = False
            if lj <= l:
                is_low = False
        if is_high:
            swings.append(Swing(i, h, "high"))
        if is_low:
            swings.append(Swing(i, l, "low"))
    return sorted(swings, key=lambda s: s.index)


def find_order_blocks(
    candles: Sequence[Candle | Sequence[float]], swings: Sequence[Swing] | None = None
) -> list[OrderBlock]:
    """Order block sederhana: candle pengecekan (opposite) sebelum pergerakan
    impulsif.
      - bullish OB: candle bearish yang diikuti (dalam 3 candle) oleh candle
        bullish yang close di atas high candle OB.
      - bearish OB: candle bullish yang diikuti candle bearish yang close
        di bawah low candle OB.
    """
    obs: list[OrderBlock] = []
    for i in range(len(candles) - 1):
        o, h, l, c = _candle(candles[i])
        bearish = c < o
        bullish = c > o
        if not (bearish or bullish):
            continue
        for j in range(i + 1, min(i + 4, len(candles))):
            oj, hj, lj, cj = _candle(candles[j])
            if bearish and cj > oj and cj > h:
                obs.append(OrderBlock(i, "bullish", h, l))
                break
            if bullish and cj < oj and cj < l:
                obs.append(OrderBlock(i, "bearish", h, l))
                break
    return obs


def find_fvg(candles: Sequence[Candle | Sequence[float]]) -> list[FVG]:
    """Fair Value Gap 3-candle:
      - bullish: low[i] > high[i-2]  → gap antara high[i-2] dan low[i]
      - bearish: high[i] < low[i-2]  → gap antara low[i-2] dan high[i]
    """
    fvgs: list[FVG] = []
    for i in range(2, len(candles)):
        _, h0, l0, _ = _candle(candles[i - 2])
        _, h2, l2, _ = _candle(candles[i])
        if l2 > h0:
            fvgs.append(FVG(i - 1, "bullish", l2, h0))
        elif h2 < l0:
            fvgs.append(FVG(i - 1, "bearish", l0, h2))  # top=low lama, bottom=high baru
    return fvgs


def find_mss(
    candles: Sequence[Candle | Sequence[float]],
    swings: Sequence[Swing] | None = None,
) -> list[MSS]:
    """Market Structure Shift: close menembus swing terakhir yang berlawanan
    arah tren sebelumnya. Definisi operasional yang dipakai:

    Telusuri candle berurutan. Untuk setiap candle, bandingkan close dengan
    swing high/low yang sudah *confirmed* (index + right < i, default 2).
    Bullish MSS: close menembus swing high terakhir setelah struktur
    sebelumnya bearish (swing low terbaru lebih baru dari swing high terbaru).
    Bearish MSS: kebalikannya. Satu break → arah berubah, break berikutnya
    baru dihitung setelah arah berubah lagi.
    """
    if swings is None:
        swings = find_swing_points(candles)
    RIGHT = 2
    mss: list[MSS] = []
    trend: str | None = None  # arah struktur saat ini
    last_high: Swing | None = None
    last_low: Swing | None = None

    swing_by_idx = sorted(swings, key=lambda s: s.index)
    si = 0
    for i in range(len(candles)):
        while si < len(swing_by_idx) and swing_by_idx[si].index + RIGHT <= i:
            s = swing_by_idx[si]
            if s.kind == "high":
                last_high = s
            else:
                last_low = s
            si += 1
        _, _, _, c = _candle(candles[i])
        if last_high is not None and c > last_high.price:
            if trend != "bullish":
                mss.append(MSS(i, "bullish", last_high.price, last_high))
                trend = "bullish"
            last_high = None
        elif last_low is not None and c < last_low.price:
            if trend != "bearish":
                mss.append(MSS(i, "bearish", last_low.price, last_low))
                trend = "bearish"
            last_low = None
    return mss


@dataclass
class StructureReport:
    swings: list[Swing] = field(default_factory=list)
    order_blocks: list[OrderBlock] = field(default_factory=list)
    fvgs: list[FVG] = field(default_factory=list)
    mss: list[MSS] = field(default_factory=list)


def analyze(candles: Sequence[Candle | Sequence[float]]) -> StructureReport:
    """Analisa lengkap satu set candle. Pure, tanpa klaim performa."""
    swings = find_swing_points(candles)
    return StructureReport(
        swings=swings,
        order_blocks=find_order_blocks(candles),
        fvgs=find_fvg(candles),
        mss=find_mss(candles, swings),
    )
