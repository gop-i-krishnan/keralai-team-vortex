// frontend/src/components/CorridorMap.jsx
// Static SVG map of Kerala NW-3 waterway corridor.
// No API, no tiles — works fully offline (Constitution P8).
export default function CorridorMap({ highlight }) {
  // Rough pixel positions mapped from lat/lon for display only
  const nodes = [
    { id: "node-001", label: "Kochi\nThevara", x: 210, y: 80,  type: "major" },
    { id: "node-002", label: "Alappuzha", x: 190, y: 210, type: "major" },
    { id: "node-003", label: "Kollam",    x: 170, y: 360, type: "major" },
  ];

  const routes = [
    { from: { x: 210, y: 80 },  to: { x: 190, y: 210 }, label: "~75 km", id: "corridor-001" },
    { from: { x: 190, y: 210 }, to: { x: 170, y: 360 }, label: "~80 km", id: "corridor-002" },
  ];

  const roadRoutes = [
    { from: { x: 210, y: 80 },  to: { x: 190, y: 210 }, offset: 20 },
    { from: { x: 190, y: 210 }, to: { x: 170, y: 360 }, offset: 20 },
  ];

  return (
    <div className="card">
      <h2>Kerala NW-3 Corridor Map</h2>
      <p className="muted" style={{ marginBottom: 12 }}>
        National Waterway 3 · Static diagram · No live GPS (Constitution P10)
      </p>
      <div style={{ display: "flex", gap: 24, alignItems: "flex-start", flexWrap: "wrap" }}>
        <svg width="300" height="440" style={{ border: "1px solid #e5e7eb", borderRadius: 6, background: "#e8f4fd" }}>
          {/* Water background */}
          <rect width="300" height="440" fill="#dbeafe" rx="6" />

          {/* Land mass rough outline */}
          <path d="M40,0 L260,0 L280,440 L20,440 Z" fill="#d1fae5" opacity="0.4" />

          {/* NW-3 waterway */}
          <path d="M210,80 Q200,145 190,210 Q180,285 170,360"
            fill="none" stroke="#3b82d4" strokeWidth="6" strokeLinecap="round"
            opacity="0.7" />
          <text x="230" y="155" fill="#1d4ed8" fontSize="10" fontWeight="600">NW-3</text>

          {/* Road routes (dashed) */}
          <path d="M230,80 Q220,145 210,210 Q200,285 190,360"
            fill="none" stroke="#f59e0b" strokeWidth="3" strokeDasharray="6,4"
            opacity="0.8" />

          {/* Corridor distances */}
          {routes.map(r => (
            <text key={r.id}
              x={(r.from.x + r.to.x) / 2 - 30}
              y={(r.from.y + r.to.y) / 2}
              fill="#1e40af" fontSize="10" fontStyle="italic"
            >{r.label}</text>
          ))}

          {/* Nodes */}
          {nodes.map(n => (
            <g key={n.id}>
              <circle cx={n.x} cy={n.y} r={n.type === "major" ? 10 : 7}
                fill={highlight === n.id ? "#f59e0b" : "#1d4ed8"}
                stroke="#fff" strokeWidth="2" />
              {n.label.split("\n").map((line, i) => (
                <text key={i} x={n.x + 14} y={n.y + 4 + i * 13}
                  fill="#1e3a5f" fontSize="11" fontWeight="600">{line}</text>
              ))}
            </g>
          ))}

          {/* Legend */}
          <line x1="20" y1="400" x2="50" y2="400" stroke="#3b82d4" strokeWidth="4" />
          <text x="55" y="404" fill="#1e3a5f" fontSize="10">Waterway</text>
          <line x1="20" y1="418" x2="50" y2="418" stroke="#f59e0b" strokeWidth="2" strokeDasharray="4,3" />
          <text x="55" y="422" fill="#1e3a5f" fontSize="10">Road</text>
        </svg>

        {/* Stats panel */}
        <div style={{ flex: 1, minWidth: 180 }}>
          <h3 style={{ marginBottom: 10 }}>Corridor facts</h3>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
            <thead>
              <tr style={{ background: "#f7f8fa" }}>
                <th style={{ padding: "4px 8px", textAlign: "left", borderBottom: "1px solid #e5e7eb" }}>Route</th>
                <th style={{ padding: "4px 8px", textAlign: "right", borderBottom: "1px solid #e5e7eb" }}>km</th>
              </tr>
            </thead>
            <tbody>
              <tr><td style={{ padding: "4px 8px" }}>Kochi → Alappuzha</td><td style={{ padding: "4px 8px", textAlign: "right" }}>~75 km</td></tr>
              <tr><td style={{ padding: "4px 8px" }}>Alappuzha → Kollam</td><td style={{ padding: "4px 8px", textAlign: "right" }}>~80 km</td></tr>
              <tr style={{ background: "#f7f8fa" }}><td style={{ padding: "4px 8px", fontWeight: 600 }}>Total NW-3</td><td style={{ padding: "4px 8px", textAlign: "right", fontWeight: 600 }}>~155 km</td></tr>
            </tbody>
          </table>

          <div style={{ marginTop: 14 }}>
            <div style={{ fontSize: 12, fontWeight: 600, color: "#57606a", marginBottom: 6 }}>CO₂ advantage</div>
            <div style={{ fontSize: 13 }}>🚛 Road: <strong>0.062</strong> kg/t·km</div>
            <div style={{ fontSize: 13 }}>⛵ Water: <strong>0.019</strong> kg/t·km</div>
            <div style={{ fontSize: 12, color: "#16a34a", marginTop: 4, fontWeight: 600 }}>
              Water is 3× cleaner per tonne-km
            </div>
          </div>

          <div style={{ marginTop: 14, fontSize: 11, color: "#57606a" }}>
            Distances approximate [assumed] · CO₂ factors IPCC AR6 [sourced]
          </div>
        </div>
      </div>
    </div>
  );
}
