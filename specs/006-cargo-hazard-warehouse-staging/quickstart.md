# Quickstart Validation Guide: Feature 006

**Feature ID:** 006
**Phase:** Plan — Phase 1 Quickstart
**Date:** 2026-10-07

---

## Prerequisites

1. Python 3.11+ environment with project dependencies installed:
   ```
   pip install -r backend/requirements.txt
   ```
2. Environment variable set for offline/mock mode:
   ```
   set JALSETU_MOCK_LLM=1       # Windows PowerShell
   export JALSETU_MOCK_LLM=1    # bash/zsh
   ```
3. All 54 existing tests pass before starting:
   ```
   pytest backend/ -q
   ```

---

## A. Engine unit tests (pure functions, no server needed)

Run after each engine batch:

```powershell
pytest backend/engine/tests/ -q
```

Expected output after all engine work is complete:
```
collected XX items
.....  [engine tests]
XX passed in X.XXs
```

SC-1 through SC-8 from the spec are covered by these tests.

---

## B. API validation (requires running server)

Start the server:
```powershell
$env:JALSETU_MOCK_LLM=1
uvicorn backend.api.main:app --reload --port 8000
```

### B.1 — Hazard filter: flammable with no certified vessel (SC-1)

```powershell
# cargo-003 is the seed flammable cargo; no vessel has flammable cert
Invoke-RestMethod -Method Post -Uri http://localhost:8000/api/match `
  -ContentType application/json `
  -Body '{"cargo_id":"cargo-003","cargo_class":"flammable"}'
```

**Expected:**
```json
{
  "ranked": [],
  "excluded": [
    {"sailing_id":"sailing-001","vessel_id":"vessel-001","reason":"missing_hazmat_cert"},
    {"sailing_id":"sailing-002","vessel_id":"vessel-002","reason":"missing_hazmat_cert"}
  ]
}
```

### B.2 — Compliance gate: explosive booking (SC-2)

```powershell
# Step 1: create booking → should be pending_review
$book = Invoke-RestMethod -Method Post -Uri http://localhost:8000/api/book `
  -ContentType application/json `
  -Body '{"cargo_id":"cargo-004","sailing_id":"sailing-001"}'
$book.status   # expected: "pending_review"
$bid = $book.booking_id

# Step 2: try to confirm → should be rejected
Invoke-RestMethod -Method Post -Uri "http://localhost:8000/api/book/$bid/confirm" `
  -ContentType application/json -Body '{}'
# expected: {"error": "compliance_review_required"}

# Step 3: approve compliance review
Invoke-RestMethod -Method Post `
  -Uri "http://localhost:8000/api/compliance/review/$bid/approve" `
  -ContentType application/json `
  -Body '{"reviewer_note":"Demo review approved"}'

# Step 4: confirm now succeeds
Invoke-RestMethod -Method Post -Uri "http://localhost:8000/api/book/$bid/confirm" `
  -ContentType application/json -Body '{}'
# expected: {"status":"confirmed"}
```

### B.3 — Warehouse registration

```powershell
Invoke-RestMethod -Method Post -Uri http://localhost:8000/api/warehouse/register `
  -ContentType application/json `
  -Body '{
    "name":"Test Warehouse",
    "location_node_id":"node-001",
    "total_capacity_t":20.0,
    "storage_cost_per_t_per_day":5.0,
    "handling_in_cost_per_t":10.0,
    "handling_out_cost_per_t":10.0,
    "allowed_cargo_classes":["general"]
  }'
# expected: 201 with Warehouse JSON, source_status: "simulated"
```

### B.4 — Staging proposal (SC-3)

```powershell
# cargo-001 (10 t, Kochi → Alappuzha); wait > staging_wait_threshold_h (4h)
Invoke-RestMethod -Method Post -Uri http://localhost:8000/api/warehouse/stage `
  -ContentType application/json `
  -Body '{"cargo_id":"cargo-001","next_sailing_wait_h":8.0,"deadline_h":48.0}'
# expected: proposals list with at least one StagingPlan; total_cost_inr matches sum of 5 components
```

### B.5 — Staging confirmation capacity guard (SC-4)

```powershell
# First fill seed warehouse wh-001 (50 t capacity) to capacity using the API
# Then stage 1 more tonne
Invoke-RestMethod -Method Post -Uri http://localhost:8000/api/warehouse/stage `
  -ContentType application/json `
  -Body '{"cargo_id":"cargo-001","next_sailing_wait_h":8.0,"deadline_h":48.0}'
# Take the proposal_id from the response
$pid = "..."
Invoke-RestMethod -Method Post -Uri http://localhost:8000/api/warehouse/stage/confirm `
  -ContentType application/json `
  -Body "{`"proposal_id`":`"$pid`"}"
# If warehouse already full: expected 409 {"error":"warehouse_at_capacity"}
```

### B.6 — Warehouse list and utilisation

```powershell
Invoke-RestMethod http://localhost:8000/api/warehouse/list
Invoke-RestMethod http://localhost:8000/api/warehouse/utilisation
# expected: source_status: "simulated" on every row
```

### B.7 — Demo reset

```powershell
Invoke-RestMethod -Method Post http://localhost:8000/api/demo/reset
# Then check warehouse utilisation:
Invoke-RestMethod http://localhost:8000/api/warehouse/utilisation
# expected: all capacity_used_t == 0; runtime warehouses gone
```

---

## C. Full test suite

After all implementation is complete:

```powershell
pytest backend/ -q
```

Expected: all tests pass (existing 54 + new Feature 006 tests), 0 failures, 0 skipped.

---

## D. Constitution quality gates

```powershell
# No hardcoded constants in Python or JS (P3)
grep -rn "[0-9]\+\.[0-9]\+" backend/engine/ --include="*.py" | grep -v "test_" | grep -v "#"
# Expected: only formatting strings, no bare numeric constants

# No LLM calls inside engine/ (P2)
grep -rn "llm\|adapter\|watsonx\|granite" backend/engine/ --include="*.py"
# Expected: no matches
```

---

## E. Cross-references

- Data model: [`data-model.md`](data-model.md)
- API contract: [`contracts/openapi.yaml`](contracts/openapi.yaml)
- Feature spec: [`spec.md`](spec.md)
- Implementation plan: [`plan.md`](plan.md)
- Tasks: [`tasks.md`](tasks.md) *(generated in next phase)*
