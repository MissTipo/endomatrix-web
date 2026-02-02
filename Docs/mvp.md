# The MVP

A cycle-aware symptom pattern interpreter that turns daily logs into a clear, 
phase-based insight summary a user has never seen before.

## The single job of the MVP
**Help one person answer this question:**
  “When does my body reliably get worse, how does it show up, and what can I do before it does?”

## MVP shape
1. **Input:**
User logs **once per day:**
      - Pain level (0–10)
      - Fatigue level (0–10)
      - Mood level (0–10)
      - One dominant symptom (from a predefined list (dropdown, max 1))
      - Optional free text note (one sentence)

2. **Processing:**
Behind the scenes, the app does:
      - Phase bucketing (follicular, ovulatory, luteal, menstrual or simplified equivalents)
      - Rolling pattern detection over 2–3 cycles
      - Symptom clustering by phase
      - Escalation detection (this phase is getting worse over time)
This can be:
      - Simple rule-based logic
      - Basic statistical analysis
      - Assisted by lightweight ML models (later)
      - Even semi-manual at the start
3. **Output:**
Once per cycle, the user gets a single insight page.
Example:
- **What we’re seeing**
  - Over the last 3 cycles, days 20–26 consistently show:
    - Pain spikes averaging 2.3x baseline
    - Fatigue increases starting 3 days earlier each cycle
    - GI symptoms appearing only in this phase
  - **What this means**
    Your most severe symptoms are not random. They cluster predictably in the late luteal 
    phase and are intensifying over time.

  - **What to try next cycle**
    - Reduce physical load starting day 18
    - Schedule rest or remote work days during this window
    - Prepare symptom notes for clinical visits using this summary

## What comes after the MVP
Only if users ask for it:
- Longer-term modeling
- Clinician exports
- Life-stage transitions
- Digital twin language


### STEP 2A: What this web/mobile app actually is (no fluff)

This is not a “women’s health app”.

It is:

  - A private, cycle-aware symptom interpreter for people with chronic menstrual pain.

### STEP 2B: The smallest app that can exist
**Core screens (only 4)**
1. **Daily Check-in (the only thing users must do)**

    - Pain level (0–10 slider)
    - Fatigue level (0–10 slider)
    - One dominant symptom (dropdown)
    - Cycle day selector

        - “I know my cycle day”

        - “Irregular / not sure”

    - Optional: one short note

Time to complete: under 30 seconds


2. **Today at a Glance (very calm, very validating)**

No charts yet. Just text.

Example:

      Today you’re likely in a higher-sensitivity phase.
      Many users report increased pain and fatigue around this point.

This is support, not prediction.

3. **Pattern Insight (this is the product)**

Locked until enough data exists (eg. 30–45 days).

One page. No scrolling fatigue.

Sections:
  - “What repeats”
  - “When symptoms intensify”
  - “How this has changed over time”

This is where the “I’m not crazy” moment happens.

4. Cycle Summary (shareable, optional)

A clean summary users can:
  - Export as PDF
  - Screenshot
  - Bring to a clinician

### STEP 2C: What you explicitly do NOT build yet

Do not build:

  - Community
  - Education library
  - Hormone explanations
  - AI chat
  - Nutrition plans
  - Wearables
  - Notifications spam

Those dilute trust early.

### STEP 2D: Tech stack (lean + credible)

Suggested stack:

  - Frontend: React or React Native (Expo if mobile-first)
  -  Backend: FastAPI
  -  DB: Postgres
  -  Auth: email + password only
  -  Analytics: simple event logging
  -  AI/ML:
      - Start rule-based
      - Add lightweight pattern detection later
      - No “LLM diagnosis” nonsense

We are building interpretation, not prediction.

### STEP 2E: The first “AI” is mostly structure

This is important:
Our early differentiation is how we structure data, not fancy models.

We win by:

  - Phase alignment
  - Longitudinal comparisons
  - Escalation detection

Most competitors flatten time.
We respect it.

### STEP 2F: Success criteria for the MVP

The MVP is successful if one user says any of these:

  - “I finally see the pattern.”
  - “I stopped blaming myself.”
  - “I knew this felt predictable, but I couldn’t prove it.”
  - “This helped me explain my pain better.”
 

### STEP 2G: Timeline (realistic, solo)

- Week 1: UX flows + schema

- Week 2: Daily logging + auth

- Week 3: Phase logic + summaries

- Week 4: Insight generation

- Week 5–6: Polish + private beta

That’s it. No heroics.
