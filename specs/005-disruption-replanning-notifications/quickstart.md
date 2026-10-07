# Quickstart — Feature 005 (checkpoint T540, run 2026-10-07)

```bash
JALSETU_MOCK_LLM=1 python -m uvicorn backend.api.main:app --port 8000
B=http://localhost:8000/api; J='-H Content-Type:application/json'
curl -X POST $B/demo/reset
curl -X POST $B/book $J -d '{"cargo_id":"cargo-001","sailing_id":"sailing-001","deadline_h":10}'   # -> id
curl -X POST $B/book/{id}/confirm
curl -X POST $B/demo/booking/{id}/advance      # twice -> In Transit (current node: Vaikom)
curl -X POST $B/demo/booking/{id}/disrupt $J -d '{"scenario_id":"scn-001"}'
curl -X POST $B/replan/{id}                    # read-only proposal; booking unchanged
curl -X POST $B/replan/{id}/confirm $J -d '{"alternative_id":"alt-wait_and_continue"}'
curl -X POST $B/booking/{id}/notify            # preview only, delivered:false
curl $B/disruptions/summary
```

Observed (hero booking, breakdown at Vaikom, 4 h): severity `moderate`, deadline not at risk; alternatives
wait_and_continue Rs 480 (meets deadline), truck_from_jetty Rs 2,271 (meets), return_to_origin Rs 1,963
(does not complete delivery). Confirm produced status `replanned` and events
`replan_proposed, replan_confirmed, notification_preview`. Reset returned the store to zero bookings.
Error codes are listed in plan.md section 4.
