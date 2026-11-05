"""Modul analisa SMC/ICT AgenticTrade.

parser.py: baca & validasi signals/*.json (aturan skema = CI).
smc.py: struktur pasar SMC/ICT sebagai pure functions.
"""

from .parser import (
    REQUIRED_FIELDS,
    SignalValidationError,
    load_signals,
    parse_signal_file,
    validate_append_only,
    validate_signal,
)
from .smc import (
    FVG,
    MSS,
    OrderBlock,
    StructureReport,
    Swing,
    analyze,
    find_fvg,
    find_mss,
    find_order_blocks,
    find_swing_points,
)

__all__ = [
    "REQUIRED_FIELDS",
    "SignalValidationError",
    "load_signals",
    "parse_signal_file",
    "validate_append_only",
    "validate_signal",
    "FVG",
    "MSS",
    "OrderBlock",
    "StructureReport",
    "Swing",
    "analyze",
    "find_fvg",
    "find_mss",
    "find_order_blocks",
    "find_swing_points",
]
