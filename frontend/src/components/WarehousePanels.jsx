// frontend/src/components/WarehousePanels.jsx
// Warehouse role: register a warehouse, simple utilisation table. All warehouse data is simulated (P13).
import { useState } from "react";
import { api } from "../api";
import { useFetch, Loading, ErrorBox, Empty, Banner, FieldError, CLASS_LABEL } from "./ui";
import SourceBadge from "./SourceBadge";

export function WarehouseRegister({ onChanged, refreshKey }) {
  const nodes = useFetch(api.nodes, []);
  const classes = useFetch(api.hazardClasses, []);
  const list = useFetch(api.warehouses, [refreshKey]);
  const [f, setF] = useState({ name: "", location_node_id: "node-001", total_capacity_t: "", storage_cost_per_t_per_day: "", handling_in_cost_per_t: "", handling_out_cost_per_t: "", allowed_cargo_classes: ["general"] });
  const [errors, setErrors] = useState({});
  const [error, setError] = useState(null);
  const [done, setDone] = useState(null);
  const [busy, setBusy] = useState(false);
  const set = (k, v) => setF((s) => ({ ...s, [k]: v }));

  if (nodes.loading || classes.loading || list.loading) return <Loading what="Loading warehouses" />;
  const err = nodes.error || classes.error || list.error;
  if (err) return <ErrorBox error={err} onRetry={() => { nodes.reload(); classes.reload(); list.reload(); }} />;

  const num = (k) => (f[k] === "" ? null : Number(f[k]));
  async function submit(e) {
    e.preventDefault(); setErrors({}); setError(null); setDone(null); setBusy(true);
    try {
      const w = await api.registerWarehouse({
        ...f, total_capacity_t: num("total_capacity_t"), storage_cost_per_t_per_day: num("storage_cost_per_t_per_day"),
        handling_in_cost_per_t: num("handling_in_cost_per_t"), handling_out_cost_per_t: num("handling_out_cost_per_t"),
      });
      setDone(w); list.reload(); onChanged?.();
    } catch (x) { if (x.status === 422) setErrors(x.fieldErrors); else setError(x); } finally { setBusy(false); }
  }
  const nodeName = (id) => nodes.data.nodes.find((n) => n.id === id)?.name || id;
  const toggle = (c) => set("allowed_cargo_classes", f.allowed_cargo_classes.includes(c) ? f.allowed_cargo_classes.filter((x) => x !== c) : [...f.allowed_cargo_classes, c]);
  const field = (k, label, props = {}) => (
    <div className="col form-group"><label htmlFor={`w-${k}`}>{label}</label>
      <input id={`w-${k}`} value={f[k]} onChange={(e) => set(k, e.target.value)} {...props} /><FieldError errors={errors} name={k} /></div>
  );

  return (
    <div>
      <form className="card" onSubmit={submit} noValidate>
        <h2>Register a warehouse <SourceBadge status="simulated" /></h2>
        <div className="row">
          {field("name", "Name")}
          <div className="col form-group"><label htmlFor="w-node">Location</label>
            <select id="w-node" value={f.location_node_id} onChange={(e) => set("location_node_id", e.target.value)}>{nodes.data.nodes.map((n) => <option key={n.id} value={n.id}>{n.name}</option>)}</select>
            <FieldError errors={errors} name="location_node_id" /></div>
          {field("total_capacity_t", "Total capacity (tonnes)", { type: "number", min: "0" })}
        </div>
        <div className="row">
          {field("storage_cost_per_t_per_day", "Storage (Rs / t / day)", { type: "number", min: "0" })}
          {field("handling_in_cost_per_t", "Handling in (Rs / t)", { type: "number", min: "0" })}
          {field("handling_out_cost_per_t", "Handling out (Rs / t)", { type: "number", min: "0" })}
        </div>
        <div className="form-group"><label>Cargo classes accepted</label>
          <div className="checks">{classes.data.classes.map((c) => <label key={c.class_id}><input type="checkbox" checked={f.allowed_cargo_classes.includes(c.class_id)} onChange={() => toggle(c.class_id)} /> {CLASS_LABEL[c.class_id]}</label>)}</div>
          <FieldError errors={errors} name="allowed_cargo_classes" /></div>
        <button className="btn-primary" disabled={busy}>{busy ? "Registering…" : "Register warehouse"}</button>
        <ErrorBox error={error} />
        {done && <Banner kind="ok" title={`Registered ${done.name}.`}>It is listed below and in Utilisation <SourceBadge status="simulated" />.</Banner>}
      </form>

      <h2>Registered warehouses</h2>
      {list.data.warehouses.length === 0 ? <Empty>No warehouses yet.</Empty> : (
        <table className="t"><thead><tr><th>Name</th><th>Location</th><th>Accepts</th><th>Storage / t / day</th><th>Handling in / out</th></tr></thead>
          <tbody>{list.data.warehouses.map((w) => (
            <tr key={w.id}><td>{w.name}</td><td>{nodeName(w.location_node_id)}</td>
              <td>{w.allowed_cargo_classes.map((c) => CLASS_LABEL[c]).join(", ")}</td>
              <td>Rs {w.storage_cost_per_t_per_day} <SourceBadge status="simulated" /></td>
              <td>Rs {w.handling_in_cost_per_t} / {w.handling_out_cost_per_t} <SourceBadge status="simulated" /></td></tr>))}</tbody></table>
      )}
    </div>
  );
}

export function WarehouseUtilisation({ refreshKey }) {
  const { data, error, loading, reload } = useFetch(api.utilisation, [refreshKey]);
  if (loading) return <Loading what="Loading utilisation" />;
  if (error) return <ErrorBox error={error} onRetry={reload} />;
  if (!data.utilisation.length) return <Empty>No warehouses registered, so there is nothing to show.</Empty>;
  return (
    <div>
      <h2>Warehouse utilisation <SourceBadge status="simulated" /></h2>
      <div className="muted">Simulated figures; they reset on demo reset.</div>
      <table className="t"><thead><tr><th>Warehouse</th><th>Total</th><th>Used</th><th>Available</th><th>Utilisation</th></tr></thead>
        <tbody>{data.utilisation.map((u) => (
          <tr key={u.warehouse_id}><td>{u.name}</td>
            <td>{u.total_capacity_t} t <SourceBadge status="simulated" /></td>
            <td>{u.capacity_used_t} t <SourceBadge status="simulated" /></td>
            <td>{u.available_capacity_t} t <SourceBadge status="simulated" /></td>
            <td><strong>{u.utilisation_pct}%</strong> <SourceBadge status="simulated" /></td></tr>))}</tbody></table>
    </div>
  );
}
