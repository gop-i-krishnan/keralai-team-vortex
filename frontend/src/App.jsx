// frontend/src/App.jsx
import { useState, useEffect } from "react";
import "./index.css";
import LiveDecisionPanel from "./components/LiveDecisionPanel";
import BookingConfirm    from "./components/BookingConfirm";
import WhatsAppChat      from "./components/WhatsAppChat";
import CorridorMap       from "./components/CorridorMap";
import ViabilityChart    from "./components/ViabilityChart";
import ImpactCounter     from "./components/ImpactCounter";
import DemoResetButton   from "./components/DemoResetButton";
import { getViability }  from "./api";

const TABS = [
  { id: "decide",     label: "⚡ Decide"    },
  { id: "chat",       label: "💬 Operator"  },
  { id: "book",       label: "📦 Book"      },
  { id: "map",        label: "🗺 Map"       },
  { id: "viability",  label: "📊 Viability" },
];

export default function App() {
  const [tab,          setTab]          = useState("decide");
  const [viabilityData,setViabilityData]= useState(null);
  const [resetKey,     setResetKey]     = useState(0);

  useEffect(() => {
    if (tab === "viability") {
      getViability().then(setViabilityData).catch(() => {});
    }
  }, [tab, resetKey]);

  function handleReset() { setResetKey(k => k + 1); setViabilityData(null); }

  return (
    <>
      {/* ── Nav ── */}
      <nav>
        <span style={{ fontWeight: 800, fontSize: 15, letterSpacing: "-0.3px" }}>
          ⛵ JalSetu
        </span>
        <span style={{ color: "#6b7280", fontSize: 12, marginLeft: 4 }}>
          Kerala Waterway AI
        </span>
        {TABS.map(t => (
          <a key={t.id} href="#"
            className={tab === t.id ? "active" : ""}
            style={{ fontSize: 13 }}
            onClick={e => { e.preventDefault(); setTab(t.id); }}>
            {t.label}
          </a>
        ))}
        <span style={{ marginLeft: "auto" }}>
          <DemoResetButton onReset={handleReset} />
        </span>
      </nav>

      <main key={resetKey}>

        {/* ── Always-visible impact counter ── */}
        <ImpactCounter bookings={[]} />

        {/* ── Tabs ── */}
        {tab === "decide" && (
          <section className="section">
            <h2 style={{ marginBottom: 12 }}>
              Shipment Decision Engine
              <span className="muted" style={{ fontWeight: 400, marginLeft: 8 }}>
                — drag the deadline slider and watch the recommendation flip
              </span>
            </h2>
            <LiveDecisionPanel />
          </section>
        )}

        {tab === "chat" && (
          <section className="section">
            <h2 style={{ marginBottom: 12 }}>
              Operator Chat Interface
              <span className="muted" style={{ fontWeight: 400, marginLeft: 8 }}>
                — type a shipment in plain language
              </span>
            </h2>
            <WhatsAppChat />
          </section>
        )}

        {tab === "book" && (
          <section className="section">
            <h2 style={{ marginBottom: 12 }}>
              Booking &amp; Backhaul
              <span className="muted" style={{ fontWeight: 400, marginLeft: 8 }}>
                — human confirmation required before commit
              </span>
            </h2>
            <BookingConfirm cargoId="cargo-001" sailingId="sailing-001" />
          </section>
        )}

        {tab === "map" && (
          <section className="section">
            <CorridorMap />
          </section>
        )}

        {tab === "viability" && (
          <section className="section">
            <h2 style={{ marginBottom: 12 }}>
              Corridor Viability
              <span className="muted" style={{ fontWeight: 400, marginLeft: 8 }}>
                — break-even distance analysis for NW-3
              </span>
            </h2>
            <ViabilityChart data={viabilityData} />
          </section>
        )}

        {/* ── Footer ── */}
        <footer style={{
          marginTop: 40, paddingTop: 12,
          borderTop: "1px solid #e5e7eb",
          fontSize: 11, color: "#6b7280",
          display: "flex", flexWrap: "wrap", gap: 12, justifyContent: "space-between",
        }}>
          <span>
            All numbers tagged <span className="badge-sourced">[sourced]</span> or{" "}
            <span className="badge-assumed">[assumed]</span> — Constitution P3
          </span>
          <span>Subsidy OFF by default · No auto-confirm · Offline mode active</span>
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
