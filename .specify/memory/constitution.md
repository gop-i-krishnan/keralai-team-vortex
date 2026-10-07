# JalSetu Project Constitution

**Version:** 1.1.0
**Ratification date:** 2026-07-15
**Last amended:** 2026-10-07
**Status:** Active

---

## Preamble

JalSetu is an AI waterway logistics orchestrator for Kerala, built as a 24-hour hackathon
prototype for the KeralAI Grand Challenge 2026. Its purpose is to compare road, waterway, and
hybrid shipment plans and recommend the best door-to-door option using deterministic,
auditable logic — without assuming water is always superior.

This constitution is the supreme governance document for the project. It outranks all feature
specifications, implementation plans, and task lists. Every engineer, agent, and reviewer
working on JalSetu MUST read and comply with this document before making any contribution.
Conflicts between any other document and this constitution MUST be resolved in favour of
the constitution.

---

## Principles

### P1 — Shipment First, Vessel Second

The unit of decision is a **shipment**, not a boat.

- `build_plans()` MUST generate road, water, and hybrid door-to-door options for every request.
- The system MUST recommend road when road is the better option by the scoring criteria.
- No code path, UI element, or prompt MAY assume that water transport is the default winner.
- Vessel availability is a constraint on a plan, not the starting point of a decision.

**Rationale:** Cargo owners care about outcomes (cost, time, CO₂, reliability), not vessel types.
Defaulting to water would introduce systematic bias and reduce shipper trust.

---

### P2 — Transparent, Deterministic Logic

All scoring, pricing, and recommendation logic MUST be deterministic code with human-readable
reasons.

- `backend/engine/` functions MUST be pure: same inputs → same outputs, no randomness, no I/O,
  no external calls.
- Every plan comparison MUST produce a `reason` string that a non-technical user can read and
  verify.
- Language models (LLMs) MAY ONLY be used to parse natural-language text into structured data
  fields (cargo weight, origin, destination, deadline).
- LLMs MUST NEVER price, rank, score, or recommend. Any LLM output that contains a cost
  estimate, a mode recommendation, or a relative comparison of options is a constitution
  violation.
- The scoring formula and all weights MUST be readable in `data/config.yaml`.

**Rationale:** Hackathon judges, regulators, and cargo owners must be able to audit every number.
Non-deterministic recommendations erode trust and cannot be defended under time pressure.

---

### P3 — Honest Data

Every numeric constant used by the engine MUST live in `data/config.yaml` or `data/seed.json`.
No constant MAY be hardcoded in Python or JavaScript source files.

- Each value in `data/config.yaml` MUST carry:
  - `source_status`: exactly one of `"sourced"` or `"assumed"`.
  - `note`: a human-readable string citing the source or explaining the assumption.
- Every number displayed in the UI MUST render a visible `[sourced]` or `[assumed]` badge
  adjacent to the value. Hiding, omitting, or styling badges into invisibility is a violation.
- If a jetty name, freight rate, depth, or policy rule is unknown, the team MUST either ask a
  domain expert or mark the value `assumed` with an explanatory note. Invented facts that are
  not flagged are a violation.
- `water_km = straight_km × tortuosity_factor` — the tortuosity factor MUST be a named entry
  in `data/config.yaml`, not an inline literal.

**Rationale:** Hackathon prototypes are often critiqued for using made-up numbers. Explicit tagging
converts a weakness into a demonstration of intellectual honesty and production readiness.

---

### P4 — Subsidy Is a What-If

Any government incentive or subsidy scheme MUST be modelled as an optional scenario toggle.

- The subsidy toggle MUST default to **OFF** in every context: API request, UI render, demo
  reset, and test fixture.
- When OFF, subsidy values MUST NOT alter any cost, score, or recommendation.
- When ON, the subsidy MUST apply only to the water-leg freight cost and MUST be clearly
  labelled in the UI and API response.
- A comment in `data/config.yaml` next to every subsidy value MUST note that available Kerala
  government schemes may not cover short inland waterway routes.

**Rationale:** Falsely presenting a subsidised fare as the base case would mislead shippers and
misrepresent the economics of the NW-3 corridor to evaluators.

---

### P5 — Test-First for the Engine

No engine function is complete until its pytest tests pass.

- Engine tests MUST be written before or alongside the implementation, never after.
- All engine functions MUST be pure (P2); tests therefore require no mocking of I/O or external
  services.
- The canonical scenario MUST be covered by at least one test:
  - **10 t, Kochi → Alappuzha, 10 h deadline** → recommended mode is **hybrid**.
  - **10 t, Kochi → Alappuzha, 3 h deadline** → recommended mode is **road**.
- A task is not marked complete until `pytest backend/` exits with 0 failures.
- Test files live in `backend/engine/tests/` and `backend/api/tests/`.

**Rationale:** The engine is the core intellectual contribution of JalSetu. Bugs in pure functions
are cheap to catch with unit tests; bugs found during a live demo are not.

---

### P6 — Layer, Do Not Replace

JalSetu positions itself as an **intelligence layer above existing systems**, not a replacement
for them.

- Existing platforms referenced by JalSetu — including FOCAL, PANI, CAR-D, and Jalyan — MUST
  be described using the phrase **"per their documented scope"** whenever their capabilities are
  mentioned.
- No documentation, slide, UI copy, or code comment MAY describe any existing platform as
  ineffective, outdated, incomplete, or inferior.
- JalSetu's value proposition is additive: it provides cross-mode optimisation and shipper-facing
  decision support that complements, not competes with, operator-facing tools.

**Rationale:** The hackathon evaluators include government and industry stakeholders who built or
operate those systems. Disparaging claims would be factually unsupported and politically damaging.

---

### P7 — Human in the Loop

No booking MUST be confirmed without an explicit human confirmation step.

- The booking flow MUST be a minimum two-step sequence:
  1. `POST /api/book` — creates a booking in `pending` state; returns a preview to the user.
  2. `POST /api/book/{id}/confirm` — transitions to `confirmed` state only after this call.
- A booking body that sets `human_confirmed: true` in step 1 MUST NOT skip step 2 or auto-confirm.
  The confirm endpoint is the canonical gate; pre-set flags in the request body are ignored.
- Any parse result with `confidence < 0.8` MUST be surfaced to the user for correction before
  the parsed data is used in any plan computation or booking creation.
- The UI MUST render a confirmation dialogue with a clearly labelled "Confirm Booking" action;
  implicit closures or timeouts MUST NOT trigger confirmation.

**Rationale:** Logistics bookings carry real financial and operational consequences. Automated
confirmation without human review is unsafe even in a prototype, where accidental submissions
during a demo could confuse evaluators.

---

### P8 — Graceful Degradation

The demo MUST work fully offline. Every external dependency MUST have a documented fallback.

| Dependency | Fallback |
|---|---|
| LLM / IBM Granite | `MockAdapter` (fixture-based regex parser, `JALSETU_MOCK_LLM=1`) |
| Road routing API | Straight-line distance × road detour factor from `data/config.yaml` |
| Live vessel positions | Static seed data from `data/seed.json` |
| Map tiles | Static SVG corridor diagram embedded in the frontend |

- No network call MAY block the critical path of the demo.
- `JALSETU_MOCK_LLM=1` MUST be the default in `README.md` startup instructions and in
  `.env.example`.
- A demo reset (`POST /api/demo/reset`) MUST restore all in-memory state to the seed in under
  1 second with no external dependencies.

**Rationale:** Hackathon venues have unreliable Wi-Fi. A prototype that cannot demo offline is a
prototype that cannot demo.

---

### P9 — Privacy and Disclosure

All personal and operator data used in the prototype MUST be simulated.

- No real shipper names, vessel registration numbers, phone numbers, or addresses MAY appear in
  `data/seed.json` or any fixture.
- No personal data MAY be transmitted to any LLM, API, or third-party service.
- `docs/disclosures.md` MUST list every third-party tool used in the project, including:
  AI coding assistants, LLM providers, map data sources, and open-source frameworks.
- The disclosures file MUST be kept current; adding a new external dependency without updating
  `docs/disclosures.md` is a violation.

**Rationale:** Responsible AI practice and hackathon rules both require disclosure of AI tool
usage. Simulated data prevents accidental PII leakage during live demos or public repository
exposure.

---

### P10 — Simplicity for the Time Box

Features outside the defined scope MUST NOT be added.

- The following are explicitly **out of scope** for this prototype and MUST NOT be built:
  authentication, payments, live GPS tracking, weather routing, blockchain, demand forecasting
  models, multi-tenant data isolation, background workers, or database infrastructure.
- State MUST be held in-memory; no persistent database (SQL, NoSQL, file-based) MAY be
  introduced.
- The project MUST NOT grow beyond two top-level directories (`backend/`, `frontend/`) plus
  `data/`, `docs/`, and `.specify/`.
- When in doubt about whether a feature is in scope, the answer is **no**; consult the spec
  before adding anything.
- Prefer fewer files and simpler constructs over abstraction layers that would not be needed
  within the prototype's operational lifetime.

**Rationale:** Time-boxed projects fail most often by scope creep. A complete, well-tested,
well-explained prototype of a smaller scope beats an incomplete prototype of a larger one.

---

### P11 — Safety Before Convenience

Hazardous or restricted cargo is never auto-matched. The system provides routing and eligibility
guidance only — it MUST NOT provide handling or technical safety instructions.

- Hazardous cargo classes covered by this principle include, at minimum: explosives, flammable
  liquids and solids, toxic/corrosive substances, and liquid bulk cargoes subject to IWAI or
  state-authority permit requirements.
- Every hazard classification rule and vessel certification requirement MUST be stored in
  `data/config.yaml` with `source_status: assumed` and a `note` stating
  `"verify with IWAI / PESO / state authority before production use"`.
- Vessels that lack the required certification for a hazard class MUST be excluded by a named
  hard filter (e.g. `missing_hazmat_cert`) before any scoring takes place. They MUST appear in
  the excluded list with that reason — not silently dropped.
- No booking, match, or plan involving hazardous cargo MAY transition to `confirmed` state
  without an explicit human compliance-review step, separate from and in addition to the
  standard P7 booking confirmation.
- The UI MUST display a clearly visible compliance-review banner for any shipment flagged as
  hazardous. The banner MUST carry a text label; colour alone MUST NOT be the only indicator.
- The system MUST NOT emit text that could be interpreted as handling, stowage, or emergency
  response instructions. If asked, it MUST redirect the user to the relevant authority.

**Rationale:** Hazardous cargo on inland waterways is governed by IWAI, PESO, and state-level
regulations that change and carry criminal liability. A prototype that silently routes hazmat
creates safety and legal risk that no hackathon exemption covers.

---

### P12 — Re-plan, Never Auto-Switch

When a disruption occurs (sailing cancelled, vessel capacity reduced, deadline brought forward),
the system proposes alternatives but MUST NOT activate any new plan without human confirmation.

- The disruption engine MUST produce a structured `ReplanProposal` that includes, for each
  alternative: mode, cost delta (₹), time delta (h), and whether the new plan meets the
  original deadline. All deltas are relative to the disrupted plan.
- A `ReplanProposal` MUST NOT update any booking, capacity figure, or sailing record in the
  in-memory state. It is read-only until the cargo owner (and operator, where relevant) confirms.
- The confirmation step for a re-plan follows the same two-step flow as P7: preview first,
  explicit confirm second. Setting a flag in the proposal request body MUST NOT skip the confirm
  endpoint.
- The UI MUST present re-plan alternatives side-by-side with their cost/time/deadline impact and
  require an explicit "Accept this plan" action. Dismissing the disruption notice MUST NOT
  silently accept any alternative.
- All cost and time figures in a `ReplanProposal` carry `source_status` tags and the same
  port-to-port / truck-leg caveats as standard plans (P3).

**Rationale:** Disruptions in freight logistics have cascading financial consequences. Automatic
re-routing without owner consent would expose JalSetu to liability and undermine shipper trust.

---

### P13 — Simulated Is Labelled

Any feature or data point that is simulated in the prototype MUST carry a visible `[simulated]`
tag in every context where it appears: API responses, UI components, test fixtures, and
documentation.

- Simulated features include, at minimum: vessel tracking milestones, push notifications,
  delivery history, vessel credential verification, and demand/volume statistics.
- A `[simulated]` tag is distinct from `[assumed]`. `[assumed]` means a real-world value whose
  exact figure is uncertain; `[simulated]` means a feature that does not exist yet and whose
  output is fabricated for demo purposes.
- No UI copy, documentation, or spoken demo script MAY claim that simulated features are live or
  production-ready.
- `data/seed.json` fields that represent simulated state (e.g. vessel position, on-time history)
  MUST carry `"source_status": "simulated"` rather than `"assumed"`.
- Adding a `source_status: simulated` value to `data/config.yaml` is a P3 violation; simulated
  values belong in `data/seed.json` only.

**Rationale:** Presenting simulated tracking or verification as live capability would constitute
a material misrepresentation to evaluators and potential users.

---

### P14 — Reputation Is Evidence-Based and Fair

Operator reliability statistics MUST be computed from recorded delivery history with a
configured Bayesian prior, so that new operators are not penalised for having no history.

- Every displayed reliability statistic MUST show the number of recorded trips on which it is
  based (e.g. "87% on-time — 23 trips [simulated]").
- The prior parameters (prior trip count and prior on-time rate) MUST be stored in
  `data/config.yaml` with `source_status: assumed` and a note explaining the choice.
- The reliability formula MUST be deterministic and pure (P2): given the same history and prior,
  it MUST return the same score.
- Reliability statistics in the seed data are simulated and MUST carry `"source_status":
  "simulated"` per P13.
- No reliability score MAY be displayed without its trip count. Displaying only a percentage
  without a sample size is a violation.
- The engine MUST NOT incorporate subjective ratings, star scores, or any input that is not
  a recorded, timestamped delivery event.

**Rationale:** Unfair reliability scoring could systematically exclude small or new operators from
receiving cargo, creating an anti-competitive effect that would be difficult to detect and
justify to regulators.

---

### P15 — Privacy by Minimisation

Personal data is collected only to the minimum required for matching, and is never transmitted
beyond the prototype boundary.

- Phone numbers and email addresses MUST be scrubbed from any text before it is passed to an
  LLM or any external service. The `scrub_pii()` function in `backend/engine/parser.py` is the
  canonical implementation; all text-intake paths MUST call it.
- Registration data stored in `data/seed.json` MUST contain only fields that are strictly
  necessary for matching (operator id, simulated contact, capacity). No field MAY be added
  unless its matching purpose is documented in the entry's `note`.
- In the demo, all shipper and operator contact details MUST be fictional (e.g.
  `simulated@operator.example`). No real names, phone numbers, or addresses MAY appear.
- Any future addition of a real-data field requires an explicit amendment to this principle
  with a documented legal basis and retention policy.
- Compliance with this principle is verified by the existing `test_scrub_pii_removes_phone`
  and `test_scrub_pii_removes_email` tests; those tests MUST NOT be removed or weakened.

**Rationale:** Kerala's Personal Data Protection obligations and general responsible-AI practice
both require that personal data collection is proportionate, transparent, and bounded. A
prototype that accumulates unnecessary personal data is a liability, not an asset.

---

## Governance

### Authority Hierarchy

The following artifacts are listed in descending order of authority. Any artifact lower in
this hierarchy that contradicts a higher one MUST be updated to conform. The constitution is
**never** updated to conform to lower artifacts.

```
constitution.md   (this file — supreme)
      ↓
spec.md           (feature scope and user stories — one file per feature under specs/)
      ↓
plan.md           (design and architecture decisions — one file per feature)
      ↓
tasks.md          (implementation task list — one file per feature)
      ↓
source code
```

### Amendment Procedure

1. Open a pull request or raise the amendment in the team channel with the proposed change,
   the principle(s) affected, and the rationale.
2. State the version bump type (MAJOR / MINOR / PATCH) and justify it:
   - **MAJOR**: a principle is removed, fundamentally redefined, or made incompatible with a
     prior commitment.
   - **MINOR**: a new principle or section is added, or existing guidance is materially expanded.
   - **PATCH**: clarification, wording improvement, typo fix, non-semantic refinement.
3. At least one other team member (or the project lead in a solo hackathon) MUST review and
   approve before the constitution is updated.
4. Update the **Version**, **Last amended** header fields.
5. Append an entry to the Amendment Log below, recording the version, date, author, and a
   one-line rationale.
6. Remove the SYNC IMPACT REPORT comment block before merging.

### Compliance Review

- Before each demo milestone, the team MUST verify all Quality Gates (see below) pass.
- Any new engine function merged without passing tests is an immediate P5 violation.
- Any constant found hardcoded in source rather than in `data/config.yaml` is a P3 violation.
- Any hazardous-cargo code path that bypasses the hard filter or the compliance-review step
  is an immediate P11 violation.
- Any simulated feature presented without a `[simulated]` tag is a P13 violation.
- Violations discovered during review MUST be remediated before the demo, not deferred.

---

## Quality Gates

All gates MUST pass before the prototype is considered demo-ready:

| Gate | Check |
|---|---|
| **Tests green** | `pytest backend/ -q` exits 0; no skipped tests without justification |
| **Config-only constants** | Search for hardcoded rates, speeds, emission factors, hazard rules, and weights in `*.py` and `*.jsx` returns no matches |
| **Tags visible in UI** | Every numeric value rendered in the frontend carries a `[sourced]`, `[assumed]`, or `[simulated]` badge in the DOM |
| **Demo reset works** | `POST /api/demo/reset` followed by a full options request returns deterministic seed results within 1 second, with no network calls |
| **Hazmat gate** | Any request with a hazardous cargo type returns a compliance-review flag and no auto-confirmed booking |
| **Simulated tag** | Every feature listed under P13 renders a visible `[simulated]` tag in the UI and API response |

---

## Amendment Log

| Version | Date | Author | Summary |
|---|---|---|---|
| 1.0.0 | 2026-07-15 | JalSetu team | Initial ratification — 10 principles, governance, quality gates |
| 1.1.0 | 2026-10-07 | JalSetu team | Added P11 (Safety Before Convenience), P12 (Re-plan Never Auto-Switch), P13 (Simulated Is Labelled), P14 (Reputation Is Evidence-Based and Fair), P15 (Privacy by Minimisation); updated Governance authority hierarchy to name spec/plan/tasks files explicitly; added two new Quality Gates (Hazmat, Simulated tag); updated Compliance Review checklist. MINOR bump: no existing principle changed. |
