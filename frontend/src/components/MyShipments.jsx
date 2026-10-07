// frontend/src/components/MyShipments.jsx
// Shipper: milestone timeline, simulated disruption, notification preview, ranked alternatives, re-plan confirm.
// Constitution P12: alternatives are only proposals; nothing changes until "Confirm re-plan".
import { useState, useEffect } from "react";
import { api } from "../api";
import { useFetch, Loading, ErrorBox, Empty, Banner, StatusBadge, ClassBadge, AUTHORITY_TEXT } from "./ui";
import SourceBadge from "./SourceBadge";

const ALT_LABEL = {
  wait_and_continue: "Wait and continue",
  alternative_vessel: "Alternative vessel",
  truck_from_jetty: "Truck from current jetty",
  return_to_origin: "Return to origin",
  hold_warehouse: "Hold at warehouse",
};
const DISRUPTION_LABEL = {
  vessel_breakdown: "Vessel breakdown", low_depth: "Low water depth", jetty_closed: "Jetty closed",
  road_blocked: "Road blocked", weather_delay: "Weather delay",
};

function Timeline({ milestones }) {
  return (
    <div className="timeline" aria-label="Shipment milestones">
      {milestones.map((m) => (
        <div key={m.name} className={`step ${m.status}`}>
          <strong>{m.name}</strong>
          <div>{m.status === "completed" ? "✓ done" : m.status === "current" ? "● now" : "○ upcoming"}</div>
          <div className="muted">Planned {m.planned_time} IST</div>
          {m.actual_time && <div className="muted">Actual {m.actual_time} IST</div>}
          <SourceBadge status="simulated" />
        </div>
      ))}
    </div>
  );
}

function DisruptionPanel({ booking, onDone }) {
  const sc = useFetch(api.scenarios, []);
  const [type, setType] = useState("vessel_breakdown");
  const [dur, setDur] = useState("4");
  const [scenario, setScenario] = useState("");
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  async function trigger() {
    setError(null); setBusy(true);
    try {
      const body = scenario
        ? { scenario_id: scenario }
        : { type, expected_duration_h: dur === "" ? null : Number(dur) };
      onDone(await api.disrupt(booking.id, body));
    } catch (e) { setError(e); } finally { setBusy(false); }
  }
  return (
    <div className="card" style={{ borderStyle: "dashed", borderColor: "#7c3aed" }}>
      <strong>Demo control — simulated disruption</strong> <SourceBadge status="simulated" />
      <div className="row" style={{ marginTop: 8 }}>
        <div className="col form-group">
          <label htmlFor={`sc-${booking.id}`}>Ready-made scenario</label>
          <select id={`sc-${booking.id}`} value={scenario} onChange={(e) => setScenario(e.target.value)}>
            <option value="">— choose type below —</option>
            {(sc.data?.scenarios || []).map((s) => <option key={s.id} value={s.id}>{s.label}</option>)}
          </select>
        </div>
        <div className="col form-group">
          <label htmlFor={`ty-${booking.id}`}>Disruption type</label>
          <select id={`ty-${booking.id}`} disabled={!!scenario} value={type} onChange={(e) => setType(e.target.value)}>
            {Object.entries(DISRUPTION_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
        </div>
        <div className="col form-group">
          <label htmlFor={`du-${booking.id}`}>Expected duration (hours, optional)</label>
          <input id={`du-${booking.id}`} type="number" min="0" step="0.5" disabled={!!scenario} value={dur} onChange={(e) => setDur(e.target.value)} />
        </div>
      </div>
      <button className="btn-demo" disabled={busy} onClick={trigger}>Trigger disruption</button>
      <ErrorBox error={error} />
    </div>
  );
}

function Alternatives({ booking, onResolved }) {
  const [state, setState] = useState({ proposal: null, loading: false, error: null });
  const [chosen, setChosen] = useState(null);
  const [reviewed, setReviewed] = useState(false);
  const [note, setNote] = useState("");
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  async function load() {
    setState({ proposal: null, loading: true, error: null }); setChosen(null); setReviewed(false);
    try { setState({ proposal: await api.replan(booking.id), loading: false, error: null }); }
    catch (e) { setState({ proposal: null, loading: false, error: e }); }
  }
  const p = state.proposal;

  async function review() {
    setError(null); setBusy(true);
    try { await api.replanReview(p.proposal_id, note); setReviewed(true); } catch (e) { setError(e); } finally { setBusy(false); }
  }
  async function confirm() {
    setError(null); setBusy(true);
    try { onResolved(await api.replanConfirm(booking.id, chosen.id)); } catch (e) { setError(e); } finally { setBusy(false); }
  }

  return (
    <div>
      {!p && !state.loading && <button className="btn-primary" onClick={load}>Show alternatives</button>}
      {state.loading && <Loading what="Computing alternatives" />}
      <ErrorBox error={state.error} onRetry={load} />
      {p && (
        <>
          <h3>Ranked alternatives <SourceBadge status="simulated" /></h3>
          <div className="muted">Nothing changes until you accept one. Dismissing this notice does not accept any option. Costs are new spend; earlier payments are treated as sunk <SourceBadge status="assumed" />.</div>
          {p.banner && <Banner kind="warn">{p.banner}</Banner>}
          {p.no_alternatives_found && <Empty>No feasible alternatives were found. Contact the operator directly.</Empty>}
          <div className="alts" style={{ marginTop: 8 }}>
            {p.alternatives.map((a, i) => (
              <div key={a.id} className={`alt ${i === 0 ? "best" : ""}`}>
                <strong>{ALT_LABEL[a.type] || a.type}</strong> {i === 0 && <span style={{ color: "#1d4ed8" }}>★ top ranked</span>}
                <div>Extra cost: <strong>Rs {a.extra_cost_inr.toLocaleString("en-IN")}</strong> <SourceBadge status="assumed" /></div>
                <div>New ETA: <strong>{a.new_eta} IST</strong> ({a.total_time_delta_h >= 0 ? "+" : ""}{a.total_time_delta_h.toFixed(1)} h) <SourceBadge status="assumed" /></div>
                <div>{a.deadline_met ? <span className="status ok">✓ Meets deadline</span> : <span className="status bad">✗ Misses deadline</span>}</div>
                <div>Reliability: {a.reliability_score.toFixed(2)} <SourceBadge status="assumed" /> · Score {a.score.toFixed(3)}</div>
                <div className="muted" style={{ margin: "6px 0" }}>{a.reason}</div>
                {a.type === "return_to_origin" && (
                  <div className="muted">Distance already travelled: {a.distance_already_travelled_km} km <SourceBadge status="assumed" /></div>
                )}
                <button className="btn-primary" disabled={busy} onClick={() => setChosen(a)}>Accept this plan</button>
              </div>
            ))}
          </div>

          {chosen && (
            <div className="card" role="dialog" aria-label="Confirm re-plan" style={{ borderColor: "#16a34a", borderWidth: 2, marginTop: 10 }}>
              <h3>Confirm re-plan</h3>
              <div><strong>{ALT_LABEL[chosen.type]}</strong> — extra Rs {chosen.extra_cost_inr.toLocaleString("en-IN")} <SourceBadge status="assumed" />,
                new ETA {chosen.new_eta} IST, {chosen.deadline_met ? "meets" : "misses"} the deadline.</div>
              <div className="muted">The operator will be notified <SourceBadge status="simulated" /> (message preview only; nothing is sent).</div>
              {p.compliance_review_required && !reviewed && (
                <Banner kind="warn" title="Compliance review required — hazardous cargo [assumed].">
                  A changed plan needs its own review. {AUTHORITY_TEXT}
                  <div className="form-group" style={{ marginTop: 6 }}>
                    <label htmlFor="rr-note">Reviewer note</label>
                    <input id="rr-note" value={note} onChange={(e) => setNote(e.target.value)} />
                  </div>
                  <button className="btn-demo" disabled={busy || !note.trim()} onClick={review}>Compliance review — simulated; production requires a qualified person [simulated]</button>
                </Banner>
              )}
              <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
                <button className="btn-confirm" disabled={busy || (p.compliance_review_required && !reviewed)} onClick={confirm}>✓ Confirm re-plan</button>
                <button className="btn-secondary" onClick={() => setChosen(null)}>Cancel — keep the disruption open</button>
              </div>
            </div>
          )}
          <ErrorBox error={error} />
        </>
      )}
    </div>
  );
}

function ShipmentCard({ b, reload }) {
  const [open, setOpen] = useState(false);
  const [alert, setAlert] = useState(null);       // {disruption, notification, deadline_at_risk}
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const [delivery, setDelivery] = useState({ status: "on_time", time: "12:00" });
  const [showLog, setShowLog] = useState(false);

  async function act(fn) { setError(null); setBusy(true); try { await fn(); await reload(); } catch (e) { setError(e); } finally { setBusy(false); } }
  const dis = b.open_disruption;
  useEffect(() => {
    if (dis && !alert) api.notify(b.id).then((n) => setAlert({ notification: n })).catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dis?.id]);

  return (
    <div className="card">
      <div style={{ display: "flex", justifyContent: "space-between", flexWrap: "wrap", gap: 8 }}>
        <div>
          <strong>Shipment {b.id.slice(0, 8)}</strong> <StatusBadge status={b.status} /> <ClassBadge cls={b.cargo_class || "general"} />
          <div className="muted">{b.weight_t} t <SourceBadge status="simulated" /> · deadline {b.deadline_hhmm} IST · now at {b.current_node_name}</div>
        </div>
        <div style={{ textAlign: "right" }}>
          Plan: <strong>{b.mode}</strong> · Rs {Math.round(b.planned_cost_inr || 0).toLocaleString("en-IN")} <SourceBadge status="assumed" /> · {(b.planned_time_h || 0).toFixed(1)} h <SourceBadge status="assumed" />
        </div>
      </div>

      <Timeline milestones={b.milestones} />
      {b.staging && (
        <Banner kind="info" title="Staged at a warehouse.">
          Rs {Math.round(b.staging.total_cost_inr).toLocaleString("en-IN")} <SourceBadge status="assumed" /> · space reserved <SourceBadge status="simulated" />.
        </Banner>
      )}

      {dis && (
        <Banner kind="bad" title={`Disruption: ${DISRUPTION_LABEL[dis.type]} at ${b.current_node_name}.`}>
          Severity: <strong>{dis.severity}</strong> <SourceBadge status="assumed" />.{" "}
          {b.deadline_at_risk ? "Your original deadline is at risk." : "Your original deadline still looks achievable."}{" "}
          <SourceBadge status="simulated" />
        </Banner>
      )}
      {dis && alert?.notification && (
        <div className="card" style={{ background: "#faf5ff" }}>
          <strong>Message preview — not sent [simulated]</strong>
          <div><em>{alert.notification.subject_en}</em></div>
          <div>{alert.notification.body_rendered}</div>
        </div>
      )}
      {dis && <Alternatives booking={b} onResolved={() => { setAlert(null); reload(); }} />}

      {b.status === "replanned" && b.resolution && (
        <Banner kind="ok" title="Re-plan confirmed.">
          Accepted: {ALT_LABEL[b.resolution.type]} · new ETA {b.resolution.new_eta} IST. Operator notification is a preview only <SourceBadge status="simulated" />.
        </Banner>
      )}

      {(b.status === "confirmed" || b.status === "replanned") && (
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 8 }}>
          <button className="btn-demo" onClick={() => setOpen(!open)} aria-expanded={open}>⚡ Simulate disruption</button>
          <button className="btn-secondary" disabled={busy} onClick={() => act(() => api.advance(b.id))}>Advance milestone (demo) <SourceBadge status="simulated" /></button>
        </div>
      )}
      {b.status === "pending_review" && <Banner kind="warn" title="Compliance review required.">Go to Confirm to record the review.</Banner>}
      {open && (b.status === "confirmed" || b.status === "replanned") && (
        <DisruptionPanel booking={b} onDone={(r) => { setAlert(r); setOpen(false); reload(); }} />
      )}

      {(b.status === "confirmed" || b.status === "replanned") && b.milestones.some((m) => m.name === "Arrived" && m.status !== "pending") && !b.delivered && (
        <div className="row" style={{ marginTop: 8, alignItems: "flex-end" }}>
          <div className="form-group"><label htmlFor={`da-${b.id}`}>Actual arrival (HH:MM IST)</label><input id={`da-${b.id}`} type="time" value={delivery.time} onChange={(e) => setDelivery({ ...delivery, time: e.target.value })} /></div>
          <div className="form-group"><label htmlFor={`ds-${b.id}`}>Outcome</label>
            <select id={`ds-${b.id}`} value={delivery.status} onChange={(e) => setDelivery({ ...delivery, status: e.target.value })}>
              <option value="on_time">On time</option><option value="late">Late</option><option value="incident">Incident</option>
            </select></div>
          <button className="btn-confirm" disabled={busy} style={{ marginBottom: 12 }}
            onClick={() => act(() => api.deliver(b.id, { actual_arrival: delivery.time, status: delivery.status }))}>Mark delivered</button>
        </div>
      )}
      {b.delivered && <div className="success">✓ Delivered — recorded in the vessel history.</div>}

      <ErrorBox error={error} />
      <button className="btn-secondary" style={{ marginTop: 8, padding: "2px 10px" }} onClick={() => setShowLog(!showLog)}>{showLog ? "Hide" : "Show"} event log ({b.event_log.length})</button>
      {showLog && (b.event_log.length === 0 ? <div className="muted">No events yet.</div> :
        <ul style={{ marginTop: 6, paddingLeft: 18 }}>{b.event_log.map((e) => <li key={e.id} className="muted">{e.timestamp} — {e.detail} <SourceBadge status="simulated" /></li>)}</ul>)}
    </div>
  );
}

export default function MyShipments({ refreshKey }) {
  const { data, error, loading, reload } = useFetch(api.bookings, [refreshKey]);
  if (loading && !data) return <Loading what="Loading shipments" />;
  if (error) return <ErrorBox error={error} onRetry={reload} />;
  if (!data.bookings.length) {
    return <Empty>No shipments yet. Post cargo, pick a sailing in Matches, then confirm the booking to track it here.</Empty>;
  }
  return <div>{data.bookings.map((b) => <ShipmentCard key={b.id} b={b} reload={reload} />)}</div>;
}
