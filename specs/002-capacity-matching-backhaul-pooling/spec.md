# Feature Specification: Capacity Matching, Backhaul and Pooling

**Feature ID:** 002
**Short name:** capacity-matching-backhaul-pooling
**Status:** Draft
**Created:** 2025-07-17
**Last updated:** 2025-07-17

---

## Overview

Choosing water transport is only useful if a suitable vessel or sailing exists at the right
time. Small loads are uneconomic as dedicated charters, and boats that return empty waste
capacity and drive up effective rates. This feature finds and ranks vessels and sailings for
a water or hybrid shipment, handles the explicit booking confirmation step, and then
surfaces backhaul and cargo-pooling opportunities in a single follow-on step.

---

## Problem Statement

After deciding that water or hybrid is preferable, a cargo owner still needs to know which
vessel, on which sailing, can actually take their load. Without this, the decision engine's
recommendation is theoretical. Simultaneously, a boat that departs full one way and returns
empty represents a real inefficiency that a backhaul suggestion can address. Small loads
that cannot fill a vessel alone can be pooled with other cargo on the same sailing to share
cost.

---

## Clarifications

### Session 2025-07-17

- Q: What currency and weight units are used? → A: INR (₹ in UI, "Rs." in text). Weights in
  tonnes.
- Q: What time zone applies to all sailing departure times and deadlines? → A: IST
  throughout.
- Q: Is waiting time to the next sailing included in the time shown to the user? → A: Yes;
  waiting time from cargo ready time to sailing departure is included in the door-to-door
  time displayed on the plan card (inherited from Feature 001).
- Q: What happens when no vessel passes the hard filters? → A: See FR-8 (Edge Cases) below.
- Q: What happens when cargo is heavier than any vessel's capacity? → A: See FR-8 below.
- Q: What accessibility requirements apply to the ranked list and confirmation UI? → A:
  Readable contrast (WCAG AA). Every score badge and exclusion-reason badge MUST have a
  text label; colour alone MUST NOT be the only indicator.
- Q: Is booking state in memory or persisted? → A: In-memory only; the demo reset restores
  all bookings and capacity figures to their seed state without a server restart.

---

## Actors

| Actor | Role |
|---|---|
| Cargo owner | Selects a sailing, confirms a booking, receives backhaul and pooling suggestions |
| Boat operator | Secondary actor; sees booking confirmation and backhaul offer (per their documented scope) |
| Presenter / demo operator | Verifies that the seeded demo produces the expected backhaul and pooling results |

---

## User Stories

### P1 — Ranked vessel and sailing list

As a cargo owner who has chosen a water or hybrid plan, I see a ranked list of vessels and
scheduled sailings, each with:

- A match score (0–100) with named reasons
- Capacity fit (load vs. available capacity)
- Distance from vessel's current position to the pickup jetty
- Slack time between the sailing's arrival and my deadline (IST)
- Price estimate for the water leg (₹)
- Reliability sub-score (from Feature 001)

Vessels and sailings that fail any hard filter are excluded from the ranked list. I can
expand a collapsed section to see each excluded vessel and the specific reason it was
excluded (capacity exceeded, draft greater than route depth, route not permitted, cannot
meet deadline).

### P1 — Explicit booking confirmation

As a cargo owner, I select a sailing and confirm the booking through an explicit
confirmation step. Before the booking is finalised, I see a summary of what I am
confirming (vessel name, sailing departure time in IST, load in tonnes, cost estimate in
₹). The sailing's available capacity decreases by my load once the booking is confirmed.
Booking state is held in memory; the demo reset restores all capacity figures to seed.

### P1 — Backhaul suggestion after booking

After confirming a booking, I see a return-load suggestion: open cargo requests whose
origin is near my arrival jetty and whose destination is near my departure jetty, that
fit within the vessel's remaining capacity after my load. For each suggestion I see:
tonnage (t), estimated backhaul leg cost (₹), estimated detour distance (km), and the
estimated price effect for both the backhaul cargo owner (₹ saved or added) and myself
(₹ change). All monetary figures are tagged with source_status.

### P2 — Pooling suggestions after booking

After confirming a booking, I see a list of cargo-pooling suggestions: other open cargo
requests that fit on the same sailing in the remaining capacity. For each suggestion I
see: the additional tonnage (t), the resulting vessel utilisation (%), and the new
cost-per-tonne (₹/t) for the combined load. Suggestions are sorted by utilisation impact
descending.

### P3 — Demo scenario

As a presenter, the seeded demo data produces exactly one clear backhaul opportunity
(7 t, Alappuzha → Kochi) and exactly two poolable small loads after the reference booking
is confirmed.

---

## Functional Requirements

**FR-1 — Vessel and sailing scoring**
For each candidate vessel and sailing, the engine computes a match score (0–100) from
five weighted factors read from `data/config.yaml`:

| Factor | Default weight |
|---|---|
| Capacity fit | 0.30 |
| Proximity to pickup jetty | 0.25 |
| Schedule slack before deadline | 0.25 |
| Price | 0.15 |
| Reliability | 0.05 |

Each factor contributes a named sub-score and a human-readable reason string. Weights are
read from `data/config.yaml`; changing them requires no code change. Weights MUST sum to
1.0; the engine returns a named error if they do not.

**FR-2 — Hard filters with visible reasons**
Before scoring, the engine applies hard filters. Vessels/sailings that fail a filter are
excluded with a named reason:

- `capacity_exceeded` — vessel's available capacity is less than shipment weight
- `draft_too_deep` — vessel draft exceeds route navigable depth minus safety margin
- `route_not_permitted` — sailing's route does not pass through required jetties
- `deadline_not_met` — earliest arrival time (departure + transit, IST) exceeds shipment
  deadline (IST)

The excluded list and reasons are included in the response and displayable in the UI.
Every exclusion-reason badge MUST have a text label; colour alone MUST NOT be the only
indicator.

**FR-3 — Explicit booking confirmation**
The booking function accepts a `human_confirmed: bool` field (default: `false`). Without
`human_confirmed: true`, the system returns a preview response only and makes no state
change. When `human_confirmed: true` is received, the sailing's `capacity_used` field
increases by the shipment weight and the booking is recorded in the in-memory state.
No booking is auto-confirmed by the system.

**FR-4 — Backhaul suggestion**
After a booking is confirmed, the engine scans all open (unbooked) cargo requests and
returns those that satisfy all of:
- Origin node within a configured proximity radius of the booking's arrival jetty
- Destination node within a configured proximity radius of the booking's departure jetty
- Weight ≤ remaining vessel capacity after the confirmed booking
- No hard-filter failure against the same vessel and sailing

Each backhaul suggestion includes: cargo request id, weight (t), estimated backhaul leg
cost (₹), detour distance (km), and estimated price effect for both parties (₹). All
monetary figures carry source_status. The detour and price-effect calculations use the
same cost model as Feature 001.

**FR-5 — Pooling suggestion**
After a booking is confirmed, the engine scans all open cargo requests destined for the
same sailing route and returns those that fit in the remaining capacity. Each pooling
suggestion includes: cargo request id, weight (t), resulting vessel utilisation (%), and
new cost-per-tonne (₹/t) for the combined load. Suggestions are sorted by utilisation
impact descending.

**FR-6 — Config-only scoring weights**
All scoring weights, proximity radii, safety margins, and hard-filter thresholds are read
from `data/config.yaml`. Every value carries `source_status` and `note`. A missing
required value produces a clear named error.

**FR-7 — Seeded demo scenario**
`data/seed.json` contains vessels, sailings, and cargo requests such that: the reference
booking (10 t, Kochi → Alappuzha) produces a non-empty ranked list; after confirmation,
exactly one backhaul suggestion (7 t, Alappuzha → Kochi) and exactly two pooling
suggestions are returned.

**FR-8 — Edge cases**

- *No vessel passes hard filters*: The ranked list is empty. A message states "No vessels
  available for this shipment" with a summary of the most common exclusion reason. No
  exception is raised. Road is still available via Feature 001.
- *Cargo heavier than every vessel's capacity*: All vessels are excluded with reason
  `capacity_exceeded`. The ranked list is empty; the message reads "Your load exceeds the
  capacity of all available vessels." The booking step is not reachable.
- *All sailings miss the deadline*: All sailings are excluded with reason `deadline_not_met`.
  The ranked list is empty; the message states "No sailing can meet your deadline." Road
  is still available via Feature 001.
- *Booking attempt on a sailing that has since filled (race condition)*: In this in-memory
  prototype, concurrent writes are not modelled. The capacity check is performed at
  confirmation time; if remaining capacity is insufficient, the confirmation returns an
  error "Insufficient capacity — please select another sailing."
- *Backhaul or pooling finds no matches*: Returns an empty list with the message "No
  return-load opportunities found" or "No pooling opportunities found" respectively; no
  exception is raised.

---

## Success Criteria

| ID | Criterion | Measurement |
|---|---|---|
| SC-1 | Reference hero shipment returns a ranked vessel list with at least one valid sailing | Automated pytest |
| SC-2 | A vessel with draft exceeding route depth is excluded with reason `draft_too_deep` | Automated pytest with a crafted seed vessel |
| SC-3 | Confirming the hero booking triggers exactly one backhaul and two pooling suggestions in one step | Automated pytest against seed data |
| SC-4 | All scoring weights sum to 1.0 and are read from configuration | Automated pytest asserting sum and config source |
| SC-5 | Empty ranked list (all vessels excluded) returns a structured message without exceptions | Automated pytest with an all-overweight seed scenario |
| SC-6 | Every score badge and exclusion-reason badge has a text label; no information conveyed by colour alone | Visual accessibility review |

---

## Key Entities

| Entity | Attributes (additions to Feature 001) |
|---|---|
| Sailing | id, vessel_id, route_nodes, departure_time (IST), capacity_total_t, capacity_used_t |
| Booking | id, shipment_id, sailing_id, weight_t, confirmed, created_at (IST) |
| MatchResult | vessel_id, sailing_id, score, sub_scores, reasons, excluded, exclusion_reason |
| BackhaulSuggestion | cargo_request_id, weight_t, backhaul_cost_₹, detour_km, price_effect_owner_₹, price_effect_requester_₹, source_status |
| PoolingSuggestion | cargo_request_id, weight_t, utilisation_pct, cost_per_tonne_₹, source_status |

---

## Out of Scope

- Payment processing or invoicing
- Ratings or reviews of vessels or operators
- Real operator onboarding or KYC
- Optimisation beyond greedy selection (no linear programming, no combinatorial matching)
- Multi-stop voyage planning
- Concurrent-write conflict resolution beyond the capacity-at-confirmation check
- Integration with FOCAL, PANI, CAR-D, or Jalyan (per their documented scope)

---

## Assumptions

1. Vessel position is approximated by the departure jetty of its next scheduled sailing;
   no live GPS is used (`source_status: assumed`).
2. Proximity is measured as straight-line distance between node coordinates multiplied by
   a road-factor constant (`source_status: assumed`).
3. "Remaining capacity" is `capacity_total_t − capacity_used_t` at the time of the
   confirmation call; concurrent writes are not modelled in this prototype.
4. Backhaul detour is the additional distance the vessel would travel; cost impact uses
   the same per-km water rate as Feature 001.
5. Booking state is in-memory only; the demo reset restores all capacity figures to their
   seed values without a server restart.
6. Seed data uses simulated operators and cargo owners; no personal data is included.
7. All monetary values are in INR (₹); all times are IST.

---

## Constraints (from Constitution)

- No booking is confirmed without an explicit `confirmed: true` flag from the user.
- All scoring weights MUST be in `data/config.yaml` and MUST sum to 1.0.
- Engine functions (scoring, filtering, backhaul, pooling) MUST be pure and have passing
  pytest tests.
- Backhaul and pooling calculations MUST be deterministic over the seed data.
- The demo reset MUST restore all bookings and capacity figures to their seed state.
- Every score badge and exclusion-reason indicator MUST have a text label; colour alone
  MUST NOT convey information (accessibility requirement).
