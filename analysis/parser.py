"""Parser untuk log sinyal append-only di signals/.

Aturan skema sama persis dengan CI (.github/workflows/validate-signals.yml):
- field wajib: id, instrument, setup, strategy_version, direction, entry,
  sl, tp, confidence, reasoning, executed
- reasoning tidak boleh kosong; reasoning "TEMPLATE..." hanya boleh
  di file *example.json
- file yang gagal di-parse (JSON invalid) adalah error.

Fungsi append-only di sini bekerja pada konten file saat ini (bukan git
history): file sinyal adalah JSON per-hari yang hanya ditambah entri.
`validate_append_only` membandingkan snapshot lama vs baru dan menolak
jika ada file yang hilang atau isinya menyusut.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

REQUIRED_FIELDS = {
    "id",
    "instrument",
    "setup",
    "strategy_version",
    "direction",
    "entry",
    "sl",
    "tp",
    "confidence",
    "reasoning",
    "executed",
}

ALLOWED_DIRECTIONS = {"buy", "sell"}
ALLOWED_RISK_CHECKS = {
    "within_daily_loss_limit",
    "within_max_positions",
    "news_filter_clear",
}


class SignalValidationError(ValueError):
    """Schema violation pada satu file sinyal."""


def parse_signal_file(path: str | Path) -> dict[str, Any]:
    """Baca satu file sinyal JSON dan validasi skema (aturan CI).

    Raise SignalValidationError jika invalid; return dict jika valid.
    """
    path = Path(path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise SignalValidationError(f"{path}: JSON tidak valid: {e}") from e
    except OSError as e:
        raise SignalValidationError(f"{path}: tidak bisa dibaca: {e}") from e

    if not isinstance(data, dict):
        raise SignalValidationError(f"{path}: root harus object JSON")

    validate_signal(data, source=str(path))
    return data


def validate_signal(data: dict[str, Any], source: str = "<signal>") -> None:
    """Validasi satu objek sinyal; aturan identik dengan CI.

    CI tidak mengecek tipe/nilai detail, tapi parser ini menambahkan
    pemeriksaan lembut (direction, risk_checks, executed bool) —
    field wajib dan aturan reasoning/TEMPLATE disamakan persis dengan CI.
    """
    missing = REQUIRED_FIELDS - data.keys()
    if missing:
        raise SignalValidationError(f"{source}: field hilang {sorted(missing)}")

    reasoning = data.get("reasoning")
    if not reasoning or (isinstance(reasoning, str) and reasoning.startswith("TEMPLATE")):
        if not source.endswith("example.json"):
            raise SignalValidationError(f"{source}: reasoning kosong")

    if data.get("direction") not in ALLOWED_DIRECTIONS:
        raise SignalValidationError(
            f"{source}: direction harus salah satu dari {sorted(ALLOWED_DIRECTIONS)}"
        )

    if not isinstance(data.get("executed"), bool):
        raise SignalValidationError(f"{source}: 'executed' harus boolean")

    risk_checks = data.get("risk_checks")
    if risk_checks is not None:
        if not isinstance(risk_checks, dict):
            raise SignalValidationError(f"{source}: 'risk_checks' harus object")
        unknown = set(risk_checks) - ALLOWED_RISK_CHECKS
        if unknown:
            raise SignalValidationError(
                f"{source}: risk_checks tidak dikenal: {sorted(unknown)}"
            )


def load_signals(signals_dir: str | Path) -> list[dict[str, Any]]:
    """Baca semua signals/*.json (urut nama file) dan validasi semuanya.

    Return list of (dict, path) style dict + '_path' agar traceable.
    """
    signals_dir = Path(signals_dir)
    results: list[dict[str, Any]] = []
    for path in sorted(signals_dir.glob("*.json")):
        sig = parse_signal_file(path)
        sig = dict(sig)
        sig["_path"] = str(path)
        results.append(sig)
    return results


def _signal_fingerprint(sig: dict[str, Any]) -> str:
    """Identitas stabil satu entri sinyal untuk cek append-only."""
    return str(sig.get("id"))


def validate_append_only(
    old: Iterable[dict[str, Any]], new: Iterable[dict[str, Any]]
) -> list[str]:
    """Cek append-only antara snapshot lama dan baru (per file via caller).

    Aturan (paralel dengan CI): tidak ada entri yang hilang atau diubah;
    hanya boleh ada entri baru di akhir. Return list pelanggaran (kosong = OK).
    """
    old_list = list(old)
    new_list = list(new)
    violations: list[str] = []
    if len(new_list) < len(old_list):
        violations.append(
            f"entri menyusut dari {len(old_list)} ke {len(new_list)}"
        )
        return violations
    for i, old_sig in enumerate(old_list):
        new_sig = new_list[i]
        old_fp = _signal_fingerprint(old_sig)
        new_fp = _signal_fingerprint(new_sig)
        # entri lama tidak boleh berubah (kecuali field hasil eksekusi yang
        # di-update append-style: executed/blocked_reason/result)
        frozen = {k: v for k, v in old_sig.items() if k not in ("executed", "blocked_reason", "result")}
        new_frozen = {k: v for k, v in new_sig.items() if k not in ("executed", "blocked_reason", "result")}
        if old_fp != new_fp or frozen != new_frozen:
            violations.append(f"entri #{i} (id={old_fp}) berubah")
    return violations
