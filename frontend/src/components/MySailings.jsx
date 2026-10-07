// frontend/src/components/MySailings.jsx
// Boat owner: vessels with status, publish a recurring sailing, simulated admin verification.
import { useState } from "react";
import { api } from "../api";
import { useFetch, Loading, ErrorBox, Empty, Banner, FieldError, StatusBadge } from "./ui";
import SourceBadge from "./SourceBadge";

const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

function PublishForm({ vessels, nodes, onDone }) {
  const [f, setF] = useState({ vessel_id: vessels[0].id, route: [], weekdays: [], departure_time: "07:00", price_per_t: "", capacity_offered_t: "" });
  const [errors, setErrors] = useState({});
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const toggle = (k, v) => setF((s) => ({ ...s, [k]: s[k].includes(v) ? s[k].filter((x) => x !== v) : [...s[k], v] }));

  async function submit(e) {
    e.preventDefault(); setErrors({}); setError(null); setBusy(true);
    try {
      await api.publishSailing({
        vessel_id: f.vessel_id, route_node_ids: f.route, weekdays: f.weekdays, departure_time: f.departure_time,
        price_per_t: f.price_per_t === "" ? null : Number(f.price_per_t),
        capacity_offered_t: f.capacity_offered_t === "" ? null : Number(f.capacity_offered_t),
      });
      onDone();
    } catch (err) { if (err.status === 422 || err.status === 409) setErrors(err.fieldErrors); else setError(err); } finally { setBusy(false); }
  }
  return (
    <form className="card" onSubmit={submit} noValidate>
      <h3>Publish a recurring sailing</h3>
      <div className="row">
        <div className="col form-group"><label htmlFor="ps-v">Vessel</label>
          <select id="ps-v" value={f.vessel_id} onChange={(e) => setF({ ...f, vessel_id: e.target.value })}>{vessels.map((v) => <option key={v.id} value={v.id}>{v.name}</option>)}</select>
          <FieldError errors={errors} name="vessel_id" /></div>
        <div className="col form-group"><label htmlFor="ps-t">Departure (HH:MM IST)</label>
          <input id="ps-t" type="time" value={f.departure_time} onChange={(e) => setF({ ...f, departure_time: e.target.value })} /><FieldError errors={errors} name="departure_time" /></div>
      </div>
      <div className="form-group"><label>Route — tick jetties in sailing order</label>
        <div className="checks">{nodes.map((n) => <label key={n.id}><input type="checkbox" checked={f.route.includes(n.id)} onChange={() => toggle("route", n.id)} /> {n.name}{f.route.includes(n.id) ? ` (stop ${f.route.indexOf(n.id) + 1})` : ""}</label>)}</div>
        <FieldError errors={errors} name="route_node_ids" />
        <div className="muted">Only the first and last stop are used for matching in this prototype <SourceBadge status="assumed" />.</div></div>
      <div className="form-group"><label>Weekdays</label>
        <div className="checks">{DAYS.map((d) => <label key={d}><input type="checkbox" checked={f.weekdays.includes(d)} onChange={() => toggle("weekdays", d)} /> {d}</label>)}</div>
        <FieldError errors={errors} name="weekdays" /></div>
      <div className="row">
        <div className="col form-group"><label htmlFor="ps-p">Price per tonne (Rs)</label>
          <input id="ps-p" type="number" min="0" value={f.price_per_t} onChange={(e) => setF({ ...f, price_per_t: e.target.value })} /><FieldError errors={errors} name="price_per_t" /></div>
        <div className="col form-group"><label htmlFor="ps-c">Capacity offered (tonnes)</label>
          <input id="ps-c" type="number" min="0" value={f.capacity_offered_t} onChange={(e) => setF({ ...f, capacity_offered_t: e.target.value })} /><FieldError errors={errors} name="capacity_offered_t" /></div>
      </div>
      <button className="btn-primary" disabled={busy}>{busy ? "Publishing…" : "Publish sailing"}</button>
      <ErrorBox error={error} />
    </form>
  );
}

export default function MySailings({ operatorId, refreshKey, onChanged }) {
  const profile = useFetch(() => api.operatorProfile(operatorId), [operatorId, refreshKey]);
  const sailings = useFetch(api.sailings, [refreshKey]);
  const nodes = useFetch(api.nodes, []);
  const [notice, setNotice] = useState(null);
  const [error, setError] = useState(null);

  if (profile.loading || sailings.loading || nodes.loading) return <Loading what="Loading vessels" />;
  const err = profile.error || sailings.error || nodes.error;
  if (err) return <ErrorBox error={err} onRetry={() => { profile.reload(); sailings.reload(); nodes.reload(); }} />;

  const vessels = profile.data.vessels;
  const mine = new Set(vessels.map((v) => v.id));
  const nodeName = (id) => nodes.data.nodes.find((n) => n.id === id)?.name || id;
  const rows = sailings.data.sailings.filter((s) => mine.has(s.vessel_id));

  async function admin(fn, v) {
    setError(null); setNotice(null);
    try { const r = await fn(v.id); setNotice(r.notice); profile.reload(); onChanged?.(); } catch (e) { setError(e); }
  }

  if (!vessels.length) return <Empty>This operator has no vessels yet. Register one first.</Empty>;
  return (
    <div>
      <h2>My vessels</h2>
      {notice && <Banner kind="info">{notice}</Banner>}
      <ErrorBox error={error} />
      {vessels.map((v) => (
        <div className="card" key={v.id}>
          <strong>{v.name}</strong> <StatusBadge status={v.status} /> · {v.capacity_t} t <SourceBadge status="simulated" />
          <div className="muted">{v.reliability.on_time_rate != null && `${Math.round(v.reliability.on_time_rate * 100)}% on time — ${v.reliability.trip_count_label}`}</div>
          <div style={{ display: "flex", gap: 6, marginTop: 6, flexWrap: "wrap" }}>
            {v.status === "pending_verification" && <button className="btn-demo" onClick={() => admin(api.verifyVessel, v)}>Mark Verified (demo admin) [simulated]</button>}
            {v.status === "verified" && <button className="btn-demo" onClick={() => admin(api.suspendVessel, v)}>Suspend (demo admin) [simulated]</button>}
            {v.status === "suspended" && <button className="btn-demo" onClick={() => admin(api.reinstateVessel, v)}>Reinstate (demo admin) [simulated]</button>}
          </div>
          {v.status === "suspended" && <Banner kind="warn">This vessel is suspended — existing bookings unaffected; no new bookings can be made.</Banner>}
        </div>
      ))}

      <h2>My sailings</h2>
      {rows.length === 0 ? <Empty>No sailings published yet.</Empty> : (
        <table className="t"><thead><tr><th>Sailing</th><th>Route</th><th>Days</th><th>Departs</th><th>Capacity</th><th>Price / t</th></tr></thead>
          <tbody>{rows.map((s) => (
            <tr key={s.id}><td>{s.id}</td><td>{(s.route_node_ids || [s.origin_node_id, s.destination_node_id]).map(nodeName).join(" → ")}</td>
              <td>{s.days.join(", ")}</td><td>{s.departure_time} IST</td>
              <td>{s.available_capacity_t} t <SourceBadge status="simulated" /></td>
              <td>{s.price_per_t != null ? <>Rs {s.price_per_t} <SourceBadge status="simulated" /></> : "—"}</td></tr>))}</tbody></table>
      )}
      <PublishForm vessels={vessels.filter((v) => v.status !== "suspended").length ? vessels.filter((v) => v.status !== "suspended") : vessels}
        nodes={nodes.data.nodes} onDone={() => { sailings.reload(); onChanged?.(); }} />
    </div>
  );
}
