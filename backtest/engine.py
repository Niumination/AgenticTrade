#!/usr/bin/env python3
"""AgenticTrade backtest engine — event-driven, tick-level (Fase 1).

Reads:
  - signals/*.json  : entry signals (schema identical to signals/ template)
  - tick data CSV   : Dukascopy bid/ask ticks (time,bid,ask) per instrument

Writes (APPEND-ONLY, never rewrites/backfills):
  - backtest/results/<run_id>.jsonl : header row + one JSON object per
    processed signal + one close row per closed position, using the SAME
    schema as signals/*.json (executed / blocked_reason / result filled by
    the simulation), so the dashboard generator's loader can read it
    unchanged. Output rows carry "verification": "NOT VERIFIED".

Risk guards (docs/RISK.md) are enforced HERE, at engine level, hard-coded:
  - risk per position  <= 1% of equity (lot size derived from SL distance)
  - max 2 open positions in parallel
  - daily loss 3%      -> no new trades for the rest of the calendar day
  - equity drawdown 10% from HWM -> kill switch, no further trades
  - SL always present and on the correct side
  - no symbol outside ALLOWED_SYMBOLS; no martingale / averaging-down /
    grid (one entry per signal, single position per signal id).
  - Every blocked guard is recorded in blocked_reason (evidence the guard
    works; blocked signals stay visible in the log per VERIFICATION.md).

Execution model: conservative, minimal slippage.
  - Entry: a signal created at tick T fills at the NEXT tick (T+1) at ask
    (buy) / bid (sell), plus a fixed slippage in pips.
  - SL/TP: SL assumed hit before TP when both levels lie within one tick's
    range (conservative). Exits at exact SL/TP price.

P&L model (Fase 1 simplification, explicit): money R = equity * 1%; a
closed trade moves equity by +R * pnl_r (tp) or -R (sl). End-of-data exits
use pnl_r from the actual exit distance. This keeps results in R units —
compatible with the dashboard's R-based drawdown/streak stats.

STATUS: internal backtest — all output marked NOT VERIFIED; never present
as a real track record (docs/VERIFICATION.md).

Stdlib only. Python 3.8+.

Usage:
  python3 backtest/engine.py --ticks data/ticks/XAUUSD.csv --run-id demo-001 \
      [--equity 10000] [--slippage-points 0] [--signals signals]
"""

import argparse
import csv
import glob
import json
import os
import sys
from datetime import datetime, timezone

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ---- RISK.md hard-coded guards (mirror docs/RISK.md; change = major bump) ----
RISK = {
    "max_risk_per_position_pct": 1.0,   # maks 1% ekuitas per posisi
    "max_open_positions": 2,            # maks 2 posisi paralel
    "daily_loss_halt_pct": 3.0,         # loss harian 3% -> stop hari itu
    "equity_dd_kill_pct": 10.0,         # DD dari HWM 10% -> berhenti total
    "require_sl": True,                 # SL selalu ada
}
ALLOWED_SYMBOLS = ("XAUUSD",)           # daftar instrumen resmi
PIP_SIZE = {"XAUUSD": 0.1}              # 1 pip = 0.1 pada XAUUSD (konvensi 1 pip = 10 points)

NOT_VERIFIED = "NOT VERIFIED"


# --------------------------------------------------------------------------- #
# Input loading
# --------------------------------------------------------------------------- #
def load_signals(signals_dir):
    """Load signals/*.json (read-only). Malformed files are reported, skipped."""
    signals = []
    for path in sorted(glob.glob(os.path.join(signals_dir, "*.json"))):
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                signals.extend(data)
            else:
                signals.append(data)
        except (OSError, json.JSONDecodeError) as exc:
            print("WARN: skipping malformed signal file %s: %s" % (path, exc),
                  file=sys.stderr)
    return [s for s in signals
            if isinstance(s, dict) and s.get("id") and not s.get("_header")]


def _parse_ts(value):
    ts = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts


def load_ticks(path):
    """Load Dukascopy tick CSV: time,bid,ask ascending. -> [(utc_dt, bid, ask)]"""
    ticks = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        cols = {c.lower().strip(): c for c in (reader.fieldnames or [])}
        if not {"time", "bid", "ask"} <= set(cols):
            raise SystemExit("tick CSV needs columns: time,bid,ask (got %r)"
                             % (reader.fieldnames,))
        for row in reader:
            ticks.append((_parse_ts(row[cols["time"]]),
                          float(row[cols["bid"]]),
                          float(row[cols["ask"]])))
    if not ticks:
        raise SystemExit("no ticks loaded from %s" % path)
    ticks.sort(key=lambda t: t[0])
    return ticks


# --------------------------------------------------------------------------- #
# Simulation
# --------------------------------------------------------------------------- #
class Position(object):
    __slots__ = ("signal_id", "direction", "entry", "sl", "tp", "risk_pips",
                 "risk_money", "open_time")

    def __init__(self, signal_id, direction, entry, sl, tp, risk_pips,
                 risk_money, open_time):
        self.signal_id = signal_id
        self.direction = direction
        self.entry = entry
        self.sl = sl
        self.tp = tp
        self.risk_pips = risk_pips
        self.risk_money = risk_money
        self.open_time = open_time


class Engine(object):
    """Event-driven simulator. One instance == one backtest run."""

    def __init__(self, equity=10000.0, slippage_points=0.0, pip=0.1):
        self.equity = float(equity)
        self.equity_hwm = self.equity
        self.slippage_points = float(slippage_points)
        self.pip = float(pip)
        self.open_positions = []       # list[Position]
        self.seen_signal_ids = set()   # duplicate-signal protection
        self.halted_today = None       # day_key where 3% daily halt triggered
        self.killed = False            # 10% DD kill switch
        self.day_pnl = 0.0
        self.day_key = None
        self.rows = []                 # output log rows (signals/ schema)
        self.close_log = []            # per-close detail (pnl_r, outcome, ...)

    # ---- helpers ----
    @staticmethod
    def _day_of(ts):
        return ts.astimezone(timezone.utc).strftime("%Y-%m-%d")

    def _roll_day(self, ts):
        dk = self._day_of(ts)
        if dk != self.day_key:
            self.day_key = dk
            self.day_pnl = 0.0
            self.halted_today = None

    def _to_pips(self, price_delta):
        return price_delta / self.pip

    def _daily_dd_pct(self):
        return -self.day_pnl / self.equity_hwm * 100.0 if self.day_pnl < 0 else 0.0

    def _equity_dd_pct(self):
        return (self.equity_hwm - self.equity) / self.equity_hwm * 100.0

    # ---- guards (RISK.md at engine level) ----
    def _guard(self, sig, tick_time):
        """None if the signal passes every guard, else blocked_reason."""
        if self.killed:
            return "guard_kill_switch_dd10"
        self._roll_day(tick_time)
        if self.halted_today == self.day_key:
            return "guard_daily_loss_halt_3pct"
        if sig.get("instrument") not in ALLOWED_SYMBOLS:
            return "guard_symbol_not_allowed"
        if sig.get("id") in self.seen_signal_ids:
            return "guard_duplicate_signal_id"
        direction = str(sig.get("direction", "")).lower()
        if direction not in ("buy", "sell"):
            return "guard_direction_invalid"
        entry, sl, tp = sig.get("entry"), sig.get("sl"), sig.get("tp")
        try:
            entry, sl = float(entry), float(sl)
        except (TypeError, ValueError):
            return "guard_entry_or_sl_missing"
        if RISK["require_sl"] and (sl is None or sl == 0):
            return "guard_sl_missing"
        if (direction == "buy" and sl >= entry) or \
           (direction == "sell" and sl <= entry):
            return "guard_sl_wrong_side"
        if len(self.open_positions) >= RISK["max_open_positions"]:
            return "guard_max_positions_2"
        # risk sizing sanity: risk must fit within 1% cap (by construction it
        # does; guard documents the invariant for the audit log)
        return None

    def _fill_crosses_sl(self, direction, fill, sl):
        """True if a market fill landed at/beyond the SL (gap through stop)."""
        return fill <= sl if direction == "buy" else fill >= sl

    # ---- execution ----
    def _fill_price(self, direction, bid, ask):
        slip = self.slippage_points * self.pip
        return (ask + slip) if direction == "buy" else (bid - slip)

    def _open(self, sig, fill_ts, bid, ask, row):
        direction = sig["direction"].lower()
        fill = self._fill_price(direction, bid, ask)
        sl, tp = float(sig["sl"]), float(sig.get("tp") or 0)
        risk_pips = abs(self._to_pips(fill - sl))
        if risk_pips <= 0:
            row["executed"] = False
            row["blocked_reason"] = "guard_sl_zero_distance_after_fill"
            return
        if self._fill_crosses_sl(direction, fill, sl):
            # fill gapped through the stop: refusing avoids a >1R loss at entry
            row["executed"] = False
            row["blocked_reason"] = "guard_fill_gap_through_sl"
            return
        risk_money = self.equity * RISK["max_risk_per_position_pct"] / 100.0
        self.seen_signal_ids.add(sig["id"])
        self.open_positions.append(Position(
            sig["id"], direction, fill, sl, tp, risk_pips, risk_money, fill_ts))
        row["executed"] = True
        row["result"] = {
            "status": "open",
            "fill": round(fill, 5),
            "slippage": round(abs(fill - (ask if direction == "buy" else bid)), 5),
            "risk_pips": round(risk_pips, 2),
            "risk_money": round(risk_money, 2),
            "risk_cap_pct": RISK["max_risk_per_position_pct"],
            "opened_at": fill_ts.isoformat(),
        }

    def _close(self, pos, ts, exit_price, outcome):
        """Settle a position. pnl in R units vs its own risk_money."""
        if outcome == "sl":
            pnl_r = -1.0
        else:
            pnl_r = self._to_pips(abs(exit_price - pos.entry)) / pos.risk_pips
        pnl = pnl_r * pos.risk_money
        self.equity += pnl
        self.day_pnl += pnl
        self.equity_hwm = max(self.equity_hwm, self.equity)
        # RISK.md: daily loss 3% -> halt until next day; equity DD 10% -> kill
        if self._daily_dd_pct() >= RISK["daily_loss_halt_pct"]:
            self.halted_today = self.day_key
        if self._equity_dd_pct() >= RISK["equity_dd_kill_pct"]:
            self.killed = True
        rec = {"signal_id": pos.signal_id, "outcome": outcome,
               "exit": round(exit_price, 5), "pnl_r": round(pnl_r, 4),
               "pnl": round(pnl, 2), "equity": round(self.equity, 2),
               "equity_dd_pct": round(self._equity_dd_pct(), 2),
               "daily_dd_pct": round(self._daily_dd_pct(), 2),
               "closed_at": ts.isoformat()}
        self.close_log.append(rec)
        return rec

    def _mark(self, ts, bid, ask):
        """SL/TP checks against this tick. Conservative: SL wins ties."""
        for pos in list(self.open_positions):
            if pos.direction == "buy":
                hit_sl, hit_tp = bid <= pos.sl, (pos.tp > 0 and bid >= pos.tp)
            else:
                hit_sl, hit_tp = ask >= pos.sl, (pos.tp > 0 and ask <= pos.tp)
            if hit_sl:
                outcome, exit_px = "sl", pos.sl
            elif hit_tp:
                outcome, exit_px = "tp", pos.tp
            else:
                continue
            self.open_positions.remove(pos)
            self._append_close_row(self._close(pos, ts, exit_px, outcome))

    def _append_close_row(self, rec):
        self.rows.append({
            "id": rec["signal_id"],
            "instrument": None, "setup": None, "strategy_version": None,
            "direction": None, "entry": None, "sl": None, "tp": None,
            "rr": None, "confidence": None, "reasoning": None, "model": None,
            "created_at": None,
            "risk_checks": {"within_daily_loss_limit": self.halted_today != self.day_key,
                            "within_max_positions": True,
                            "news_filter_clear": None},
            "executed": True,
            "blocked_reason": None,
            "result": {"status": "closed", "outcome": rec["outcome"],
                       "exit": rec["exit"], "pnl_r": rec["pnl_r"],
                       "pnl": rec["pnl"], "equity": rec["equity"],
                       "equity_dd_pct": rec["equity_dd_pct"],
                       "closed_at": rec["closed_at"]},
            "source": "backtest_engine",
            "run_kind": "close",
            "simulated_at": rec["closed_at"],
            "verification": NOT_VERIFIED,
        })

    def _base_row(self, sig, ts):
        return {
            "id": sig.get("id"),
            "instrument": sig.get("instrument"),
            "setup": sig.get("setup"),
            "strategy_version": sig.get("strategy_version"),
            "direction": sig.get("direction"),
            "entry": sig.get("entry"),
            "sl": sig.get("sl"),
            "tp": sig.get("tp"),
            "rr": sig.get("rr"),
            "confidence": sig.get("confidence"),
            "reasoning": sig.get("reasoning"),
            "model": sig.get("model"),
            "created_at": sig.get("created_at"),
            "risk_checks": {
                "within_daily_loss_limit": self.halted_today != self.day_key,
                "within_max_positions":
                    len(self.open_positions) < RISK["max_open_positions"],
                "news_filter_clear":
                    sig.get("risk_checks", {}).get("news_filter_clear"),
            },
            "executed": False,
            "blocked_reason": None,
            "result": None,
            "source": "backtest_engine",
            "run_kind": "entry",
            "simulated_at": ts.isoformat(),
            "verification": NOT_VERIFIED,
        }

    # ---- main loop ----
    def run(self, signals, ticks):
        # skip signals without created_at up-front (WARN-and-skip), so the
        # sort below can never raise KeyError on a malformed signal dict
        for s in list(signals):
            if not s.get("created_at"):
                print("WARN: signal %s missing field 'created_at'; skipped"
                      % (s.get("id"),), file=sys.stderr)
        signals = [s for s in signals if s.get("created_at")]
        queue = sorted(
            ((s, _parse_ts(s["created_at"])) for s in signals),
            key=lambda p: p[1])
        for sig, _ in queue:                      # validation pass
            for field in ("instrument", "direction", "entry"):
                if not sig.get(field):
                    print("WARN: signal %s missing field %r; skipped"
                          % (sig.get("id"), field), file=sys.stderr)
        queue = [(s, t) for s, t in queue if s.get("instrument")
                 and s.get("direction") and s.get("entry")]

        for i, (ts, bid, ask) in enumerate(ticks):
            self._roll_day(ts)
            if i > 0:                             # fill against current tick
                self._mark(ts, bid, ask)
                while queue and queue[0][1] < ts:
                    sig, sig_ts = queue.pop(0)
                    row = self._base_row(sig, ts)
                    reason = self._guard(sig, ts)
                    if reason:
                        row["blocked_reason"] = reason
                    else:
                        self._open(sig, ts, bid, ask, row)
                    self.rows.append(row)
            # else: first tick has no previous-tick signal; positions cannot exist
        # end of data: settle remaining positions at last tick, tagged
        if self.open_positions and ticks:
            ts, bid, ask = ticks[-1]
            for pos in list(self.open_positions):
                exit_px = bid if pos.direction == "buy" else ask
                outcome = "tp" if ((pos.direction == "buy" and exit_px > pos.entry)
                                   or (pos.direction == "sell" and exit_px < pos.entry)) \
                    else "sl"
                self.open_positions.remove(pos)
                self._append_close_row(self._close(pos, ts, exit_px, outcome))
        return self.rows

    # ---- metrics (dashboard-compatible) ----
    def metrics(self):
        entries = [r for r in self.rows if r["run_kind"] == "entry"]
        rs = [c["pnl_r"] for c in self.close_log]
        wins = [r for r in rs if r > 0]
        losses = [r for r in rs if r <= 0]
        streak = worst = 0
        for r in rs:
            streak = streak + 1 if r <= 0 else 0
            worst = max(worst, streak)
        return {
            "signals_total": len(entries),
            "executed": sum(1 for r in entries if r["executed"]),
            "blocked": sum(1 for r in entries if not r["executed"]),
            "blocked_by_guard": sorted({r["blocked_reason"]
                                        for r in entries if r["blocked_reason"]}),
            "trades_closed": len(rs),
            "wins": len(wins),
            "losses": len(losses),
            "win_rate_pct": round(100.0 * len(wins) / len(rs), 2) if rs else None,
            "total_r": round(sum(rs), 4),
            "expectancy_r": round(sum(rs) / len(rs), 4) if rs else None,
            "final_equity": round(self.equity, 2),
            "start_equity": round(self.equity_hwm if not self.close_log else
                                  self.close_log[0]["equity"] -
                                  self.close_log[0]["pnl"], 2),
            "equity_hwm": round(self.equity_hwm, 2),
            "max_equity_dd_pct": round(self._equity_dd_pct(), 2),
            "guards_triggered": {
                "daily_halt_3pct": self.halted_today,
                "kill_switch_10pct": self.killed,
            },
            "max_consecutive_losses": worst,
            "open_positions_end": len(self.open_positions),
            "verification": NOT_VERIFIED,
        }


# --------------------------------------------------------------------------- #
# Output (append-only)
# --------------------------------------------------------------------------- #
def write_results(rows, run_id, results_dir, meta):
    os.makedirs(results_dir, exist_ok=True)
    path = os.path.join(results_dir, "%s.jsonl" % run_id)
    exists = os.path.exists(path)
    with open(path, "a", encoding="utf-8") as f:   # APPEND-ONLY
        if not exists:
            f.write(json.dumps({"_header": True, "run_id": run_id,
                                "risk_guards": RISK,
                                "allowed_symbols": list(ALLOWED_SYMBOLS),
                                "verification": NOT_VERIFIED,
                                **meta}) + "\n")
        for row in rows:
            f.write(json.dumps(row, sort_keys=True) + "\n")
    return path


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="AgenticTrade backtest engine (internal, NOT VERIFIED)")
    ap.add_argument("--ticks", required=True, help="tick CSV: time,bid,ask")
    ap.add_argument("--signals", default=os.path.join(REPO, "signals"))
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--equity", type=float, default=10000.0)
    ap.add_argument("--slippage-points", type=float, default=0.0)
    ap.add_argument("--pip", type=float, default=PIP_SIZE["XAUUSD"])
    ap.add_argument("--results-dir", default=os.path.join(REPO, "backtest", "results"))
    args = ap.parse_args(argv)

    signals = load_signals(args.signals)
    ticks = load_ticks(args.ticks)
    eng = Engine(equity=args.equity, slippage_points=args.slippage_points,
                 pip=args.pip)
    rows = eng.run(signals, ticks)
    path = write_results(rows, args.run_id, args.results_dir,
                         meta={"ticks_file": os.path.abspath(args.ticks),
                               "start_equity": args.equity,
                               "slippage_points": args.slippage_points})
    print(json.dumps({"results": path, "metrics": eng.metrics(),
                      "verification": NOT_VERIFIED}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
