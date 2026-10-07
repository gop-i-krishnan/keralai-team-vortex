# Quickstart — Feature 004 (checkpoint T440, run 2026-10-07)

```bash
JALSETU_MOCK_LLM=1 python -m uvicorn backend.api.main:app --port 8000
B=http://127.0.0.1:8000/api; J='-H Content-Type:application/json'
curl -X POST $B/demo/reset
curl -X POST $B/vessel/parse-message $J -d '{"message":"12 ton barge, Vaikom, free tomorrow, going Alappuzha"}'
curl -X POST $B/vessel/register $J -d '{"vessel_name":"MV Curl","capacity_t":12,"draft_m":1.4,"home_jetty_id":"node-004","contact":"simulated@operator.example","operator_id":"op-001"}'
curl -X POST $B/sailing/publish $J -d '{"vessel_id":"vessel-008","route_node_ids":["node-001","node-004","node-002"],"weekdays":["Mon","Fri"],"departure_time":"07:00","price_per_t":350,"capacity_offered_t":12}'
curl -X POST $B/admin/vessel/vessel-008/verify        # 200; repeat -> 409 invalid_transition
curl -X POST $B/admin/vessel/vessel-002/suspend       # then /match lists it in "excluded": vessel_suspended
curl -X POST $B/booking/{id}/deliver $J -d '{"actual_arrival":"12:00","status":"on_time"}'   # repeat -> 409 already_delivered
curl $B/operator/op-002/profile                       # vessel-004: "0 trips [simulated]"
```

Observed: all endpoints returned the expected status (200/201/409/422/404). Hero message parsed to
capacity 12, home `node-004`, route hint `node-002`, confidence 0.9, `needs_review: false`.

Note: `status` on deliver comes from the caller (spec FR-3). A caller can report `on_time` with a
104 min delay; the system does not infer or override it.
