# JalSetu — Kerala waterway shipment decision engine

KeralAI Grand Challenge 2026 (Kochi), Team Vortex, Problem 07 (Backwater Cargo Exchange).
JalSetu compares road, waterway and hybrid door-to-door plans for a shipment and recommends one,
with a plain-English reason. All decisions are deterministic Python (`backend/engine/`). No LLM
prices, ranks or recommends. A person must confirm every booking.

**Offline by default.** The demo needs no API keys and makes no external network calls (tested with
all non-loopback network access blocked). An optional IBM watsonx.ai Granite adapter exists for
text parsing only; it is used only if you set `JALSETU_MOCK_LLM=0`, install `ibm-watsonx-ai` and
provide your own keys. Libraries: see `ATTRIBUTIONS.md` and `docs/disclosures.md`.

## Prerequisites
Python 3.11+ and Node.js 18+.

## 1. Backend (Terminal 1, from the repository root)

Windows PowerShell:
```
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r backend/requirements.txt
$env:JALSETU_MOCK_LLM="1"
python -m uvicorn backend.api.main:app --port 8000
```
macOS / Linux:
```
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
export JALSETU_MOCK_LLM=1
python -m uvicorn backend.api.main:app --port 8000
```
Optional: copy `.env.example` to `.env`. The defaults already work.

## 2. Frontend (Terminal 2)
```
cd frontend
npm install
npm run dev
```
Open http://localhost:5173 (backend must be running on port 8000).

## 3. Run the tests
```
python -m pytest backend/ -q
```
Expected: 52 passed.

## 4. Demo scenario
- Kochi Thevara Jetty -> Alappuzha Boat Jetty, 10 t, ready 04:00.
- Deadline 10 h -> recommended: hybrid. Deadline 3 h -> recommended: road.
- "Apply subsidy scenario" is a what-if and is OFF by default.
- "Reset Demo" restores the seed state.

## 5. Data honesty
Every constant is in `data/config.yaml` with `source_status` (`sourced` or `assumed`) and a note.
Most rates and speeds are **assumed** and must be verified with the relevant authority (e.g. IWAI)
before real use. All shippers, operators and cargo in `data/seed.json` are simulated.

## 6. API (also at http://localhost:8000/docs)
| Method | Path | Description |
|---|---|---|
| POST | /api/options | Compare road/hybrid plans |
| POST | /api/match | Rank sailings for cargo |
| POST | /api/book | Create booking (preview, pending) |
| POST | /api/book/{id}/confirm | Human confirmation step |
| GET  | /api/backhaul/{id} | Backhaul + pooling opportunities |
| POST | /api/parse | Parse free-text request |
| GET  | /api/viability | Corridor viability analysis |
| POST | /api/operator/message | Operator free text -> options |
| POST | /api/demo/reset | Reset to seed state |
| GET  | /api/config/assumptions | All config values + tags |

## 7. Provenance note
Parts of the project (specs, constitution, seed data, engine, initial UI) were prepared on
6 Oct 2026, the evening before the event. Commit author dates in early history do not reflect
real writing time; file timestamps and the organisers' review take precedence.
