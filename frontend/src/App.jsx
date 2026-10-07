// frontend/src/App.jsx
// Four role tabs. Landing = Shipper → Compare options (the hero deadline slider): zero clicks to see it.
import { useState } from "react";
import "./index.css";
import LiveDecisionPanel from "./components/LiveDecisionPanel";
import ImpactCounter     from "./components/ImpactCounter";
import DemoResetButton   from "./components/DemoResetButton";
import PostCargo         from "./components/PostCargo";
import Matches           from "./components/Matches";
import BookingConfirm    from "./components/BookingConfirm";
import MyShipments       from "./components/MyShipments";
import VesselRegister    from "./components/VesselRegister";
import MySailings        from "./components/MySailings";
import MyHistory         from "./components/MyHistory";
import { WarehouseRegister, WarehouseUtilisation } from "./components/WarehousePanels";
import { CorridorViability, DisruptionSummary }   from "./components/PlannerPanels";
import BadgeLegend from "./components/BadgeLegend";
import { SubNav, useFetch } from "./components/ui";
import { api } from "./api";

const ROLES = [
  { id: "shipper",   label: "📦 Shipper" },
  { id: "owner",     label: "⛵ Boat owner" },
  { id: "warehouse", label: "🏭 Warehouse" },
  { id: "planner",   label: "📊 Planner" },
];

const SUBTABS = {
  shipper: [
    { id: "compare", label: "Compare options" }, { id: "post", label: "Post cargo" },
    { id: "matches", label: "Matches" }, { id: "confirm", label: "Confirm" }, { id: "shipments", label: "My shipments" },
  ],
  owner: [{ id: "register", label: "Register vessel" }, { id: "sailings", label: "My sailings" }, { id: "history", label: "My history" }],
  warehouse: [{ id: "wh-register", label: "Register warehouse" }, { id: "wh-util", label: "Utilisation" }],
  planner: [{ id: "viability", label: "Corridor viability" }, { id: "disruptions", label: "Disruption summary" }],
};

function OperatorPicker({ value, onChange }) {
  const ops = useFetch(api.operators, []);
  if (!ops.data) return null;
  return (
    <div className="muted" style={{ marginBottom: 8 }}>
      Viewing as{" "}
      <select aria-label="Operator" style={{ width: "auto", display: "inline-block" }} value={value} onChange={(e) => onChange(e.target.value)}>
        {ops.data.operators.map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}
      </select>{" "}
      <span className="badge-simulated">[simulated]</span> — no login in this demo
    </div>
  );
}

export default function App() {
  const [role, setRole] = useState("shipper");
  const [sub, setSub] = useState({ shipper: "compare", owner: "register", warehouse: "wh-register", planner: "viability" });
  const [resetKey, setResetKey] = useState(0);
  const [touch, setTouch] = useState(0);              // bump after any state change so other tabs refetch
  const [cargoId, setCargoId] = useState(null);
  const [sailingId, setSailingId] = useState(null);
  const [operatorId, setOperatorId] = useState("op-001");
  const [prefill, setPrefill] = useState(null);

  const bump = () => setTouch((t) => t + 1);
  const go = (r, s) => { setRole(r); setSub((x) => ({ ...x, [r]: s })); };
  const key = `${resetKey}-${touch}`;
  const current = sub[role];

  function handleReset() { setResetKey((k) => k + 1); setCargoId(null); setSailingId(null); setSub({ shipper: "compare", owner: "register", warehouse: "wh-register", planner: "viability" }); setRole("shipper"); }

  return (
    <>
      <nav>
        <span style={{ fontWeight: 800, fontSize: 15, letterSpacing: "-0.3px" }}>⛵ JalSetu</span>
        <span style={{ color: "#9ca3af", fontSize: 12, marginLeft: 4 }}>Kerala Waterway AI</span>
        {ROLES.map((r) => (
          <button key={r.id} className={`role ${role === r.id ? "active" : ""}`} aria-current={role === r.id} onClick={() => setRole(r.id)}>{r.label}</button>
        ))}
        <span style={{ marginLeft: "auto" }}><DemoResetButton onReset={handleReset} /></span>
      </nav>

      <main key={resetKey}>
        <ImpactCounter refreshKey={key} />
        <BadgeLegend />
        <SubNav tabs={SUBTABS[role]} value={current} onChange={(s) => setSub({ ...sub, [role]: s })} />

        {role === "owner" && <OperatorPicker value={operatorId} onChange={setOperatorId} />}

        {role === "shipper" && current === "compare" && (
          <section className="section">
            <h2 style={{ marginBottom: 12 }}>Shipment Decision Engine
              <span className="muted" style={{ fontWeight: 400, marginLeft: 8 }}>— drag the deadline slider and watch the recommendation flip</span></h2>
            <LiveDecisionPanel onPostCargo={(v) => { setPrefill(v); go("shipper", "post"); }} />
          </section>
        )}
        {role === "shipper" && current === "post" && (
          <PostCargo key={JSON.stringify(prefill)} prefill={prefill} onPosted={(c, goNext) => { setCargoId(c.id); bump(); if (goNext) go("shipper", "matches"); }} />
        )}
        {role === "shipper" && current === "matches" && (
          <Matches cargoId={cargoId} setCargoId={setCargoId} refreshKey={key}
            onSelect={(sid) => { setSailingId(sid); go("shipper", "confirm"); }} />
        )}
        {role === "shipper" && current === "confirm" && (
          <BookingConfirm cargoId={cargoId} sailingId={sailingId} onBooked={() => { bump(); }} />
        )}
        {role === "shipper" && current === "shipments" && <MyShipments refreshKey={key} />}

        {role === "owner" && current === "register" && <VesselRegister operatorId={operatorId} onRegistered={bump} />}
        {role === "owner" && current === "sailings" && <MySailings operatorId={operatorId} refreshKey={key} onChanged={bump} />}
        {role === "owner" && current === "history" && <MyHistory operatorId={operatorId} refreshKey={key} />}

        {role === "warehouse" && current === "wh-register" && <WarehouseRegister refreshKey={key} onChanged={bump} />}
        {role === "warehouse" && current === "wh-util" && <WarehouseUtilisation refreshKey={key} />}

        {role === "planner" && current === "viability" && <section className="section"><CorridorViability refreshKey={key} /></section>}
        {role === "planner" && current === "disruptions" && <DisruptionSummary refreshKey={key} />}

        <footer style={{
          marginTop: 40, paddingTop: 12, borderTop: "1px solid #e5e7eb", fontSize: 11, color: "#57606a",
          display: "flex", flexWrap: "wrap", gap: 12, justifyContent: "space-between",
        }}>
          <span>
            Numbers are tagged <span className="badge-sourced">[sourced]</span> <span className="badge-assumed">[assumed]</span> or <span className="badge-simulated">[simulated]</span> — Constitution P3, P13
          </span>
          <span>Subsidy OFF by default · No auto-confirm · Offline parser active (no live LLM used in this build)</span>
          <span>
            <a href="http://localhost:8000/docs" target="_blank" rel="noreferrer">API docs</a>
            {" · "}
            <a href="http://localhost:8000/api/config/assumptions" target="_blank" rel="noreferrer">All assumptions</a>
          </span>
        </footer>
      </main>
    </>
  );
}
