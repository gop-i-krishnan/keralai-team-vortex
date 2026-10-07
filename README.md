# JalSetu — Kerala waterway shipment decision engine

KeralAI Grand Challenge 2026 (Kochi), Team Vortex, Problem 07 (Backwater Cargo Exchange).
A **prototype** that compares road and hybrid (road + water) door-to-door plans for a shipment, recommends
one with a plain-English reason, matches the shipment to vessel sailings, and lets a person confirm
bookings, handle simulated disruptions, and register vessels and warehouses.

- All decisions are deterministic Python in `backend/engine/` (no I/O, no LLM calls, checked by grep).
- No LLM prices, ranks, scores or recommends. The demo never calls an LLM.
- A person must confirm every booking, every re-plan, and every hazardous-cargo booking.
- Everything runs offline. No API keys. State is in memory.

Full status of every feature: **[docs/SPEC.md](docs/SPEC.md)**. Competition write-up: **[docs/SUBMISSION.md](docs/SUBMISSION.md)**.

![Landing screen: 10 h deadline recommends hybrid](docs/screenshots/01-hero-deadline-10h-hybrid.png)
![Same screen with the deadline slider at 3 h: road](docs/screenshots/02-hero-deadline-3h-road.png)

## What is real and what is not

| Label | Meaning |
|---|---|
| **BUILT AND TESTED** | Covered by pytest tests that pass today |
| **BUILT, MOCKED** | Runs, but data/actor/integration is simulated and tagged `[simulated]` |
| **ROADMAP** | Not built, or never run |

| Capability | Status |
|---|---|
| Road vs hybrid comparison with reason; subsidy what-if (OFF by default) | BUILT AND TESTED |
| Sailing matching, capacity ranking, excluded vessels with reasons | BUILT AND TESTED |
| Two-step booking confirmation; hazard classes with hard filter | BUILT AND TESTED |
| Vessel registration (form or pasted English message), sailings, Bayesian reliability | BUILT AND TESTED |
| Disruption re-plan: ranked alternatives, explicit confirm | BUILT AND TESTED |
| Warehouse registry, utilisation, staging plan | BUILT AND TESTED |
| Vessel verification, compliance review, milestones, disruption trigger, notifications | BUILT, MOCKED |
| Delivery history, warehouses, operators, cargo (seed data) | BUILT, MOCKED |
| Live IBM watsonx.ai Granite parsing | ROADMAP (code present, never run) |
| Live GPS, payments, authentication, real WhatsApp/SMS, vessel-registry check, Malayalam intake, database | ROADMAP |

Test status today: **261 passed** (`python -m pytest backend/ -q`). The React UI has no automated tests;
see screenshots in `docs/screenshots/`.

## Run the demo

Prerequisites: Python and Node.js. Tested only on Python 3.14.5 and Node.js 24.14.0 (Windows 11); other versions are untested.

**Terminal 1 — backend, from the repository root**

```
python -m venv .venv
# Windows PowerShell:  .venv\Scripts\Activate.ps1      macOS/Linux:  source .venv/bin/activate
pip install -r backend/requirements.txt
```
Then start it (bash / macOS / Linux / Git Bash):
```
JALSETU_MOCK_LLM=1 python -m uvicorn backend.api.main:app --port 8000
```
Windows PowerShell:
```
$env:JALSETU_MOCK_LLM="1"; python -m uvicorn backend.api.main:app --port 8000
```

**Terminal 2 — frontend**

```
cd frontend
npm install
npm run dev
```
Open **http://localhost:5173**. API docs at http://localhost:8000/docs. (CORS allows only port 5173.)

**Run the tests**
```
python -m pytest backend/ -q
```
Expected: `261 passed`.

## Five-minute demo script

1. **Hero** (landing screen, no clicks): 10 t Kochi Thevara → Alappuzha. Drag the deadline slider: 10 h → HYBRID,
   3 h → ROAD. Every number carries `[sourced]`, `[assumed]` or `[simulated]`.
2. **Hazard**: Shipper → Post cargo → class *Flammable* (compliance banner appears) → Post → Matches: no certified
   vessel, with a reason per excluded sailing.
3. **Book**: post a *General* cargo → Matches → Select → Confirm → Preview → Confirm booking.
4. **Disruption**: My shipments → *Advance milestone* twice → *⚡ Simulate disruption* → Trigger → notification
   preview and *Show alternatives* → *Accept this plan* → *Confirm re-plan*. Nothing changes until that last click.
5. **Planner → Disruption summary**, **Boat owner → Register vessel → Paste a message → Read message**.
6. **Reset Demo** (top right) restores the seed state.

![Disruption, notification preview and ranked alternatives](docs/screenshots/05-shipment-disruption-ranked-alternatives.png)

More screenshots (all taken from the running app): `docs/screenshots/` and [docs/SPEC.md](docs/SPEC.md#4-screenshots-real-from-the-running-app).
To regenerate them: `pip install websockets`, start both servers, then `python docs/screenshots/capture.py`
(needs Chrome or Edge; dev tooling only).

## Data honesty

Every constant is in `data/config.yaml` tagged `sourced` or `assumed` with a note. Only four values are
`sourced` (IST offset, road and water CO₂ factors, IBM model id) and **the CO₂ factors have not been
re-checked against the IPCC table by the team**. All rates, speeds, weights and hazard rules are assumptions to be
verified with IWAI / PESO / state authorities. All shippers, operators, vessels, delivery history and
warehouses in `data/seed.json` are fictional and tagged `simulated`. The generated tables are in
[docs/SPEC.md §5](docs/SPEC.md#5-data-honesty-sourced-assumed-simulated) and are checked by a test.

## Main limitations

- In-memory state; no authentication, database, payments, live tracking or real messaging.
- Distances are straight-line × a factor, not routed; only four illustrative jetties.
- Hybrid cost and CO₂ are port-to-port (no first/last-mile truck legs).
- Hazard rules are placeholders, not regulations; the system gives eligibility guidance only.
- Message parsing is regex-based and English-only; no LLM is used in the demo.
- Re-plans use a demo clock and do not change sailing capacity. Several controls (verify, compliance review,
  advance, disrupt) are open demo buttons.

Complete list: [docs/SPEC.md §6](docs/SPEC.md#6-limitations).

## API (also at /docs)

| Method | Path | Description |
|---|---|---|
| POST | /api/options | Compare road/hybrid plans |
| POST | /api/match | Rank sailings for cargo (hazard filter, excluded list) |
| POST | /api/cargo, GET /api/cargo/list | Post / list cargo |
| POST | /api/book, /api/book/{id}/confirm | Create booking (pending), human confirmation |
| POST | /api/compliance/review/{id}/approve | Simulated compliance review (hazardous cargo) |
| POST | /api/parse, /api/operator/message | Free-text intake (offline parser) |
| POST | /api/vessel/register, /api/vessel/parse-message, /api/sailing/publish | Vessel and sailing registration |
| POST | /api/admin/vessel/{id}/verify, /suspend, /reinstate | Simulated admin actions |
| POST | /api/booking/{id}/deliver, GET /api/operator/{id}/profile | Delivery record, reliability |
| GET | /api/bookings, /api/booking/{id} | Shipments with milestones and event log |
| POST | /api/demo/booking/{id}/advance, /disrupt | Simulated milestone and disruption controls |
| POST | /api/replan/{id}, /api/replan/{id}/confirm | Re-plan proposal (read-only), explicit confirm |
| POST | /api/booking/{id}/notify | Notification preview (never sent) |
| GET | /api/disruptions/summary, /api/viability | Planner analytics |
| POST/GET | /api/warehouse/register, /list, /stage, /stage/confirm, /utilisation | Warehouses and staging |
| POST | /api/demo/reset | Reset to seed state |
| GET | /api/config/assumptions | All config values with tags |

Contracts for Features 004–006: `specs/*/contracts/openapi.yaml`.

## Disclosures

AI tools (IBM Bob, Claude Code), specification tooling (Spec Kit), LLM provider (IBM watsonx.ai, optional and not
used in the demo) and every library: [docs/disclosures.md](docs/disclosures.md) and [ATTRIBUTIONS.md](ATTRIBUTIONS.md).

## Provenance note

Parts of the project (specs, constitution, seed data, engine, initial UI) were prepared on 6 Oct 2026, the
evening before the event. Commit author dates in early history do not reflect real writing time; file timestamps
and the organisers' review take precedence.
