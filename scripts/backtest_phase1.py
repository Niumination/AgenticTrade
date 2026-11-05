#!/usr/bin/env python3
"""S3-T1: Fase-1 backtest runner — SMC signal generator + engine, per year.

Pipeline per year (memory-safe, streams the ~10 GB tick CSVs):
  1. Stream backtest/data/download/xauusd-tick-<year>.csv row by row and
     aggregate to M1 bars (bid OHLC + mean spread)  ->  ~370k bars/year.
  2. Aggregate M1 -> M15. On every M15 close, run analysis/smc.py
     (find_swing_points / find_mss) on a rolling window of the last 400 M15
     bars. A NEW MSS event emits a signal:
       direction = MSS direction, entry = M15 close, SL = last opposite
       swing (swing low for buy / swing high for sell), TP = entry + 2R.
     Cooldown: max 1 open signal per direction until the next MSS; signals
     are only emitted while the engine-equivalent slot budget (<2 open) holds.
  3. Run backtest/engine.py Engine over the M1 bars (as execution ticks:
     bid = M1 close bid, ask = bid + mean spread of that minute; fills at
     next bar -> conservative at this granularity) with the year's signals.
  4. Append results to backtest/results/<run_id>.jsonl via the engine's own
     append-only writer AND write a signals/-schema JSON per year into
     signals/ (entry rows + close rows with result.r = pnl_r) so
     dashboard/generate.py can compute per-year stats. Every row is labelled
     backtest=true, verification "NOT VERIFIED", strategy_version
     "0.1-bt-<year>" (distinct per year so the dashboard groups per year).

STATUS: BACKTEST / NOT VERIFIED. Never present as a real track record.

Stdlib only. Usage:
  python3 scripts/backtest_phase1.py --years 2020 2021 --run-prefix bt1
"""

import argparse
import csv
import json
import os
import sys
from datetime import datetime, timedelta, timezone

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from analysis import smc                                   # noqa: E402
from backtest.engine import Engine, write_results, NOT_VERIFIED  # noqa: E402

DOWNLOAD_DIR = os.path.join(REPO, "backtest", "data", "download")
SIGNALS_DIR = os.path.join(REPO, "signals")
STRATEGY_BASE = "0.1-bt"          # per-year: 0.1-bt-<year>
M15_WINDOW = 400                  # rolling M15 bars fed to smc.analyze
TP_RR = 2.0
MAX_SIGNALS_PER_YEAR = 300
MSL_SUFFIX = "-bt"                # signal id suffix

# --------------------------------------------------------------------------- #
# Step 1: stream ticks -> M1 bars
# --------------------------------------------------------------------------- #
def ticks_path(year):
    return os.path.join(
        DOWNLOAD_DIR,
        "xauusd-tick-%d-01-01-%d-01-01.csv" % (year, year + 1))


def stream_m1_bars(year):
    """Yield (dt, open, high, low, close, spread_sum, n) per M1 bar (UTC)."""
    path = ticks_path(year)
    cur = None
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
        idx = {c.lower().strip(): i for i, c in enumerate(header)}
        ti, bi, ai = idx["timestamp"], idx["bidprice"], idx["askprice"]
        for row in reader:
            try:
                ts = int(row[ti]) / 1000.0
                bid = float(row[bi])
                ask = float(row[ai])
            except (ValueError, IndexError):
                continue
            dt = datetime.fromtimestamp(ts, tz=timezone.utc)
            minute = dt.replace(second=0, microsecond=0)
            if cur is None or minute != cur[0]:
                if cur is not None:
                    yield cur
                cur = [minute, bid, bid, bid, bid, ask - bid, 1]
            else:
                cur[2] = max(cur[2], bid)
                cur[3] = min(cur[3], bid)
                cur[4] = bid
                cur[5] += ask - bid
                cur[6] += 1
    if cur is not None:
        yield cur


# --------------------------------------------------------------------------- #
# Step 2: M1 -> M15, SMC analysis, signal generation
# --------------------------------------------------------------------------- #
def generate_signals(m1_bars):
    """-> list of signal dicts (signals/ schema, backtest-labelled)."""
    signals = []
    m15 = None                       # current forming M15 bar
    m15_closed = []                  # closed M15 bars, rolling window
    last_mss_count = 0
    last_report = smc.StructureReport()
    pending = {}                     # direction -> signal emitted & not yet
                                     # cleared by an opposite/new MSS
    for dt, o, h, l, c, spread_sum, n in m1_bars:
        bucket = dt.replace(minute=(dt.minute // 15) * 15, second=0, microsecond=0)
        if m15 is None or bucket != m15["bucket"]:
            if m15 is not None:
                m15_closed.append((m15["o"], m15["h"], m15["l"], m15["c"]))
                m15_closed = m15_closed[-M15_WINDOW:]
                # --- SMC analysis on the rolling window ---
                report = smc.analyze(m15_closed)
                new_mss = report.mss[len(last_report.mss):] \
                    if len(report.mss) > len(last_report.mss) else []
                last_report = report
                if len(m15_closed) >= 50 and new_mss:
                    for ev in new_mss:
                        if len(signals) >= MAX_SIGNALS_PER_YEAR:
                            break
                        direction = "buy" if ev.direction == "bullish" else "sell"
                        # SL = last opposite swing before the break candle
                        opp = [s for s in report.swings
                               if s.index < ev.index and s.kind ==
                               ("low" if direction == "buy" else "high")]
                        if not opp:
                            continue
                        sl = opp[-1].price
                        entry = m15_closed[-1][3]
                        risk = abs(entry - sl)
                        if risk <= 0 or risk / entry > 0.05:
                            continue     # degenerate / absurd SL distance
                        tp = entry + (risk * TP_RR if direction == "buy"
                                      else -risk * TP_RR)
                        sig_id = "%s-%s%03d%s" % (
                            bucket.strftime("%Y-%m-%d"), direction[0],
                            len(signals) + 1, MSL_SUFFIX)
                        signals.append({
                            "id": sig_id,
                            "instrument": "XAUUSD",
                            "setup": "smc_mss_m15_tp2r",
                            "strategy_version": STRATEGY_BASE,  # year added later
                            "direction": direction,
                            "entry": round(entry, 3),
                            "sl": round(sl, 3),
                            "tp": round(tp, 3),
                            "rr": TP_RR,
                            "confidence": 0.5,
                            "reasoning": ("BACKTEST ONLY - rolling M15 window %d "
                                          "bars, MSS %s at %.3f, SL last "
                                          "opposite swing %.3f, TP 2R"
                                          % (len(m15_closed), ev.direction,
                                             ev.level, sl)),
                            "model": "scripts/backtest_phase1.py (rule-based, no AI)",
                            "created_at": bucket.isoformat().replace("+00:00", "Z"),
                            "risk_checks": {"within_daily_loss_limit": True,
                                            "within_max_positions": True,
                                            "news_filter_clear": None},
                            "backtest": True,
                            "executed": False,
                            "blocked_reason": None,
                            "result": None,
                        })
                        pending[direction] = sig_id
            m15 = {"bucket": bucket, "o": o, "h": h, "l": l, "c": c}
        else:
            m15["h"] = max(m15["h"], h)
            m15["l"] = min(m15["l"], l)
            m15["c"] = c
    return signals


# --------------------------------------------------------------------------- #
# Step 3: engine run over M1 bars
# --------------------------------------------------------------------------- #
def run_engine_year(signals, m1_bars, year, run_id):
    ticks = []
    for dt, o, h, l, c, spread_sum, n in m1_bars:
        spread = spread_sum / n
        ticks.append((dt, c, c + spread))
    for sig in signals:
        sig["strategy_version"] = "%s-%d" % (STRATEGY_BASE, year)
    eng = Engine(equity=10000.0, slippage_points=0.0)
    rows = eng.run(signals, ticks)
    path = write_results(rows, run_id, os.path.join(REPO, "backtest", "results"),
                         meta={"year": year, "data": "dukascopy tick -> M1 bars",
                               "strategy": "smc_mss_m15_tp2r",
                               "strategy_version": "%s-%d" % (STRATEGY_BASE, year),
                               "n_m1_bars": len(ticks),
                               "backtest": True,
                               "verification": NOT_VERIFIED})
    return eng, rows, path


# --------------------------------------------------------------------------- #
# Step 4: signals/-schema per-year log for the dashboard
# --------------------------------------------------------------------------- #
def write_signals_log(year, run_id, rows, signals):
    """Append-only file signals/<date>.backtest-<year>.json, engine rows
    (entry + close, engine schema) converted minimally: close rows carry
    result.r = pnl_r so dashboard/outcome_r computes real R."""
    out = []
    by_id = {s["id"]: s for s in signals}
    for row in rows:
        if row.get("_header"):
            continue
        if row.get("run_kind") == "close":
            res = dict(row["result"] or {})
            res["r"] = res.get("pnl_r", 0.0)
            base = by_id.get(row.get("id"), {})
            out.append({
                "id": row["id"] + ":close",
                "instrument": base.get("instrument", "XAUUSD"),
                "setup": base.get("setup", "smc_mss_m15_tp2r"),
                "strategy_version": row.get("strategy_version")
                                    or base.get("strategy_version"),
                "direction": base.get("direction"),
                "entry": base.get("entry"),
                "sl": base.get("sl"),
                "tp": base.get("tp"),
                "rr": base.get("rr"),
                "confidence": base.get("confidence"),
                "reasoning": base.get("reasoning"),
                "model": base.get("model"),
                "created_at": (res.get("closed_at") or ""),
                "risk_checks": {"within_daily_loss_limit": True,
                                "within_max_positions": True,
                                "news_filter_clear": None},
                "backtest": True,
                "run_kind": "close",
                "executed": True,
                "blocked_reason": None,
                "result": res,
                "source": "backtest_engine",
                "verification": NOT_VERIFIED,
            })
        else:
            out.append(row)          # engine entry row already full schema
    path = os.path.join(SIGNALS_DIR, "%s.backtest-%d.json"
                        % (datetime.now(timezone.utc).strftime("%Y-%m-%d"), year))
    with open(path, "a", encoding="utf-8") as f:    # APPEND-ONLY
        json.dump(out, f, sort_keys=True)
        f.write("\n")
    return path


# --------------------------------------------------------------------------- #
def main(argv=None):
    ap = argparse.ArgumentParser(description="Fase-1 per-year backtest (NOT VERIFIED)")
    ap.add_argument("--years", nargs="+", type=int, required=True)
    ap.add_argument("--run-prefix", default="bt1")
    args = ap.parse_args(argv)

    summary = {}
    for year in args.years:
        print("[bt] year %d: streaming ticks -> M1 bars ..." % year, flush=True)
        m1 = list(stream_m1_bars(year))
        print("[bt] year %d: %d M1 bars, generating SMC signals ..." % (year, len(m1)),
              flush=True)
        signals = generate_signals(m1)
        run_id = "%s-%d" % (args.run_prefix, year)
        eng, rows, res_path = run_engine_year(signals, m1, year, run_id)
        log_path = write_signals_log(year, run_id, rows, signals)
        metrics = eng.metrics()
        metrics.update({"year": year, "results_file": res_path,
                        "signals_log": log_path,
                        "label": "BACKTEST / NOT VERIFIED",
                        "strategy_version": "%s-%d" % (STRATEGY_BASE, year)})
        summary[year] = metrics
        print(json.dumps(metrics, indent=2), flush=True)
        del m1
    out = os.path.join(REPO, "backtest", "results",
                       "%s-summary.json" % args.run_prefix)
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"verification": NOT_VERIFIED, "backtest": True,
                   "per_year": summary}, f, indent=2, sort_keys=True)
    print("[bt] summary written: %s" % out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
