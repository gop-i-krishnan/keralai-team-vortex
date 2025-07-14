# Quickstart & Validation Guide: Capacity Matching, Backhaul and Pooling

**Feature:** 002 — Capacity Matching, Backhaul and Pooling
**Created:** 2025-07-17
**Depends on:** Feature 001 running (backend + seed data loaded)

This guide validates Feature 002 end-to-end. Refer to
[`data-model.md`](data-model.md) and [`contracts/openapi.yaml`](contracts/openapi.yaml)
for schema details. Feature 001 quickstart covers environment setup — run that first.

---

## Prerequisites

Feature 001 backend running at `http://localhost:8000`.
All Feature 001 tests green (`pytest backend/ -v`).

No additional dependencies are required. Feature 002 adds no new Python packages.

---

## New engine modules

```
backend/engine/matching.py    # hard_filter, score_sailing, rank_sailings
backend/engine/backhaul.py    # find_backhaul
backend/engine/pooling.py     # find_pooling
```

All three are pure Python with no I/O. Restart the server after adding them:

```bash
cd backend
uvicorn api.main:app --reload --port 8000
```

---

## Run the automated tests

```bash
cd backend
pytest engine/tests/test_matching.py -v
pytest engine/tests/test_backhaul.py -v
pytest engine/tests/test_pooling.py  -v
pytest api/tests/test_match.py       -v
pytest api/tests/test_booking.py     -v
pytest api/tests/test_backhaul_api.py -v
pytest -v   # all tests — must all pass before any task is done
```

### Expected engine test outcomes

| Test | Expected result |
|---|---|
| `test_rank_hero` | `ranked` list non-empty; `sailing-001` present with score > 0 |
| `test_hard_filter_draft` | Vessel with draft > depth − margin excluded as `draft_too_deep` |
| `test_hard_filter_capacity` | 200 t shipment: `ranked` empty, all excluded as `capacity_exceeded` |
| `test_hard_filter_deadline` | Deadline before earliest arrival: all excluded as `deadline_not_met` |
| `test_weight_sum_1` | `abs(sum(match weights) - 1.0) < 1e-9` |
| `test_backhaul_seeded` | Hero booking confirmed → exactly 1 suggestion: cargo-013, 7 t, Alappuzha→Kochi |
| `test_backhaul_none` | Booking with no open return cargo → `[]`, no exception |
| `test_pooling_seeded` | Hero booking confirmed → exactly 2 suggestions: cargo-011 (4 t) and cargo-012 (3 t) |
| `test_pooling_greedy_order` | cargo-011 appears before cargo-012 (higher value-per-tonne) |
| `test_pooling_none` | No matching open requests → `[]`, no exception |

---

## Verify the seeded demo scenario via curl

### Step 1 — Match sailings for the hero shipment

```bash
curl -s -X POST http://localhost:8000/match \
  -H "Content-Type: application/json" \
  -d '{
    "cargo_type": "construction_sand",
    "weight_t": 10,
    "origin_node": "kochi-maradu",
    "destination_node": "alappuzha-depot",
    "ready_time": "08:00",
    "deadline": "18:00",
    "plan_mode": "water"
  }' | python -m json.tool
```

Expected: `ranked` array non-empty; `sailing-001` present; `excluded` may be empty or
contain vessels with insufficient draft or capacity for other test vessels in seed.

### Step 2 — Preview the booking (no state change)

```bash
curl -s -X POST http://localhost:8000/book \
  -H "Content-Type: application/json" \
  -d '{
    "sailing_id": "sailing-001",
    "cargo_type": "construction_sand",
    "weight_t": 10,
    "origin_node": "kochi-maradu",
    "destination_node": "alappuzha-depot",
    "ready_time": "08:00",
    "deadline": "18:00",
    "human_confirmed": false
  }' | python -m json.tool
```

Expected: response contains `"preview": true`, `estimated_cost_inr`, no `booking_id`.

### Step 3 — Confirm the booking

```bash
curl -s -X POST http://localhost:8000/book \
  -H "Content-Type: application/json" \
  -d '{
    "sailing_id": "sailing-001",
    "cargo_type": "construction_sand",
    "weight_t": 10,
    "origin_node": "kochi-maradu",
    "destination_node": "alappuzha-depot",
    "ready_time": "08:00",
    "deadline": "18:00",
    "human_confirmed": true
  }' | python -m json.tool
```

Expected:
```json
{
  "booking_id": "<32-char hex>",
  "sailing_id": "sailing-001",
  "backhaul_suggestions": [
    { "cargo_request_id": "cargo-013", "weight_t": 7, ... }
  ],
  "pooling_suggestions": [
    { "cargo_request_id": "cargo-011", "weight_t": 4, ... },
    { "cargo_request_id": "cargo-012", "weight_t": 3, ... }
  ]
}
```

Save `<booking_id>` from the response for step 4.

### Step 4 — Re-fetch suggestions via booking id

```bash
export BOOKING_ID="<paste hex from step 3>"
curl -s http://localhost:8000/backhaul/$BOOKING_ID | python -m json.tool
```

Expected: same backhaul and pooling lists as step 3.

### Step 5 — Verify capacity was decremented

```bash
curl -s -X POST http://localhost:8000/match \
  -H "Content-Type: application/json" \
  -d '{
    "cargo_type": "gravel",
    "weight_t": 20,
    "origin_node": "kochi-maradu",
    "destination_node": "alappuzha-depot",
    "ready_time": "08:00",
    "deadline": "18:00",
    "plan_mode": "water"
  }' | python -m json.tool
```

Expected: `sailing-001` has `capacity_available_t` = 15 (was 25, minus 10 booked).
A 20 t shipment would be excluded as `capacity_exceeded` if remaining is 15.

### Step 6 — Reset demo

```bash
curl -s -X POST http://localhost:8000/demo/reset | python -m json.tool
```

Expected: `{"status": "reset", "message": "Demo state restored to seed."}`.

After reset, `GET /backhaul/$BOOKING_ID` → HTTP 404 (booking cleared).

```bash
curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/backhaul/$BOOKING_ID
# Expected: 404
```

### Step 7 — Verify 409 on over-capacity booking

Confirm the hero booking again (step 3), then immediately try to book another 20 t on
the same sailing without resetting:

```bash
curl -s -X POST http://localhost:8000/book \
  -H "Content-Type: application/json" \
  -d '{
    "sailing_id": "sailing-001",
    "weight_t": 20,
    "cargo_type": "gravel",
    "origin_node": "kochi-maradu",
    "destination_node": "alappuzha-depot",
    "human_confirmed": true
  }' -w "\nHTTP %{http_code}\n"
```

Expected: HTTP 409.

---

## Frontend manual checks

With both backend and frontend running:

| Step | Action | Expected |
|---|---|---|
| 1 | Run the reference shipment via Feature 001 UI and click through to "Choose a sailing" | `RankedSailings` component renders with at least one card showing sailing-001 |
| 2 | Expand a sailing card's sub-scores | Five sub-score rows visible, each with a text reason |
| 3 | Expand "Excluded sailings" accordion | Each entry shows exclusion reason as text (not colour only) |
| 4 | Select sailing-001 | `BookingConfirm` modal appears with vessel name, departure time, load (t), cost (₹) |
| 5 | Check the confirm button before the 300 ms delay | Button is disabled (cannot click immediately) |
| 6 | Wait 300 ms then click "Confirm Booking" | `BackhaulPopup` appears with 1 backhaul card and 2 pooling cards |
| 7 | Check monetary figures in `BackhaulPopup` | `[assumed]` badge text visible next to all cost figures |
| 8 | Press "Reset Demo" | `BackhaulPopup` dismisses; `RankedSailings` re-renders with fresh capacity |
| 9 | Repeat steps 1–6 | Results identical to first run (deterministic seed) |

---

## Acceptance gate summary

| Gate | How verified |
|---|---|
| SC-1: hero shipment → ranked list with sailing-001 | `test_rank_hero` pytest (green) |
| SC-2: draft-too-deep vessel excluded with reason | `test_hard_filter_draft` pytest (green) |
| SC-3: hero booking → 1 backhaul + 2 pooling in one step | `test_backhaul_seeded` + `test_pooling_seeded` pytest (green) |
| SC-4: weights sum to 1.0 from config | `test_weight_sum_1` pytest (green) |
| SC-5: empty ranked list → structured message, no exception | `test_hard_filter_capacity` pytest (green) |
| SC-6: text label on every badge | Manual checklist steps 2–3 |
| Constitution P7: no auto-confirm | Preview response has no `booking_id`; curl step 2 verifies |
| Constitution P3: no hardcoded weights | `grep -r "0.30\|0.25\|0.15\|0.05" backend/engine/` returns nothing |
| Constitution P5: pytest green | `pytest -v` exits 0 |
| Demo reset clears bookings | Curl step 6 + 404 verification |
