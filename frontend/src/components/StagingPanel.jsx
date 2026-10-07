// frontend/src/components/StagingPanel.jsx
// Shipper: optional "Stage at warehouse" plan when the wait for a sailing is long (FR-6, FR-8).
// Constitution P12: a proposal changes nothing; only "Confirm staging" uses up warehouse capacity.
import { useState } from "react";
import { api } from "../api";
import { useFetch, ErrorBox, Banner, Empty } from "./ui";
import SourceBadge from "./SourceBadge";

const REASON = {
  warehouse_class_mismatch: "This warehouse does not accept this cargo class",
  warehouse_at_capacity: "Warehouse is at capacity",
  no_warehouse_in_range: "Too far from the pickup point",
};

const inr = (n) => `Rs ${Math.round(n).toLocaleString("en-IN")}`;

export default function StagingPanel({ cargoId }) {
  const whs = useFetch(api.warehouses, []);
  const bks = useFetch(api.bookings, []);
  const [bookingId, setBookingId] = useState("");
  const [wait, setWait] = useState(8);
  const [deadline, setDeadline] = useState(24);
  const [res, setRes] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [chosen, setChosen] = useState(null);
  const [done, setDone] = useState(null);

  const name = (id) => whs.data?.warehouses.find((w) => w.id === id)?.name || id;

  async function check() {
    setError(null); setBusy(true); setRes(null); setChosen(null); setDone(null);
    try { setRes(await api.stage({ cargo_id: cargoId, next_sailing_wait_h: Number(wait), deadline_h: Number(deadline), booking_id: bookingId || null })); }
    catch (e) { setError(e); } finally { setBusy(false); }
  }
  async function confirm() {
    setError(null); setBusy(true);
    try { setDone(await api.stageConfirm(chosen.proposal_id)); setChosen(null); setRes(null); whs.reload(); bks.reload(); }
    catch (e) { setError(e); } finally { setBusy(false); }
  }

  return (
    <details className="card">
      <summary style={{ cursor: "pointer", fontWeight: 600 }}>Waiting a long time for a sailing? Stage the cargo at a warehouse</summary>
      <div className="form-group" style={{ marginTop: 10, maxWidth: 420 }}>
        <label htmlFor="st-b">Attach to a booking (optional)</label>
        <select id="st-b" value={bookingId} onChange={(e) => setBookingId(e.target.value)}>
          <option value="">No booking — just check options</option>
          {(bks.data?.bookings || []).filter((b) => b.cargo_id === cargoId && !b.staging).map((b) => (
            <option key={b.id} value={b.id}>Booking {b.id.slice(0, 8)} — {b.status}</option>
          ))}
        </select>
      </div>
      <div className="row" style={{ alignItems: "flex-end" }}>
        <div className="form-group"><label htmlFor="st-w">Wait for next sailing (hours)</label>
          <input id="st-w" type="number" min="0" step="0.5" value={wait} onChange={(e) => setWait(e.target.value)} /></div>
        <div className="form-group"><label htmlFor="st-d">Deadline (hours)</label>
          <input id="st-d" type="number" min="1" value={deadline} onChange={(e) => setDeadline(e.target.value)} /></div>
        <button className="btn-primary" style={{ marginBottom: 12 }} disabled={busy || !cargoId} onClick={check}>Check staging options</button>
      </div>
      <ErrorBox error={error} />
      {done && <Banner kind="ok" title="Staging confirmed.">Warehouse now has {done.available_capacity_t} t available <SourceBadge status="simulated" />.{done.booking_id ? " The booking now shows this staging under My shipments." : ""}</Banner>}

      {res && res.proposals.length === 0 && (
        <Empty>
          {Number(wait) < res.staging_threshold_h
            ? <>Staging is only offered when the wait is at least {res.staging_threshold_h} h <SourceBadge status="assumed" />.</>
            : "No suitable warehouse is available for this cargo."}
        </Empty>
      )}

      {res?.proposals.map((p) => (
        <div className="card" key={p.proposal_id}>
          <strong>Stage at {name(p.warehouse_id)}</strong> <SourceBadge status="assumed" />
          <table className="t" style={{ margin: "8px 0" }}>
            <tbody>
              <tr><td>Truck to warehouse</td><td>{inr(p.truck_to_warehouse_cost_inr)}</td></tr>
              <tr><td>Handling in</td><td>{inr(p.handling_in_cost_inr)}</td></tr>
              <tr><td>Storage ({p.storage_days} day{p.storage_days > 1 ? "s" : ""})</td><td>{inr(p.storage_cost_inr)}</td></tr>
              <tr><td>Handling out</td><td>{inr(p.handling_out_cost_inr)}</td></tr>
              <tr><td>Truck from warehouse</td><td>{inr(p.truck_from_warehouse_cost_inr)}</td></tr>
              <tr><td><strong>Total</strong></td><td><strong>{inr(p.total_cost_inr)}</strong> <SourceBadge status="assumed" /></td></tr>
            </tbody>
          </table>
          <div>Time: <strong>{p.total_time_h.toFixed(1)} h</strong> <SourceBadge status="assumed" /> · CO₂: <strong>{p.co2_kg.toFixed(1)} kg</strong> <SourceBadge status="assumed" /> <span className="muted">({p.co2_scope})</span></div>
          <div>{p.deadline_met ? <span className="status ok">✓ Meets deadline</span> : <span className="status bad">✗ Misses deadline</span>}</div>
          {p.perishable_adjustments_applied && <div className="muted">Perishable cargo adjustments applied <SourceBadge status="assumed" /></div>}
          <div className="muted">{p.note}</div>
          <button className="btn-primary" style={{ marginTop: 8 }} onClick={() => setChosen(p)}>Stage here…</button>
        </div>
      ))}

      {res?.ineligible_warehouses?.length > 0 && (
        <div className="muted">Not offered: {res.ineligible_warehouses.map((w) => `${name(w.warehouse_id)} — ${REASON[w.reason] || w.reason}`).join("; ")}</div>
      )}

      {chosen && (
        <div className="card" role="dialog" aria-label="Confirm staging" style={{ borderColor: "#16a34a", borderWidth: 2 }}>
          <h3>Confirm staging</h3>
          <div>Stage {chosen.weight_t ?? ""} t at <strong>{name(chosen.warehouse_id)}</strong> for {inr(chosen.total_cost_inr)} <SourceBadge status="assumed" />. This reserves warehouse space <SourceBadge status="simulated" />.</div>
          <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
            <button className="btn-confirm" disabled={busy} onClick={confirm}>✓ Confirm staging</button>
            <button className="btn-secondary" onClick={() => setChosen(null)}>Cancel — reserve nothing</button>
          </div>
        </div>
      )}
    </details>
  );
}
