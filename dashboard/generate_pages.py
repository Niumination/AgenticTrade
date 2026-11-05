#!/usr/bin/env python3
"""Static tear-sheet for GitHub Pages, regenerated from backtest/results/bt1-*.jsonl.

Reads the per-run header line of each bt1-<year>.jsonl plus every trade line,
computes per-year stats, and writes index.html. All data is backtest-only;
the BACKTEST / NOT VERIFIED banner is mandatory and always shown.
Stdlib only.
"""

import glob
import html
import json
import os
import re

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS_DIR = os.path.join(REPO, "backtest", "results")
OUTPUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "index.html")


def load_runs():
    runs = []
    for path in sorted(glob.glob(os.path.join(RESULTS_DIR, "bt1-*.jsonl"))):
        header, trades, n_entries = None, [], 0
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if rec.get("_header"):
                    header = rec
                elif rec.get("run_kind") == "entry":
                    n_entries += 1
                elif rec.get("executed") and isinstance(rec.get("result"), dict):
                    res = rec["result"]
                    if res.get("status") == "closed":
                        trades.append(res)
        if header:
            header.setdefault("signals_total", n_entries)
            header.setdefault("executed", len(trades))
            runs.append((header, trades))
    return runs


def stats(trades):
    wins = [t for t in trades if t.get("outcome") == "tp"]
    losses = [t for t in trades if t.get("outcome") in ("sl", "stopped")]
    pnls = [t.get("pnl", 0.0) for t in trades]
    total_r = sum(t.get("pnl_r", 0.0) for t in trades)
    eq, hwm, max_dd, streak, max_streak = 1.0, 1.0, 0.0, 0, 0
    for p in pnls:
        eq += p / 10000.0
        hwm = max(hwm, eq)
        max_dd = max(max_dd, (hwm - eq) / hwm * 100)
        streak = streak + 1 if p < 0 else 0
        max_streak = max(max_streak, streak)
    closed = len(wins) + len(losses)
    wr = (len(wins) / closed * 100) if closed else None
    exp = (total_r / closed) if closed else None
    return dict(closed=closed, wins=len(wins), losses=len(losses), wr=wr,
                exp=exp, total_r=total_r, dd=max_dd, streak=max_streak)  # noqa


def fmt(x, nd=2, suffix=""):
    return "—" if x is None else f"{x:.{nd}f}{suffix}"


def main():
    rows, tot = [], dict(signals=0, executed=0, closed=0, wins=0, losses=0,
                         total_r=0.0, dd=0.0, streak=0)
    for header, trades in load_runs():
        s = stats(trades)
        n_sig = header.get("signals_total", 0)
        n_exec = header.get("executed", len(trades))
        year = header.get("year", "?")
        rows.append((year, n_sig, n_exec, s))
        tot["signals"] += n_sig
        tot["executed"] += n_exec
        tot["closed"] += s["closed"]
        tot["wins"] += s["wins"]
        tot["losses"] += s["losses"]
        tot["total_r"] += s["total_r"]
        tot["dd"] = max(tot["dd"], s["dd"])
        tot["streak"] = max(tot["streak"], s["streak"])

    body_rows = "".join(
        f"<tr><td>{y}</td><td>{n_sig}</td><td>{n_exec}</td><td>{s['closed']}</td>"
        f"<td>{s['wins']}</td><td>{s['losses']}</td><td>{fmt(s['wr'],1,'%')}</td>"
        f"<td>{fmt(s['exp'],4,' R')}</td><td>{fmt(s['total_r'])} R</td>"
        f"<td>{fmt(s['dd'],1,'%')}</td><td>{s['streak']}</td></tr>"
        for y, n_sig, n_exec, s in rows)
    tc = tot["closed"]
    tot_wr = tot["wins"] / tc * 100 if tc else None
    tot_exp = tot["total_r"] / tc if tc else None

    out = f"""<!DOCTYPE html>
<html lang="id">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AgenticTrade — Tear Sheet (Backtest)</title>
<style>
  body {{ font-family: system-ui, sans-serif; margin: 2rem; color: #1a1a1a; }}
  .banner {{ background: #b00020; color: #fff; padding: 1rem 1.25rem; font-weight: 700;
             border-radius: 6px; margin-bottom: 1.5rem; font-size: 1.05rem; }}
  table {{ border-collapse: collapse; margin: 1rem 0; }}
  th, td {{ border: 1px solid #ccc; padding: .4rem .8rem; text-align: right; }}
  th {{ background: #f4f4f4; }}
  th:first-child, td:first-child {{ text-align: left; }}
  h1 {{ font-size: 1.4rem; }} h2 {{ font-size: 1.1rem; }}
</style>
</head>
<body>
<div class="banner">⚠ BACKTEST / NOT VERIFIED — Ini BUKAN track record live/real.
Semua angka berasal dari backtest internal (data tick Dukascopy 2020–2025, rule-based SMC MSS,
strategy_version 0.1-bt-*). Belum diverifikasi pihak ketiga; lihat docs/VERIFICATION.md.</div>
<h1>AgenticTrade — Tear Sheet Backtest (XAUUSD, 2020–2025)</h1>
<h2>Overall</h2>
<p>Sinyal: {tot['signals']} &middot; dieksekusi: {tot['executed']} &middot; ditutup: {tc}
&middot; win: {tot['wins']} &middot; loss: {tot['losses']}
&middot; win rate: {fmt(tot_wr,1,'%')} &middot; expectancy: {fmt(tot_exp,4,' R')}
&middot; total R: {fmt(tot['total_r'])} R &middot; worst-year max DD: {fmt(tot['dd'],1,'%')}
&middot; max losing streak: {tot['streak']}</p>
<h2>Per tahun (masing-masing mulai dari equity $10.000, guards RISK.md aktif)</h2>
<table>
<thead><tr><th>Tahun</th><th>Sinyal</th><th>Dieksekusi</th><th>Ditutup</th><th>Win</th>
<th>Loss</th><th>Win rate</th><th>Expectancy</th><th>Total R</th><th>Max DD</th>
<th>Max losing streak</th></tr></thead>
<tbody>
{body_rows}
</tbody>
</table>
<p><em>Sumber: backtest/results/bt1-*.jsonl (append-only). Dihasilkan oleh
dashboard/generate_pages.py. Banner BACKTEST/NOT VERIFIED wajib tampil sampai ada
verifikasi pihak ketiga.</em></p>
</body>
</html>
"""
    with open(OUTPUT, "w", encoding="utf-8") as f:
        f.write(out)
    print(f"wrote {OUTPUT} ({len(rows)} runs, {tc} closed trades)")


if __name__ == "__main__":
    main()
