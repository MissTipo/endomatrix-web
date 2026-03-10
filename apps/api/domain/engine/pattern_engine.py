"""
PatternEngine

Detects patterns in a sequence of DailyLogs and produces a PatternResult.

This is v0/MVP rule-based logic. No ML, no statistical libraries.
The goal is to earn the data before adding model complexity.
The engine wins by respecting time — most competitors flatten logs
into averages. We preserve phase structure and longitudinal order.

What the engine detects:

1. Symptom onset range
   The cycle day range when symptoms typically begin.
   Defined as: the first day in a cycle window where pain >= ONSET_THRESHOLD.

2. Escalation speed
   How quickly pain rises from the onset day.
   SHARP:    pain reaches peak within 1 day of onset
   MODERATE: pain reaches peak within 2–3 days
   GRADUAL:  pain builds over 4+ days

3. Symptom clusters
   Pairs of symptoms that appear together on high-pain days
   more often than individually. Simple co-occurrence counting.

4. Phase patterns
   Per-phase averages and dominant symptoms across all analyzed logs.
   Ordered by average pain descending.

5. Severity trend
   Whether the most symptomatic phase is getting worse, better, or
   holding steady across the analyzed period.
   Computed by splitting logs into two halves chronologically and
   comparing average pain in the most symptomatic phase window.

6. Early feedback
   A single plain-language observation for the Home screen.
   Generated when >= MIN_LOGS_FOR_FEEDBACK logs exist.
   Never fabricated — returns None if no clear pattern is visible.

Thresholds:
    All thresholds are named constants at the top of this file.
    They are intentionally conservative. A false positive
    (telling a user they have a pattern when they do not) damages
    trust more than a false negative.

Design note on honest uncertainty:
    The engine does not suppress low-confidence results — it annotates
    them. PhasePattern.has_sufficient_data and
    CyclePrediction.display_confidence carry the uncertainty forward.
    The presentation layer decides how to qualify the language.
    The engine's job is to compute, not to decide what is safe to show.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime
from uuid import uuid4

from domain.models.cycle import CyclePhase, Score
from domain.models.daily_log import DailyLog
from domain.models.pattern import (
    CyclePrediction,
    EarlyFeedback,
    EscalationSpeed,
    PatternResult,
    PhasePattern,
    SeverityTrend,
    SymptomCluster,
)
from domain.models.symptom import Symptom


# ---------------------------------------------------------------------------
# Thresholds — change these deliberately, not casually
# ---------------------------------------------------------------------------

# Pain score at or above this value marks a day as symptomatic for onset detection
ONSET_THRESHOLD: int = 5

# Pain score at or above this is considered a "high pain day" for clustering
HIGH_PAIN_THRESHOLD: int = 7

# Fraction of high-pain days on which two symptoms must co-occur to form a cluster
CLUSTER_MIN_OCCURRENCE_RATE: float = 0.3

# Minimum logs required before any pattern output is produced
MIN_LOGS_FOR_PATTERN: int = 14

# Minimum logs before early feedback is generated
MIN_LOGS_FOR_FEEDBACK: int = 7

# Minimum logs before a CyclePrediction is attempted
MIN_LOGS_FOR_PREDICTION: int = 2  # cycles worth, checked by caller

# Percentage change in average pain between first and second half
# required to classify a trend as ESCALATING or IMPROVING
TREND_CHANGE_THRESHOLD: float = 0.15  # 15%


# ---------------------------------------------------------------------------
# PatternEngine
# ---------------------------------------------------------------------------

class PatternEngine:
    """
    Produces a PatternResult from a sequence of DailyLogs.

    Stateless. The same instance can be used for any number of users.
    All state lives in the inputs.

    Usage:
        engine = PatternEngine()
        result = engine.analyze(logs)
        if result is not None:
            # show on Insights screen
    """

    def analyze(self, logs: list[DailyLog]) -> PatternResult | None:
        """
        Analyze a sequence of logs and return a PatternResult.

        Returns None if there are not enough logs to produce
        a meaningful result (fewer than MIN_LOGS_FOR_PATTERN).

        Logs should be sorted by logged_date ascending before
        passing to this method. The engine does not re-sort —
        sort order matters for trend detection.
        """
        if len(logs) < MIN_LOGS_FOR_PATTERN:
            return None

        user_id = logs[0].user_id
        sorted_logs = sorted(logs, key=lambda l: l.logged_date)

        onset_range = self._detect_onset_range(sorted_logs)
        escalation = self._detect_escalation_speed(sorted_logs, onset_range)
        clusters = self._detect_symptom_clusters(sorted_logs)
        phase_patterns = self._build_phase_patterns(sorted_logs)
        trend = self._detect_severity_trend(sorted_logs)
        prediction = self._build_prediction(sorted_logs, phase_patterns)
        cycles_analyzed = self._estimate_cycles(sorted_logs)

        return PatternResult(
            id=uuid4(),
            user_id=user_id,
            generated_at=datetime.utcnow(),
            cycles_analyzed=cycles_analyzed,
            total_logs=len(sorted_logs),
            symptom_onset_range=onset_range,
            escalation_speed=escalation,
            symptom_clusters=clusters,
            phase_patterns=phase_patterns,
            severity_trend=trend,
            prediction=prediction,
        )

    def generate_early_feedback(
        self,
        logs: list[DailyLog],
    ) -> EarlyFeedback | None:
        """
        Generate a single early feedback sentence for the Home screen.

        Returns None if there are not enough logs or no clear
        observation can be made honestly.

        Called every 5–7 days during the day 7–30 window.
        """
        if len(logs) < MIN_LOGS_FOR_FEEDBACK:
            return None

        sorted_logs = sorted(logs, key=lambda l: l.logged_date)
        user_id = sorted_logs[0].user_id
        message, trigger_phase = self._pick_feedback_message(sorted_logs)

        if message is None:
            return None

        return EarlyFeedback(
            user_id=user_id,
            message=message,
            generated_at=datetime.utcnow(),
            log_count=len(sorted_logs),
            trigger_phase=trigger_phase,
        )

    # ------------------------------------------------------------------
    # Onset detection
    # ------------------------------------------------------------------

    def _detect_onset_range(
        self,
        logs: list[DailyLog],
    ) -> tuple[int, int]:
        """
        Find the typical cycle day range when symptoms begin.

        For each cycle present in the logs, find the first day
        where pain >= ONSET_THRESHOLD. Collect those cycle days
        and return (min, max) as the onset range.

        Falls back to (1, len(logs)) if no onset days are found.
        """
        onset_days: list[int] = []

        # Group logs by their approximate cycle number
        cycles = self._group_by_cycle(logs)

        for cycle_logs in cycles.values():
            onset = self._find_onset_day(cycle_logs)
            if onset is not None:
                onset_days.append(onset)

        if not onset_days:
            # No clear onset detected — return a wide range
            all_days = [l.cycle_day for l in logs]
            return (min(all_days), max(all_days))

        return (min(onset_days), max(onset_days))

    def _find_onset_day(self, logs: list[DailyLog]) -> int | None:
        """
        Find the first cycle day in this log sequence where pain
        meets the onset threshold. Returns None if no such day exists.
        """
        sorted_logs = sorted(logs, key=lambda l: l.cycle_day)
        for log in sorted_logs:
            if log.pain_level.value >= ONSET_THRESHOLD:
                return log.cycle_day
        return None

    # ------------------------------------------------------------------
    # Escalation speed
    # ------------------------------------------------------------------

    def _detect_escalation_speed(
        self,
        logs: list[DailyLog],
        onset_range: tuple[int, int],
    ) -> EscalationSpeed:
        """
        Measure how quickly pain rises from the onset day to peak.

        For each cycle, find the onset day and the peak pain day.
        Calculate the gap in days between them.
        Average the gaps across cycles and classify.
        """
        gaps: list[int] = []
        cycles = self._group_by_cycle(logs)

        for cycle_logs in cycles.values():
            sorted_cycle = sorted(cycle_logs, key=lambda l: l.cycle_day)
            onset_day = self._find_onset_day(sorted_cycle)
            if onset_day is None:
                continue

            # Find peak pain day at or after onset
            post_onset = [l for l in sorted_cycle if l.cycle_day >= onset_day]
            if not post_onset:
                continue

            peak_log = max(post_onset, key=lambda l: l.pain_level.value)
            gap = peak_log.cycle_day - onset_day
            gaps.append(gap)

        if not gaps:
            return EscalationSpeed.UNKNOWN

        avg_gap = sum(gaps) / len(gaps)

        if avg_gap <= 1:
            return EscalationSpeed.SHARP
        if avg_gap <= 3:
            return EscalationSpeed.MODERATE
        return EscalationSpeed.GRADUAL

    # ------------------------------------------------------------------
    # Symptom clustering
    # ------------------------------------------------------------------

    def _detect_symptom_clusters(
        self,
        logs: list[DailyLog],
    ) -> list[SymptomCluster]:
        """
        Find symptom pairs that co-occur on high-pain days.

        High-pain days: pain_level >= HIGH_PAIN_THRESHOLD.
        A pair forms a cluster if it appears together on at least
        CLUSTER_MIN_OCCURRENCE_RATE fraction of high-pain days.

        Only considers days where the dominant_symptom co-occurs
        with other symptoms from the same log sequence on that phase.
        We approximate co-occurrence using the dominant symptom
        alongside the most common symptom in the same phase window.
        """
        high_pain_logs = [l for l in logs if l.pain_level.value >= HIGH_PAIN_THRESHOLD]

        if len(high_pain_logs) < 3:
            return []

        # Build phase-level symptom co-occurrence
        phase_symptoms: dict[CyclePhase, list[Symptom]] = defaultdict(list)
        for log in high_pain_logs:
            phase_symptoms[log.cycle_phase].append(log.dominant_symptom)

        clusters: list[SymptomCluster] = []

        for phase, symptoms in phase_symptoms.items():
            if len(symptoms) < 2:
                continue

            counts = Counter(symptoms)
            total = len(symptoms)

            # Find the top two symptoms in this phase
            top_two = counts.most_common(2)
            if len(top_two) < 2:
                continue

            symptom_a, count_a = top_two[0]
            symptom_b, count_b = top_two[1]

            # Use the lower count as a conservative co-occurrence estimate
            co_occurrence_rate = min(count_a, count_b) / total

            if co_occurrence_rate < CLUSTER_MIN_OCCURRENCE_RATE:
                continue

            if symptom_a == symptom_b:
                continue

            try:
                cluster = SymptomCluster(
                    symptoms=frozenset({symptom_a, symptom_b}),
                    typical_phase=phase,
                    occurrence_rate=round(co_occurrence_rate, 2),
                )
                clusters.append(cluster)
            except ValueError:
                continue

        return clusters

    # ------------------------------------------------------------------
    # Phase patterns
    # ------------------------------------------------------------------

    def _build_phase_patterns(
        self,
        logs: list[DailyLog],
    ) -> list[PhasePattern]:
        """
        Build a PhasePattern for each phase that has enough logs.

        Returns patterns ordered by average_pain descending so the
        most burdensome phase appears first.
        """
        phase_logs: dict[CyclePhase, list[DailyLog]] = defaultdict(list)

        for log in logs:
            if log.cycle_phase.is_known:
                phase_logs[log.cycle_phase].append(log)

        patterns: list[PhasePattern] = []

        for phase, phase_log_list in phase_logs.items():
            if not phase_log_list:
                continue

            avg_pain = sum(l.pain_level.value for l in phase_log_list) / len(phase_log_list)
            avg_energy = sum(l.energy_level.value for l in phase_log_list) / len(phase_log_list)

            symptom_counts = Counter(l.dominant_symptom for l in phase_log_list)
            dominant = [s for s, _ in symptom_counts.most_common(3)]

            cycle_days = [l.cycle_day for l in phase_log_list]
            onset_range = (min(cycle_days), max(cycle_days))

            trend = self._detect_phase_trend(phase_log_list)

            patterns.append(PhasePattern(
                phase=phase,
                onset_day_range=onset_range,
                average_pain=round(avg_pain, 2),
                average_energy=round(avg_energy, 2),
                dominant_symptoms=dominant,
                severity_trend=trend,
                log_count=len(phase_log_list),
            ))

        return sorted(patterns, key=lambda p: p.average_pain, reverse=True)

    def _detect_phase_trend(self, logs: list[DailyLog]) -> SeverityTrend:
        """
        Detect the trend within a single phase's logs by comparing
        the first half to the second half chronologically.
        """
        if len(logs) < 4:
            return SeverityTrend.INSUFFICIENT_DATA

        sorted_logs = sorted(logs, key=lambda l: l.logged_date)
        midpoint = len(sorted_logs) // 2
        first_half = sorted_logs[:midpoint]
        second_half = sorted_logs[midpoint:]

        avg_first = sum(l.pain_level.value for l in first_half) / len(first_half)
        avg_second = sum(l.pain_level.value for l in second_half) / len(second_half)

        return self._classify_trend(avg_first, avg_second)

    # ------------------------------------------------------------------
    # Overall severity trend
    # ------------------------------------------------------------------

    def _detect_severity_trend(self, logs: list[DailyLog]) -> SeverityTrend:
        """
        Detect whether overall symptom severity is escalating,
        improving, stable, or variable across the full log window.

        Splits logs chronologically and compares average pain
        between the two halves.
        """
        if len(logs) < 6:
            return SeverityTrend.INSUFFICIENT_DATA

        midpoint = len(logs) // 2
        first_half = logs[:midpoint]
        second_half = logs[midpoint:]

        avg_first = sum(l.pain_level.value for l in first_half) / len(first_half)
        avg_second = sum(l.pain_level.value for l in second_half) / len(second_half)

        return self._classify_trend(avg_first, avg_second)

    def _classify_trend(
        self,
        avg_first: float,
        avg_second: float,
    ) -> SeverityTrend:
        """
        Classify a trend given two average pain values.

        ESCALATING:  second half is more than TREND_CHANGE_THRESHOLD higher
        IMPROVING:   second half is more than TREND_CHANGE_THRESHOLD lower
        STABLE:      within threshold
        VARIABLE:    avg_first is 0 (edge case guard)
        """
        if avg_first == 0:
            return SeverityTrend.VARIABLE

        change = (avg_second - avg_first) / avg_first

        if change > TREND_CHANGE_THRESHOLD:
            return SeverityTrend.ESCALATING
        if change < -TREND_CHANGE_THRESHOLD:
            return SeverityTrend.IMPROVING
        return SeverityTrend.STABLE

    # ------------------------------------------------------------------
    # Cycle prediction
    # ------------------------------------------------------------------

    def _build_prediction(
        self,
        logs: list[DailyLog],
        phase_patterns: list[PhasePattern],
    ) -> CyclePrediction | None:
        """
        Build a soft next-cycle prediction from phase patterns.

        Only attempted if:
        - At least 2 estimated cycles are present in the logs
        - At least one phase pattern has sufficient data
        - The most burdensome phase is known

        Confidence is derived from how consistent the onset range
        is across cycles — a narrow onset range = higher confidence.
        """
        cycles = self._estimate_cycles(logs)
        if cycles < 2:
            return None

        if not phase_patterns:
            return None

        most_burdensome = phase_patterns[0]
        if not most_burdensome.phase.is_known:
            return None

        onset_start, onset_end = most_burdensome.onset_day_range
        onset_spread = onset_end - onset_start

        # Confidence decreases as the onset range widens
        # Spread of 0 = max confidence, spread of 14+ = low confidence
        confidence = max(0.1, round(1.0 - (onset_spread / 14), 2))

        try:
            return CyclePrediction(
                high_symptom_day_range=most_burdensome.onset_day_range,
                predicted_dominant_phase=most_burdensome.phase,
                confidence=confidence,
                basis_cycles=cycles,
            )
        except ValueError:
            return None

    # ------------------------------------------------------------------
    # Early feedback
    # ------------------------------------------------------------------

    def _pick_feedback_message(
        self,
        logs: list[DailyLog],
    ) -> tuple[str | None, CyclePhase | None]:
        """
        Pick the most honest and useful observation to show on the Home screen.

        Priority order:
        1. Phase-specific pain pattern (most informative)
        2. Energy-pain relationship
        3. Consistency acknowledgement (always available as fallback)

        Returns (message, trigger_phase) or (None, None).
        """
        # Check for a phase-specific pain pattern
        phase_logs: dict[CyclePhase, list[DailyLog]] = defaultdict(list)
        for log in logs:
            if log.cycle_phase.is_known:
                phase_logs[log.cycle_phase].append(log)

        # Find the phase with the highest average pain
        if phase_logs:
            highest_phase = max(
                phase_logs.items(),
                key=lambda kv: sum(l.pain_level.value for l in kv[1]) / len(kv[1]),
            )
            phase, phase_log_list = highest_phase
            avg_pain = sum(l.pain_level.value for l in phase_log_list) / len(phase_log_list)

            if avg_pain >= ONSET_THRESHOLD:
                return (
                    f"You tend to log higher pain during your "
                    f"{phase.display_name.lower()} phase.",
                    phase,
                )

        # Check for energy preceding pain
        high_pain_logs = [l for l in logs if l.pain_level.value >= HIGH_PAIN_THRESHOLD]
        if len(high_pain_logs) >= 2:
            # Check if energy was low on the day before high pain days
            low_energy_before_pain = 0
            log_by_date = {l.logged_date: l for l in logs}

            for log in high_pain_logs:
                prev_date = log.logged_date - __import__("datetime").timedelta(days=1)
                prev_log = log_by_date.get(prev_date)
                if prev_log and prev_log.energy_level.is_low():
                    low_energy_before_pain += 1

            if low_energy_before_pain >= 2:
                return (
                    "Energy drops often appear the day before your highest-pain days.",
                    None,
                )

        # Consistency fallback — always honest, never fabricated
        if len(logs) >= MIN_LOGS_FOR_FEEDBACK:
            return (
                f"You've logged {len(logs)} days in a row. "
                "That's building a clearer picture.",
                None,
            )

        return (None, None)

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    def _group_by_cycle(
        self,
        logs: list[DailyLog],
    ) -> dict[int, list[DailyLog]]:
        """
        Group logs into approximate cycles based on cycle_day resets.

        A new cycle starts when cycle_day goes from a high value
        back to a low value (day 1–5 after day 15+).
        Returns a dict of {cycle_index: [logs]}.
        """
        if not logs:
            return {}

        cycles: dict[int, list[DailyLog]] = defaultdict(list)
        cycle_index = 0
        prev_day = logs[0].cycle_day

        for log in logs:
            if log.cycle_day < prev_day and prev_day > 14:
                # Cycle reset detected
                cycle_index += 1
            cycles[cycle_index].append(log)
            prev_day = log.cycle_day

        return dict(cycles)

    def _estimate_cycles(self, logs: list[DailyLog]) -> int:
        """
        Estimate the number of cycles represented in the log sequence.
        Uses cycle resets detected in _group_by_cycle.
        Minimum return value is 1 if any logs are present.
        """
        if not logs:
            return 0
        return max(1, len(self._group_by_cycle(logs)))
