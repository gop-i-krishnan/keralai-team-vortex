# Feature Specification: Vessel Registration and Delivery History

**Feature ID:** 004
**Short name:** vessel-registration-delivery-history
**Status:** Draft
**Created:** 2026-10-07
**Last updated:** 2026-10-07

---

## Overview

The JalSetu supply side currently exists only as static seed data. Boat owners cannot
register their vessels, publish sailings, or build a track record that cargo owners can
trust. This feature lets operators join the network through a short form or a plain-text
message, publish recurring sailings, and accumulate a delivery history that cargo owners
can inspect before choosing a vessel. A Bayesian reliability score ensures new operators
are visible immediately rather than buried by lack of history.

---

## Problem Statement

Cargo owners cannot evaluate an operator they have never used. Operators have no way to
publish availability or credentials. Without a registration and history layer the platform
cannot grow beyond its seed vessels, and the supply-demand match remains fictional. This
feature creates the minimum viable supply-side lifecycle: register → verify (simulated) →
sail → record delivery → build reputation.

---

## Clarifications

### Session 2026-10-07

- Q: What is the canonical currency and weight unit? → A: INR (₹ in UI, "Rs." in text),
  tonnes for weight, metres for draft. IST for all timestamps.
- Q: What vessel types should the type field accept? → A: Open-ended text in the form;
  the seed data uses "cargo barge", "country boat", "mechanised vessel". No fixed enum in
  this prototype — validation only checks the field is non-empty.
- Q: How is "verified" status set in the demo? → A: A demo-admin action (`POST
  /api/admin/vessel/{id}/verify`) sets status to `verified`. The endpoint is accessible
  without authentication (demo-only). The roadmap note in the UI explains that production
  would integrate with the national vessel registry.
- Q: Should the operator message parser reuse the existing Feature 003 LLM/regex pipeline?
  → A: Yes. `scrub_pii()` → LLM (if available) → regex fallback. The same confidence
  threshold from config applies. No new parsing pipeline is introduced (P10).
- Q: What fields are required vs optional on registration? → A: Required: vessel name,
  capacity (t), draft (m), home jetty (node id). Optional: registration number
  (placeholder, no format validation), vessel type, hazard certifications (default empty),
  contact (fictional in demo). A vessel with only required fields is valid.
- Q: Are sailing schedules per-vessel or independent? → A: Per-vessel. A sailing record
  references exactly one vessel. Multiple sailings can reference the same vessel.
- Q: How does the delivery record link to a booking? → A: Via `booking_id`. When
  `POST /api/booking/{id}/deliver` is called, the system creates a delivery record and
  recomputes the vessel's reliability statistics in memory.
- Q: What accessibility requirements apply? → A: WCAG AA contrast. Every badge
  (verification status, simulated tag, source tag) MUST have a text label; colour alone
  MUST NOT be the only indicator (constitution P3, P11, P13).


### Session 2026-10-07 (edge cases)

- Q: What happens to existing bookings when a vessel is suspended? → A: Confirmed bookings
  are NOT cancelled, modified, or auto-disrupted (P12: no auto-switch). Bookings in `pending`
  or `pending_review` for that vessel's sailings cannot be confirmed: confirm returns
  `vessel_suspended`. The suspend response lists `affected_booking_ids` (read-only info) so a
  human can decide; a presenter may trigger a `vessel_breakdown` disruption (Feature 005)
  separately. New matching excludes the vessel with reason `vessel_suspended`; new sailing
  publication returns `vessel_suspended`. UI notice per Spec 006 clarification.
- Q: Legacy vessels without a `status` field? → A: Treated as `verified` (backward compat
  with existing fixtures and tests); seed vessels are given explicit status.
- Q: Repeated actions? → A: Verify on a `verified` vessel, suspend on a `suspended` vessel,
  or any transition not in FR-1 returns HTTP 409 `invalid_transition` with no state change.
  Registering a vessel with the same `vessel_name` + `home_jetty_id` as an existing one
  returns 409 `duplicate_vessel` (double-click guard). A second `deliver` on a booking that
  already has a delivery record returns 409 `already_delivered`; no second record.
- Q: Empty states? → A: A vessel with zero records returns `total_trips: 0`,
  `on_time_rate = prior_rate`, `avg_delay_min: null`, `reliability_trend: []`,
  `trip_count_label: "0 trips [simulated]"`. An operator with no vessels returns an empty
  vessel list (200); an unknown operator id returns 404.
- Q: Invalid deliver input? → A: `actual_arrival` must be HH:MM (00:00–23:59) else 422
  `{field, code: "invalid_time"}`; `status` must be on_time|late|incident else 422; booking
  must be `confirmed` or `replanned`, else 409 `booking_not_deliverable`. `delay_min` is
  computed; if actual is earlier than planned by more than `history.midnight_wrap_h`
  (config, assumed) the arrival is treated as next-day.
- Q: Which "hazardous" definition does FR-8 use? → A: A class is hazardous when its hazard
  rule has `certification_required` or `human_review_required` true (config-driven; no new
  hardcoded list).
- Q: Sailing publish shape vs existing sailings? → A: Stored in the existing sailing shape
  (`origin_node_id` = route[0], `destination_node_id` = route[-1], `days`,
  `departure_time`, `available_capacity_t` = capacity offered) plus `route_node_ids` and
  `price_per_t`. Matching uses first/last stop only; intermediate stops are display-only
  [assumed]. `price_per_t` becomes the matching `cost_inr` (price × weight), so the "ties by
  lower cost" rule has a real value; it is operator-quoted data, not engine pricing.
- Q: Unverified penalty mechanism? → A: Subtracted from the match score (floor 0) for
  `pending_verification` vessels only; verified vessels' scores are unchanged. Reliability
  statistics are displayed (with trip counts) but do not alter ranking beyond this penalty
  (P14: no unfair exclusion of new operators).
- Q: New node for the hero message ("Vaikom")? → A: Add a Vaikom node to seed with
  `source_status: assumed`, approximate coordinates and note "verify with IWAI / Kerala State
  Water Transport Dept." Seed changes are listed in the task report for user review.
- Q: Operator message → registration parse? → A: Reuses the `/parse` adapter pattern and
  `scrub_pii()`, plus a regex helper for type/capacity/jetty; the LLM only extracts fields,
  never decides. Confidence below threshold shows editable fields; nothing is registered
  until the user clicks Confirm (P7 — registration is a state change).

---

## Actors

| Actor | Role |
|---|---|
| Boat operator | Registers vessels, publishes sailings, views own delivery history and reliability trend |
| Cargo owner | Views operator profile, verification status, and track record when comparing sailings |
| Demo admin | Sets a vessel's status to `verified` via a single demo action (simulated; no real identity check) |
| System | Appends a delivery record and updates reliability statistics when a booking is marked delivered |

---

## User Stories

### P1 — Vessel registration by form

As a boat owner, I open a registration form and fill in: vessel name, registration number
(free text, labelled "placeholder — not validated"), vessel type, capacity in tonnes,
draft in metres, home jetty (selected from the known node list), hazard classes certified
(multi-select, default none), and contact (fictional in demo). I click Register. If any
required field is missing or a numeric field is zero or negative, I see a clear error
message for that field and the form is not submitted. On success, my vessel appears in the
vessel list with status `pending_verification` and a `[simulated]` tag on all history
figures.

### P1 — Vessel registration by message

As a boat owner, I type or paste a plain message such as "12 ton barge, Vaikom, free
tomorrow, going Alappuzha" (English or Malayalam) into the operator chat. The system
extracts: vessel type, capacity, home jetty, and any deadline or route hints. It shows
me the extracted fields with a confidence value. If confidence is below the threshold
I see a warning banner (text label, not colour only) and all fields are editable. I
correct any wrong field and click Confirm to register the vessel.

### P1 — Publish a recurring sailing

As a boat owner, after registering a vessel I publish a recurring sailing: I select the
vessel, choose a route (ordered list of jetties from the node list), tick the weekdays,
set the departure time (HH:MM IST), enter the price per tonne (₹), and set the capacity
offered for this sailing (≤ vessel capacity). The sailing appears immediately in matching
results for eligible cargo.

### P1 — Newly registered vessels appear in matching

As a cargo owner, when I request options for a shipment, newly registered and published
sailings appear in the ranked list. Each ranked sailing shows a verification status badge
(`pending_verification` or `verified`) with a text label. An unverified vessel is shown
but ranked with a reliability penalty applied (configured constant, `source_status:
assumed`).

### P2 — Demo admin verifies a vessel

As a demo admin, I click "Mark Verified" on a vessel card. The vessel's status changes
from `pending_verification` to `verified`. A UI notice says "Verification is simulated —
production would check the national vessel registry [simulated]." The change takes effect
immediately in the in-memory store and persists until the next demo reset.

### P2 — Operator profile view

As a cargo owner, I expand an operator's profile card in the matching results. I see:
completed trips, on-time rate displayed as "NN% — N trips [simulated]", average delay in
minutes, any recorded incidents, and the list of certified hazard classes. All figures
carry a `[simulated]` tag. The profile also shows the vessel's verification status badge.

### P2 — Operator's own delivery history

As a boat owner, I open my vessel's history tab and see a list of delivery records:
booking ID, planned arrival, actual arrival, delay in minutes, and status (on time / late
/ incident). Each record carries a `[simulated]` tag. I also see a reliability trend line
(trip number vs running on-time rate) computed from the same records.

### P3 — Booking marked delivered triggers history update

When a booking is marked delivered (`POST /api/booking/{id}/deliver`) with an actual
arrival time and status, the system appends a delivery record for that booking's vessel
and immediately recomputes the vessel's reliability statistics. The updated on-time rate
and trip count are returned in the response and visible in the operator profile on the
next request.

---

## Functional Requirements

**FR-1 — Vessel lifecycle states**

A vessel record MUST be in exactly one of four states at any time:

| State | Meaning |
|---|---|
| `draft` | Created but not yet submitted for registration |
| `pending_verification` | Submitted; awaiting simulated verification |
| `verified` | Marked verified by demo admin action |
| `suspended` | Removed from matching; visible to admin only |

State transitions: `draft → pending_verification` (on form submit); `pending_verification
→ verified` (admin action); `verified → suspended` and `suspended → verified` (admin
actions). No other transitions are permitted. An attempt to transition to an invalid state
MUST return a named error, not a silent no-op.

**FR-2 — Reliability formula (Bayesian prior)**

The on-time rate for a vessel MUST be computed as:

```
on_time_rate = (on_time_trips + k × prior_rate) / (total_trips + k)
```

where:
- `on_time_trips` — count of delivery records with status `on_time` for this vessel
- `total_trips` — count of all delivery records for this vessel
- `k` — prior weight (number of virtual prior trips), read from `data/config.yaml`
- `prior_rate` — prior on-time rate (0–1), read from `data/config.yaml`

Both `k` and `prior_rate` MUST carry `source_status: assumed` and a note explaining the
choice. A vessel with zero delivery records returns `on_time_rate = prior_rate` and
`total_trips = 0`. The formula is a pure function; given the same inputs it MUST return
the same result (P2, P14).

**FR-3 — Delivery record structure**

Each delivery record MUST contain:

| Field | Type | Notes |
|---|---|---|
| `id` | string | Unique record id |
| `vessel_id` | string | References the vessel |
| `booking_id` | string | References the booking |
| `planned_eta` | string | HH:MM IST from the original sailing schedule |
| `actual_arrival` | string | HH:MM IST provided at mark-delivered time |
| `delay_min` | integer | `actual_arrival − planned_eta` in minutes; negative = early |
| `status` | enum | `on_time`, `late`, `incident` |
| `cargo_class` | string | Cargo description from the booking |
| `source_status` | string | `"simulated"` for all seed records; `"recorded"` for records created at runtime |

A delivery record is immutable once created. The `status` field MUST be supplied by the
caller; the system does not infer it from `delay_min`.

**FR-4 — Registration validation**

The registration endpoint MUST validate:

- `vessel_name`: non-empty string
- `capacity_t`: numeric, strictly greater than 0
- `draft_m`: numeric, strictly greater than 0
- `home_jetty_id`: must exist in the current node list
- `contact`: non-empty string (fictional in demo; no format validation)

For each failing field, the response MUST return a structured error object with
`field`, `code`, and `message`. The vessel MUST NOT be created if any required validation
fails. Optional fields that are present but malformed (e.g. a non-positive price) MUST
also return a field-level error.

**FR-5 — PII scrubbing before LLM**

Any text input that reaches the operator message parser MUST pass through `scrub_pii()`
before being sent to the LLM adapter. Phone numbers and email addresses MUST be replaced
with `[PHONE]` and `[EMAIL]` placeholders. This is the existing `scrub_pii()` function in
`backend/engine/parser.py` (P15). No new scrubbing implementation is introduced.

**FR-6 — Seed data: 6–8 vessels with delivery history**

`data/seed.json` MUST be extended with:

- 6 to 8 vessels, each with `source_status: "simulated"` and varied capacity, draft,
  home jetty, and certification data.
- One vessel with `status: "pending_verification"` (demonstrates the unverified path).
- One vessel with zero delivery records (demonstrates the prior; SC-3).
- One vessel with `status: "verified"` and 10 or more delivery records (demonstrates
  a mature track record).
- Remaining vessels: 3 to 12 delivery records each, mixing `on_time`, `late`, and
  `incident` statuses.
- All delivery records carry `source_status: "simulated"`.
- A `delivery_history` top-level key in `seed.json` holds the array of delivery records.

**FR-7 — Unverified vessel reliability penalty**

When a vessel is `pending_verification`, its reliability score used in plan scoring MUST
be reduced by a configured penalty constant (`unverified_reliability_penalty`, stored in
`data/config.yaml`, `source_status: assumed`). A `verified` vessel receives no penalty.
A `suspended` vessel MUST be excluded from matching entirely (hard filter, reason:
`vessel_suspended`). The penalty and suspension are applied in the matching engine before
scoring, consistent with the hard-filter pattern in Spec 002 FR-2.

**FR-8 — Hazmat and unverified vessel hard filters (P11)**

Hazardous cargo MUST NOT be matched to an unverified vessel. If the cargo's hazard class
is non-empty and the vessel's `status` is not `verified`, the vessel is excluded with
reason `unverified_vessel_for_hazmat`. This is a hard filter, not a score penalty. The
excluded vessel MUST appear in the exclusion list with this reason. The compliance-review
flag is set on the plan response (P11).

**FR-9 — Sailing publication**

A boat owner may publish a recurring sailing for a registered vessel (any state except
`suspended`). Required fields: vessel id, route (ordered list of at least two node ids,
all of which must exist), weekdays (at least one), departure time (HH:MM), price per
tonne (> 0 ₹), capacity offered (> 0 t, ≤ vessel capacity). On success the sailing is
added to the in-memory store and immediately available to matching. The sailing is
removed on demo reset.

**FR-10 — Operator profile response**

`GET /api/operator/{id}/profile` returns:

- Vessel list with status badges
- Aggregate statistics: `total_trips`, `on_time_trips`, `on_time_rate`, `avg_delay_min`,
  `incident_count`
- `trip_count_label`: string such as `"12 trips [simulated]"` (P14)
- `source_status: "simulated"` on all history fields
- Reliability trend: array of `{trip_number, running_on_time_rate}` points, one per
  delivery record in chronological order

**FR-11 — Demo reset behaviour**

`POST /api/demo/reset` MUST restore all vessel records, sailing records, and delivery
records to their seed state. Any vessel or sailing registered at runtime and any delivery
record appended at runtime MUST be removed. The reset MUST complete in under 1 second
(P8).

---

## Reference Scenario

| Attribute | Value |
|---|---|
| Hero operator message | "12 ton barge, Vaikom, free tomorrow, going Alappuzha" |
| Expected extracted fields | capacity=12 t, home_jetty≈Vaikom (fuzzy), route hint=Alappuzha |
| Zero-history vessel | Vessel with 0 delivery records; displayed on-time rate = `prior_rate` config value |
| Verified mature vessel | ≥10 delivery records; on-time rate converges toward actual history |
| Seed penalty scenario | Cargo with empty hazard classes booked on unverified vessel; reliability score reduced |

---

## Success Criteria

| ID | Criterion | Measurement |
|---|---|---|
| SC-1 | A vessel registered by form with valid required fields appears in ranked sailings for a matching cargo within the same request cycle | Automated pytest: register vessel → publish sailing → call `/api/match` → assert sailing in ranked list |
| SC-2 | The reference operator message ("12 ton barge, Vaikom, free tomorrow, going Alappuzha") is parsed with capacity=12 and a home jetty that matches Vaikom | Automated pytest against regex fallback (offline); no LLM required |
| SC-3 | A vessel with zero delivery records returns `on_time_rate = prior_rate` and `total_trips = 0` | Automated pytest: assert formula with zero records |
| SC-4 | Marking a booking delivered with status `on_time` changes the vessel's `on_time_trips` by exactly 1 and recomputes `on_time_rate` to the expected value | Automated pytest: hand-calculated expected value vs engine output |
| SC-5 | A vessel with `pending_verification` that carries hazardous cargo is excluded with reason `unverified_vessel_for_hazmat` and the compliance-review flag is set | Automated pytest |
| SC-6 | Registration with a missing required field returns a structured error for that specific field, not a generic error | Automated pytest covering each required field |
| SC-7 | Demo reset removes all runtime-registered vessels, sailings, and delivery records | Automated pytest: register → reset → assert not present |
| SC-8 | Every reliability statistic displayed in the UI shows its trip count label in the format "N trips [simulated]" | Visual review of operator profile card |

---

## Key Entities

| Entity | Attributes |
|---|---|
| Vessel | id, name, registration_number (optional), type (optional), capacity_t, draft_m, home_jetty_id, hazard_certs (list, default []), contact, status (draft\|pending_verification\|verified\|suspended), source_status |
| Sailing | id, vessel_id, route_node_ids (ordered list), weekdays (list), departure_time (HH:MM IST), price_per_t (₹), capacity_offered_t, source_status |
| DeliveryRecord | id, vessel_id, booking_id, planned_eta (HH:MM IST), actual_arrival (HH:MM IST), delay_min (int), status (on_time\|late\|incident), cargo_class, source_status |
| VesselReliability | vessel_id, total_trips, on_time_trips, on_time_rate (Bayesian), avg_delay_min, incident_count, trip_count_label, reliability_trend (list of {trip_number, running_on_time_rate}) |
| OperatorProfile | operator_id, vessels (list), aggregate_stats (VesselReliability per vessel), source_status |
| RegistrationResult | vessel (Vessel), validation_errors (list of {field, code, message}), success (bool) |
| DeliverResult | delivery_record (DeliveryRecord), updated_reliability (VesselReliability) |

---

## Out of Scope

- Real identity verification or integration with any vessel registry
- Authentication or operator login
- Payment processing or invoicing
- Live GPS position of vessels
- Real WhatsApp or SMS messaging
- Persistent database storage (in-memory only, per P10)
- Multi-operator onboarding workflow beyond the demo admin action
- Automated suspension logic (suspension is a manual admin action only)

---

## Assumptions

1. Vessel registration number is free text in the demo; no format or checksum validation
   is implemented (`source_status: assumed`). Production would validate against IWAI or
   state registry formats.
2. The Bayesian prior parameters (`k` and `prior_rate`) are assumed constants. Default
   values: `k = 5`, `prior_rate = 0.80` (i.e. a new vessel is treated as having 5 virtual
   trips at 80% on-time until real history accumulates). Both tagged `source_status:
   assumed`.
3. The unverified reliability penalty is an assumed constant. Default: `0.10` reduction
   applied to the raw reliability score before plan scoring. Tagged `source_status: assumed`.
4. Delivery record timestamps are HH:MM IST strings, consistent with the rest of the
   codebase. Date component is not modelled in this prototype.
5. The operator message parser uses the existing Feature 003 pipeline. No new ML model or
   parsing logic is introduced.
6. Vessel type is free text; the seed data uses representative examples. No enum is
   enforced in this prototype.
7. A sailing's `capacity_offered_t` may be less than the vessel's total `capacity_t` to
   allow partial capacity publication (e.g. one operator shares a vessel with another).
8. All seed delivery records and operator statistics carry `source_status: "simulated"`.
   Records created at runtime via `POST /api/booking/{id}/deliver` carry
   `source_status: "recorded"`.
9. The `cargo_class` field on a delivery record is the free-text description from the
   booking; it is not validated against a hazard taxonomy in this prototype.
10. The reliability trend is computed at read time from the full delivery record list in
    chronological record-insertion order. No separate trend storage is needed.

---

## Constraints (from Constitution)

- P2: Reliability formula and all registration validation MUST be pure deterministic
  functions with no I/O. Tests require no mocking of external services.
- P3: `k`, `prior_rate`, and `unverified_reliability_penalty` MUST live in
  `data/config.yaml` with `source_status: assumed` and explanatory notes.
- P5: All engine functions MUST have passing pytest tests before the feature is complete.
  SC-1 through SC-7 are the mandatory automated tests.
- P10: No new database, authentication, or out-of-scope features. State is in-memory only.
- P11: Hazardous cargo MUST NOT be matched to an unverified vessel. The hard filter and
  compliance-review flag are mandatory, not optional.
- P13: All delivery history, reliability statistics, and verification simulation MUST
  carry a visible `[simulated]` tag in the UI and `source_status: "simulated"` in the API.
- P14: Every displayed reliability percentage MUST be accompanied by a trip count label.
  Displaying a percentage without its sample size is a constitution violation.
- P15: `scrub_pii()` MUST be called on all operator message text before any LLM call.
  The existing implementation in `backend/engine/parser.py` is used unchanged.
