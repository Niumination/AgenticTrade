#!/usr/bin/env python3
"""AgenticTrade tear-sheet generator.

Reads signals/*.json (append-only log, READ-ONLY — never writes to signals/),
computes performance statistics (overall + per strategy_version), and renders
a static HTML dashboard at dashboard/index.html.

Mandatory disclaimer banner "BACKTEST/INTERNAL — NOT VERIFIED" is shown on the
page until docs/VERIFICATION.md contains a third-party verification link
(Myfxbook/FXBlue/MQL5 URL). See docs/VERIFICATION.md.

Stdlib only. Python 3.8+.
"""

import glob
import html
import json
import os
import re
import sys
from collections import OrderedDict

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SIGNALS_DIR = os.path.join(REPO, "signals")
DOCS_VERIFICATION = os.path.join(REPO, "docs", "VERIFICATION.md")
OUTPUT = os.path.join(REPO, "dashboard", "index.html")

REQUIRED_FIELDS = {
    "id", "instrument", "setup", "strategy_version", "direction",
    "entry", "sl", "tp", "confidence", "reasoning", "executed",
}

# Third-party verification domains that may clear the banner.
VERIFIED_DOMAINS = (
    "myfxbook.com", "fxblue.com", "mql5.com",
)


def is_verified(docs_path):
    """True only if VERIFICATION.md contains a third-party verification link."""
    try:
        with open(docs_path, encoding="utf-8") as f:
            text = f.read()
    except OSError:
        return False
    for m in re.finditer(r"https?://[^\s)\]>]+", text):
        host = m.group(0).split("//", 1)[1].split("/", 1)[0].lower()
        if any(host == d or host.endswith("." + d) for d in VERIFIED_DOMAINS):
            return True
    return False


def load_signals():
    """Read every signals/*.json. Read-only; malformed files are reported, not fixed."""
    signals, errors = [], []
    for path in sorted(glob.glob(os.path.join(SIGNALS_DIR, "*.json"))):
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):  # tolerate JSONL-style appends
                signals.extend(data)
            else:
                signals.append(data)
        except Exception as exc:  # noqa: BLE001 — surface, never mutate
            errors.append(f"{os.path.basename(path)}: {exc}")
            continue
        missing = REQUIRED_FIELDS - set(data)
        if missing:
            errors.append(f"{os.path.basename(path)}: missing fields {sorted(missing)}")
    return signals, errors


def outcome_r(sig):
    """Return (closed: bool, r: float) for one signal.

    Outcome comes from the optional `result` field:
      - dict with "r"            -> explicit R multiple
      - "tp" / "win"             -> +rr (falls back to computed RR, else +2)
      - "sl" / "loss"            -> -1
      - "be" / "breakeven"       -> 0
      - anything else / missing  -> not closed, excluded from stats
    """
    result = sig.get("result")
    if result is None:
        return False, 0.0
    if isinstance(result, dict):
        r = result.get("r")
        if isinstance(r, (int, float)):
            return True, float(r)
        result = result.get("outcome")
    key = str(result).strip().lower()
    if key in ("tp", "win"):
        entry, sl, tp = sig.get("entry"), sig.get("sl"), sig.get("tp")
        try:
            risk = abs(entry - sl)
            rr = abs(tp - entry) / risk if risk else None
        except TypeError:
            rr = None
        return True, float(rr) if rr else 2.0
    if key in ("sl", "loss"):
        return True, -1.0
    if key in ("be", "breakeven"):
        return True, 0.0
    return False, 0.0


def compute_stats(signals):
    """Win rate, expectancy, max drawdown (R), max consecutive-loss streak."""
    closed = []
    for sig in signals:
        closed_flag, r = outcome_r(sig)
        if closed_flag:
            closed.append((sig.get("created_at", ""), r))
    closed.sort(key=lambda x: x[0])  # chronological by created_at

    n = len(closed)
    wins = sum(1 for _, r in closed if r > 0)
    losses = sum(1 for _, r in closed if r < 0)
    total_r = sum(r for _, r in closed)

    stats = {
        "total_signals": len(signals),
        "closed": n,
        "wins": wins,
        "losses": losses,
        "win_rate": round(100.0 * wins / n, 1) if n else None,
        "expectancy": round(total_r / n, 3) if n else None,
        "total_r": round(total_r, 2),
        "max_dd_r": 0.0,
        "max_loss_streak": 0,
    }
    if n:
        # Max drawdown: peak-to-trough on cumulative R.
        cum = peak = 0.0
        max_dd = 0.0
        streak = 0
        for _, r in closed:
            cum += r
            peak = max(peak, cum)
            max_dd = max(max_dd, peak - cum)
            streak = streak + 1 if r < 0 else 0
            stats["max_loss_streak"] = max(stats["max_loss_streak"], streak)
        stats["max_dd_r"] = round(max_dd, 2)
    return stats


def group_by_version(signals):
    """Isolate stats per strategy_version (never merge versions — STRATEGY.md rule)."""
    groups = OrderedDict()
    for sig in signals:
        groups.setdefault(str(sig.get("strategy_version", "?")), []).append(sig)
    return groups


def render(stats_by_version, overall, errors, verified):
    """Render one page: banner + overall + one stats table per strategy_version."""
    if verified:
        banner = ('<div class="banner ok">Verified: third-party track record link '
                  'present in docs/VERIFICATION.md</div>')
    else:
        banner = ('<div class="banner">BACKTEST/INTERNAL — NOT VERIFIED. '
                  'Ini BUKAN track record real. Angka berasal dari log internal; '
                  'lihat docs/VERIFICATION.md.</div>')

    def table_rows():
        rows = []
        for version, stats in stats_by_version.items():
            wr = f"{stats['win_rate']}%" if stats["win_rate"] is not None else "—"
            exp = stats["expectancy"] if stats["expectancy"] is not None else "—"
            rows.append(
                f"<tr><td>{html.escape(version)}</td>"
                f"<td>{stats['total_signals']}</td><td>{stats['closed']}</td>"
                f"<td>{stats['wins']}</td><td>{stats['losses']}</td>"
                f"<td>{wr}</td><td>{exp} R</td><td>{stats['total_r']} R</td>"
                f"<td>{stats['max_dd_r']} R</td><td>{stats['max_loss_streak']}</td></tr>"
            )
        return "\n".join(rows)

    error_html = ""
    if errors:
        items = "".join(f"<li><code>{html.escape(e)}</code></li>" for e in errors)
        error_html = f"<h2>Peringatan data</h2><ul>{items}</ul>"

    return f"""<!DOCTYPE html>
<html lang="id">
<head>
<meta charset="utf-8">
<title>AgenticTrade — Tear Sheet</title>
<style>
  body {{ font-family: system-ui, sans-serif; margin: 2rem; color: #1a1a1a; }}
  .banner {{ background: #b00020; color: #fff; padding: 1rem; font-weight: 700;
             border-radius: 6px; margin-bottom: 1.5rem; }}
  .banner.ok {{ background: #1b5e20; }}
  table {{ border-collapse: collapse; margin: 1rem 0; }}
  th, td {{ border: 1px solid #ccc; padding: .4rem .8rem; text-align: right; }}
  th:first-child, td:first-child {{ text-align: left; }}
  h1 {{ font-size: 1.4rem; }}
</style>
</head>
<body>
{banner}
<h1>AgenticTrade — Tear Sheet (dari signals/, append-only)</h1>
<h2>Overall</h2>
<p>Sinyal total: {overall['total_signals']} &middot; ditutup: {overall['closed']}
 &middot; total R: {overall['total_r']} R</p>
<h2>Statistik per versi strategi</h2>
<table>
<thead><tr><th>Versi</th><th>Sinyal</th><th>Ditutup</th><th>Win</th><th>Loss</th>
<th>Win rate</th><th>Expectancy</th><th>Total R</th><th>Max DD</th><th>Max losing streak</th></tr></thead>
<tbody>
{table_rows()}
</tbody>
</table>
{error_html}
<p><em>Dihasilkan otomatis oleh dashboard/generate.py. Input hanya dibaca, tidak pernah ditulis ulang.
Statistik tidak digabung antar versi strategi.</em></p>
</body>
</html>
"""


def main():
    verified = is_verified(DOCS_VERIFICATION)
    signals, errors = load_signals()

    stats_by_version = OrderedDict()
    for version, group in group_by_version(signals).items():
        stats_by_version[version] = compute_stats(group)
    overall = compute_stats(signals)

    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    with open(OUTPUT, "w", encoding="utf-8") as f:
        f.write(render(stats_by_version, overall, errors, verified))
    print(f"wrote {OUTPUT} ({len(signals)} signals, "
          f"{len(stats_by_version)} strategy versions, verified={verified})")
    if errors:
        for e in errors:
            print(f"WARNING: {e}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
