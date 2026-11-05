#!/usr/bin/env python3
"""S6-T2: Walk-forward optimization (WFO) engine for strategy v0.3.

Design source: docs/STRATEGY_V03.md (S6-T1) + task brief t_f4664db0.
Task brief scheme (primary): ROLLING window fit 2 years -> test 1 year,
roll every year, RR grid 1.5-3.0. With 2020-2025 data that gives 4 folds:

    fold 1: IS 2020-2021 -> OOS 2022
    fold 2: IS 2021-2022 -> OOS 2023
    fold 3: IS 2022-2023 -> OOS 2024
    fold 4: IS 2023-2024 -> OOS 2025

(The S6-T1 doc prefers 12M/3M anchored; the task brief's 24M/12M rolling
is implemented as specified and the deviation is documented in
docs/WALKFORWARD.md. Purge gap of 2 days is applied at every IS->OOS
boundary: signals created in the first PURGE_DAYS of the OOS year are
dropped, so no M15 indicator window straddles the boundary.)

Strategy: v0.2 baseline (SMC MSS M15 + EMA20/50-vs-ATR14 regime filter +
synthetic NFP/CPI news filter) via scripts/backtest_v02.py, executed on
backtest/engine.py with commission/swap/news-slippage costs.

Regime-filter candidates (each evaluated with the SAME walk-forward
protocol; signals generated once per variant per year, RR only changes TP):

  base      : v0.2 as-is (EMA spread regime filter)
  session   : base + killzone filter (entry only 07:00-10:00 / 12:00-15:00 UTC)
  atrpct    : base + ATR%(14) <= MA100(ATR%) volatility regime (normal/low vol)
  adx       : base + ADX(14) >= 25 trend-strength filter

Trials budget: 4 variants x 4 RR = 16 configurations (<= 50 per S6-T1),
all logged to backtest/results/bt4-trials.csv.

Robustness metrics reported per docs/STRATEGY_V03.md section 3:
  - per fold: IS best RR, IS grid, OOS result at chosen RR, degradation
    (OOS - IS) and ODR = OOS/IS (only meaningful when IS > 0)
  - stitched OOS (all folds concatenated), WFE = stitched OOS / aggregated IS
  - majority-pass: share of OOS segments with total_r > 0
  - plateau/cliff check on the RR grid: adjacent-grid results at the chosen
    parameter must not flip sign or degrade > 40%

Outputs (append-only, all BACKTEST / NOT VERIFIED):
  backtest/results/bt4-<year>-<variant>-rr<rr>.jsonl
  backtest/results/bt4-trials.csv
  backtest/results/bt4-walkforward.json

Engine tests must keep passing: python3 -m unittest backtest.test_engine

STATUS: BACKTEST / NOT VERIFIED. Never present as a real track record.
Stdlib only. Usage:
  python3 scripts/walkforward.py --years 2020 2021 2022 2023 2024 2025
"""

import argparse
import csv
import json
import os
import sys
from datetime import datetime, timedelta, timezone

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from backtest import engine as btengine                       # noqa: E402
from backtest.engine import Engine, write_results, NOT_VERIFIED  # noqa: E402
import scripts.backtest_v02 as v02                            # noqa: E402
from scripts.backtest_phase1 import stream_m1_bars, ticks_path  # noqa: E402

RUN_PREFIX = "bt4"
RR_GRID = (1.5, 2.0, 2.5, 3.0)
IS_YEARS = 2                     # rolling fit window (task brief: 2 years)
PURGE_DAYS = 2                   # purge gap at IS->OOS boundary
KILLZONE_HOURS = set(range(7, 10)) | set(range(12, 15))   # London + NY UTC
ADX_MIN = 25.0
ATRPCT_REL = 1.0                 # trade only when ATR% <= MA100(ATR%) * 1.0
VARIANTS = ("base", "session", "atrpct", "adx")
RESULTS_DIR = os.path.join(REPO, "backtest", "results")


# --------------------------------------------------------------------------- #
# M15 aggregation + indicator filters (once per year, reused by variants)
# --------------------------------------------------------------------------- #
def aggregate_m15(m1):
    """m1 bars -> list of (bucket_dt, o, h, l, c) M15 bars, sorted."""
    out = []
    cur = None
    for dt, o, h, l, c, _s, _n in m1:
        bucket = dt.replace(minute=(dt.minute // 15) * 15, second=0,
                            microsecond=0)
        if cur is None or bucket != cur[0]:
            if cur is not None:
                out.append(tuple(cur))
            cur = [bucket, o, h, l, c]
        else:
            cur[2] = max(cur[2], h)
            cur[3] = min(cur[3], l)
            cur[4] = c
    if cur is not None:
        out.append(tuple(cur))
    return out


def wilder_adx(m15, n=14):
    """ADX(n) per M15 bar index. Returns {bucket: adx} for buckets where
    enough bars exist (>= 2n). Standard Wilder smoothing."""
    adx = {}
    trs, pdms, mdms = [], [], []
    prev_h = prev_l = prev_c = None
    smooth_tr = smooth_pdm = smooth_mdm = None
    dxs = []
    dx_sum = 0.0
    adx_last = None
    for bucket, _o, h, l, c in m15:
        if prev_c is not None:
            tr = max(h - l, abs(h - prev_c), abs(l - prev_c))
            up, dn = h - prev_h, prev_l - l
            pdm = up if (up > dn and up > 0) else 0.0
            mdm = dn if (dn > up and dn > 0) else 0.0
            if smooth_tr is None:
                smooth_tr, smooth_pdm, smooth_mdm = tr, pdm, mdm
            else:
                smooth_tr = smooth_tr - smooth_tr / n + tr
                smooth_pdm = smooth_pdm - smooth_pdm / n + pdm
                smooth_mdm = smooth_mdm - smooth_mdm / n + mdm
            if smooth_tr > 0:
                pdi = 100.0 * smooth_pdm / smooth_tr
                mdi = 100.0 * smooth_mdm / smooth_tr
                denom = pdi + mdi
                dx = 100.0 * abs(pdi - mdi) / denom if denom > 0 else 0.0
                dxs.append(dx)
                if len(dxs) > n:
                    dx_sum = dx_sum - dxs.pop(0)   # keep last n DX values
                if len(dxs) == n:
                    if adx_last is None:
                        adx_last = dx_sum / n      # first ADX = mean of DX
                    else:
                        adx_last = (adx_last * (n - 1) + dx) / n
                    adx[bucket] = adx_last
        prev_h, prev_l, prev_c = h, l, c
    return adx


def atrpct_map(m15, n=14, ma=100):
    """ATR%(14) = ATR/close, and MA(ma) of the ATR% series itself.
    Returns {bucket: (atrpct, atrpct_ma)}."""
    out = {}
    trs = []
    prev_c = None
    series = []
    for bucket, _o, h, l, c in m15:
        if prev_c is not None:
            trs.append(max(h - l, abs(h - prev_c), abs(l - prev_c)))
            trs = trs[-200:]
            if len(trs) >= n:
                a = sum(trs[-n:]) / n
                p = a / c if c > 0 else None
                if p is not None:
                    series.append((bucket, p))
                    if len(series) >= ma:
                        m = sum(x[1] for x in series[-ma:]) / ma
                        out[bucket] = (p, m)
        prev_c = c
    return out


def variant_passes(sig, variant, adx, atrp):
    """Extra regime-filter check on top of the v0.2 baseline."""
    ts = datetime.fromisoformat(sig["created_at"].replace("Z", "+00:00"))
    bucket = ts.replace(minute=(ts.minute // 15) * 15, second=0, microsecond=0)
    if variant == "base":
        return True
    if variant == "session":
        return ts.hour in KILLZONE_HOURS
    if variant == "adx":
        v = adx.get(bucket)
        return v is not None and v >= ADX_MIN
    if variant == "atrpct":
        pair = atrp.get(bucket)
        if pair is None:
            return False
        p, m = pair
        return m > 0 and p <= m * ATRPCT_REL
    raise ValueError(variant)


def signals_for_variant(year, m1, news, variant):
    """v0.2 signal generation at rr=2.0 + the variant's extra filter.
    RR is applied later by re-deriving TP (risk = |entry - sl| is fixed)."""
    sigs, drops = v02.generate_signals_v02(m1, 2.0, news)
    if variant == "base":
        return sigs, drops
    m15 = aggregate_m15(m1)
    adx = wilder_adx(m15) if variant == "adx" else {}
    atrp = atrpct_map(m15) if variant == "atrpct" else {}
    kept = [s for s in sigs if variant_passes(s, variant, adx, atrp)]
    drops = dict(drops)
    drops["dropped_%s" % variant] = len(sigs) - len(kept)
    return kept, drops


def apply_rr(sig, rr, year, variant):
    """Re-derive TP at a different RR; everything else identical."""
    s = dict(sig)
    entry, sl = s["entry"], s["sl"]
    risk = abs(entry - sl)
    if s["direction"] == "buy":
        s["tp"] = round(entry + risk * rr, 3)
    else:
        s["tp"] = round(entry - risk * rr, 3)
    s["rr"] = rr
    s["id"] = "%d-%s-rr%02d-%s" % (year, variant, int(rr * 10), sig["id"])
    s["strategy_version"] = "0.3-wf-%s-rr%02d-%d" % (variant, int(rr * 10),
                                                     year)
    s["setup"] = "smc_mss_m15_v03_wf_%s" % variant
    s["reasoning"] = ("BACKTEST ONLY v0.3 WFO - %s variant, RR %.1f, IS-best "
                      "parameter applied OOS" % (variant, rr))
    return s


# --------------------------------------------------------------------------- #
# One engine run over one year (mirrors v02.run_year, parametrised)
# --------------------------------------------------------------------------- #
def run_year(year, m1, signals, run_id, extra_meta):
    ticks = [(dt, c, c + spread_sum / n)
             for dt, o, h, l, c, spread_sum, n in m1]
    news = v02.synth_news_windows(year)
    eng = Engine(equity=10000.0, slippage_points=v02.NEWS_SLIPPAGE_POINTS,
                 news_windows=[(datetime.fromisoformat(w["block_start_utc"]),
                                datetime.fromisoformat(w["block_end_utc"]),
                                w["title"]) for w in news])
    rows = eng.run(signals, ticks)
    path = write_results(rows, run_id, RESULTS_DIR,
                         meta=dict({"year": year,
                                    "data": "dukascopy tick -> M1 bars",
                                    "strategy": "smc_mss_m15_v03_walkforward",
                                    "strategy_version": run_id,
                                    "costs": btengine.COSTS,
                                    "n_signals": len(signals),
                                    "backtest": True,
                                    "verification": NOT_VERIFIED},
                                   **extra_meta))
    met = eng.metrics()
    met.update({"year": year, "results_file": path,
                "label": "BACKTEST / NOT VERIFIED", "run_id": run_id})
    met.update(extra_meta)
    return met


def purge(signals, year):
    """Drop signals created within the first PURGE_DAYS of the OOS year."""
    lo = datetime(year, 1, 1, tzinfo=timezone.utc)
    hi = lo + timedelta(days=PURGE_DAYS)
    kept = []
    for s in signals:
        ts = datetime.fromisoformat(s["created_at"].replace("Z", "+00:00"))
        if ts < hi:
            continue
        kept.append(s)
    return kept


# --------------------------------------------------------------------------- #
# Walk-forward driver
# --------------------------------------------------------------------------- #
def load_year(year):
    print("[bt4] %d: streaming ticks -> M1 ..." % year, flush=True)
    return list(stream_m1_bars(year))


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="v0.3 walk-forward optimization (NOT VERIFIED)")
    ap.add_argument("--years", nargs="+", type=int,
                    default=[2020, 2021, 2022, 2023, 2024, 2025])
    args = ap.parse_args(argv)
    years = sorted(args.years)

    # cache per-year: m1 bars, news windows, signals per variant
    cache = {}
    for y in years:
        m1 = load_year(y)
        news = v02.synth_news_windows(y)
        var_sigs = {}
        for variant in VARIANTS:
            sigs, drops = signals_for_variant(y, m1, news, variant)
            var_sigs[variant] = (sigs, drops)
            print("[bt4] %d %s: %d signals (%s)" % (
                y, variant, len(sigs), drops), flush=True)
        cache[y] = {"m1": m1, "news": news, "sigs": var_sigs}
        del m1

    folds = []
    i = IS_YEARS
    while i < len(years):
        folds.append((years[i - IS_YEARS:i], years[i]))
        i += 1

    trials = []
    fold_rows = []
    is_best = {}                       # (variant) -> [(is_years, rr, total_r)]
    for is_years, oos_year in folds:
        fold_id = "f%d-%d-%d" % (folds.index((is_years, oos_year)) + 1,
                                 is_years[0], oos_year)
        print("[bt4] FOLD %s: IS %s -> OOS %d" % (
            fold_id, is_years, oos_year), flush=True)
        for variant in VARIANTS:
            # ---- IS: evaluate the RR grid, pick best ----
            grid = {}
            for y in is_years:
                sigs0, _drops = cache[y]["sigs"][variant]
                for rr in RR_GRID:
                    sigs = [apply_rr(s, rr, y, variant) for s in sigs0]
                    run_id = "%s-is-%s-%d-rr%02d" % (
                        RUN_PREFIX, variant, y, int(rr * 10))
                    met = run_year(y, cache[y]["m1"], sigs, run_id,
                                   {"fold": fold_id, "phase": "is",
                                    "variant": variant, "rr": rr})
                    grid.setdefault(rr, []).append(met)
                    trials.append({"fold": fold_id, "phase": "is",
                                   "variant": variant, "rr": rr, "year": y,
                                   "total_r": met["total_r"],
                                   "trades": met["trades_closed"]})
            agg = {}
            for rr, ms in grid.items():
                agg[rr] = {
                    "total_r": round(sum(m["total_r"] for m in ms), 4),
                    "trades": sum(m["trades_closed"] for m in ms),
                    "win_rate_pct": round(
                        sum((m["win_rate_pct"] or 0) * m["trades_closed"]
                            for m in ms) / max(1, sum(m["trades_closed"]
                                                      for m in ms)), 2),
                    "per_year": {str(m["year"]): m["total_r"] for m in ms}}
            best_rr = max(agg, key=lambda r: agg[r]["total_r"])
            best = agg[best_rr]

            # plateau / cliff check on the IS 1-D RR grid at best_rr
            nb = []
            idx = RR_GRID.index(best_rr)
            for j in (idx - 1, idx + 1):
                if 0 <= j < len(RR_GRID):
                    nb.append(RR_GRID[j])
            neighbours = {str(r): agg[r]["total_r"] for r in nb}
            cliff = any((agg[r]["total_r"] <= 0) or
                        (best["total_r"] > 0 and
                         agg[r]["total_r"] < 0.6 * best["total_r"])
                        for r in nb)

            # ---- OOS: apply best RR unchanged ----
            sigs0, _d = cache[oos_year]["sigs"][variant]
            sigs = purge([apply_rr(s, best_rr, oos_year, variant)
                          for s in sigs0], oos_year)
            run_id = "%s-oos-%s-%d-rr%02d" % (
                RUN_PREFIX, variant, oos_year, int(best_rr * 10))
            oos = run_year(oos_year, cache[oos_year]["m1"], sigs, run_id,
                           {"fold": fold_id, "phase": "oos",
                            "variant": variant, "rr": best_rr,
                            "purged_signals": len(sigs0) - len(sigs)})
            trials.append({"fold": fold_id, "phase": "oos", "variant": variant,
                           "rr": best_rr, "year": oos_year,
                           "total_r": oos["total_r"],
                           "trades": oos["trades_closed"]})
            deg = round(oos["total_r"] - best["total_r"], 4)
            odr = (round(oos["total_r"] / best["total_r"], 3)
                   if best["total_r"] > 0 else None)
            fold_rows.append({
                "fold": fold_id, "variant": variant,
                "is_years": is_years, "oos_year": oos_year,
                "is_grid": {str(r): agg[r]["total_r"] for r in RR_GRID},
                "is_best_rr": best_rr, "is_total_r": best["total_r"],
                "is_trades": best["trades"],
                "is_neighbours": neighbours,
                "cliff_at_best": cliff,
                "oos_total_r": oos["total_r"],
                "oos_trades": oos["trades_closed"],
                "oos_win_rate_pct": oos["win_rate_pct"],
                "oos_max_dd_pct": oos["max_equity_dd_pct"],
                "degradation_r": deg,
                "odr": odr,
                "purged_signals": len(sigs0) - len(sigs),
            })
            print("[bt4] %s %s: best RR %.1f (IS %+.2fR) -> OOS %+.2fR "
                  "(deg %+.2f, ODR %s, cliff=%s)" % (
                      fold_id, variant, best_rr, best["total_r"],
                      oos["total_r"], deg, odr, cliff), flush=True)
        del cache[is_years[0]]        # free the year leaving the IS window

    # ---- aggregate robustness per variant ----
    summary = {"verification": NOT_VERIFIED, "backtest": True,
               "method": "rolling WFO: IS 2y -> OOS 1y, roll 1y, "
                         "RR grid %s, purge %dd" % (list(RR_GRID), PURGE_DAYS),
               "strategy": "v0.3 walk-forward over v0.2 signal generator",
               "variants": {}}
    for variant in VARIANTS:
        rows = [r for r in fold_rows if r["variant"] == variant]
        is_sum = sum(r["is_total_r"] for r in rows)
        oos_sum = sum(r["oos_total_r"] for r in rows)
        pos = sum(1 for r in rows if r["oos_total_r"] > 0)
        wfe = round(oos_sum / is_sum, 3) if is_sum > 0 else None
        odrs = [r["odr"] for r in rows if r["odr"] is not None]
        summary["variants"][variant] = {
            "folds": rows,
            "is_aggregate_r": round(is_sum, 4),
            "oos_stitched_r": round(oos_sum, 4),
            "wfe": wfe,
            "odr_folds": odrs,
            "oos_positive_segments": "%d/%d" % (pos, len(rows)),
            "cliffs": sum(1 for r in rows if r["cliff_at_best"]),
            "best_rr_sequence": [r["is_best_rr"] for r in rows],
            "label": "BACKTEST / NOT VERIFIED",
        }

    os.makedirs(RESULTS_DIR, exist_ok=True)
    out = os.path.join(RESULTS_DIR, "%s-walkforward.json" % RUN_PREFIX)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, sort_keys=True)
    tpath = os.path.join(RESULTS_DIR, "%s-trials.csv" % RUN_PREFIX)
    with open(tpath, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["fold", "phase", "variant", "rr",
                                          "year", "total_r", "trades"])
        w.writeheader()
        for t in trials:
            w.writerow(t)
    n_trials = len(trials)
    print("[bt4] trials logged: %d (budget <= 50 per S6-T1)" % n_trials)
    print("[bt4] summary written: %s" % out)
    for variant in VARIANTS:
        v = summary["variants"][variant]
        print("[bt4] %-8s stitched OOS %+8.2fR  WFE %s  positive %s  "
              "cliffs %d  RR seq %s" % (
                  variant, v["oos_stitched_r"], v["wfe"],
                  v["oos_positive_segments"], v["cliffs"],
                  v["best_rr_sequence"]), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
