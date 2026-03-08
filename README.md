# EndoMatrix Core

A cycle-aware symptom pattern interpreter that transforms daily logs into longitudinal insight — helping users understand when their body gets worse, how it shows up, and what to expect next.

> Pattern recognition and interpretation. Not diagnosis.

---

## What this is

Most cycle trackers answer one question: when is my next period? EndoMatrix answers a different one: **why does my body feel the way it does, and when will it happen again?**

Users log three signals per day. The system learns their personal baseline, maps symptoms to cycle phases, and after 30 days produces an insight page that shows patterns the user could not see on their own. The goal is a single moment of recognition: *I'm not imagining this. I can prove it. I can plan around it.*

---

## Screens

### 1. Onboarding
*First open only. Under 2 minutes.*

| Screen | What the user sees |
|---|---|
| Welcome | App name, one-line purpose, single CTA: Get started |
| Intent | "What brings you here?" — one of four options: chronic menstrual pain, irregular cycles, severe PMS, just trying to understand my body |
| Cycle baseline | Last period start date (date picker) + average cycle length (or "irregular / not sure") |
| Expectation setting | "We won't diagnose you. We help you notice patterns you couldn't see before." — single continue button |

The system infers cycle phase silently from this point forward. The user never selects a phase manually.

---

### 2. Home
*The screen you open every day.*

| Element | Description |
|---|---|
| Phase indicator | Current inferred cycle phase shown at the top (e.g. "Luteal phase · Day 22") |
| Log prompt | If today has no log: a single prompt card — "Log today · 10 seconds" |
| Logged state | If today is already logged: a quiet confirmation showing the pain and energy values recorded |
| Early feedback card | Appears from day 7 onward, one sentence only: e.g. "You tend to log higher pain around this point in your cycle." Refreshes every 5–7 days. |
| Streak indicator | A subtle count of consecutive days logged. Motivation without pressure. |

No charts. No summaries. Nothing that competes with the habit of logging.

---

### 3. Daily Log
*One screen. No scrolling.*

| Input | Type | Detail |
|---|---|---|
| Pain today | Slider 0–10 | Neutral label, no emoji |
| Energy level | Slider 0–10 | Neutral label, no emoji |
| Dominant symptom | Single-select dropdown | Pelvic pain, lower back pain, leg pain, bloating, nausea, headache, acne flare, mood crash, brain fog, insomnia, other |
| Log button | Full-width CTA | "Log today" |

After logging: "Saved. See you tomorrow." Nothing else.

Cycle day and phase are attached to the log silently by the system.

---

### 4. History
*A calendar view of every logged day.*

| Element | Description |
|---|---|
| Monthly calendar | Each day shows a colored intensity dot based on pain level: light to deep |
| Day tap | Tapping any logged day opens a small card showing the pain score, energy score, and dominant symptom recorded |
| Empty days | Days with no log shown as empty circles — no guilt, no streak-breaking language |
| Month navigation | Swipe or arrow to move between months |
| Phase banding | Subtle background color bands on the calendar showing inferred cycle phases across the month |

This screen gives users a visual sense of the shape of their month before the 30-day insight unlocks.

---

### 5. Insights
*Locked until 30 days of logs exist.*

**Before unlock — teaser state:**

A preview of the insight page with all content blurred or masked. Overlaid with:
- A progress indicator: "Day 14 of 30 — keep logging to unlock your pattern"
- Three masked section titles visible through the blur: "When symptoms begin", "How severity changes", "What travels together"
- A single line: "Your pattern is forming. Check back after 30 days."

The teaser communicates what is coming without fabricating data.

**After unlock — full insight page:**

| Section | Content |
|---|---|
| When symptoms begin | Which cycle days your symptoms typically start, shown as a range not a single day |
| How severity changes | How quickly pain and energy shift from onset — gradual or sharp |
| What travels together | Which symptoms cluster: e.g. "mood crash and brain fog appear together on your highest-pain days" |
| Trend over time | Whether the logged period shows stable, variable, or escalating severity |
| What to expect | Soft predictive framing for the next cycle: "Based on your pattern, days 20–25 may be your most symptomatic" |

All language uses qualifiers: "so far", "based on your data", "this may change as we learn more."

---

### 6. Export
*Available after the first insight unlocks.*

A single clean page summarising the insight in a format designed for clinical conversations.

| Element | Description |
|---|---|
| Summary header | Date range, number of cycles logged, cycle length average |
| Symptom timeline | A clean visual showing when in the cycle symptoms typically appear |
| Severity pattern | Pain and energy averages by phase |
| Dominant symptoms by phase | Which symptoms appeared most in each phase |
| Escalation note | Whether severity increased, decreased, or held steady across the logged period |
| Export options | Download as PDF or share as image |

The user controls if and when this is shared. Nothing is sent anywhere automatically.

---

### 7. Settings
*Utility screen.*

| Option | Description |
|---|---|
| Daily reminder | Toggle on/off, set preferred time |
| Cycle info | Edit last period date and average cycle length |
| Account | Email, change password, delete account |
| Privacy | View what data is stored, request full export, delete all data |
| About | Version, non-diagnostic disclaimer, link to endomatrixlabs.tech |

---

## MVP additions
*Shipped after v0 validation. The core screens stay the same — these extend them.*

**Daily log gains two optional inputs:**
- Mood level (0–10 slider) — fourth slider, same neutral treatment as pain and energy
- Free text note — one sentence maximum, optional, appears below the log button

**Insights page gains one new section:**
- Cycle comparison: this cycle versus the previous cycle, side by side, same phase windows

**History calendar gains:**
- Mood overlaid as a secondary dot color alongside pain intensity

**Wearable data (optional, user-initiated):**
- Resting heart rate, HRV, skin temperature, sleep duration ingested as supplementary signals
- Shown in the Insights page as supporting context alongside logged data
- Never the primary signal — the daily log always anchors the pattern

---

## Roadmap
*Not in scope until MVP is validated.*

- SMS/USSD interface for low-connectivity access
- Clinician export with structured symptom timeline format
- Perimenopause and menopause logging cohort
- Population analytics layer — EndoMatrix Sentinel

---

## Architecture

Hexagonal architecture (ports and adapters). The domain layer has zero framework dependencies and is fully testable in isolation.

```
endomatrix/
├── apps/
│   ├── web/                    ← Next.js PWA (TypeScript)
│   └── api/                    ← FastAPI (Python)
│       ├── domain/             ← Pure Python. No FastAPI. No SQLAlchemy.
│       │   ├── models/         ← DailyLog, CyclePhase, Symptom, PatternResult
│       │   ├── services/       ← PatternEngine, PhaseCalculator (pure functions)
│       │   └── ports/          ← ILogRepository, IPatternStore (ABCs)
│       ├── application/        ← Use cases: LogDailyEntry, GetPatternSummary
│       ├── infrastructure/     ← SQLAlchemy models, Alembic migrations, repo implementations
│       └── presentation/       ← FastAPI routers, Pydantic schemas, middleware
└── packages/
    └── shared-types/           ← TypeScript types generated from FastAPI OpenAPI schema
```

---

## Tech stack

| Layer | Technology |
|---|---|
| Frontend | Next.js + TypeScript + Tailwind |
| Backend | FastAPI (Python) |
| Database | PostgreSQL |
| ORM / Migrations | SQLAlchemy + Alembic |
| Auth | Clerk |
| Deployment | GCP Cloud Run (API) + Vercel (web) |
| Secrets | GCP Secret Manager |
| Observability | Prometheus + Grafana + Loki |
| Shared types | openapi-typescript (generated from FastAPI schema) |

---

## Data and privacy

- **Audit log**: every mutation to health data writes an immutable append-only event to `audit_events` — ships from day one, not a later addition
- **Data minimisation**: the daily log captures only what pattern detection requires
- **No third-party data sharing**: user-level data never leaves the platform
- **Consent**: explicit, versioned, checked before every data write
- **User data export and deletion**: available from settings at any time

---

## Status

| Milestone | Status |
|---|---|
| Architecture and domain design | In progress |
| Onboarding | Not started |
| Daily log | Not started |
| Home screen + early reinforcement | Not started |
| History calendar | Not started |
| Insights teaser + 30-day summary | Not started |
| Export / share | Not started |
| MVP: mood + notes + cycle comparison | Not started |
| MVP: wearable ingestion | Not started |
| Beta (50 users) | Targeted Q1 2026 |

---

## Related

- [EndoMatrix Labs](https://endomatrixlabs.tech) — company and Sentinel overview
- [EndoMatrix Sentinel](https://endomatrixlabs.tech/#products) — population health early warning layer
