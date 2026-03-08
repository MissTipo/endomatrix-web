# Domain Models

Core domain models for EndoMatrix’s symptom, cycle, pattern, and audit-event logic.

This package defines the language of the domain. It is where the system expresses facts such as:

- what a symptom is
- what cycle phase means
- what a valid daily log looks like
- what counts as a pattern result
- what domain events must be recorded for auditability

These models are intentionally small, explicit, and validation-heavy. They are designed to support longitudinal symptom intelligence and phase-aware insights while keeping a strict boundary between domain truth and UI or infrastructure concerns.

## Design goals

### 1. Domain-first, not UI-first
The models represent business meaning, not storage shape or transport format.

A symptom is a domain concept.  
A cycle phase is a domain concept.  
A pattern result is a domain concept.  

The UI, API, and database adapt to these models, not the other way around.

### 2. Validation at construction time
Invalid state should be hard to represent.

Where possible, constraints are enforced when the object is created instead of being deferred to services, forms, or controllers.

Examples:
- note length is capped in the domain
- cycle length is validated in the baseline
- predictions require enough historical basis to be meaningful

### 3. Explicit uncertainty
Unknown is treated as a valid domain state where appropriate.

For example, `CyclePhase.UNKNOWN` is not the same thing as missing data. It is a first-class value that allows the engine to represent irregular or currently unclassifiable cycles honestly.

### 4. Stable semantics
Ordering and exported names are deliberate.

Some values are intentionally ordered to stay stable across the system, especially where UI rendering depends on consistent presentation.

### 5. Renderable outcomes
Pattern-facing models are shaped around what the product can actually show to the user.

`PatternResult` is not just an internal computation artifact. It is the domain representation of what the Insights experience can render.

### 6. Auditability
User-facing health systems need durable records for sensitive actions such as consent capture and deletion requests.

Domain events exist to preserve that trail.

## Module overview

### `symptom.py`
Defines the `Symptom` enum.

This enum is intentionally ordered:

1. physical symptoms
2. systemic symptoms
3. `OTHER` last

That ordering is stable by design and mirrors the product’s dropdown behavior. This avoids accidental UI drift and keeps symptom presentation deterministic.

It also owns symptom classification helpers such as:

- `is_physical()`
- `is_systemic()`

These methods belong on the enum because they describe facts about symptoms themselves, not about any specific user record.

### `cycle.py`
Defines cycle-related primitives:

- `CyclePhase`
- `CycleBaseline`
- `Score`

#### `Score`
`Score` is a value object.

A score of `7` should mean the same thing everywhere in the system and compare equal wherever it appears. Treating it as an immutable value object makes that intent explicit and prevents score semantics from drifting across features.

#### `CyclePhase`
`CyclePhase.UNKNOWN` is a first-class value.

It exists to model real uncertainty and irregularity without pretending the phase is known or silently dropping the state.

#### `CycleBaseline`
`CycleBaseline` validates cycle length in the range `21..45` days.

That range is treated as the accepted normal domain input for baseline modeling. Values outside it are assumed to be far more likely to reflect bad input than a usable baseline for the current engine.

### `daily_log.py`
Defines `DailyLog`.

This model carries both current and near-term fields together, including optional MVP-era fields such as:

- `mood_level`
- `note`

These fields are optional from the start so the model can evolve without painful retrofits to a frozen dataclass later.

The `note` field is domain-validated with a maximum length of `280` characters. This rule is enforced here because UI constraints are not security or integrity guarantees.

### `pattern.py`
Defines the pattern-analysis output models, including:

- `PatternResult`
- `SymptomCluster`
- `PatternWindow`
- `CyclePrediction`
- `SeverityTrend`
- `EscalationSpeed`

This is the highest-value model set in the package because it expresses the longitudinal insight layer.

#### `PatternResult`
`PatternResult` is the domain contract for the Insights experience.

Every field on it should correspond to something the product can meaningfully render. If a field cannot be surfaced or explained, it likely does not belong here.

#### `CyclePrediction`
Predictions require at least **two basis cycles**.

A single cycle is an observation, not a prediction. This guard exists to preserve semantic honesty in the product.

#### `EarlyFeedback`
Where present, early feedback requires at least **three logs** for the same reason: the engine should not overstate confidence from insufficient input.

### `events.py`
Defines domain events.

These events are the audit trail for sensitive lifecycle actions and system facts.

Examples include:
- deletion requested
- consent recorded

#### `DataDeletionRequested`
This event is retained even after deletion completes.

The underlying user data may be erased, but the fact that deletion was requested and processed remains part of the compliance and audit trail.

#### `ConsentRecorded`
Consent includes a version string.

Consent language evolves. A durable record must capture not just that consent happened, but exactly which version of the consent text the user agreed to.

### `__init__.py`
Provides the package’s clean public exports.

The goal is to make imports predictable and to expose a stable public surface for the rest of the domain and application layers.

## Principles encoded in these models

### Immutability where identity should not drift
Value-like concepts should be frozen and comparable.

### Optional does not mean unimportant
Some fields are optional because they are not always available, not because they are secondary.

### Domain rules live in the domain
Validation belongs here when violating the rule would create invalid business state.

### Predictions need enough evidence
The system should prefer “not enough basis yet” over false confidence.

### Audits outlive operational state
Some events must remain recorded even when the associated user data no longer exists in its original form.

## What does not belong here

These models should not contain:

- persistence concerns
- ORM behavior
- API serialization glue
- UI formatting rules
- analytics/reporting hacks
- diagnosis or treatment claims

This package models structure and meaning. It does not make medical decisions.

## Usage

Prefer importing from the package root when possible:

```python
from domain.models import (
    Symptom,
    CyclePhase,
    CycleBaseline,
    Score,
    DailyLog,
    PatternResult,
)
```
## Maintenance notes

  - When changing this package:

  - preserve stable enum ordering unless a migration is intentional

  - keep invariants enforced close to object creation

  - treat UNKNOWN states as meaningful, not accidental

  - keep PatternResult aligned with what the Insights UI can actually render

  - add new domain events when auditability matters

  - export only the package surface you want downstream code to rely on

## Why this package matters

These models are the foundation for representing hormone-aware, longitudinal symptom data in a way that is explicit, auditable, and honest about uncertainty.

They exist to make the rest of the system simpler:

  - services can rely on validated inputs

  - the UI can render stable structures

  - the engine can reason over clear concepts

  - compliance-sensitive actions can be traced
