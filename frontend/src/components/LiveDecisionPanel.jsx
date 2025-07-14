// frontend/src/components/LiveDecisionPanel.jsx
// The "aha moment" — drag the deadline slider, recommendation flips live.
// No submit button. Updates on every slider move.
import { useState, useEffect, useCallback } from "react";
import { getOptions } from "../api";
import SourceBadge from "./SourceBadge";

const NODES = [
  { id: "node-001", label: "Kochi Thevara Jetty" },
  { id: "node-002", label: "Alappuzha Boat Jetty" },
  { id: "node-003", label: "Kollam Jetty" },
];

const MODE_COLOR = { road: "#f59e0b", hybrid: "#3b82d4" };
const MODE_ICON  = { road: "🚛", hybrid: "⛵" };

function Co2Bar({ road, hybrid }) {
  if (!road || !hybrid) return null;
  const max = Math.max(road, hybrid, 1);
  return (
    <div style={{ marginTop: 16 }}>
      <div style={{ fontWeight: 600, marginBottom: 6, fontSize: 13 }}>CO₂ comparison <SourceBadge status="sourced" /></div>
      {[{ label: "Road 🚛", val: road, color: "#f59e0b" }, { label: "Water ⛵", val: hybrid, color: "#3b82d4" }].map(r => (
        <div key={r.label} style={{ marginBottom: 6 }}>
          <div style={{ fontSize: 12, color: "#57606a", marginBottom: 2 }}>{r.label}</div>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <div style={{
              height: 18, width: `${Math.round((r.val / max) * 220)}px`,
              background: r.color, borderRadius: 3, minWidth: 4, transition: "width 0.3s"
            }} />
            <span style={{ fontSize: 13, fontWeight: 600 }}>{r.val.toFixed(1)} kg</span>
          </div>
        </div>
      ))}
      <div style={{ fontSize: 11, color: "#57606a", marginTop: 4 }}>
        Water saves {Math.max(0, road - hybrid).toFixed(1)} kg CO₂ ({road > 0 ? Math.round((1 - hybrid / road) * 100) : 0}% less)
      </div>
    </div>
  );
}

export default function LiveDecisionPanel({ onSave }) {
  const [weight, setWeight]   = useState(10);
  const [origin, setOrigin]   = useState("node-001");
  const [dest, setDest]       = useState("node-002");
  const [deadline, setDeadline] = useState(10);
  const [subsidy, setSubsidy] = useState(false);
  const [result, setResult]   = useState(null);
  const [loading, setLoading] = useState(false);

  const fetch = useCallback(async () => {
    if (origin === dest) return;
    setLoading(true);
    try {
      const r = await getOptions({
        weight_t: weight,
        origin_node_id: origin,
        destination_node_id: dest,
        ready_time: "04:00",
        deadline_h: deadline,
        subsidy,
      });
      setResult(r);
    } catch (_) {}
    finally { setLoading(false); }
  }, [weight, origin, dest, deadline, subsidy]);

  useEffect(() => { fetch(); }, [fetch]);

  const rec = result?.recommended;
  const recPlan = rec && result?.plans?.[rec];
  const road = result?.plans?.road;
  const hybrid = result?.plans?.hybrid;

  return (
    <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
      {/* Left: controls */}
      <div className="card" style={{ flex: "1 1 280px" }}>
        <h2 style={{ marginBottom: 12 }}>⚡ Live Decision Engine</h2>

        <div className="form-group">
          <label>Weight (tonnes)</label>
          <input type="range" min="1" max="50" value={weight}
            onChange={e => setWeight(+e.target.value)} />
          <span style={{ fontWeight: 600 }}>{weight} t</span>
        </div>

        <div className="form-group">
          <label>Origin</label>
          <select value={origin} onChange={e => setOrigin(e.target.value)}>
            {NODES.map(n => <option key={n.id} value={n.id}>{n.label}</option>)}
          </select>
        </div>
        <div className="form-group">
          <label>Destination</label>
          <select value={dest} onChange={e => setDest(e.target.value)}>
            {NODES.map(n => <option key={n.id} value={n.id}>{n.label}</option>)}
          </select>
        </div>

        <div className="form-group">
          <label style={{ display: "flex", justifyContent: "space-between" }}>
            <span>Deadline</span>
            <span style={{ fontWeight: 700, color: deadline <= 3 ? "#dc2626" : "#3b82d4" }}>
              {deadline} h
            </span>
          </label>
          <input type="range" min="1" max="24" value={deadline}
            onChange={e => setDeadline(+e.target.value)}
            style={{ accentColor: deadline <= 3 ? "#dc2626" : "#3b82d4" }} />
          <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, color: "#57606a" }}>
            <span>1h (urgent)</span><span>24h (relaxed)</span>
          </div>
        </div>

        <label style={{ fontSize: 13, display: "flex", alignItems: "center", gap: 6, cursor: "pointer" }}>
          <input type="checkbox" checked={subsidy} onChange={e => setSubsidy(e.target.checked)} />
          Subsidy scenario <span className="badge-assumed">[assumed]</span>
          <span className="muted" style={{ fontSize: 11 }}>what-if only</span>
        </label>
      </div>

      {/* Right: live result */}
      <div style={{ flex: "1 1 280px", display: "flex", flexDirection: "column", gap: 12 }}>
        {loading && <div className="card" style={{ textAlign: "center", color: "#57606a" }}>Calculating…</div>}

        {result && !loading && (
          <>
            {/* Big recommendation badge */}
            <div className="card" style={{
              borderColor: MODE_COLOR[rec] || "#e5e7eb",
              borderWidth: 2,
              textAlign: "center",
            }}>
              <div style={{ fontSize: 13, color: "#57606a", marginBottom: 4 }}>Recommendation</div>
              <div style={{ fontSize: 36, fontWeight: 800, color: MODE_COLOR[rec] }}>
                {MODE_ICON[rec]} {rec?.toUpperCase()}
              </div>
              {recPlan && (
                <div style={{ marginTop: 8, display: "flex", justifyContent: "center", gap: 24 }}>
                  <div><div className="muted">Cost</div><strong>Rs {recPlan.cost_inr?.toLocaleString("en-IN")}</strong> <SourceBadge status={recPlan.source_status} /></div>
                  <div><div className="muted">Time</div><strong>{recPlan.time_h?.toFixed(1)} h</strong></div>
                  <div><div className="muted">CO₂</div><strong>{recPlan.co2_kg?.toFixed(1)} kg</strong></div>
                </div>
              )}
              <div className="why-box" style={{ marginTop: 10, textAlign: "left", fontSize: 12 }}>{result.why}</div>
            </div>

            {/* Side-by-side mini comparison */}
            {road && hybrid && (
              <div style={{ display: "flex", gap: 8 }}>
                {[["road", road], ["hybrid", hybrid]].map(([mode, plan]) => (
                  <div key={mode} style={{
                    flex: 1, padding: "10px 12px", border: `1px solid ${rec === mode ? MODE_COLOR[mode] : "#e5e7eb"}`,
                    borderRadius: 6, background: rec === mode ? "#f8faff" : "#fff", fontSize: 12,
                  }}>
                    <div style={{ fontWeight: 700, color: MODE_COLOR[mode] }}>{MODE_ICON[mode]} {mode}</div>
                    <div>Rs {plan.cost_inr?.toLocaleString("en-IN")}</div>
                    <div>{plan.time_h?.toFixed(1)} h · {plan.co2_kg?.toFixed(1)} kg CO₂</div>
                    {rec === mode && <div style={{ color: MODE_COLOR[mode], fontSize: 11, marginTop: 4 }}>★ Recommended</div>}
                  </div>
                ))}
              </div>
            )}

            <Co2Bar
              road={road?.co2_kg}
              hybrid={hybrid?.co2_kg}
            />
          </>
        )}
      </div>
    </div>
  );
}
