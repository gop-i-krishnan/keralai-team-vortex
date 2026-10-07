// frontend/src/components/MyHistory.jsx
// Boat owner: delivery history and Bayesian reliability. A percentage is never shown without its trip count (P14).
import { api } from "../api";
import { useFetch, Loading, ErrorBox, Empty, StatusBadge, CLASS_LABEL } from "./ui";
import SourceBadge from "./SourceBadge";

const OUTCOME = { on_time: "On time", late: "Late", incident: "Incident" };

function Trend({ points }) {
  if (points.length < 2) return <div className="muted">Trend appears after two trips.</div>;
  const w = 220, h = 50;
  const xs = (i) => (i / (points.length - 1)) * (w - 8) + 4;
  const ys = (r) => h - 4 - r * (h - 8);
  const d = points.map((p, i) => `${i ? "L" : "M"}${xs(i).toFixed(1)},${ys(p.running_on_time_rate).toFixed(1)}`).join(" ");
  const last = points[points.length - 1];
  return (
    <div>
      <svg width={w} height={h} role="img" aria-label={`Running on-time rate over ${points.length} trips, now ${Math.round(last.running_on_time_rate * 100)}%`}>
        <path d={d} fill="none" stroke="#3b82d4" strokeWidth="2" />
      </svg>
      <div className="muted">Running on-time rate, trip 1 to {points.length} <SourceBadge status="simulated" /></div>
    </div>
  );
}

export default function MyHistory({ operatorId, refreshKey }) {
  const { data, error, loading, reload } = useFetch(() => api.operatorProfile(operatorId), [operatorId, refreshKey]);
  if (loading) return <Loading what="Loading history" />;
  if (error) return <ErrorBox error={error} onRetry={reload} />;
  if (!data.vessels.length) return <Empty>No vessels registered for this operator, so there is no history yet.</Empty>;
  return (
    <div>
      <div className="muted">Reliability uses a prior of virtual trips so new boats are not penalised <SourceBadge status="assumed" />. Recorded deliveries only; no ratings.</div>
      {data.vessels.map((v) => {
        const r = v.reliability;
        return (
          <div className="card" key={v.id}>
            <strong>{v.name}</strong> <StatusBadge status={v.status} />
            <div style={{ fontSize: 18, margin: "6px 0" }}>
              <strong>{Math.round(r.on_time_rate * 100)}% on time — {r.trip_count_label}</strong>
              {r.total_trips === 0 && <span className="muted"> (starting value only; no trips recorded yet)</span>}
            </div>
            <div className="muted">
              Average delay: {r.avg_delay_min == null ? "n/a" : `${r.avg_delay_min} min`} · Incidents: {r.incident_count} ·
              Certified for: {v.hazard_certs.length ? v.hazard_certs.map((c) => CLASS_LABEL[c] || c).join(", ") : "general cargo only"}
              {" "}<SourceBadge status={r.source_status} />
            </div>
            <Trend points={r.reliability_trend} />
            {v.history.length === 0 ? <div className="muted">No deliveries yet.</div> : (
              <details style={{ marginTop: 6 }}><summary style={{ cursor: "pointer" }}>Delivery records ({v.history.length})</summary>
                <table className="t"><thead><tr><th>Booking</th><th>Planned</th><th>Actual</th><th>Delay</th><th>Outcome</th><th>Source</th></tr></thead>
                  <tbody>{v.history.map((h) => (
                    <tr key={h.id}><td>{h.booking_id.slice(0, 10)}</td><td>{h.planned_eta}</td><td>{h.actual_arrival}</td>
                      <td>{h.delay_min} min</td><td>{OUTCOME[h.status]}</td><td><SourceBadge status={h.source_status} /></td></tr>))}</tbody></table>
              </details>
            )}
          </div>
        );
      })}
    </div>
  );
}
