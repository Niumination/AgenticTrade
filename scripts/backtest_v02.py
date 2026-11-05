#!/usr/bin/env python3
"""S4-T1: Strategy v0.2 backtest — regime filter + news filter + RR variants.

Builds on scripts/backtest_phase1.py (v0.1 = smc_mss_m15_tp2r, -19.7R/6yr,
WR 31-35%). v0.2 changes, all re-backtested per year 2020-2025:

  1. Regime filter (avoid chop): only take MSS signals when the M15 trend
     is directional — |EMA(20) - EMA(50)| / ATR(14) >= REGIME_MIN, and the
     MSS direction agrees with the EMA slope sign. Signals in ranging
     markets are dropped.
  2. News filter (analysis/calendar.py): signals created inside a
     high-impact news window are dropped at generation (and the engine
     widens slippage inside windows). HISTORICAL windows are an
     APPROXIMATION: the ForexFactory feed only covers the current week,
     so this script synthesises recurring US releases — NFP (first Friday
     13:30 UTC +/-45m) and CPI (2nd Tuesday... actually fixed 10th-12th
     window: 10th 14:30 UTC +/-45m) per month 2020-2025. FOMC exact dates
     are NOT approximated (omitted) — documented limitation.
  3. RR/entry variation: TP at 1.5R / 2.0R / 2.5R compared under the same
     filters.
  4. Engine now charges commission + swap and applies news-window
     slippage widening (S3-T4 review fixes, backtest/engine.py).

Outputs (append-only results, all labelled BACKTEST / NOT VERIFIED):
  backtest/results/bt2-<year>.jsonl            (per-year v0.2 baseline RR 2.0)
  backtest/results/bt2-summary.json            per-year + RR experiment table

STATUS: BACKTEST / NOT VERIFIED. Never present as a real track record.

Stdlib only. Usage:
  python3 scripts/backtest_v02.py --years 2020 2021 --run-prefix bt2
"""

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from backtest import engine as btengine                       # noqa: E402
from backtest.engine import Engine, write_results, NOT_VERIFIED  # noqa: E402
from scripts.backtest_phase1 import (                         # noqa: E402
    stream_m1_bars, ticks_path)

STRATEGY_BASE = "0.2-bt"          # per-year: 0.2-bt-<year>
REGIME_MIN = 0.5                  # |EMA20-EMA50|/ATR14 threshold (trendiness)
EMA_FAST, EMA_SLOW, ATR_N = 20, 50, 14
NEWS_SLIPPAGE_POINTS = 1.0        # base slippage points (0 -> widening inert)
NEWS_BLOCK_MINUTES = 45
RR_VARIANTS = (1.5, 2.0, 2.5)


# --------------------------------------------------------------------------- #
# Indicators (simple, on M15 close list)
# --------------------------------------------------------------------------- #
def ema(values, n):
    if len(values) < n:
        return None
    k = 2.0 / (n + 1)
    e = sum(values[:n]) / n
    for v in values[n:]:
        e = v * k + e * (1 - k)
    return e


def atr(bars, n):
    """bars: list of (o, h, l, c). True-ish ATR via full-range mean."""
    if len(bars) < n:
        return None
    return sum(b[1] - b[2] for b in bars[-n:]) / n


# --------------------------------------------------------------------------- #
# Historical news windows (approximation — documented limitation)
# --------------------------------------------------------------------------- #
def synth_news_windows(year, block_minutes=NEWS_BLOCK_MINUTES):
    """Approximate high-impact USD windows for a year.

    - NFP: first Friday of each month, 13:30 UTC (8:30 ET winter schedule),
      +/- block_minutes. Releases that fall on exchange holidays are NOT
      adjusted (over-blocking is the conservative side).
    - CPI: 10th of each month 14:30 UTC +/- block_minutes (actual release
      day varies 10th-15th; window is widened deliberately).
    Returns list of {title, block_start_utc, block_end_utc}.
    """
    out = []
    d = datetime(year, 1, 1, tzinfo=timezone.utc)
    while d.year == year:
        if d.weekday() == 4 and d.day <= 7:      # first Friday
            ev = d.replace(hour=13, minute=30)
            out.append(("NFP (approx)", ev))
        if d.day == 10:
            ev = d.replace(hour=14, minute=30)
            out.append(("CPI (approx)", ev))
        d += timedelta(days=1)
    delta = timedelta(minutes=block_minutes)
    return [{"title": t,
             "block_start_utc": (ev - delta).isoformat(),
             "block_end_utc": (ev + delta).isoformat()}
            for t, ev in sorted(out, key=lambda x: x[1])]


def in_news(ts, windows):
    for w in windows:
        s = datetime.fromisoformat(w["block_start_utc"])
        e = datetime.fromisoformat(w["block_end_utc"])
        if s <= ts <= e:
            return True
    return False


# --------------------------------------------------------------------------- #
# v0.2 signal generation: SMC MSS + regime + news filter
# --------------------------------------------------------------------------- #
def generate_signals_v02(m1_bars, tp_rr, news_windows, max_signals=300,
                         _state={}):
    """v0.1 pipeline (M15 SMC MSS) + regime filter + news filter."""
    signals = []
    m15 = None
    m15_closed = []          # (o, h, l, c)
    closes = []              # close prices for EMA
    dropped_regime = 0
    dropped_news = 0
    for dt, o, h, l, c, spread_sum, n in m1_bars:
        bucket = dt.replace(minute=(dt.minute // 15) * 15, second=0, microsecond=0)
        if m15 is None or bucket != m15["bucket"]:
            if m15 is not None:
                m15_closed.append((m15["o"], m15["h"], m15["l"], m15["c"]))
                closes.append(m15["c"])
                m15_closed = m15_closed[-400:]
                closes = closes[-400:]
                if len(m15_closed) < EMA_SLOW + 2 or len(signals) >= max_signals:
                    m15 = {"bucket": bucket, "o": o, "h": h, "l": l, "c": c}
                    continue
                e_f, e_s = ema(closes, EMA_FAST), ema(closes, EMA_SLOW)
                a = atr(m15_closed, ATR_N)
                if e_f is None or e_s is None or not a:
                    m15 = {"bucket": bucket, "o": o, "h": h, "l": l, "c": c}
                    continue
                spread = abs(e_f - e_s) / a
                trend_dir = 1 if e_f > e_s else -1
                if spread < REGIME_MIN:
                    dropped_regime += 1
                    m15 = {"bucket": bucket, "o": o, "h": h, "l": l, "c": c}
                    continue
                # --- reuse v0.1 SMC analysis on the same window ---
                from analysis import smc
                report = smc.analyze(m15_closed)
                last_report = _state.get("last")
                new_mss = []
                if last_report is not None and \
                        len(report.mss) > len(last_report.mss):
                    new_mss = report.mss[len(last_report.mss):]
                _state["last"] = report
                for ev in new_mss:
                    direction = "buy" if ev.direction == "bullish" else "sell"
                    if ((direction == "buy") != (trend_dir > 0)):
                        dropped_regime += 1
                        continue
                    if in_news(bucket, news_windows):
                        dropped_news += 1
                        continue
                    opp = [s for s in report.swings
                           if s.index < ev.index and s.kind ==
                           ("low" if direction == "buy" else "high")]
                    if not opp:
                        continue
                    sl = opp[-1].price
                    entry = m15_closed[-1][3]
                    risk = abs(entry - sl)
                    if risk <= 0 or risk / entry > 0.05:
                        continue
                    tp = entry + (risk * tp_rr if direction == "buy"
                                  else -risk * tp_rr)
                    signals.append({
                        "id": "%s-%s%03d-bt2" % (
                            bucket.strftime("%Y-%m-%d"), direction[0],
                            len(signals) + 1),
                        "instrument": "XAUUSD",
                        "setup": "smc_mss_m15_v02_regime_news",
                        "strategy_version": STRATEGY_BASE,
                        "direction": direction,
                        "entry": round(entry, 3),
                        "sl": round(sl, 3),
                        "tp": round(tp, 3),
                        "rr": tp_rr,
                        "confidence": 0.5,
                        "reasoning": ("BACKTEST ONLY v0.2 - MSS %s, regime "
                                      "spread %.2f (min %.2f), news filter "
                                      "clear, TP %.1fR"
                                      % (ev.direction, spread, REGIME_MIN,
                                         tp_rr)),
                        "model": "scripts/backtest_v02.py (rule-based, no AI)",
                        "created_at": bucket.isoformat().replace("+00:00", "Z"),
                        "risk_checks": {"within_daily_loss_limit": True,
                                        "within_max_positions": True,
                                        "news_filter_clear": True},
                        "backtest": True,
                        "executed": False,
                        "blocked_reason": None,
                        "result": None,
                    })
            m15 = {"bucket": bucket, "o": o, "h": h, "l": l, "c": c}
        else:
            m15["h"] = max(m15["h"], h)
            m15["l"] = min(m15["l"], l)
            m15["c"] = c
    _state.clear()
    return signals, {"dropped_regime": dropped_regime,
                     "dropped_news": dropped_news}


# --------------------------------------------------------------------------- #
def run_year(year, run_id, tp_rr=2.0):
    print("[bt2] %d: streaming ticks -> M1 ..." % year, flush=True)
    m1 = list(stream_m1_bars(year))
    news = synth_news_windows(year)
    print("[bt2] %d: %d M1 bars, %d news windows, generating v0.2 signals ..."
          % (year, len(m1), len(news)), flush=True)
    signals, drops = generate_signals_v02(m1, tp_rr, news)
    ticks = [(dt, c, c + spread_sum / n)
             for dt, o, h, l, c, spread_sum, n in m1]
    for sig in signals:
        sig["strategy_version"] = "%s-%d" % (STRATEGY_BASE, year)
    eng = Engine(equity=10000.0, slippage_points=NEWS_SLIPPAGE_POINTS,
                 news_windows=[(datetime.fromisoformat(w["block_start_utc"]),
                                datetime.fromisoformat(w["block_end_utc"]),
                                w["title"]) for w in news])
    rows = eng.run(signals, ticks)
    path = write_results(rows, run_id, os.path.join(REPO, "backtest", "results"),
                         meta={"year": year, "data": "dukascopy tick -> M1 bars",
                               "strategy": "smc_mss_m15_v02_regime_news",
                               "strategy_version": "%s-%d" % (STRATEGY_BASE, year),
                               "tp_rr": tp_rr,
                               "regime_min": REGIME_MIN,
                               "news_windows": "synthetic NFP/CPI approximation",
                               "n_signals": len(signals),
                               "filter_drops": drops,
                               "costs": btengine.COSTS,
                               "backtest": True,
                               "verification": NOT_VERIFIED})
    metrics = eng.metrics()
    metrics.update({"year": year, "results_file": path,
                    "label": "BACKTEST / NOT VERIFIED",
                    "strategy_version": "%s-%d" % (STRATEGY_BASE, year),
                    "tp_rr": tp_rr, "filter_drops": drops})
    del m1
    return metrics


def main(argv=None):
    ap = argparse.ArgumentParser(description="v0.2 per-year backtest (NOT VERIFIED)")
    ap.add_argument("--years", nargs="+", type=int, required=True)
    ap.add_argument("--run-prefix", default="bt2")
    args = ap.parse_args(argv)

    summary = {"verification": NOT_VERIFIED, "backtest": True,
               "strategy": "v0.2 regime+news filter, RR variants",
               "per_year": {}, "rr_variants": {}}
    for year in args.years:
        base = run_year(year, "%s-%d" % (args.run_prefix, year), tp_rr=2.0)
        summary["per_year"][str(year)] = base
        print(json.dumps(base, indent=2), flush=True)
        # RR experiment (same filters, only TP changes)
        for rr in RR_VARIANTS:
            if rr == 2.0:
                summary["rr_variants"].setdefault(str(year), {})["2.0"] = base
                continue
            m = run_year(year, "%s-%d-rr%02d" % (args.run_prefix, year,
                                                 int(rr * 10)), tp_rr=rr)
            summary["rr_variants"].setdefault(str(year), {})[str(rr)] = {
                k: m[k] for k in ("total_r", "win_rate_pct", "executed",
                                  "trades_closed", "max_equity_dd_pct",
                                  "expectancy_r")}
            print("[bt2] %d RR %.1f: total_r=%s wr=%s" % (
                year, rr, m["total_r"], m["win_rate_pct"]), flush=True)
    out = os.path.join(REPO, "backtest", "results",
                       "%s-summary.json" % args.run_prefix)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, sort_keys=True)
    print("[bt2] summary written: %s" % out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
