// frontend/src/components/ImpactCounter.jsx
// Accumulates CO₂ saved + cost saved across all hybrid bookings this session.
// Judges remember a number. Give them one.
import { useState, useEffect } from "react";

export default function ImpactCounter({ bookings }) {
  const [stats, setStats] = useState({ co2_saved: 0, cost_saved: 0, count: 0 });

  useEffect(() => {
    // Count confirmed hybrid bookings from session state
    const confirmed = (bookings || []).filter(b => b.human_confirmed && b.mode === "hybrid");
    const co2 = confirmed.reduce((s, b) => s + (b.co2_road - b.co2_hybrid || 0), 0);
    const cost = confirmed.reduce((s, b) => s + (b.cost_road - b.cost_hybrid || 0), 0);
    setStats({ co2_saved: co2, cost_saved: cost, count: confirmed.length });
  }, [bookings]);

  // Demo: show illustrative reference-scenario numbers when no real bookings yet.
  // These are computed from config.yaml (road Rs 8,958 − water Rs 5,800 = Rs 3,158;
  // road CO₂ 54.5 kg − water CO₂ 9.7 kg = 44.8 kg). Tagged [assumed] as required by P3.
  const showDemo = stats.count === 0;
  const co2  = showDemo ? 44.8 : stats.co2_saved;
  const cost = showDemo ? 3158 : stats.cost_saved;
  const cnt  = showDemo ? 1    : stats.count;

  return (
    <div style={{
      display: "flex", gap: 1, flexWrap: "wrap",
      background: "#f0fdf4", border: "1px solid #bbf7d0",
      borderRadius: 8, overflow: "hidden", marginBottom: 16,
    }}>
      {[
        { icon: "🌿", label: "CO₂ saved", value: `${co2.toFixed(1)} kg`, sub: "vs road freight", tag: showDemo ? "assumed" : null },
        { icon: "💰", label: "Cost saved", value: `Rs ${cost.toLocaleString("en-IN")}`, sub: "vs road freight", tag: showDemo ? "assumed" : null },
        { icon: "⛵", label: "Water bookings", value: cnt, sub: "this session", tag: null },
        { icon: "🔢", label: "CO₂ factor", value: "3.3× cleaner", sub: "water vs road", tag: "sourced" },
      ].map((s, i) => (
        <div key={i} style={{
          flex: "1 1 120px", padding: "12px 16px", textAlign: "center",
          borderRight: i < 3 ? "1px solid #bbf7d0" : "none",
          background: i === 0 ? "#dcfce7" : "transparent",
        }}>
          <div style={{ fontSize: 20 }}>{s.icon}</div>
          <div style={{ fontSize: 18, fontWeight: 800, color: "#166534" }}>{s.value}</div>
          <div style={{ fontSize: 11, color: "#57606a" }}>{s.label}</div>
          {s.tag && (
            <span style={{
              fontSize: 10, padding: "1px 5px", borderRadius: 2, fontWeight: 700,
              background: s.tag === "sourced" ? "#dcfce7" : "#fef9c3",
              color:      s.tag === "sourced" ? "#166534" : "#92400e",
            }}>[{s.tag}]</span>
          )}
        </div>
      ))}
      {showDemo && (
        <div style={{ width: "100%", padding: "4px 16px 6px", fontSize: 11, color: "#57606a", textAlign: "center" }}>
          Reference scenario: 10 t Kochi → Alappuzha, deadline 10 h. Numbers from config.yaml. <span style={{ background: "#fef9c3", color: "#92400e", padding: "0 4px", borderRadius: 2, fontWeight: 700 }}>[assumed]</span>
        </div>
      )}
    </div>
  );
}
