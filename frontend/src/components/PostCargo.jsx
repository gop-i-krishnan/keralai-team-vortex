// frontend/src/components/PostCargo.jsx
// Shipper: post a cargo with a hazard class. Hazardous classes show a compliance banner (P11).
import { useState } from "react";
import { api } from "../api";
import { useFetch, Loading, ErrorBox, Banner, FieldError, CLASS_LABEL, AUTHORITY_TEXT } from "./ui";
import SourceBadge from "./SourceBadge";
import WhatsAppChat from "./WhatsAppChat";

export default function PostCargo({ onPosted, prefill }) {
  const nodes = useFetch(api.nodes, []);
  const classes = useFetch(api.hazardClasses, []);
  const [form, setForm] = useState({
    description: "", weight_t: 10, cargo_class: "general",
    origin_node_id: "node-001", destination_node_id: "node-002",
    ...(prefill || {}),
  });
  const [errors, setErrors] = useState({});
  const [apiError, setApiError] = useState(null);
  const [posted, setPosted] = useState(null);
  const [busy, setBusy] = useState(false);
  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  if (nodes.loading || classes.loading) return <Loading what="Loading form" />;
  if (nodes.error || classes.error) return <ErrorBox error={nodes.error || classes.error} onRetry={() => { nodes.reload(); classes.reload(); }} />;

  const rule = classes.data.classes.find((c) => c.class_id === form.cargo_class);

  async function submit(e) {
    e.preventDefault();
    setErrors({}); setApiError(null); setBusy(true);
    try {
      const c = await api.postCargo({ ...form, weight_t: Number(form.weight_t) });
      setPosted(c);
      onPosted?.(c);
    } catch (err) {
      if (err.status === 422) setErrors(err.fieldErrors); else setApiError(err);
    } finally { setBusy(false); }
  }

  return (
    <div>
      <form className="card" onSubmit={submit} noValidate>
        <h2>Post cargo <SourceBadge status="simulated" /></h2>
        <div className="muted">Posted cargo is demo data. Do not enter real names, phone numbers or addresses.</div>
        <div className="row" style={{ marginTop: 10 }}>
          <div className="col form-group">
            <label htmlFor="pc-desc">What are you shipping?</label>
            <input id="pc-desc" value={form.description} onChange={(e) => set("description", e.target.value)} placeholder="e.g. Coconut oil cans" />
            <FieldError errors={errors} name="description" />
          </div>
          <div className="col form-group">
            <label htmlFor="pc-wt">Weight (tonnes)</label>
            <input id="pc-wt" type="number" min="0.1" step="0.1" value={form.weight_t} onChange={(e) => set("weight_t", e.target.value)} />
            <FieldError errors={errors} name="weight_t" />
          </div>
        </div>
        <div className="row">
          <div className="col form-group">
            <label htmlFor="pc-from">From</label>
            <select id="pc-from" value={form.origin_node_id} onChange={(e) => set("origin_node_id", e.target.value)}>
              {nodes.data.nodes.map((n) => <option key={n.id} value={n.id}>{n.name}</option>)}
            </select>
            <FieldError errors={errors} name="origin_node_id" />
          </div>
          <div className="col form-group">
            <label htmlFor="pc-to">To</label>
            <select id="pc-to" value={form.destination_node_id} onChange={(e) => set("destination_node_id", e.target.value)}>
              {nodes.data.nodes.map((n) => <option key={n.id} value={n.id}>{n.name}</option>)}
            </select>
            <FieldError errors={errors} name="destination_node_id" />
          </div>
          <div className="col form-group">
            <label htmlFor="pc-class">Cargo class</label>
            <select id="pc-class" value={form.cargo_class} onChange={(e) => set("cargo_class", e.target.value)}>
              {classes.data.classes.map((c) => (
                <option key={c.class_id} value={c.class_id}>
                  {CLASS_LABEL[c.class_id] || c.class_id}{c.human_review_required ? " — compliance review required" : c.certification_required ? " — certified vessel required" : ""}
                </option>
              ))}
            </select>
            <FieldError errors={errors} name="cargo_class" />
            <div className="muted">Class rules <SourceBadge status="assumed" /> — {classes.data.note}</div>
          </div>
        </div>

        {rule?.human_review_required && (
          <Banner kind="warn" title="Compliance review required — hazardous cargo [assumed].">
            This shipment will need a separate compliance review before booking can be confirmed.
            Only certified vessels are matched. {AUTHORITY_TEXT}
          </Banner>
        )}
        {rule && rule.allowed_modes.length === 0 && (
          <Banner kind="bad" title="No transport mode is offered for this class by default [assumed].">
            A special permit is needed; nothing will be matched automatically. {AUTHORITY_TEXT}
          </Banner>
        )}

        <button className="btn-primary" type="submit" disabled={busy}>{busy ? "Posting…" : "Post cargo"}</button>
        <ErrorBox error={apiError} />
        {posted && (
          <Banner kind="ok" title={`Posted ${posted.id}.`}>
            {posted.weight_t} t of {posted.description} <SourceBadge status="simulated" />.{" "}
            <button type="button" className="btn-secondary" style={{ padding: "2px 10px" }} onClick={() => onPosted?.(posted, true)}>
              Find matching sailings →
            </button>
          </Banner>
        )}
      </form>

      <details className="card">
        <summary style={{ cursor: "pointer", fontWeight: 600 }}>Or describe it in plain language (simulated chat)</summary>
        <div style={{ marginTop: 10 }}><WhatsAppChat /></div>
      </details>
    </div>
  );
}
