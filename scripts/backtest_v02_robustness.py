#!/usr/bin/env python3
"""S5-T3: Backtest v0.2 robustness — OOS split + parameter sensitivity.

All output BACKTEST / NOT VERIFIED. Stdlib only.

Experiments (RR 2.0 unless stated):
  A. OOS split (no rerun needed — the strategy is rule-based with no fitted
     coefficients; the only "fit" is the parameter choice, so IS/OOS is
     evaluated on the RR-variant grid from bt2-summary.json):
       - IS 2020-2022 -> pick best RR -> test on 2023-2025
       - IS 2023-2025 -> pick best RR -> test on 2020-2022
  B. EMA regime filter shift: EMA20/50 -> 15/45 and 25/55 (signal regeneration).
  C. Slippage: 1.0 pts base -> 0.5 / 1.5 (+50%/-50%).
  D. Commission: 7.0 USD/lot round-turn -> 3.5 / 10.5 (+50%/-50%).

Per year the tick CSV is streamed to M1 ONCE; all variants of that year reuse
the same in-memory bars. Engine-only variants (C, D) reuse the base signals.

Outputs:
  backtest/results/bt3-<year>.jsonl        (append-only per-run logs)
  backtest/results/bt3-robustness.json     (all experiment tables)

Usage:
  python3 scripts/backtest_v02_robustness.py --years 2020 2021 2022 2023 2024 2025
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from backtest import engine as btengine                       # noqa: E402
from backtest.engine import Engine, write_results, NOT_VERIFIED  # noqa: E402
import scripts.backtest_v02 as v02                            # noqa: E402
from scripts.backtest_phase1 import stream_m1_bars            # noqa: E402

RUN_PREFIX = "bt3"
BASE_SLIPPAGE = v02.NEWS_SLIPPAGE_POINTS      # 1.0 pts
BASE_COMMISSION = btengine.COSTS["commission_per_lot_roundturn_usd"]  # 7.0

EMA_VARIANTS = [  # (label, ema_fast, ema_slow)
    ("ema20-50", 20, 50),
    ("ema15-45", 15, 45),
    ("ema25-55", 25, 55),
]
SLIP_VARIANTS = [("slip0.5", 0.5), ("slip1.0", 1.0), ("slip1.5", 1.5)]
COMM_VARIANTS = [("comm3.5", 3.5), ("comm7.0", 7.0), ("comm10.5", 10.5)]


def _ews(m1, ema_fast, ema_slow, tp_rr, news, label, year):
    """Generate v0.2 signals with explicit EMA periods (module constants)."""
    old_f, old_s = v02.EMA_FAST, v02.EMA_SLOW
    v02.EMA_FAST, v02.EMA_SLOW = ema_fast, ema_slow
    try:
        signals, drops = v02.generate_signals_v02(m1, tp_rr, news)
    finally:
        v02.EMA_FAST, v02.EMA_SLOW = old_f, old_s
    for sig in signals:
        sig["strategy_version"] = "0.2-bt-rob-%s-%d" % (label, year)
        sig["setup"] = "smc_mss_m15_v02_%s" % label
    return signals, drops


def run_variant(year, label, signals, ticks, news, slippage, commission,
                run_id):
    costs = dict(btengine.COSTS)
    costs["commission_per_lot_roundturn_usd"] = commission
    eng = Engine(equity=10000.0, slippage_points=slippage,
                 news_windows=[(datetime.fromisoformat(w["block_start_utc"]),
                                datetime.fromisoformat(w["block_end_utc"]),
                                w["title"]) for w in news],
                 costs=costs)
    eng.run(signals, ticks)
    m = eng.metrics()
    write_results(eng.rows, run_id,
                  os.path.join(REPO, "backtest", "results"),
                  meta={"year": year, "experiment": label,
                        "strategy": "smc_mss_m15_v02_regime_news",
                        "tp_rr": 2.0, "regime_min": v02.REGIME_MIN,
                        "slippage_points": slippage,
                        "commission_per_lot_roundturn_usd": commission,
                        "news_windows": "synthetic NFP/CPI approximation",
                        "n_signals": len(signals),
                        "costs": costs, "backtest": True,
                        "verification": NOT_VERIFIED})
    return m


def compact(m):
    keys = ("total_r", "win_rate_pct", "trades_closed", "executed",
            "expectancy_r", "max_equity_dd_pct", "max_consecutive_losses",
            "final_equity")
    return {k: m[k] for k in keys}


def run_year(year, results):
    print("[bt3] %d: streaming ticks -> M1 (once for all variants) ..."
          % year, flush=True)
    m1 = list(stream_m1_bars(year))
    news = v02.synth_news_windows(year)
    ticks = [(dt, c, c + spread_sum / n)
             for dt, o, h, l, c, spread_sum, n in m1]
    yres = {"year": year, "verification": NOT_VERIFIED,
            "ema_variants": {}, "slippage": {}, "commission": {}}

    # --- B: EMA variants (signal regeneration; base costs) ---
    base_signals = None
    for label, ef, es in EMA_VARIANTS:
        print("[bt3] %d: EMA %d/%d generating signals ..." % (year, ef, es),
              flush=True)
        signals, drops = _ews(m1, ef, es, 2.0, news, label, year)
        rid = "%s-%d-%s" % (RUN_PREFIX, year, label)
        m = run_variant(year, label, signals, ticks, news, BASE_SLIPPAGE,
                        BASE_COMMISSION, rid)
        m["filter_drops"] = drops
        yres["ema_variants"][label] = compact(m)
        print("[bt3] %d %s: total_r=%s wr=%s n=%d" % (
            year, label, m["total_r"], m["win_rate_pct"], m["trades_closed"]),
            flush=True)
        if label == "ema20-50":
            base_signals = signals

    # --- C/D: cost sensitivity on base EMA20/50 signals ---
    for label, slip in SLIP_VARIANTS:
        rid = "%s-%d-%s" % (RUN_PREFIX, year, label)
        m = run_variant(year, label, base_signals, ticks, news, slip,
                        BASE_COMMISSION, rid)
        yres["slippage"][label] = compact(m)
        print("[bt3] %d %s: total_r=%s" % (year, label, m["total_r"]),
              flush=True)
    for label, comm in COMM_VARIANTS:
        rid = "%s-%d-%s" % (RUN_PREFIX, year, label)
        m = run_variant(year, label, base_signals, ticks, news,
                        BASE_SLIPPAGE, comm, rid)
        yres["commission"][label] = compact(m)
        print("[bt3] %d %s: total_r=%s" % (year, label, m["total_r"]),
              flush=True)

    results[str(year)] = yres
    del m1, ticks, base_signals
    return yres


def oos_split():
    """Experiment A from the existing RR-variant grid (bt2-summary.json)."""
    with open(os.path.join(REPO, "backtest", "results",
                           "bt2-summary.json"), encoding="utf-8") as f:
        s = json.load(f)
    grid = {rr: sum(v[str(rr)]["total_r"] for v in s["rr_variants"].values())
            for rr in ("1.5", "2.0", "2.5")}
    per = {rr: {y: v[str(rr)]["total_r"]
                for y, v in s["rr_variants"].items()}
           for rr in grid}
    experiments = []
    for is_years, oos_years in ((("2020", "2021", "2022"),
                                 ("2023", "2024", "2025")),
                                (("2023", "2024", "2025"),
                                 ("2020", "2021", "2022"))):
        best_rr = max(grid, key=lambda rr: sum(per[rr][y] for y in is_years))
        exp = {
            "is_years": list(is_years), "oos_years": list(oos_years),
            "chosen_rr": float(best_rr),
            "is_total_r": round(sum(per[best_rr][y] for y in is_years), 4),
            "is_per_year": {y: per[best_rr][y] for y in is_years},
            "oos_total_r": round(sum(per[best_rr][y] for y in oos_years), 4),
            "oos_per_year": {y: per[best_rr][y] for y in oos_years},
            "degradation_r": round(sum(per[best_rr][y] for y in oos_years)
                                   - sum(per[best_rr][y] for y in is_years), 4),
            "verification": NOT_VERIFIED,
        }
        experiments.append(exp)
    return {"method": "RR-grid parameter selection (the only fitted choice "
                      "in the rule-based v0.2); IS = pick best total_r, "
                      "OOS = apply unchanged", "experiments": experiments,
            "rr_grid_totals": {k: round(v, 4) for k, v in grid.items()}}


def main(argv=None):
    ap = argparse.ArgumentParser(description="v0.2 robustness (NOT VERIFIED)")
    ap.add_argument("--years", nargs="+", type=int,
                    default=[2020, 2021, 2022, 2023, 2024, 2025])
    args = ap.parse_args(argv)
    out_path = os.path.join(REPO, "backtest", "results",
                            "%s-robustness.json" % RUN_PREFIX)
    results = {}
    if os.path.exists(out_path):           # resume support
        with open(out_path, encoding="utf-8") as f:
            prev = json.load(f)
        results = prev.get("experiments", {}).get("ema_shift", {})
    for year in args.years:
        if str(year) in results:
            print("[bt3] %d already done, skipping" % year, flush=True)
            continue
        run_year(year, results)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump({"verification": NOT_VERIFIED, "backtest": True,
                       "experiments": {
                           "oos_split": oos_split(),
                           "ema_shift": results,
                           "notes": ["EMA shift changes signal generation "
                                     "(regime filter + EMA slope agreement)",
                                     "slippage/commission shift engine-only, "
                                     "same EMA20/50 RR2.0 signals",
                                     "news slippage multiplier 3x applies "
                                     "on top of base slippage"]}},
                      f, indent=2, sort_keys=True)
        print("[bt3] checkpoint written: %s" % out_path, flush=True)
    print("[bt3] done -> %s" % out_path, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
