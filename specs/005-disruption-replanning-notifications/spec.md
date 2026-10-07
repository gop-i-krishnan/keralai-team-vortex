# Feature Specification: Disruption Re-planning, Notifications and Milestone Tracking

**Feature ID:** 005
**Short name:** disruption-replanning-notifications
**Status:** Draft
**Created:** 2026-10-07
**Last updated:** 2026-10-07

---

## Overview

Once a shipment is booked, JalSetu has no way to respond when things go wrong. A vessel
breakdown, a shallow stretch, a closed jetty, or a blocked road can strand cargo mid-journey
for hours. This feature adds the missing reactive layer: a milestone timeline that shows
where cargo is at every stage, a disruption event that a presenter can trigger in the demo,
instant in-app notification to the cargo owner, and a ranked set of alternatives — computed
from the cargo's current position — so the owner can make a fast, informed choice. Nothing
changes without an explicit "Accept this plan" confirmation.

---

## Problem Statement

Cargo owners booking via JalSetu receive no signal when a disruption occurs and no structured
help recovering from it. They would have to phone around and improvise at exactly the moment
when clear, fast options matter most. Without a re-planning capability the platform covers only
the smooth case and fails the trust test for real commercial use.

---

## Clarifications

### Session 2026-10-07

- Q: What is the canonical currency, weight unit, and time zone? → A: INR (₹ in UI, "Rs." in
  text), tonnes, IST. All timestamps are HH:MM IST strings, consistent with the rest of
  the codebase.
- Q: What is a "current position" for a mid-water shipment? → A: The cargo's current position
  is represented as a node id (the last confirmed milestone node) or, if in transit between
  two nodes, the origin node of the active leg. A partial-leg position is approximated as the
  leg origin (P10 — no live GPS). This is an assumed simplification tagged in config.
- Q: How many alternatives must the re-plan engine return? → A: At least one (the best
  available). Up to five alternatives are ranked and displayed. If fewer than two pass hard
  filters the response includes all that do pass, with a clear message if only one or zero
  are available.
- Q: Is "hold at a nearby warehouse" a distinct alternative type or part of "wait and
  continue"? → A: A distinct type, `hold_warehouse`. In the prototype it uses a configured
  cost-per-hour storage rate and the nearest node in the seed data labelled `"type":
  "warehouse"`. If no warehouse node exists, this alternative is omitted without error.
- Q: What does "return to origin" mean once cargo is mid-water? → A: Travel back to the
  cargo's origin node via road (barge return is not modelled in this prototype because it
  would require a reverse sailing). Cost includes road cost for the distance already
  travelled plus the return road distance. See SC-4.
- Q: Where do notification templates live? → A: In `data/config.yaml` under a `notifications`
  section, with English text and a Malayalam placeholder comment. `source_status: assumed`.
- Q: Does the event log replace or extend the booking record? → A: Extends. The booking
  record gains an `event_log` list. Each entry is appended; nothing is ever overwritten.
- Q: How does the demo advance milestones? → A: A presenter calls
  `POST /api/demo/booking/{id}/advance` to step the booking to the next milestone. The
  endpoint is demo-only and carries a `[simulated]` label in the UI.
- Q: Does the disruption engine re-use `build_plans()` from Feature 001? → A: Yes, for the
  road and hybrid sub-cases. The re-plan engine calls `build_plans()` with the cargo's
  current node as origin and the remaining weight and deadline. It does not duplicate cost
  or CO₂ logic (P10).
- Q: What accessibility requirements apply? → A: WCAG AA contrast throughout. Every badge,
  timeline node, disruption severity indicator, and notification label MUST have a text
  label; colour alone MUST NOT be the only indicator (P3, P13).


### Session 2026-10-07 (edge cases)

- Q: Where do a booking's deadline and original plan come from? → A: `POST /api/book`
  gains optional `deadline_h` (default: config `demo.deadline_hybrid_h`) and stores
  `weight_t`, `deadline_h`, `ready_time` (default "06:00"), `planned_cost_inr` and
  `planned_time_h` (from `build_plans()` hybrid plan). Re-plan deltas are relative to these.
- Q: Which bookings can be disrupted? → A: Status `confirmed` or `replanned` only; else 409
  `booking_not_disruptable`. At most one open disruption per booking; a second trigger
  returns 409 `disruption_already_open`. Unknown booking → 404.
- Q: Repeated actions? → A: `POST /api/replan/{id}` is read-only and idempotent: calling it
  again returns the same proposal id (deterministic from inputs). Confirming twice → second
  call returns 409 `replan_already_confirmed`, no second event-log entry. Confirm with an
  `alternative_id` not in the current proposal → 422 `unknown_alternative`. Confirm when the
  booking changed since the proposal → 409 `proposal_stale`. Confirm without a prior
  proposal → 409 `no_proposal`. Dismissing in the UI sends nothing (P12).
- Q: Invalid input? → A: `type` outside the five enums → 422; `expected_duration_h` negative
  or non-numeric → 422 `invalid_duration`; unknown `location_node_id` → 422 `not_found`;
  default location is the cargo's current node.
- Q: Empty states? → A: No disruptions → `/api/disruptions/summary` returns `rows: []`
  (200). No feasible alternative → `alternatives: []`, `no_alternatives_found: true`.
  `wait_and_continue` is omitted when `expected_duration_h` is null.
- Q: "Hold at warehouse" source? → A: Spec 005 says a node with `type: "warehouse"`; the
  seed has none. Resolved: use the Feature 006 `warehouses` registry via
  `find_eligible_warehouses` (class- and capacity-filtered). No new node type. Storage cost
  uses the warehouse's own per-t-per-day rate; assumption 4 (flat Rs 30/t/h) is superseded
  and NOT added to config.
- Q: Hazardous cargo in re-plan? → A: Alternatives pass the hazard hard filter (cert, mode,
  vessel status). For classes with `human_review_required`, `replan/confirm` returns
  `compliance_review_required` until `POST /api/compliance/replan-review/{proposal_id}/approve`
  is recorded (simulated). A plan change is a new plan; P11 applies.
- Q: Sailing capacity on re-plan confirm? → A: Only the booking's plan fields are updated
  (`sailing_id`, mode, cost, ETA). Sailing capacity figures are not altered by re-plans
  (P12 + P10). Recorded as a known weakness.
- Q: Suspended vessels? → A: `alternative_vessel` excludes suspended vessels and, for
  hazardous cargo, unverified vessels.
- Q: Clock? → A: `detected_at` uses IST from a fixed UTC offset config value
  (`meta.ist_offset_min`, sourced) — no tz database, no new dependency. The demo trigger
  accepts optional `now_hhmm` for deterministic tests; engine functions receive time as
  arguments only.
- Q: Advance vs delivery history? → A: Advancing to `Delivered` sets the milestone only. A
  delivery record (Spec 004) is written only by `POST /api/booking/{id}/deliver`; advancing
  never fabricates history. Advance on a `disrupted` booking → 409 `booking_disrupted`.
  Advance requires `confirmed` or `replanned`, else 409 `booking_not_active`.
- Q: Positions and seed richness? → A: Node ids only; "In Transit" current node is the
  sailing's origin (assumption 1). With two-node corridors SC-1 relies on
  `wait_and_continue`, `truck_from_jetty`, `return_to_origin`, plus `alternative_vessel`
  when another sailing serves current node → destination.

---

## Actors

| Actor | Role |
|---|---|
| Cargo owner | Views milestone timeline, receives disruption notification, reviews alternatives, confirms exactly one re-plan |
| Presenter / demo operator | Triggers disruptions and advances milestones from a demo control panel |
| Boat operator | Receives notification of the disruption and the chosen resolution (in-app; simulated) |
| Planner | Views disruption counts by type and corridor on the analytics panel |
| System | Computes re-plan alternatives, appends event log entries, issues mock notifications |

---

## User Stories

### P1 — Milestone timeline

As a cargo owner with a confirmed booking, I see a milestone timeline on the booking detail
view. The milestones in order are: **Booked → Loading → In Transit → Arrived → Delivered**.
Each milestone shows planned time and, once passed, actual time. The current milestone is
highlighted. All timeline entries carry a `[simulated]` badge. A presenter can advance the
booking to the next milestone using a demo control; this does not happen automatically.

### P1 — Trigger a disruption

As a presenter, I open a demo disruption panel on a confirmed booking and choose from a
fixed list of disruption types: vessel breakdown, low depth on a waterway segment, jetty
closed, road blocked, weather delay. I select the disruption, optionally set an expected
duration in hours, and click "Trigger Disruption". A disruption record is created and the
booking moves to `disrupted` status. The trigger is clearly labelled "Demo control —
simulated disruption".

### P1 — Disruption notification

As a cargo owner, immediately after a disruption is recorded on my booking, I see an
in-app alert at the top of the booking view stating: what happened (disruption type in
plain English), where the cargo is (current node name), and whether the original deadline
is now at risk. Alongside the alert I see a "Message Preview" panel showing what a
notification to the operator would say, labelled "Message preview — not sent [simulated]".

### P1 — Ranked re-plan alternatives

As a cargo owner, below the disruption alert I see a ranked list of alternatives, each
showing:

- Alternative type (wait and continue / alternative vessel / truck from current jetty /
  return to origin / hold at warehouse)
- Extra cost (₹, delta from the original plan) with `[assumed]` tag
- New estimated time of arrival (HH:MM IST) and total time delta (h)
- Whether the original deadline is met (text label + colour indicator)
- Reliability score and reason string
- A brief plain-English rationale

Alternatives are ranked by the same weighted scoring as the main options engine (cost,
time, CO₂, reliability), read from `data/config.yaml`. If no alternative meets the
deadline, the fastest is shown as a fallback with a banner "No option meets your
deadline — fastest shown."

### P1 — Confirm a re-plan

As a cargo owner, I click "Accept this plan" on exactly one alternative. A confirmation
dialogue appears summarising the chosen alternative with cost, new ETA, and the
acknowledgement "The operator will be notified [simulated]". I click "Confirm". The
booking is updated to the new plan, the event log records the decision, and the disruption
status clears to `replanned`. Until I confirm, the booking record is unchanged.

### P2 — Operator disruption notification

As a boat operator whose vessel is affected, I see the disruption on my operator view and,
once the cargo owner confirms a resolution, I see which alternative was chosen and the
new plan details. All messages are in-app and carry `[simulated]` labels.

### P2 — Disruption analytics

As a planner, I see a summary table on the viability/analytics panel: disruption counts
broken down by type and by corridor, drawn from all disruptions recorded in the current
session. The table carries a `[simulated]` tag and a note that counts reset on demo reset.

---

## Functional Requirements

**FR-1 — Disruption record structure**

Each disruption record MUST contain:

| Field | Type | Notes |
|---|---|---|
| `id` | string | Unique disruption id |
| `booking_id` | string | The affected confirmed booking |
| `type` | enum | `vessel_breakdown`, `low_depth`, `jetty_closed`, `road_blocked`, `weather_delay` |
| `location_node_id` | string | Node at or nearest to where the disruption occurred |
| `detected_at` | string | HH:MM IST at time of trigger |
| `expected_duration_h` | float \| null | Optional estimate; null if unknown |
| `severity` | enum | `minor` (< 2 h delay expected), `moderate` (2–6 h), `severe` (> 6 h or deadline missed) |
| `source_status` | string | `"simulated"` always in this prototype |

Severity MUST be computed deterministically from `expected_duration_h` and the remaining
time to the booking's deadline, using thresholds stored in `data/config.yaml`
(`source_status: assumed`). It MUST NOT be set by the caller.

**FR-2 — Pure re-plan engine**

`replan(booking, disruption, available_sailings, nodes, config)` MUST be a pure,
deterministic function with no I/O. It:

1. Determines the cargo's current node from the booking's last confirmed milestone.
2. Removes or penalises resources affected by the disruption:
   - `vessel_breakdown`: removes the booking's vessel from the candidate sailing list.
   - `low_depth`: removes sailings whose route passes through the affected node.
   - `jetty_closed`: removes sailings originating from or arriving at the affected node.
   - `road_blocked`: applies a configured delay penalty to road-mode alternatives
     originating from the affected node.
   - `weather_delay`: applies a configured reliability penalty to all water-mode
     alternatives.
3. Computes up to five alternatives from the current node (see FR-3).
4. Scores and ranks them using the existing scoring weights from config.
5. Returns a `ReplanProposal` (see Key Entities). It MUST NOT modify any booking or
   sailing state.

All penalty and threshold constants MUST be in `data/config.yaml` with `source_status:
assumed` (P3, P12).

**FR-3 — Alternative types and cost rules**

The re-plan engine computes whichever of the following are feasible from the cargo's
current position:

| Type | Feasibility rule | Cost basis |
|---|---|---|
| `wait_and_continue` | Disruption has a finite `expected_duration_h` | Original plan cost + configured waiting cost per hour (₹/t/h from config) |
| `alternative_vessel` | At least one other sailing exists from the current node with capacity ≥ remaining weight | Recomputed using `build_plans()` from current node |
| `truck_from_jetty` | Current node is a jetty; road distance from current node to destination > 0 | Road plan cost from current node using existing road cost model |
| `return_to_origin` | Current node is not the origin | Road cost from current node back to origin + road cost already incurred (see SC-4) |
| `hold_warehouse` | A node with `type: "warehouse"` exists within the configured proximity radius | Configured hourly storage cost × expected wait hours |

If a type is not feasible, it is omitted from the proposal. If no type is feasible, the
response contains an empty alternatives list and a `no_alternatives_found` flag. This MUST
NOT raise an exception.

**FR-4 — No-deadline-met fallback**

If none of the computed alternatives meets the original deadline, the re-plan engine MUST:
- Set `deadline_met: false` on every alternative.
- Set `fastest_fallback_id` on the proposal pointing to the alternative with the lowest
  `new_total_time_h`.
- Return all alternatives ranked as normal; the UI renders the fastest with a
  "No option meets your deadline — fastest shown" banner.
- Still require human confirmation; no automatic acceptance.

**FR-5 — Notification templates**

Notification text is rendered from templates stored in `data/config.yaml` under a
`notifications` key. Each template has:
- `type`: matches the disruption type enum.
- `subject_en`: English subject line.
- `body_en`: English body with `{cargo_id}`, `{location}`, `{deadline}` placeholders.
- `body_ml_placeholder`: Malayalam placeholder string (not translated; labelled "placeholder,
  requires professional translation" in the config note).
- `source_status: assumed`.

Notification delivery is mocked: `POST /api/booking/{id}/notify` renders the template with
the booking's data and returns the rendered text in a `preview` field, along with
`delivered: false` and `note: "message preview — not sent [simulated]"`. No real message
is sent under any circumstances.

**FR-6 — Event log**

Every booking MUST carry an `event_log` list. Each entry has:

| Field | Type | Notes |
|---|---|---|
| `id` | string | Unique entry id |
| `event_type` | enum | `milestone_advanced`, `disruption_recorded`, `replan_proposed`, `replan_confirmed`, `notification_preview` |
| `timestamp` | string | HH:MM IST |
| `detail` | string | Plain-English description of what happened |
| `source_status` | string | `"simulated"` |

Entries are append-only; existing entries MUST NOT be modified or deleted. The event log
is returned in every booking response and visible in the booking detail UI.

**FR-7 — Human confirmation gate (P12)**

A `ReplanProposal` is read-only until confirmed. The confirmation flow:
1. `POST /api/replan/{booking_id}` → returns a `ReplanProposal` with all alternatives.
   No state changes.
2. `POST /api/replan/{booking_id}/confirm` with `{"alternative_id": "..."}` → validates
   the proposal is still current, applies the chosen alternative to the booking, appends
   a `replan_confirmed` event log entry, appends a `notification_preview` entry, and
   returns the updated booking. Setting `human_confirmed: true` in step 1 MUST NOT skip
   step 2 (consistent with P7 and P12).

Between steps 1 and 2, the booking status MUST remain `disrupted`. Only step 2 transitions
it to `replanned`.

**FR-8 — Demo milestone control**

`POST /api/demo/booking/{id}/advance` advances the booking's current milestone to the
next in the sequence (Booked → Loading → In Transit → Arrived → Delivered). If the booking
is already at Delivered, the call returns an error "Booking already at final milestone." The
endpoint is demo-only, carries no authentication, and every response includes
`"source_status": "simulated"`.

**FR-9 — Disruption analytics**

`GET /api/disruptions/summary` returns a list of `{disruption_type, corridor_id,
count}` rows aggregated from all in-memory disruption records. Corridor is derived from
the `location_node_id` of the disruption matched against the seed corridor definitions.
If the node does not belong to a corridor, `corridor_id` is `"unknown"`. All counts carry
`source_status: "simulated"` and a note that the data resets on demo reset.

**FR-10 — Seed disruption scenarios**

`data/seed.json` MUST include at least two pre-seeded disruption scenarios (in a
`disruption_scenarios` array) that a presenter can apply to the hero booking in one click:
1. Vessel breakdown on the hero sailing mid-transit (location: last waterway node before
   destination).
2. Jetty closed at the destination node.

Each scenario record carries `source_status: "simulated"`.

**FR-11 — Demo reset**

`POST /api/demo/reset` MUST remove all runtime disruption records, re-plan proposals,
event log entries appended at runtime, and milestone advances. All bookings revert to
their seed state (confirmed, Booked milestone). Reset completes in under 1 second (P8).

---

## Reference Scenario

| Attribute | Value |
|---|---|
| Hero booking | cargo-001, sailing-001, Kochi Thevara → Alappuzha, 10 t |
| Disruption triggered | Vessel breakdown, location: mid-waterway node (current node = Kochi Thevara after partial advance) |
| Expected alternatives | wait\_and\_continue (if duration known), alternative\_vessel (if another sailing exists), truck\_from\_jetty (road from Kochi Thevara), return\_to\_origin (road back to origin) |
| SC-2 test | Tighten remaining time to 1.5 h → only truck\_from\_jetty meets deadline; best alternative flips to road |
| SC-4 test | return\_to\_origin cost = road cost from current node back to origin; distance already travelled is included |

---

## Success Criteria

| ID | Criterion | Measurement |
|---|---|---|
| SC-1 | A vessel breakdown disruption on the hero booking returns at least two valid alternatives with different types and different cost/time trade-offs | Automated pytest with seed hero booking |
| SC-2 | Reducing the remaining time to a value that only road can meet causes the highest-ranked alternative to be `truck_from_jetty` | Automated pytest: parameterise remaining time |
| SC-3 | Calling `POST /api/replan/{id}` (step 1) leaves the booking record entirely unchanged; only `POST /api/replan/{id}/confirm` modifies it | Automated pytest: assert booking before and after step 1 are identical |
| SC-4 | The `return_to_origin` alternative's extra cost equals the road cost from the current node to the origin, and the response includes the `distance_already_travelled_km` field | Automated pytest with hand-calculated expected value |
| SC-5 | A disruption with no feasible alternatives returns an empty list with `no_alternatives_found: true` and does not raise an exception | Automated pytest with a crafted scenario (all sailings removed, no warehouse node) |
| SC-6 | Advancing a booking to each milestone in sequence and then calling advance on `Delivered` returns a structured error, not an exception | Automated pytest |
| SC-7 | Notification endpoint returns `delivered: false` and a non-empty `preview` string for each supported disruption type | Automated pytest covering all five types |
| SC-8 | Demo reset after triggering a disruption and confirming a re-plan restores the booking to its original confirmed/Booked state | Automated pytest: full cycle then reset |

---

## Key Entities

| Entity | Attributes |
|---|---|
| Milestone | `name` (Booked\|Loading\|In Transit\|Arrived\|Delivered), `planned_time` (HH:MM IST), `actual_time` (HH:MM IST \| null), `status` (pending\|current\|completed), `source_status` |
| DisruptionRecord | `id`, `booking_id`, `type` (vessel_breakdown\|low_depth\|jetty_closed\|road_blocked\|weather_delay), `location_node_id`, `detected_at`, `expected_duration_h` (nullable), `severity` (minor\|moderate\|severe), `source_status` |
| ReplanAlternative | `id`, `type` (wait_and_continue\|alternative_vessel\|truck_from_jetty\|return_to_origin\|hold_warehouse), `extra_cost_inr`, `new_eta`, `total_time_delta_h`, `deadline_met` (bool), `reliability_score`, `reason`, `score`, `source_status`, `distance_already_travelled_km` (return_to_origin only) |
| ReplanProposal | `booking_id`, `disruption_id`, `alternatives` (list of ReplanAlternative, max 5), `fastest_fallback_id` (nullable), `no_alternatives_found` (bool), `source_status` |
| EventLogEntry | `id`, `event_type` (milestone_advanced\|disruption_recorded\|replan_proposed\|replan_confirmed\|notification_preview), `timestamp`, `detail`, `source_status` |
| NotificationPreview | `disruption_type`, `subject_en`, `body_rendered`, `delivered` (always false), `note`, `source_status` |
| DisruptionSummaryRow | `disruption_type`, `corridor_id`, `count`, `source_status` |

---

## Out of Scope

- Live GPS or real-time vessel position
- Real depth or weather feeds
- Real SMS, WhatsApp, or email delivery
- Insurance, claims, or liability handling
- Automatic re-planning without human confirmation (P12)
- Multi-hop re-routing (alternatives start from the current node only; no multi-leg
  waterway re-routing is computed in this prototype)
- Authentication or per-user notification preferences
- Persistent event log storage (in-memory only, per P10)

---

## Assumptions

1. Cargo's current position is approximated as the last confirmed milestone node. If the
   cargo is in transit between two nodes (milestone = "In Transit"), the current node is
   the origin node of the active leg. This is an assumed simplification; no GPS-derived
   partial position is used (`source_status: assumed`).
2. Disruption severity thresholds (minor < 2 h, moderate 2–6 h, severe > 6 h) are assumed
   constants in `data/config.yaml` (`source_status: assumed`). They define severity from
   the perspective of additional delay, not absolute time.
3. Waiting cost for `wait_and_continue` is a flat rate per tonne per hour, stored in
   `data/config.yaml` (`source_status: assumed`). Default: Rs 20/t/h.
4. Storage cost for `hold_warehouse` is a flat rate per tonne per hour, stored in
   `data/config.yaml` (`source_status: assumed`). Default: Rs 30/t/h.
5. `road_blocked` penalty is an additive time delay applied to road alternatives from the
   affected node, stored in `data/config.yaml` (`source_status: assumed`). Default: 2 h.
6. `weather_delay` reliability penalty is a fractional reduction applied to the water mode
   reliability score, stored in `data/config.yaml` (`source_status: assumed`). Default: 0.10.
7. Return-to-origin uses road mode only for the return leg. Barge return is not modelled.
   The cost includes road cost for the distance already travelled (approximated as straight-
   line Haversine from origin to current node × road factor) plus road cost from current
   node back to origin.
8. Notification templates are in English. The Malayalam field is a placeholder labelled
   "requires professional translation" and is not evaluated for correctness.
9. The ranking of alternatives uses the same config weights as the main options engine
   (cost 0.40, time 0.35, CO₂ 0.15, reliability 0.10). `extra_cost_inr` is used as the
   cost input; CO₂ delta is not separately computed for non-road alternatives in this
   prototype (CO₂ field is carried through from the sub-plan if available, else set to 0).
10. A maximum of five alternatives is shown. If more than five pass all filters, the five
    with the highest scores are returned.
11. The `detected_at` timestamp is the server's current time when the disruption is triggered,
    represented as HH:MM IST. Date component is not modelled in this prototype.

---

## Constraints (from Constitution)

- **P2**: `replan()` MUST be a pure function. Given identical inputs it returns identical
  outputs. No I/O, no randomness. Tests require no mocking of external services.
- **P3**: All penalty constants, thresholds, waiting costs, storage costs, and notification
  templates MUST be in `data/config.yaml` with `source_status: assumed` and explanatory
  notes. No numeric constant MAY be hardcoded in Python or JavaScript.
- **P5**: All engine functions MUST have passing pytest tests before the feature is complete.
  SC-1 through SC-8 are the mandatory automated test targets.
- **P10**: No new database, authentication, live feeds, or real messaging. State is
  in-memory only. No new external dependencies introduced.
- **P12**: A `ReplanProposal` is read-only until the cargo owner explicitly calls the confirm
  endpoint. Setting any flag in the proposal request MUST NOT bypass the confirm step.
  Dismissing the disruption notice in the UI MUST NOT silently accept any alternative.
- **P13**: All milestones, disruption records, notification previews, event log entries, and
  disruption analytics carry `source_status: "simulated"` in the API and a visible
  `[simulated]` tag in the UI. The demo advance control is labelled "Demo control —
  simulated disruption".
- **P8**: All computation is offline-capable. No network call MAY block the disruption or
  re-plan path. Demo reset restores all disruption and milestone state within 1 second.
