// frontend/src/components/BookingConfirm.jsx
// Constitution P7: explicit human confirmation. P11: hazardous cargo needs a prior compliance review.
import { useState, useEffect } from "react";
import { api, getBackhaul } from "../api";
import { ErrorBox, Banner, Empty, StatusBadge, AUTHORITY_TEXT } from "./ui";
import SourceBadge from "./SourceBadge";

export default function BookingConfirm({ cargoId, sailingId, onBooked }) {
  const [booking, setBooking] = useState(null);
  const [opps, setOpps] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const [deadline, setDeadline] = useState(10);
  const [note, setNote] = useState("");

  useEffect(() => { setBooking(null); setOpps(null); setError(null); }, [cargoId, sailingId]);

  if (!cargoId || !sailingId) {
    return <Empty>Pick a cargo and a sailing in <strong>Matches</strong> first, then come back here to confirm.</Empty>;
  }

  async function run(fn) {
    setError(null); setBusy(true);
    try { await fn(); } catch (e) { setError(e); } finally { setBusy(false); }
  }

  const preview = () => run(async () => {
    setBooking(await api.book({ cargo_id: cargoId, sailing_id: sailingId, deadline_h: Number(deadline), human_confirmed: false }));
  });
  const approve = () => run(async () => {
    await api.approveCompliance(booking.id, note);
    setBooking({ ...booking, status: "pending", compliance_review_required: false });
  });
  const confirm = () => run(async () => {
    const b = await api.confirm(booking.id);
    setBooking({ ...booking, ...b });
    onBooked?.(b);
    try { setOpps(await getBackhaul(booking.id)); } catch (_) { /* optional extra */ }
  });

  const status = booking?.status;
  return (
    <div className="card">
      <h2>Confirm booking</h2>
      <div className="muted">Cargo {cargoId} · Sailing {sailingId}</div>

      {!booking && (
        <>
          <div className="form-group" style={{ marginTop: 10, maxWidth: 260 }}>
            <label htmlFor="bc-dl">Deadline (hours from 06:00 IST ready time)</label>
            <input id="bc-dl" type="number" min="1" value={deadline} onChange={(e) => setDeadline(e.target.value)} />
          </div>
          <button className="btn-primary" disabled={busy} onClick={preview}>Preview booking</button>
        </>
      )}

      {booking && status === "pending_review" && (
        <>
          <Banner kind="warn" title="Compliance review required — hazardous cargo [assumed].">
            Standard confirmation is disabled until a review is recorded. {AUTHORITY_TEXT}
          </Banner>
          <div className="form-group">
            <label htmlFor="bc-note">Reviewer note</label>
            <input id="bc-note" value={note} onChange={(e) => setNote(e.target.value)} placeholder="Short note (demo)" />
          </div>
          <button className="btn-demo" disabled={busy || !note.trim()} onClick={approve}>
            Mark review approved — Compliance review — simulated; production requires a qualified person [simulated]
          </button>
          <div style={{ marginTop: 10 }}><button className="btn-confirm" disabled>✓ Confirm booking (blocked until review)</button></div>
        </>
      )}

      {booking && status === "pending" && (
        <div style={{ marginTop: 10 }}>
          <div>Booking {booking.id.slice(0, 8)}… <StatusBadge status="pending" /> <span className="badge-review">[not confirmed]</span></div>
          <p className="muted">Review the details, then confirm. Nothing is booked until you click Confirm.</p>
          <button className="btn-confirm" disabled={busy} onClick={confirm}>✓ Confirm booking</button>
        </div>
      )}

      {booking && status === "confirmed" && (
        <div style={{ marginTop: 10 }}>
          <div className="success">✓ Booking confirmed — <StatusBadge status="confirmed" /> Track it under <strong>My shipments</strong>.</div>
          {opps && (
            <div className="muted" style={{ marginTop: 8 }}>
              Backhaul opportunities: {opps.backhaul_opportunities?.length ?? 0} · Pooling opportunities: {opps.pooling_opportunities?.length ?? 0} <SourceBadge status="simulated" />
            </div>
          )}
        </div>
      )}
      <ErrorBox error={error} />
    </div>
  );
}
