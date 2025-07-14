<!--
SYNC IMPACT REPORT — for human review before commit; remove this block before merging.

Version change:   (none) → 1.0.0  (initial ratification)
Modified principles: N/A (initial document)
Added sections:   Preamble, Principles 1–10, Governance, Quality Gates, Amendment Log
Removed sections: N/A
Deferred TODOs:   None — all placeholders resolved from user input and repository context.
-->

# JalSetu Project Constitution

**Version:** 1.0.0
**Ratification date:** 2025-07-15
**Last amended:** 2025-07-15
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

## Governance

### Authority Hierarchy

```
constitution.md   (this file — supreme)
      ↓
spec.md           (feature scope and user stories)
      ↓
plan.md           (design and architecture decisions)
      ↓
tasks.md          (implementation task list)
      ↓
source code
```

Any artifact lower in this hierarchy that contradicts a higher one MUST be updated to conform.
The constitution is never updated to conform to lower artifacts.

### Amendment Procedure

1. Open a pull request or raise the amendment in the team channel with the proposed change and
   the principle(s) affected.
2. State the version bump type (MAJOR / MINOR / PATCH) and justify it:
   - **MAJOR**: a principle is removed, fundamentally redefined, or made incompatible with a
     prior commitment.
   - **MINOR**: a new principle or section is added, or existing guidance is materially expanded.
   - **PATCH**: clarification, wording improvement, typo fix, non-semantic refinement.
3. At least one other team member (or the project lead in a solo hackathon) MUST review and
   approve before the constitution is updated.
4. Update `CONSTITUTION_VERSION` and `LAST_AMENDED_DATE` in the header.
5. Append an entry to the Amendment Log below.

### Compliance Review

- Before each demo milestone, the team MUST verify all Quality Gates (see below) pass.
- Any new engine function merged without passing tests is an immediate P5 violation.
- Any constant found hardcoded in source rather than in `data/config.yaml` is a P3 violation.
- Violations discovered during review MUST be remediated before the demo, not deferred.

---

## Quality Gates

All four gates MUST pass before the prototype is considered demo-ready:

| Gate | Check |
|---|---|
| **Tests green** | `pytest backend/ -q` exits 0; no skipped tests without justification |
| **Config-only constants** | `grep -rn` for hardcoded rates, speeds, emission factors, and weights in `*.py` and `*.jsx` returns no matches |
| **Tags visible in UI** | Every numeric value rendered in the frontend carries a `[sourced]` or `[assumed]` badge in the DOM |
| **Demo reset works** | `POST /api/demo/reset` followed by a full options request returns deterministic seed results within 1 second, with no network calls |

---

## Amendment Log

| Version | Date | Author | Summary |
|---|---|---|---|
| 1.0.0 | 2025-07-15 | JalSetu team | Initial ratification — 10 principles, governance, quality gates |
