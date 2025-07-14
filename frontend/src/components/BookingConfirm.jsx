// frontend/src/components/BookingConfirm.jsx
// Constitution P7: explicit human confirmation step before booking is confirmed.
import { useState } from "react";
import { createBooking, confirmBooking, getBackhaul } from "../api";

export default function BookingConfirm({ cargoId = "cargo-001", sailingId = "sailing-001" }) {
  const [booking, setBooking] = useState(null);
  const [opportunities, setOpportunities] = useState(null);
  const [error, setError] = useState(null);
  const [step, setStep] = useState("idle"); // idle | preview | confirmed

  async function handlePreview() {
    setError(null);
    try {
      const b = await createBooking({ cargo_id: cargoId, sailing_id: sailingId, human_confirmed: false });
      setBooking(b);
      setStep("preview");
    } catch (e) { setError(e.message); }
  }

  async function handleConfirm() {
    try {
      const b = await confirmBooking(booking.id);
      setBooking(b);
      setStep("confirmed");
      const opps = await getBackhaul(booking.id);
      setOpportunities(opps);
    } catch (e) { setError(e.message); }
  }

  return (
    <div className="card section">
      <h2>Book Cargo</h2>
      <div className="muted">Cargo: {cargoId} | Sailing: {sailingId}</div>

      {step === "idle" && (
        <button className="btn-primary" style={{ marginTop: 10 }} onClick={handlePreview}>
          Preview Booking
        </button>
      )}

      {step === "preview" && booking && (
        <div>
          <div style={{ marginTop: 10 }}>
            <strong>Preview:</strong> Booking ID {booking.id.slice(0, 8)}…
            <span className="badge-review" style={{ marginLeft: 8 }}>[not confirmed]</span>
          </div>
          <p className="muted">Review details then click Confirm to commit. Constitution P7: explicit confirmation required.</p>
          <button className="btn-confirm" style={{ marginTop: 8 }} onClick={handleConfirm}>
            ✓ Confirm Booking
          </button>
        </div>
      )}

      {step === "confirmed" && booking && (
        <div>
          <div className="success" style={{ marginTop: 10 }}>✓ Booking confirmed (human_confirmed: true)</div>
          {opportunities && (
            <div style={{ marginTop: 10 }}>
              <h3>Backhaul opportunities: {opportunities.backhaul_opportunities?.length ?? 0}</h3>
              <h3>Pooling opportunities: {opportunities.pooling_opportunities?.length ?? 0}</h3>
              {opportunities.backhaul_opportunities?.map((o, i) => (
                <div key={i} className="muted">↩ {o.cargo_id} ({o.weight_t} t)</div>
              ))}
              {opportunities.pooling_opportunities?.map((o, i) => (
                <div key={i} className="muted">+ {o.cargo_id} ({o.weight_t} t)</div>
              ))}
            </div>
          )}
        </div>
      )}

      {error && <div className="error">{error}</div>}
    </div>
  );
}
