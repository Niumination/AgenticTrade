import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from parser import (  # noqa: E402
    REQUIRED_FIELDS,
    SignalValidationError,
    load_signals,
    parse_signal_file,
    validate_append_only,
    validate_signal,
)

VALID_SIGNAL = {
    "id": "2026-11-04-001",
    "instrument": "XAUUSD",
    "setup": "order_block_m15_mss_m1",
    "strategy_version": "0.1",
    "direction": "buy",
    "entry": 2340.5,
    "sl": 2335.0,
    "tp": 2351.5,
    "rr": 2.0,
    "confidence": 0.8,
    "reasoning": "HTF bullish, OB M15 discount, MSS M1, RR 2.0",
    "model": "hermes-agent",
    "created_at": "2026-11-04T10:00:00Z",
    "risk_checks": {
        "within_daily_loss_limit": True,
        "within_max_positions": True,
        "news_filter_clear": True,
    },
    "executed": False,
    "blocked_reason": None,
    "result": None,
}


def write(tmp_path: Path, name: str, data) -> Path:
    p = tmp_path / name
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


class TestParseSignalFile:
    def test_valid_signal_ok(self, tmp_path):
        p = write(tmp_path, "s.json", VALID_SIGNAL)
        sig = parse_signal_file(p)
        assert sig["id"] == "2026-11-04-001"

    def test_missing_field_fails(self, tmp_path):
        bad = {k: v for k, v in VALID_SIGNAL.items() if k != "confidence"}
        p = write(tmp_path, "s.json", bad)
        with pytest.raises(SignalValidationError, match="confidence"):
            parse_signal_file(p)

    def test_required_fields_match_ci(self):
        ci_required = {
            "id", "instrument", "setup", "strategy_version", "direction",
            "entry", "sl", "tp", "confidence", "reasoning", "executed",
        }
        assert REQUIRED_FIELDS == ci_required

    def test_empty_reasoning_fails(self, tmp_path):
        bad = dict(VALID_SIGNAL, reasoning="")
        p = write(tmp_path, "s.json", bad)
        with pytest.raises(SignalValidationError, match="reasoning"):
            parse_signal_file(p)

    def test_template_reasoning_fails_except_example(self, tmp_path):
        bad = dict(VALID_SIGNAL, reasoning="TEMPLATE CONTOH - jangan dihapus")
        p = write(tmp_path, "2026-11-04.json", bad)
        with pytest.raises(SignalValidationError, match="reasoning"):
            parse_signal_file(p)
        p2 = write(tmp_path, "2026-11-04.example.json", bad)
        assert parse_signal_file(p2)["reasoning"].startswith("TEMPLATE")

    def test_invalid_json_fails(self, tmp_path):
        p = tmp_path / "s.json"
        p.write_text("{not json", encoding="utf-8")
        with pytest.raises(SignalValidationError, match="JSON"):
            parse_signal_file(p)

    def test_bad_direction_fails(self, tmp_path):
        p = write(tmp_path, "s.json", dict(VALID_SIGNAL, direction="long"))
        with pytest.raises(SignalValidationError, match="direction"):
            parse_signal_file(p)

    def test_bad_risk_checks_fails(self, tmp_path):
        p = write(
            tmp_path, "s.json",
            dict(VALID_SIGNAL, risk_checks={"made_up_check": True}),
        )
        with pytest.raises(SignalValidationError, match="risk_checks"):
            parse_signal_file(p)


class TestLoadSignals:
    def test_loads_dir_sorted_and_tags_path(self, tmp_path):
        write(tmp_path, "b.json", VALID_SIGNAL)
        write(tmp_path, "a.json", dict(VALID_SIGNAL, id="2026-11-04-000"))
        sigs = load_signals(tmp_path)
        assert [s["id"] for s in sigs] == ["2026-11-04-000", "2026-11-04-001"]
        assert sigs[0]["_path"].endswith("a.json")

    def test_one_bad_file_raises(self, tmp_path):
        write(tmp_path, "good.json", VALID_SIGNAL)
        (tmp_path / "bad.json").write_text("nope", encoding="utf-8")
        with pytest.raises(SignalValidationError):
            load_signals(tmp_path)

    def test_repo_signals_dir_valid(self):
        repo = Path(__file__).resolve().parents[2]
        signals = repo / "signals"
        if signals.exists():
            sigs = load_signals(signals)
            assert all(s["instrument"] for s in sigs)


class TestAppendOnly:
    def test_append_ok(self):
        new = [dict(VALID_SIGNAL), dict(VALID_SIGNAL, id="2026-11-04-002")]
        assert validate_append_only([VALID_SIGNAL], new) == []

    def test_shrink_fails(self):
        v = validate_append_only([VALID_SIGNAL, dict(VALID_SIGNAL, id="x")], [VALID_SIGNAL])
        assert v and "menyusut" in v[0]

    def test_modify_entry_fails(self):
        old = [VALID_SIGNAL]
        new = [dict(VALID_SIGNAL, entry=9999.0)]
        assert validate_append_only(old, new)

    def test_result_update_allowed(self):
        old = [VALID_SIGNAL]
        new = [dict(VALID_SIGNAL, executed=True, result={"r": 2.0})]
        assert validate_append_only(old, new) == []
