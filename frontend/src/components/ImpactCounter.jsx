// frontend/src/components/ImpactCounter.jsx
// Reference-scenario impact, computed live from the engine and config (P3: no hardcoded figures).
// The booking count is the number of water bookings made in this demo session.
import { api, getOptions, getAssumptions } from "../api";
import { useFetch } from "./ui";

const TAG_STYLE = {
  sourced:   { background: "#dcfce7", color: "#166534" },
  assumed:   { background: "#fef9c3", color: "#92400e" },
  simulated: { background: "#ede9fe", color: "#5b21b6" },
};

async function load() {
  const [a, n, bk] = await Promise.all([getAssumptions(), api.nodes(), api.bookings()]);
  const cfg = (section, key) => a.assumptions.find((x) => x.section === section && x.key === key)?.value;
  const nodeId = (name) => n.nodes.find((x) => x.name === name)?.id;
  const opt = await getOptions({
    weight_t: cfg("demo", "reference_weight_t"),
    origin_node_id: nodeId(cfg("demo", "reference_origin")),
    destination_node_id: nodeId(cfg("demo", "reference_destination")),
    ready_time: "04:00",
    deadline_h: cfg("demo", "deadline_hybrid_h"),
    subsidy: false,
  });
  return {
    road: opt.plans.road, hybrid: opt.plans.hybrid,
    ratio: cfg("road", "co2_kg_per_t_km") / cfg("water", "co2_kg_per_t_km"),
    waterBookings: bk.bookings.filter((b) => b.mode === "hybrid" && ["confirmed", "replanned", "disrupted"].includes(b.status)).length,
    weight: cfg("demo", "reference_weight_t"), deadline: cfg("demo", "deadline_hybrid_h"),
    origin: cfg("demo", "reference_origin"), destination: cfg("demo", "reference_destination"),
  };
}

export default function ImpactCounter({ refreshKey }) {
  const { data, error, loading } = useFetch(load, [refreshKey]);
  if (loading && !data) return <div className="muted" style={{ marginBottom: 16 }}>Loading reference figures…</div>;
  if (error || !data.hybrid || !data.road) {
    return <div className="muted" style={{ marginBottom: 16 }}>Reference figures unavailable (backend not reachable).</div>;
  }
  const cells = [
    { icon: "🌿", label: "CO₂ saved (reference)", value: `${(data.road.co2_kg - data.hybrid.co2_kg).toFixed(1)} kg`, tag: "assumed" },
    { icon: "💰", label: "Water-leg vs road cost", value: `Rs ${Math.round(data.road.cost_inr - data.hybrid.cost_inr).toLocaleString("en-IN")}`, tag: "assumed" },
    { icon: "⛵", label: "Water bookings this session", value: data.waterBookings, tag: "simulated" },
    { icon: "🔢", label: "CO₂ factor, road ÷ water", value: `${data.ratio.toFixed(1)}×`, tag: "sourced" },
  ];
  return (
    <div style={{ display: "flex", gap: 1, flexWrap: "wrap", background: "#f0fdf4", border: "1px solid #bbf7d0", borderRadius: 8, overflow: "hidden", marginBottom: 16 }}>
      {cells.map((s, i) => (
        <div key={s.label} style={{ flex: "1 1 120px", padding: "12px 16px", textAlign: "center", borderRight: i < 3 ? "1px solid #bbf7d0" : "none" }}>
          <div style={{ fontSize: 20 }}>{s.icon}</div>
          <div style={{ fontSize: 18, fontWeight: 800, color: "#166534" }}>{s.value}</div>
          <div style={{ fontSize: 11, color: "#57606a" }}>{s.label}</div>
          <span style={{ fontSize: 10, padding: "1px 5px", borderRadius: 2, fontWeight: 700, ...TAG_STYLE[s.tag] }}>[{s.tag}]</span>
        </div>
      ))}
      <div style={{ width: "100%", padding: "4px 16px 6px", fontSize: 11, color: "#57606a", textAlign: "center" }}>
        Reference scenario: {data.weight} t {data.origin} → {data.destination}, deadline {data.deadline} h, computed live from the engine and config.
        Water-leg cost excludes first/last-mile truck legs.
      </div>
    </div>
  );
}
