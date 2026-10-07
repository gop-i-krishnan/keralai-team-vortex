// frontend/src/components/VesselRegister.jsx
// Boat owner: register a vessel by form or by pasted message. Registration needs an explicit click (P7).
import { useState } from "react";
import { api } from "../api";
import { useFetch, Loading, ErrorBox, Banner, FieldError, StatusBadge, CLASS_LABEL } from "./ui";
import SourceBadge from "./SourceBadge";

const BLANK = {
  vessel_name: "", registration_number: "", vessel_type: "", capacity_t: "", draft_m: "",
  home_jetty_id: "node-001", hazard_certs: [], contact: "simulated@operator.example",
};

export default function VesselRegister({ operatorId, onRegistered }) {
  const nodes = useFetch(api.nodes, []);
  const classes = useFetch(api.hazardClasses, []);
  const [mode, setMode] = useState("form");
  const [form, setForm] = useState(BLANK);
  const [msg, setMsg] = useState("12 ton barge, Vaikom, free tomorrow, going Alappuzha");
  const [parsed, setParsed] = useState(null);
  const [errors, setErrors] = useState({});
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(null);
  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  if (nodes.loading || classes.loading) return <Loading what="Loading form" />;
  if (nodes.error || classes.error) return <ErrorBox error={nodes.error || classes.error} onRetry={() => { nodes.reload(); classes.reload(); }} />;

  async function readMessage() {
    setError(null); setBusy(true); setParsed(null);
    try {
      const p = await api.parseVesselMessage(msg);
      setParsed(p);
      setForm((f) => ({
        ...f,
        capacity_t: p.capacity_t ?? f.capacity_t,
        vessel_type: p.vessel_type ?? f.vessel_type,
        home_jetty_id: p.home_jetty_id ?? f.home_jetty_id,
      }));
    } catch (e) { setError(e); } finally { setBusy(false); }
  }

  async function register(e) {
    e.preventDefault();
    setErrors({}); setError(null); setDone(null); setBusy(true);
    try {
      const v = await api.registerVessel({
        ...form, operator_id: operatorId,
        capacity_t: form.capacity_t === "" ? null : Number(form.capacity_t),
        draft_m: form.draft_m === "" ? null : Number(form.draft_m),
        registration_number: form.registration_number || null, vessel_type: form.vessel_type || null,
      });
      setDone(v); setForm(BLANK); setParsed(null);
      onRegistered?.(v);
    } catch (err) {
      if (err.status === 422 || err.status === 409) setErrors(err.fieldErrors); else setError(err);
    } finally { setBusy(false); }
  }

  const toggleCert = (id) => set("hazard_certs", form.hazard_certs.includes(id) ? form.hazard_certs.filter((c) => c !== id) : [...form.hazard_certs, id]);
  const nodeName = (id) => nodes.data.nodes.find((n) => n.id === id)?.name || id;

  return (
    <form className="card" onSubmit={register} noValidate>
      <h2>Register a vessel <SourceBadge status="simulated" /></h2>
      <div style={{ display: "flex", gap: 8, marginBottom: 10 }}>
        <button type="button" className={mode === "form" ? "btn-primary" : "btn-secondary"} onClick={() => setMode("form")}>Fill in a form</button>
        <button type="button" className={mode === "msg" ? "btn-primary" : "btn-secondary"} onClick={() => setMode("msg")}>Paste a message</button>
      </div>

      {mode === "msg" && (
        <div className="form-group">
          <label htmlFor="vr-msg">Your message (English)</label>
          <textarea id="vr-msg" rows={2} style={{ width: "100%", padding: 6 }} value={msg} onChange={(e) => setMsg(e.target.value)} />
          <button type="button" className="btn-secondary" disabled={busy || !msg.trim()} onClick={readMessage}>Read message</button>
          {parsed && (
            <Banner kind={parsed.needs_review ? "warn" : "ok"}
              title={parsed.needs_review ? "Low confidence — please check every field below." : "Message read."}>
              Found: {parsed.capacity_t ?? "no capacity"} t · {parsed.vessel_type ?? "no vessel type"} · home {parsed.home_jetty_id ? nodeName(parsed.home_jetty_id) : "not recognised"}
              {parsed.route_hint_node_id ? ` · heading to ${nodeName(parsed.route_hint_node_id)}` : ""}.
              Confidence {Math.round(parsed.confidence * 100)}% <SourceBadge status="assumed" />. Phone numbers and emails are removed before reading. Add the fields the message could not give (name, draft), then click Register.
            </Banner>
          )}
        </div>
      )}

      <div className="row">
        <div className="col form-group"><label htmlFor="vr-name">Vessel name</label>
          <input id="vr-name" value={form.vessel_name} onChange={(e) => set("vessel_name", e.target.value)} /><FieldError errors={errors} name="vessel_name" /></div>
        <div className="col form-group"><label htmlFor="vr-reg">Registration number <span className="muted">(placeholder — not validated)</span></label>
          <input id="vr-reg" value={form.registration_number} onChange={(e) => set("registration_number", e.target.value)} /></div>
        <div className="col form-group"><label htmlFor="vr-type">Vessel type</label>
          <input id="vr-type" value={form.vessel_type} onChange={(e) => set("vessel_type", e.target.value)} placeholder="cargo barge, country boat…" /></div>
      </div>
      <div className="row">
        <div className="col form-group"><label htmlFor="vr-cap">Capacity (tonnes)</label>
          <input id="vr-cap" type="number" min="0" step="0.5" value={form.capacity_t} onChange={(e) => set("capacity_t", e.target.value)} /><FieldError errors={errors} name="capacity_t" /></div>
        <div className="col form-group"><label htmlFor="vr-draft">Draft (metres)</label>
          <input id="vr-draft" type="number" min="0" step="0.1" value={form.draft_m} onChange={(e) => set("draft_m", e.target.value)} /><FieldError errors={errors} name="draft_m" /></div>
        <div className="col form-group"><label htmlFor="vr-home">Home jetty</label>
          <select id="vr-home" value={form.home_jetty_id} onChange={(e) => set("home_jetty_id", e.target.value)}>
            {nodes.data.nodes.map((n) => <option key={n.id} value={n.id}>{n.name}</option>)}</select><FieldError errors={errors} name="home_jetty_id" /></div>
      </div>
      <div className="form-group"><label>Cargo classes this vessel is certified for <span className="muted">(none = general cargo only)</span></label>
        <div className="checks">
          {classes.data.classes.filter((c) => c.class_id !== "general").map((c) => (
            <label key={c.class_id}><input type="checkbox" checked={form.hazard_certs.includes(c.class_id)} onChange={() => toggleCert(c.class_id)} /> {CLASS_LABEL[c.class_id]}</label>
          ))}
        </div><FieldError errors={errors} name="hazard_certs" />
        <div className="muted">Certification is self-declared in this demo and checked only against assumed rules <SourceBadge status="assumed" />.</div>
      </div>
      <div className="form-group" style={{ maxWidth: 360 }}><label htmlFor="vr-contact">Contact (fictional in the demo)</label>
        <input id="vr-contact" value={form.contact} onChange={(e) => set("contact", e.target.value)} /><FieldError errors={errors} name="contact" /></div>

      <FieldError errors={errors} name="operator_id" />
      <button className="btn-primary" type="submit" disabled={busy}>{busy ? "Registering…" : "Register vessel"}</button>
      <ErrorBox error={error} />
      {done && (
        <Banner kind="ok" title={`Registered ${done.name}.`}>
          Status: <StatusBadge status={done.status} /> — verification is a simulated demo step; use <strong>My sailings</strong> to mark it verified <SourceBadge status="simulated" />.
        </Banner>
      )}
    </form>
  );
}
