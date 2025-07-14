// frontend/src/components/ShipmentForm.jsx
import { useState } from "react";

const NODES = [
  { id: "node-001", label: "Kochi Thevara Jetty" },
  { id: "node-002", label: "Alappuzha Boat Jetty" },
  { id: "node-003", label: "Kollam Jetty" },
];

export default function ShipmentForm({ onSubmit, loading }) {
  const [form, setForm] = useState({
    weight_t: 10,
    origin_node_id: "node-001",
    destination_node_id: "node-002",
    ready_time: "04:00",
    deadline_h: 10,
    subsidy: false,
  });

  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  return (
    <form
      onSubmit={(e) => { e.preventDefault(); onSubmit(form); }}
      className="card"
    >
      <h2>Shipment Details</h2>
      <div className="row">
        <div className="col form-group">
          <label>Weight (tonnes)</label>
          <input type="number" min="0.1" step="0.1" value={form.weight_t}
            onChange={(e) => set("weight_t", parseFloat(e.target.value))} />
        </div>
        <div className="col form-group">
          <label>Origin</label>
          <select value={form.origin_node_id} onChange={(e) => set("origin_node_id", e.target.value)}>
            {NODES.map((n) => <option key={n.id} value={n.id}>{n.label}</option>)}
          </select>
        </div>
        <div className="col form-group">
          <label>Destination</label>
          <select value={form.destination_node_id} onChange={(e) => set("destination_node_id", e.target.value)}>
            {NODES.map((n) => <option key={n.id} value={n.id}>{n.label}</option>)}
          </select>
        </div>
      </div>
      <div className="row">
        <div className="col form-group">
          <label>Ready time (HH:MM)</label>
          <input type="time" value={form.ready_time}
            onChange={(e) => set("ready_time", e.target.value)} />
        </div>
        <div className="col form-group">
          <label>Deadline (hours from ready)</label>
          <input type="range" min="1" max="48" value={form.deadline_h}
            onChange={(e) => set("deadline_h", parseFloat(e.target.value))} />
          <span>{form.deadline_h} h</span>
        </div>
        <div className="col form-group" style={{ paddingTop: 20 }}>
          <label>
            <input type="checkbox" checked={form.subsidy}
              onChange={(e) => set("subsidy", e.target.checked)} />
            {" "}Apply subsidy scenario <span className="badge-assumed">[assumed]</span>
          </label>
          <div className="muted">OFF by default — what-if only</div>
        </div>
      </div>
      <button type="submit" className="btn-primary" disabled={loading}>
        {loading ? "Calculating…" : "Compare Options"}
      </button>
    </form>
  );
}
