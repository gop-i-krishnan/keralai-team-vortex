# JalSetu — Quick Start
# Run backend: python -m uvicorn backend.api.main:app --reload --port 8000
# Run frontend: cd frontend && npm run dev
# Offline demo: set JALSETU_MOCK_LLM=1 (default) — no API keys needed

## 1. Install backend dependencies
```
pip install fastapi "uvicorn[standard]" pydantic pyyaml rapidfuzz pytest httpx python-dotenv
```

## 2. Start the backend
```
# Windows PowerShell
$env:JALSETU_MOCK_LLM="1"
python -m uvicorn backend.api.main:app --reload --port 8000
```

## 3. Start the frontend (separate terminal)
```
cd frontend
npm install   # first time only
npm run dev   # opens http://localhost:5173
```

## 4. Run all tests
```
python -m pytest backend/ -v
```

## 5. Canonical demo scenario
- Origin: Kochi Thevara Jetty → Destination: Alappuzha Boat Jetty
- Weight: 10 t, Ready: 04:00, **Deadline: 10 h** → recommended: **hybrid**
- Weight: 10 t, Ready: 04:00, **Deadline: 3 h**  → recommended: **road**
- Tick "Apply subsidy scenario" to see what-if cost reduction
- Click "↺ Reset Demo" to restore seed state at any time

## 6. API endpoints
| Method | Path | Description |
|---|---|---|
| POST | /api/options | Compare road/hybrid plans |
| POST | /api/match | Rank sailings for cargo |
| POST | /api/book | Create booking (preview) |
| POST | /api/book/{id}/confirm | Human confirmation step |
| GET  | /api/backhaul/{id} | Backhaul + pooling opps |
| POST | /api/parse | Parse free-text request |
| GET  | /api/viability | Corridor viability analysis |
| POST | /api/operator/message | Operator free-text → options |
| POST | /api/demo/reset | Reset to seed state |
| GET  | /api/config/assumptions | All config values + tags |
| GET  | /docs | FastAPI interactive docs |
