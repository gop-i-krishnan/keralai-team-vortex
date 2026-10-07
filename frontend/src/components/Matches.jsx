// frontend/src/components/Matches.jsx
// Shipper: ranked sailings for a cargo; excluded vessels listed with reasons (P11).
import { useState, useEffect } from "react";
import { api } from "../api";
import { useFetch, Loading, ErrorBox, Empty, StatusBadge, ClassBadge } from "./ui";
import SourceBadge from "./SourceBadge";
import StagingPanel from "./StagingPanel";

const REASON = {
  missing_hazmat_cert: "Not certified for this cargo class",
  mode_not_permitted_for_class: "Water transport is not offered for this cargo class (assumed rule)",
  vessel_suspended: "Vessel suspended — no new bookings",
  unverified_vessel_for_hazmat: "Vessel not yet verified — not eligible for hazardous cargo",
};

export default function Matches({ cargoId, setCargoId, onSelect, refreshKey }) {
  const cargo = useFetch(api.cargoList, [refreshKey]);
  const vessels = useFetch(api.vessels, [refreshKey]);
  const [match, setMatch] = useState({ data: null, error: null, loading: false });

  useEffect(() => {
    if (!cargoId) return;
    setMatch({ data: null, error: null, loading: true });
    api.match(cargoId).then((data) => setMatch({ data, error: null, loading: false }))
      .catch((error) => setMatch({ data: null, error, loading: false }));
  }, [cargoId, refreshKey]);

  if (cargo.loading || vessels.loading) return <Loading what="Loading cargo" />;
  if (cargo.error || vessels.error) return <ErrorBox error={cargo.error || vessels.error} onRetry={() => { cargo.reload(); vessels.reload(); }} />;
  const list = cargo.data.cargo;
  if (!list.length) return <Empty>No cargo yet. Post cargo first.</Empty>;

  const vmap = Object.fromEntries(vessels.data.vessels.map((v) => [v.id, v]));
  const picked = list.find((c) => c.id === cargoId);

  return (
    <div>
      <div className="card">
        <label htmlFor="m-cargo">Cargo to match</label>
        <select id="m-cargo" value={cargoId || ""} onChange={(e) => setCargoId(e.target.value)}>
          <option value="" disabled>Select cargo…</option>
          {list.map((c) => <option key={c.id} value={c.id}>{c.id.startsWith("cargo-new") ? "Your posting" : "Demo sample"}: {c.description} ({c.weight_t} t, {CLASS_LABEL_SAFE(c.cargo_class)})</option>)}
        </select>
        {picked && <div style={{ marginTop: 6 }}><ClassBadge cls={picked.cargo_class || "general"} /> <span className="muted">{picked.weight_t} t <SourceBadge status={picked.source_status === "simulated" ? "simulated" : "assumed"} /></span></div>}
      </div>

      {cargoId && <StagingPanel cargoId={cargoId} />}
      {!cargoId && <Empty>Choose a cargo above to see matching sailings.</Empty>}
      {match.loading && <Loading what="Matching sailings" />}
      <ErrorBox error={match.error} onRetry={() => setCargoId(cargoId)} />

      {match.data && (
        <>
          <h2>Ranked sailings</h2>
          {match.data.ranked.length === 0 && (
            <Empty>
              {match.data.excluded.length > 0
                ? "No certified vessels available for this cargo class."
                : "No sailings with enough capacity on this route."}
            </Empty>
          )}
          {match.data.ranked.map((r, i) => {
            const v = vmap[r.vessel_id];
            return (
              <div key={r.sailing_id} className={`card ${i === 0 ? "recommended" : ""}`}>
                <div style={{ display: "flex", justifyContent: "space-between", flexWrap: "wrap", gap: 8 }}>
                  <div>
                    <strong>{v?.name || r.vessel_id}</strong> {v && <StatusBadge status={v.status} />}
                    {i === 0 && <span style={{ marginLeft: 8, color: "#1d4ed8" }}>★ Best match</span>}
                    <div className="muted">Sailing {r.sailing_id} · departs {r.departure_time} IST</div>
                  </div>
                  <div style={{ textAlign: "right" }}>
                    <div>Space: <strong>{r.available_capacity_t} t</strong> <SourceBadge status="simulated" /></div>
                    <div>Match score: <strong>{r.score.toFixed(3)}</strong> <SourceBadge status="assumed" /></div>
                    {r.cost_inr != null && <div>Operator price: <strong>Rs {r.cost_inr.toLocaleString("en-IN")}</strong> <SourceBadge status="simulated" /></div>}
                  </div>
                </div>
                {v?.status === "pending_verification" && <div className="muted">Unverified vessels are ranked lower by a configured penalty <SourceBadge status="assumed" />.</div>}
                <button className="btn-primary" style={{ marginTop: 8 }} onClick={() => onSelect(r.sailing_id)}>Select and continue to Confirm</button>
              </div>
            );
          })}

          {match.data.excluded.length > 0 && (
            <details className="card" open={match.data.ranked.length === 0}>
              <summary style={{ cursor: "pointer", fontWeight: 600 }}>Excluded vessels ({match.data.excluded.length})</summary>
              <table className="t" style={{ marginTop: 8 }}>
                <thead><tr><th>Sailing</th><th>Vessel</th><th>Why it was excluded</th></tr></thead>
                <tbody>
                  {match.data.excluded.map((e) => (
                    <tr key={e.sailing_id}>
                      <td>{e.sailing_id}</td>
                      <td>{vmap[e.vessel_id]?.name || e.vessel_id}</td>
                      <td><strong>{REASON[e.reason] || e.reason}</strong> <span className="muted">({e.reason})</span></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </details>
          )}
        </>
      )}
    </div>
  );
}

function CLASS_LABEL_SAFE(c) { return (c || "general").replace("_", " "); }
