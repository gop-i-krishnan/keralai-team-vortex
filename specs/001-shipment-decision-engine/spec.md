# Feature Specification: Shipment Decision Engine

**Feature ID:** 001
**Short name:** shipment-decision-engine
**Status:** Draft
**Created:** 2025-07-17
**Last updated:** 2025-07-17

---

## Overview

Cargo owners and logistics companies in Kerala cannot easily compare road, inland waterway,
and hybrid (truck + barge + truck) options for a specific shipment. Today they phone around
and guess. This feature gives them a side-by-side comparison of all three modes for any
shipment and recommends the best option for their chosen objective — being explicit when
road wins.

---

## Problem Statement

A cargo owner knows their load, origin, destination, and deadline. They have no tool that
gives a single, honest door-to-door comparison covering cost, travel time, CO₂, and
reliability for all three transport modes. Water can be cheaper on the water leg but more
expensive overall once first- and last-mile handling is included. Today that calculation
does not happen.

---

## Clarifications

### Session 2025-07-17

- Q: What currency and weight units are displayed? → A: Currency is INR, shown as "Rs." in
  text and the ₹ symbol in the UI. Weights are in tonnes.
- Q: Are the placeholder rates real quotes or illustrative numbers? → A: Placeholder rates
  are assumed and tagged; they are tuned so the reference scenario reproduces the
  illustrative numbers. They are not real quotes.
- Q: What is the road baseline reliability score and where does it live? → A: Road baseline
  reliability is a configurable assumed constant (default 0.92), stored in
  `data/config.yaml`.
- Q: What time zone is used, and what defaults apply when the user provides only a date? →
  A: Time zone is IST. "Tomorrow" resolves relative to the current date; ready time
  defaults to 08:00 IST and deadline defaults to 18:00 IST if only a date is given.
- Q: Is waiting time for the next scheduled sailing included in door-to-door time? → A:
  Yes. Waiting time from the ready time to the next available sailing departure is included
  in total door-to-door time for water and hybrid plans.
- Q: When is hybrid marked infeasible? → A: Hybrid requires at least one jetty within a
  configurable radius of the origin node and at least one jetty within a configurable
  radius of the destination node. If either side has no qualifying jetty, hybrid is marked
  `not_viable` with the reason `no_jetty_within_radius`.
- Q: How is the "balanced" objective calculated and how are ties broken? → A: Balanced =
  weighted sum of normalised cost (weight 0.4), time (0.3), reliability (0.2), CO₂ (0.1).
  All four weights are read from `data/config.yaml`. Ties across any objective are broken
  by lower total cost.
- Q: Does the subsidy what-if apply to the entire plan cost or only part of it? → A:
  Subsidy applies to the water-leg freight cost only — never to handling charges or truck
  legs.
- Q: How is road distance computed and is OSRM supported? → A: Road distance defaults to
  straight-line distance multiplied by a configured road factor constant. OSRM integration
  is optional and out of scope for this prototype.
- Q: What exact fields are shown on each plan option card? → A: See FR-9 (Option Card
  Fields) below.
- Q: What are the exact edge-case behaviours for no available sailing, all options missing
  the deadline, and cargo heavier than any vessel? → A: See FR-10 (Edge Cases) below.
- Q: What accessibility requirements apply to the UI? → A: Readable contrast ratios
  (WCAG AA minimum). Every badge or tag (source_status, reliability label, deadline_ok)
  MUST have a text label; colour alone MUST NOT be the only indicator.

---

## Actors

| Actor | Role |
|---|---|
| Cargo owner | Primary user; enters shipment details and reads the comparison |
| Logistics company | Primary user; uses the comparison to advise clients |
| Presenter / demo operator | Resets the demo to its seed state |

---

## User Stories

### P1 — Side-by-side plan comparison

As a cargo owner, I describe a shipment (cargo type, weight in tonnes, origin node,
destination node, ready time in IST, deadline in IST, and objective) and see road, water,
and hybrid plans side by side. Each plan card shows the fields defined in FR-9. Costs are
displayed in ₹ (rupee symbol) in the UI and "Rs." in exported or plain-text contexts.
Weights are shown in tonnes.

### P1 — Recommendation with plain-language reason

As a cargo owner, I see exactly one recommended plan for my chosen objective (cheapest,
fastest, greenest, most reliable, or balanced). The recommendation includes a
plain-language "why" sentence. When road is the recommended option, that is stated
clearly. When water or hybrid cannot meet the deadline or is not cheaper, the system
recommends road and explains why. Ties on any objective are broken by lower total cost.

### P1 — Deadline slider

As a cargo owner, I change my deadline using a slider and the comparison and
recommendation update immediately. For the reference shipment (10 t, Kochi to Alappuzha)
a 10-hour deadline produces a hybrid recommendation; a 3-hour deadline produces a road
recommendation.

### P2 — Subsidy what-if

As a cargo owner, I can enable a "what-if policy subsidy" toggle to see how an incentive
on the water-leg freight would change the effective cost of water-inclusive plans. The
toggle is off by default, is clearly labelled as a hypothetical scenario, and does not
affect the recommendation unless I explicitly enable it. The subsidy is applied to the
water-leg freight cost only; handling and truck-leg costs are not affected.

### P2 — Data provenance tags

As a cargo owner, every figure I see (cost, time, CO₂, rate, speed, emission factor) is
tagged "sourced" or "assumed". Every badge has a text label; colour alone is not used to
convey meaning. A visible notice states that the prototype uses assumed rates.

### P3 — Demo reset

As a presenter, I can reset the system to its exact seed state with one action, without
restarting the server.

---

## Functional Requirements

**FR-1 — Three-plan response**
Given a valid shipment (origin, destination, weight, cargo type, ready time in IST,
deadline in IST), the engine returns exactly three plans: road, water, and hybrid. Each
plan contains an ordered list of legs, with each leg carrying: mode, distance, cost (₹),
time (h), CO₂ (kg), and the config values used. Plans that are physically impossible
return a `not_viable` status with a reason, rather than being omitted.

**FR-2 — Five objectives and one recommendation**
The engine supports five objectives: cheapest, fastest, greenest (lowest CO₂), most
reliable, and balanced. For each objective it marks one plan as recommended — only from
among plans that meet the deadline. Ties on any objective are broken by lower total cost.
Balanced scoring uses a weighted sum with weights from `data/config.yaml` (default:
cost 0.4, time 0.3, reliability 0.2, CO₂ 0.1). Each component is normalised across the
three plans before weighting.

**FR-3 — No-deadline-met fallback**
If no plan meets the deadline, the engine returns a clear "no plan meets deadline" notice
and marks the fastest plan as the fallback suggestion (not a recommendation).

**FR-4 — Reliability score**
Road reliability is a configurable constant (default 0.92, stored in `data/config.yaml`,
`source_status: assumed`). For water and hybrid plans the reliability score (0–100,
integer) is computed deterministically from three factors: schedule buffer (slack between
arrival and deadline), vessel draft versus route depth margin, and vessel on-time rate.
Each factor contributes a named sub-score and a human-readable reason string. The three
reliability sub-weights MUST sum to 1.0; the engine raises `ConfigError` if they do not.
The score is labelled "simulated model" in all outputs and the UI.

**FR-5 — Config-only constants**
All rates (₹/tonne-km for road, ₹/tonne for water leg), speeds (km/h), emission factors
(kg CO₂/tonne-km), handling times (h), loading/unloading costs (₹/tonne), route depth
data, jetty-search radius, road factor, and policy values are read from `data/config.yaml`
at startup. A missing required configuration value causes the engine to return a clear,
named error rather than a default or a silent failure.

**FR-6 — Subsidy what-if**
A boolean `subsidy_enabled` flag is accepted as part of the request (default: false).
When true, a configured subsidy percentage is applied to the water-leg freight cost only;
handling charges and truck-leg costs are not modified. The modified cost is shown alongside
the original. The subsidy value and its `source_status` are read from configuration.

**FR-7 — Assumptions list**
Every plan response includes a list of the config values used in its calculation, each
with its `source_status` ("sourced" or "assumed") and the note from configuration.

**FR-8 — Seed data**
The system ships with seed data containing: 8–10 Kerala nodes with names, approximate
coordinates, and node type (origin site, jetty, hub); 6–8 vessels with capacity, draft,
and on-time rate; 2–3 recurring sailings; 10–15 cargo requests covering the reference
scenario and varied deadlines, including edge-case scenarios (cargo heavier than any
vessel, no-deadline-met cases).

**FR-9 — Option card fields**
Each plan option card in the UI displays:

| Field | Detail |
|---|---|
| Mode label | Road / Water / Hybrid |
| Total cost | ₹ N,NNN with source_status tag |
| Effective cost (subsidy ON) | ₹ N,NNN (shown only when subsidy toggle is enabled) |
| Door-to-door time | N.N h (includes waiting time for sailing if applicable) |
| CO₂ estimate | NNN kg with source_status tag |
| Reliability score | NN/100 labelled "simulated model" with expandable reasons |
| Deadline met | Yes / No (text label + colour indicator) |
| Recommended badge | Shown on the single recommended plan; labelled with objective |
| Why text | One plain-language sentence explaining the recommendation |
| Not viable reason | Shown instead of cost/time if plan is infeasible |
| Legs summary | Collapsible list of legs with per-leg mode, distance, cost, time |

**FR-10 — Edge cases**

- *No sailing available for water/hybrid*: The water and/or hybrid plan is returned with
  `not_viable: true` and reason `no_sailing_available`. Road is compared as the sole
  viable option; if it meets the deadline it is recommended.
- *All options miss the deadline*: FR-3 applies — no plan is recommended; the fastest plan
  is shown as a fallback suggestion with a banner "No option meets your deadline."
- *Cargo heavier than any vessel's capacity*: The water and hybrid plans are returned with
  `not_viable: true` and reason `cargo_exceeds_all_vessel_capacity`. Road is evaluated
  normally. The engine MUST NOT raise an exception.
- *Hybrid: no jetty within radius*: Hybrid is returned with `not_viable: true` and reason
  `no_jetty_within_radius` (origin or destination side stated explicitly).
- *Missing config value*: The engine returns a named error identifying the missing key;
  no partial plan is emitted.
- *ready_time omitted*: Defaults to 08:00 IST on the specified date.
- *deadline omitted or date-only*: Defaults to 18:00 IST on the specified date.

---

## Reference Scenario

| Attribute | Value |
|---|---|
| Cargo | 10 t construction sand |
| Origin | Kochi (Maradu) |
| Destination | Alappuzha |
| Ready time | 08:00 IST |
| 10 h deadline | 18:00 IST — hybrid recommended |
| 3 h deadline | 11:00 IST — road recommended |
| All-road (indicative) | Rs. 9,000 · 2.5 h · 50 kg CO₂ |
| Hybrid (indicative) | Rs. 7,900 · 7.5 h · 26 kg CO₂ (includes sailing wait) |
| Hybrid with subsidy ON | Rs. 6,325 effective water-leg cost |

All figures above use placeholder assumed rates (not real quotes) and exist solely to pin
the acceptance test. They carry `source_status: assumed`.

---

## Success Criteria

| ID | Criterion | Measurement |
|---|---|---|
| SC-1 | Reference scenario: 10 h deadline → hybrid recommended; 3 h deadline → road recommended | Automated pytest: both cases pass |
| SC-2 | Comparison updates within one second of a deadline change | Measured from user interaction to updated display |
| SC-3 | 100% of displayed numbers carry a sourced/assumed tag | Visual review of every figure in the UI |
| SC-4 | A first-time viewer identifies the recommended option and reason within 10 seconds | Observed in a 3-person quick usability check |
| SC-5 | Edge cases (no sailing, all miss deadline, cargo overweight) return structured not_viable results without exceptions | Automated pytest covering each edge case |
| SC-6 | Every badge and status indicator has a text label; no information conveyed by colour alone | Visual accessibility review |

---

## Key Entities

| Entity | Attributes |
|---|---|
| Shipment | cargo_type, weight_t, origin_node, destination_node, ready_time (IST), deadline (IST), objective, subsidy_enabled |
| Node | id, name, type (site/jetty/hub), lat, lon |
| Edge | from_node, to_node, mode (road/water), distance_km, depth_m (water only) |
| Vessel | id, name, capacity_t, draft_m, on_time_rate |
| Sailing | id, vessel_id, route (list of nodes), departure_time (IST), frequency |
| Leg | mode, from_node, to_node, distance_km, cost_₹, time_h, co2_kg, config_values_used |
| Plan | mode_label (road/water/hybrid), legs, total_cost_₹, effective_cost_₹ (subsidy), total_time_h, total_co2_kg, reliability_score, reliability_reasons, deadline_ok, recommended, objective, why_text, not_viable, not_viable_reason, assumptions |
| Config value | key, value, source_status, note |

---

## Out of Scope

- Authentication or user accounts
- Payment processing or invoicing
- Live GPS or real-time vessel tracking
- Real-time water depth or weather data
- Forecasting models
- OSRM or live road-routing APIs (straight-line × road factor is the default)
- Optimisation beyond greedy selection among the three fixed mode plans
- Integration with FOCAL, PANI, CAR-D, or Jalyan (per their documented scope)

---

## Assumptions

1. Road distance between any two nodes is approximated as straight-line distance multiplied
   by a road-factor constant read from configuration (`source_status: assumed`).
2. Water distance follows the navigable route defined in the edge graph; no real nautical
   chart data is used (`source_status: assumed`).
3. A "hybrid" plan always follows the fixed pattern: origin → origin-side jetty (truck) →
   destination-side jetty (barge) → destination (truck). No multi-hop water routing is
   considered in this feature.
4. Reliability score sub-weights are read from configuration; defaults in the config file
   are marked `source_status: assumed`.
5. Road reliability is a fixed assumed constant (default 0.92) from configuration.
6. Waiting time from ready time to the next available sailing departure is included in
   total door-to-door time for water and hybrid plans (`source_status: assumed`).
7. The seed data uses simulated operators and cargo owners; no real personal data is
   included.
8. Placeholder rates are assumed values tuned to reproduce the reference scenario
   illustrative numbers; they are not real market quotes.

---

## Constraints (from Constitution)

- All numeric constants MUST be stored in `data/config.yaml` or `data/seed.json`.
- Every displayed number MUST carry a `source_status` tag in the UI.
- Every badge or status indicator MUST have a text label; colour alone MUST NOT convey
  information (accessibility requirement).
- The subsidy toggle MUST default to OFF; subsidy MUST apply only to water-leg freight.
- Engine functions MUST be pure and have passing pytest tests.
- The demo MUST work offline; no live APIs are required.
- No booking is confirmed in this feature (that is Feature 002).
