// frontend/src/components/ViabilityChart.jsx
// Simple SVG bar chart for corridor viability.
import SourceBadge from "./SourceBadge";

export default function ViabilityChart({ data }) {
  if (!data) return null;
  const { d_star_km, corridors, demand_summary } = data;

  return (
    <div className="card section">
      <h2>Corridor Viability</h2>
      <p className="muted">
        Road-equivalent distance d* = <strong>{d_star_km?.toFixed(1)} km</strong>
        <SourceBadge status="assumed" />
        &nbsp;— minimum corridor distance at which hybrid barge cost equals road cost per tonne.
        Formula: (jetty loading + barge freight + jetty unloading) ÷ road rate per t·km.
        Water variable cost treated as ~0 for flat-rate Kerala IWT routes [assumed].
        Cost coverage: port-to-port only; truck legs not included.
      </p>
      <table style={{ width: "100%", marginTop: 12, borderCollapse: "collapse", fontSize: 13 }}>
        <thead>
          <tr style={{ borderBottom: "1px solid #e5e7eb", textAlign: "left" }}>
            <th style={{ padding: "4px 8px" }}>Corridor</th>
            <th style={{ padding: "4px 8px" }}>Distance</th>
            <th style={{ padding: "4px 8px" }}>d* (break-even)</th>
            <th style={{ padding: "4px 8px" }}>Viable?</th>
            <th style={{ padding: "4px 8px" }}>Demand</th>
          </tr>
        </thead>
        <tbody>
          {corridors?.map((c) => {
            const dem = demand_summary?.find((d) => d.corridor_id === c.id);
            return (
              <tr key={c.id} style={{ borderBottom: "1px solid #f0f0f0" }}>
                <td style={{ padding: "4px 8px" }}>{c.origin_node_id} → {c.destination_node_id}</td>
                <td style={{ padding: "4px 8px" }}>{c.distance_km} km <SourceBadge status={c.source_status} /></td>
                <td style={{ padding: "4px 8px" }}>{d_star_km?.toFixed(1)} km <SourceBadge status="assumed" /></td>
                <td style={{ padding: "4px 8px" }}>
                  {c.viable
                    ? <span className="status ok">✓ Viable</span>
                    : <span className="status warn">✗ Below d*</span>}
                </td>
                <td style={{ padding: "4px 8px" }}>{dem ? <>{dem.total_t} t <SourceBadge status="simulated" /></> : "—"}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
