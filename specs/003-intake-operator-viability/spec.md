# Feature Specification: Natural-Language Intake, Operator Channel and Viability View

**Feature ID:** 003
**Short name:** intake-operator-viability
**Status:** Draft
**Created:** 2025-07-17
**Last updated:** 2025-07-17

---

## Overview

Cargo owners want to describe a shipment in plain language rather than filling a form.
Boat operators want to register availability via a text message. Planners need a quick
visual to understand where water is economically competitive along Kerala's inland
waterway corridors. This feature provides a natural-language intake path for cargo owners,
a scripted chat mock for boat operators, and a break-even and corridor viability view for
planners — all with offline fallbacks.

---

## Problem Statement

A structured form is a friction barrier for first-time users. A cargo owner should be
able to type "10 tonnes sand Kochi to Alappuzha by 6 PM tomorrow" and have the system
understand it. A boat operator should be able to register capacity availability in the
same way they communicate today — a short text message. And a planner needs to quickly
see which corridors are worth prioritising for waterway logistics, without having to run
individual shipment comparisons.

---

## Clarifications

### Session 2025-07-17

- Q: What currency and weight units are displayed? → A: INR (₹ in UI, "Rs." in text).
  Weights in tonnes.
- Q: How does "tomorrow" resolve, and what defaults apply when only a date is given? → A:
  "Tomorrow" resolves relative to the current date in IST. Ready time defaults to 08:00
  IST; deadline defaults to 18:00 IST when only a date is provided.
- Q: What happens when the language service is unavailable? → A: The system falls back to
  the regex extractor (FR-3). If regex also fails to extract a field, that field is left
  blank for manual entry. The UI MUST NOT show an unhandled error.
- Q: What is "best effort" for Malayalam parsing? → A: Malayalam input is passed as-is to
  the language service. The offline regex fallback handles English patterns only and
  returns null for Malayalam fields it cannot parse. Failures fall back silently to the
  manual form with no crash.
- Q: What accessibility requirements apply to the intake form and viability view? → A:
  Readable contrast (WCAG AA). Every badge, corridor colour indicator, and confidence
  warning MUST have a text label; colour alone MUST NOT be the only indicator.
- Q: What edge cases apply to the break-even formula? → A: If r ≤ w the function returns
  `not_viable` with reason "road rate not greater than water rate". See FR-6.
- Q: What edge cases apply to the corridor map when seed data is incomplete? → A: See
  FR-10 (Edge Cases) below.

---

## Actors

| Actor | Role |
|---|---|
| Cargo owner | Types a free-text shipment description; reviews and corrects the parsed result |
| Boat operator | Sends a plain-text availability message; sees a structured listing and a scripted reply |
| Planner | Views the break-even chart and corridor map |
| Language service | External dependency (LLM or regex fallback) that extracts structured fields |

---

## User Stories

### P1 — Natural-language shipment intake

As a cargo owner, I type a free-text description such as "10 tonnes sand Kochi to
Alappuzha by 6 PM tomorrow" (in English or Malayalam) and see it converted into a
structured shipment form pre-filled with the extracted fields. All weight fields are shown
in tonnes; monetary fields (if surfaced) use ₹. Times are shown and resolved in IST;
"tomorrow" resolves relative to the current date. I can correct any field before
proceeding. I see a confidence indicator for the parse. If the language service is
unavailable, I receive a result from the offline fallback (regex parser or blank
pre-filled form) — the screen never crashes or shows an unhandled error. Every confidence
badge and status warning has a text label; colour alone is not used to convey meaning.

### P2 — Boat operator scripted chat

As a boat operator, I send a plain-text availability message such as "12 ton barge,
Vaikom, free tomorrow, going Alappuzha" and see:
1. A structured vessel listing (capacity in t, home port, availability date in IST,
   destination) that I can review.
2. A scripted confirmation reply acknowledging my availability.
3. A backhaul offer based on open cargo near my route (weight in t, cost in ₹), which I
   can accept or decline with one action.

The operator chat in the demo is scripted: fixed messages trigger fixed responses, with
no live chat infrastructure required.

### P2 — Viability break-even chart

As a planner, I see a break-even chart that shows, for a range of water-leg distances
(km), the cost per tonne (₹/t) for road versus hybrid. The break-even distance is
computed from `d* = F / (r - w)` where F, r, and w are read from configuration. All
values are tagged "estimated". The chart axes and legend are labelled; no information is
conveyed by colour alone.

### P2 — Corridor map

As a planner, I see a Kerala corridor map (a simple diagram, not a live map tile) with
corridors coloured:
- Green — water is competitive (hybrid cheaper than road by a configured margin)
- Amber — water is marginal (within the margin)
- Red — water is not competitive (road is cheaper by the margin)

Each corridor label shows estimated CO₂ saving (kg/t) and cost saving (₹/t), both tagged
"estimated". Colour indicators have text labels. At least one green and one red corridor
appear with the seed data.

### P3 — Demand summary

As a planner, I see a simple count of simulated cargo requests per corridor, derived from
the seed data, as a table or bar view.

---

## Functional Requirements

**FR-1 — Language extraction**
The intake function accepts a free-text string and returns a structured shipment object
with extracted fields: cargo_type, weight_t (tonnes), origin_text, destination_text,
deadline_text. Times are interpreted in IST; "tomorrow" resolves relative to the current
date in IST; when only a date is given, ready_time defaults to 08:00 IST and deadline
defaults to 18:00 IST.

Origin and destination text is matched against the known node list using a two-stage
approach: Stage 1 — case-insensitive substring match against each node's `name` and
`alternate_names` list; Stage 2 (if no Stage 1 match) — rapidfuzz WRatio fuzzy match
with a score cutoff read from `data/config.yaml` (`fuzzy_match_cutoff`, default 70,
`source_status: assumed`). Both stages are deterministic over fixed node data and config.

If a place name cannot be matched by either stage, the field is returned as `null` with
a reason, and the user is prompted to select from the node list.

**FR-2 — Confidence scoring**
The extraction result includes a `confidence` score (0.0–1.0). If confidence is below a
configured threshold, the structured form is shown with a visible low-confidence warning
(text label, not colour only) and all fields are editable. If confidence meets or exceeds
the threshold, the form is still shown and editable, but without the warning.

**FR-3 — Offline fallback**
If the language service (LLM) is unavailable or returns an error, the system falls back
to a regex-based extractor that handles common numeric-unit-place patterns (e.g.
"10 tonnes", "Kochi to Alappuzha", "by 6 PM"). The regex extractor handles English
patterns only; Malayalam fields it cannot parse are returned as null for manual entry.
If the regex extractor also fails to extract a field, that field is left blank. The
fallback MUST NOT raise an unhandled exception visible to the user. The demo MUST work
with the regex fallback alone (no LLM required).

**FR-4 — Operator scripted chat**
The demo contains a fixed set of operator input strings mapped to fixed structured outputs
and scripted reply messages. Inputs that do not match a scripted entry return a
"not recognised — please use the manual form" message. The scripted map is stored in
`data/seed.json`, not in application source.

**FR-5 — Backhaul offer in operator chat**
After a scripted operator availability message is processed, the engine runs the same
backhaul matching logic from Feature 002 against the registered availability and open
cargo requests, and returns the top suggestion for the operator to accept or decline.
The suggestion shows weight (t) and estimated cost effect (₹) tagged with source_status.

**FR-6 — Break-even calculation**
The break-even distance `d*` is computed deterministically as:

```
d* = F_total / r
```

where:
- `F_total = loading_cost_per_t + unloading_cost_per_t + water_freight_rate_per_t`
  (total fixed hybrid overhead per tonne, ₹)
- `r = road_rate_per_tkm` (road cost per tonne-km, ₹/tonne-km)

All three values are read from `data/config.yaml`. The water variable cost (`w`) is
treated as approximately zero for short Kerala backwater routes, making `F_total` the
fixed overhead that the road cost must overcome (`source_status: assumed`, noted as
"water variable cost treated as ~0 for Kerala IWT routes").

If `r = 0`, the function returns a `not_viable` result with the reason "road rate is
zero — break-even distance undefined". All input values and the computed result carry
`source_status: assumed` and are labelled "estimated" in the UI.

**Note:** The original formulation `d* = F / (r - w)` with explicit water rate per km
was superseded during planning (see research.md R-5) because the per-km representation
of Kerala flat-rate water freight produces `r ≤ w` for most corridor distances, making
the chart uninformative. The adopted formula is behaviourally equivalent when `w ≈ 0`.

**FR-7 — Corridor viability classification**
For each corridor defined in the seed data, the engine computes the hybrid versus road
cost difference using the same cost model as Feature 001. The corridor is classified
green, amber, or red based on a configured margin percentage. CO₂ saving per tonne (kg/t)
is also computed. All figures carry `source_status` and are labelled "estimated". Corridor
colour indicators in the UI MUST have text labels.

**FR-8 — Demand summary**
The demand summary counts open cargo requests per corridor from the seed data and returns
a list of (corridor_label, request_count) pairs, sorted descending. No external data
source is used.

**FR-9 — No personal data**
The extraction function MUST NOT include personal names, phone numbers, or addresses in
the text sent to the language service. Seed data uses only simulated, fictional entities.

**FR-10 — Edge cases**

- *Language service unavailable*: FR-3 fallback applies. The UI shows a notice "Using
  offline parser — some fields may need manual correction." No crash.
- *Place name not in node list*: The field is returned as null; the UI prompts the user to
  select from the node dropdown. No crash; no invented node.
- *Regex also fails to extract a field*: That field is left blank in the pre-filled form.
  The user can fill it manually. No crash.
- *"By 6 PM tomorrow" with no date context*: Resolved relative to current date in IST.
  Ready time defaults to 08:00 IST; deadline is set to 18:00 IST on the resolved date.
- *Break-even: r ≤ w*: FR-6 returns `not_viable`; the chart shows "Water rate equals or
  exceeds road rate — break-even distance is undefined." No crash.
- *Corridor with insufficient seed data to classify*: Corridor is shown with
  classification `unknown` and a note "insufficient data". No crash.
- *Operator message not in scripted map*: Returns "not recognised — please use the manual
  form." No crash, no exception.

---

## Success Criteria

| ID | Criterion | Measurement |
|---|---|---|
| SC-1 | The reference sentence ("10 tonnes sand Kochi to Alappuzha by 6 PM tomorrow") is parsed correctly in 9 out of 10 manual tests | Manual repetition test; LLM and regex fallback both tested |
| SC-2 | The offline fallback (regex) never raises an unhandled exception on any input from the seed test set | Automated pytest with 10 representative inputs including edge cases |
| SC-3 | The corridor map shows at least one green and one red corridor with the seed data | Visual check against seed data |
| SC-4 | All figures on the viability view carry an "estimated" or "assumed" tag | Visual review of every figure |
| SC-5 | All edge cases in FR-10 return structured results without exceptions | Automated pytest covering each edge case |
| SC-6 | Every badge, corridor colour indicator, and confidence warning has a text label; no information conveyed by colour alone | Visual accessibility review |

---

## Key Entities

| Entity | Attributes |
|---|---|
| ParseResult | raw_text, cargo_type, weight_t, origin_text, destination_text, deadline_text (IST), origin_node_id, destination_node_id, confidence, warnings, fallback_used |
| OperatorMessage | raw_text, structured_listing, reply_text, backhaul_offer |
| BreakevenResult | fixed_cost_₹, road_rate_₹_per_tkm, water_rate_₹_per_tkm, breakeven_distance_km, not_viable, not_viable_reason, source_status |
| CorridorViability | corridor_id, label, from_node, to_node, distance_km, hybrid_cost_₹, road_cost_₹, co2_saving_kg_per_t, cost_saving_₹_per_t, classification (green/amber/red/unknown), source_status |
| DemandSummary | corridor_label, request_count |

---

## Out of Scope

- Real WhatsApp, SMS, or messaging infrastructure
- Real operator onboarding or account creation
- Live map tiles or satellite imagery
- Real-time or historical freight demand data
- Weather-based routing
- Forecasting or ML models
- Malayalam keyboard or IME integration beyond accepting Malayalam text as input
- Phonetic or transliteration matching for place names

---

## Assumptions

1. The language service is a stateless function call; conversation history is not
   required (`source_status: assumed`).
2. Node matching uses case-insensitive substring match against node names in the seed
   data; no phonetic or transliteration matching is implemented in this prototype
   (`source_status: assumed`).
3. Malayalam input is passed as-is to the language service; the offline regex fallback
   handles English-language patterns only and returns null for Malayalam fields it cannot
   parse (`source_status: assumed`).
4. The corridor diagram is a static SVG or table layout, not a live map tile.
5. Confidence threshold and corridor margin percentage are read from `data/config.yaml`.
6. All times are in IST. "Tomorrow" resolves relative to the current system date in IST.
7. Ready time defaults to 08:00 IST and deadline defaults to 18:00 IST when only a date
   is provided.
8. Placeholder rates used in the break-even and viability calculations are assumed values
   (`source_status: assumed`); they are not real market quotes.

---

## Constraints (from Constitution)

- The language service MUST only extract fields; it MUST NOT price, rank, score, or
  recommend.
- No personal data is sent to the language service; seed data uses simulated entities only.
- All break-even and viability constants MUST be in `data/config.yaml`.
- The offline fallback MUST be exercised in the test suite.
- The demo MUST work fully offline (regex fallback, no LLM required).
- The scripted operator chat map MUST be in `data/seed.json`, not in source code.
- All viability figures shown to the user MUST be tagged "estimated" or "assumed".
- Every badge, colour indicator, and status warning MUST have a text label; colour alone
  MUST NOT convey information (accessibility requirement).
