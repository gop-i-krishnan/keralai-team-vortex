// frontend/src/components/PlannerPanels.jsx
// Planner role: corridor viability (existing chart + map) and disruption summary (simulated).
import { api, getViability } from "../api";
import { useFetch, Loading, ErrorBox, Empty } from "./ui";
import SourceBadge from "./SourceBadge";
import ViabilityChart from "./ViabilityChart";
import CorridorMap from "./CorridorMap";

export function CorridorViability({ refreshKey }) {
  const { data, error, loading, reload } = useFetch(getViability, [refreshKey]);
  if (loading) return <Loading what="Loading viability" />;
  if (error) return <ErrorBox error={error} onRetry={reload} />;
  return (
    <div>
      <h2>Corridor viability <span className="muted" style={{ fontWeight: 400 }}>— estimated break-even for NW-3 <SourceBadge status="assumed" /></span></h2>
      <ViabilityChart data={data} />
      <CorridorMap />
    </div>
  );
}

const LABEL = {
  vessel_breakdown: "Vessel breakdown", low_depth: "Low water depth", jetty_closed: "Jetty closed",
  road_blocked: "Road blocked", weather_delay: "Weather delay",
};

export function DisruptionSummary({ refreshKey }) {
  const { data, error, loading, reload } = useFetch(api.disruptionSummary, [refreshKey]);
  if (loading) return <Loading what="Loading summary" />;
  if (error) return <ErrorBox error={error} onRetry={reload} />;
  return (
    <div>
      <h2>Disruption summary <SourceBadge status="simulated" /></h2>
      <div className="muted">Estimated from simulated disruptions triggered in this session. Counts reset on demo reset.</div>
      {data.rows.length === 0 ? (
        <Empty>No disruptions recorded yet. Use “Simulate disruption” on a confirmed shipment under Shipper → My shipments.</Empty>
      ) : (
        <table className="t" style={{ marginTop: 8 }}><thead><tr><th>Disruption</th><th>Corridor</th><th>Count</th></tr></thead>
          <tbody>{data.rows.map((r) => (
            <tr key={r.disruption_type + r.corridor_id}><td>{LABEL[r.disruption_type] || r.disruption_type}</td><td>{r.corridor_id}</td>
              <td><strong>{r.count}</strong> <SourceBadge status="simulated" /></td></tr>))}</tbody></table>
      )}
    </div>
  );
}
