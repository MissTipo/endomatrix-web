"""
domain.engine

Public API for the EndoMatrix engine layer.

Import from here:
    from domain.engine import PatternEngine, PhaseCalculator, PhaseResult
"""

from .pattern_engine import PatternEngine
from .phase_calculator import PhaseCalculator, PhaseResult

__all__ = [
    "PatternEngine",
    "PhaseCalculator",
    "PhaseResult",
]
