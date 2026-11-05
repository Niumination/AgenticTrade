#!/usr/bin/env python3
"""S6-T2: render the fold tables for docs/WALKFORWARD.md from
backtest/results/bt4-walkforward.json.

Only prints markdown to stdout so a human can paste it (or the developer
redirects it) into the doc — the doc's prose is written by hand, numbers are
never retyped. Every table carries the BACKTEST / NOT VERIFIED label.

Usage:
  python3 scripts/walkforward_tables.py [--json backtest/results/bt4-walkforward.json]
"""

import argparse
import json

VARIANT_ORDER = ["base", "session", "atrpct", "adx"]
VARIANT_LABEL = {
    "base": "base (v0.2 regime)",
    "session": "+ session killzone",
    "atrpct": "+ ATR% vol regime",
    "adx": "+ ADX(14)>=25",
}


def fmt(v, sign=True):
    if v is None:
        return "n/a"
    return ("%+.2f" % v) if sign else ("%.2f" % v)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default="backtest/results/bt4-walkforward.json")
    args = ap.parse_args(argv)
    with open(args.json, encoding="utf-8") as f:
        data = json.load(f)
    print("STATUS: BACKTEST / NOT VERIFIED\n")

    # ---- table 1: per fold, per variant ----
    print("### Tabel fold (IS best RR -> OOS)\n")
    print("| Fold | IS | OOS | Varian | IS grid 1.5/2.0/2.5/3.0 (R) | "
          "Best RR | IS best (R) | OOS @best RR (R) | Degradasi (R) | ODR | "
          "OOS trades | OOS WR% | Cliff |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for variant in VARIANT_ORDER:
        folds = data["variants"][variant]["folds"]
        for fr in folds:
            g = fr["is_grid"]
            grid = "/".join(fmt(g[k]) for k in ("1.5", "2.0", "2.5", "3.0"))
            print("| %s | %s | %d | %s | %s | %.1f | %s | %s | %s | %s | "
                  "%d | %s | %s |" % (
                      fr["fold"], "-".join(str(y) for y in fr["is_years"]),
                      fr["oos_year"], VARIANT_LABEL[variant], grid,
                      fr["is_best_rr"], fmt(fr["is_total_r"]),
                      fmt(fr["oos_total_r"]), fmt(fr["degradation_r"]),
                      fmt(fr["odr"], sign=False), fr["oos_trades"],
                      fmt(fr["oos_win_rate_pct"], sign=False),
                      "YA" if fr["cliff_at_best"] else "tidak"))

    # ---- table 2: aggregate robustness per variant ----
    print("\n### Tabel agregat robustness\n")
    print("| Varian | IS agregat (R) | OOS stitched (R) | WFE (OOS/IS) | "
          "Segmen OOS positif | Cliff count | Urutan RR terpilih |")
    print("|---|---|---|---|---|---|---|")
    for variant in VARIANT_ORDER:
        v = data["variants"][variant]
        print("| %s | %s | %s | %s | %s | %d | %s |" % (
            VARIANT_LABEL[variant], fmt(v["is_aggregate_r"]),
            fmt(v["oos_stitched_r"]), fmt(v["wfe"], sign=False),
            v["oos_positive_segments"], v["cliffs"],
            ", ".join("%.1f" % r for r in v["best_rr_sequence"])))
    print("\nSemua angka: BACKTEST / NOT VERIFIED — bukan track record.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
