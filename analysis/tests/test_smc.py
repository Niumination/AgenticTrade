import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from smc import (  # noqa: E402
    analyze,
    find_fvg,
    find_mss,
    find_order_blocks,
    find_swing_points,
)


def c(o, h, l, cl):
    return {"open": o, "high": h, "low": l, "close": cl}


# Sinario naik-turun sederhana, 10 candle
UP_DOWN = [
    c(100, 101, 99, 100),
    c(100, 102, 100, 101),
    c(101, 104, 100.5, 103),   # naik
    c(103, 106, 102.5, 105),   # puncak sementara
    c(105, 107, 104, 106.5),   # swing high idx4 @107
    c(106.5, 106.8, 104, 105),
    c(105, 105.5, 102, 102.5),
    c(102.5, 103, 99.5, 100),  # swing low idx7 @99.5
    c(100, 101, 100.2, 100.8),
    c(100.8, 101.5, 100.4, 101.2),
]


class TestSwings:
    def test_finds_extremes(self):
        swings = find_swing_points(UP_DOWN)
        highs = [s for s in swings if s.kind == "high"]
        lows = [s for s in swings if s.kind == "low"]
        assert any(s.index == 4 and s.price == 107 for s in highs)
        assert any(s.index == 7 and s.price == 99.5 for s in lows)

    def test_pure_function(self):
        import copy
        data = copy.deepcopy(UP_DOWN)
        find_swing_points(data)
        assert data == UP_DOWN

    def test_invalid_window(self):
        with pytest.raises(ValueError):
            find_swing_points(UP_DOWN, left=0)


class TestOrderBlocks:
    def test_bullish_ob_after_drop(self):
        # candle bearish lalu candle bullish close di atas high-nya
        candles = [
            c(100, 101, 99, 100),
            c(100, 100.5, 97, 97.5),   # bearish OB idx1
            c(98, 103, 97.5, 102.5),   # bullish, close > 100.5
            c(102.5, 104, 102, 103.5),
        ]
        obs = find_order_blocks(candles)
        assert any(
            ob.index == 1 and ob.direction == "bullish"
            and ob.top == 100.5 and ob.bottom == 97
            for ob in obs
        )

    def test_bearish_ob(self):
        candles = [
            c(100, 103, 99.5, 102.5),  # bullish OB idx0
            c(102, 102.5, 98, 98.5),   # bearish, close < 99.5
            c(98.5, 99, 96, 96.5),
        ]
        obs = find_order_blocks(candles)
        assert any(ob.index == 0 and ob.direction == "bearish" for ob in obs)

    def test_no_ob_without_displacement(self):
        candles = [
            c(100, 101, 99, 100),
            c(100, 100.8, 99.2, 100.2),  # doji-ish
            c(100.2, 100.5, 99.5, 100.0),
        ]
        assert find_order_blocks(candles) == []


class TestFVG:
    def test_bullish_fvg(self):
        candles = [
            c(100, 101, 99, 100),
            c(101, 105, 100.8, 104),  # candle tengah
            c(104, 106, 101.5, 105),  # low 101.5 > high sebelumnya 101
        ]
        fvgs = find_fvg(candles)
        assert any(
            f.direction == "bullish" and f.index == 1
            and f.top == 101.5 and f.bottom == 101
            for f in fvgs
        )

    def test_bearish_fvg(self):
        candles = [
            c(100, 101, 99, 100),
            c(100, 100.2, 96, 96.5),
            c(96.5, 97, 95, 95.5),   # high 97 < low sebelumnya 99
        ]
        fvgs = find_fvg(candles)
        assert any(f.direction == "bearish" and f.bottom == 97 and f.top == 99 for f in fvgs)

    def test_no_gap_no_fvg(self):
        candles = [
            c(100, 101, 99, 100),
            c(100, 101, 99, 100),
            c(100, 101, 99, 100),
        ]
        assert find_fvg(candles) == []


class TestMSS:
    def test_bullish_then_bearish_mss(self):
        # swing high idx4 @107 (candle 5-6 lebih rendah), lalu candle 8
        # close 108 → bullish MSS. Setelah itu turun & break swing low.
        candles = [
            c(100, 101, 99, 100),
            c(100, 102, 100, 101),
            c(101, 104, 100.5, 103),
            c(103, 106, 102.5, 105),
            c(105, 107, 104, 106.5),    # swing high idx4 @107
            c(106, 106.5, 105, 105.5),
            c(105.5, 106, 104, 104.5),
            c(105, 108, 104.5, 107.8),  # close 107.8 > 107 → bullish MSS
            c(108, 108.5, 107, 107.5),
            c(107.5, 108, 106, 106.5),
        ]
        mss = find_mss(candles)
        assert mss[0].direction == "bullish"
        assert mss[0].level == 107
        assert mss[0].index == 7

    def test_no_break_no_mss(self):
        flat = [c(100, 100.5, 99.5, 100)] * 10
        assert find_mss(flat) == []

    def test_accepts_precomputed_swings(self):
        swings = find_swing_points(UP_DOWN)
        mss = find_mss(UP_DOWN, swings)
        assert isinstance(mss, list)


class TestAnalyze:
    def test_report_contains_all(self):
        rep = analyze(UP_DOWN)
        assert rep.swings
        assert rep.fvgs is not None
        assert rep.order_blocks is not None
        assert rep.mss is not None

    def test_tuple_input_supported(self):
        tuples = [(100, 101, 99, 100), (100, 102, 100, 101), (101, 104, 100.5, 103),
                  (103, 106, 102.5, 105), (105, 107, 104, 106.5), (106, 107, 104, 105)]
        assert find_swing_points(tuples) == find_swing_points(UP_DOWN[:6])
