"""
infrastructure.orm.serializers

JSONB serialization and deserialization for PatternResult's nested types.

PatternResult contains nested domain objects (SymptomCluster, PhasePattern,
CyclePrediction) that are stored as a single JSONB payload column. This
module provides the round-trip helpers used by the pattern repository.

All serializers convert domain objects to plain dicts (for storage) and
back to domain objects (on retrieval). No external libraries — just Python
dicts and the domain model constructors.

These functions are private to the infrastructure layer. The domain and
application layers never touch them.
"""

from __future__ import annotations

from typing import Any, Optional

from domain.models.cycle import CyclePhase
from domain.models.pattern import (
    CyclePrediction,
    EscalationSpeed,
    PhasePattern,
    SeverityTrend,
    SymptomCluster,
)
from domain.models.symptom import Symptom


# ---------------------------------------------------------------------------
# SymptomCluster
# ---------------------------------------------------------------------------

def symptom_cluster_to_dict(cluster: SymptomCluster) -> dict[str, Any]:
    return {
        "symptoms": sorted(s.value for s in cluster.symptoms),
        "typical_phase": cluster.typical_phase.value,
        "occurrence_rate": cluster.occurrence_rate,
    }


def symptom_cluster_from_dict(data: dict[str, Any]) -> SymptomCluster:
    return SymptomCluster(
        symptoms=frozenset(Symptom(s) for s in data["symptoms"]),
        typical_phase=CyclePhase(data["typical_phase"]),
        occurrence_rate=data["occurrence_rate"],
    )


# ---------------------------------------------------------------------------
# PhasePattern
# ---------------------------------------------------------------------------

def phase_pattern_to_dict(pattern: PhasePattern) -> dict[str, Any]:
    return {
        "phase": pattern.phase.value,
        "onset_day_range": list(pattern.onset_day_range),
        "average_pain": pattern.average_pain,
        "average_energy": pattern.average_energy,
        "dominant_symptoms": [s.value for s in pattern.dominant_symptoms],
        "severity_trend": pattern.severity_trend.value,
        "log_count": pattern.log_count,
    }


def phase_pattern_from_dict(data: dict[str, Any]) -> PhasePattern:
    return PhasePattern(
        phase=CyclePhase(data["phase"]),
        onset_day_range=tuple(data["onset_day_range"]),  # type: ignore[arg-type]
        average_pain=data["average_pain"],
        average_energy=data["average_energy"],
        dominant_symptoms=[Symptom(s) for s in data["dominant_symptoms"]],
        severity_trend=SeverityTrend(data["severity_trend"]),
        log_count=data["log_count"],
    )


# ---------------------------------------------------------------------------
# CyclePrediction
# ---------------------------------------------------------------------------

def cycle_prediction_to_dict(prediction: CyclePrediction) -> dict[str, Any]:
    return {
        "high_symptom_day_range": list(prediction.high_symptom_day_range),
        "predicted_dominant_phase": prediction.predicted_dominant_phase.value,
        "confidence": prediction.confidence,
        "basis_cycles": prediction.basis_cycles,
    }


def cycle_prediction_from_dict(data: dict[str, Any]) -> CyclePrediction:
    return CyclePrediction(
        high_symptom_day_range=tuple(data["high_symptom_day_range"]),  # type: ignore[arg-type]
        predicted_dominant_phase=CyclePhase(data["predicted_dominant_phase"]),
        confidence=data["confidence"],
        basis_cycles=data["basis_cycles"],
    )


# ---------------------------------------------------------------------------
# PatternResult payload
# ---------------------------------------------------------------------------

def build_pattern_payload(
    symptom_clusters: list[SymptomCluster],
    phase_patterns: list[PhasePattern],
    prediction: Optional[CyclePrediction],
) -> dict[str, Any]:
    """
    Serialise the nested fields of a PatternResult into a JSONB payload dict.
    """
    return {
        "symptom_clusters": [symptom_cluster_to_dict(c) for c in symptom_clusters],
        "phase_patterns": [phase_pattern_to_dict(p) for p in phase_patterns],
        "prediction": cycle_prediction_to_dict(prediction) if prediction else None,
    }


def unpack_pattern_payload(payload: dict[str, Any]) -> tuple[
    list[SymptomCluster],
    list[PhasePattern],
    Optional[CyclePrediction],
]:
    """
    Deserialise a JSONB payload dict back into nested domain types.

    Returns (symptom_clusters, phase_patterns, prediction).
    """
    clusters = [symptom_cluster_from_dict(c) for c in payload.get("symptom_clusters", [])]
    patterns = [phase_pattern_from_dict(p) for p in payload.get("phase_patterns", [])]
    prediction_data = payload.get("prediction")
    prediction = cycle_prediction_from_dict(prediction_data) if prediction_data else None
    return clusters, patterns, prediction
