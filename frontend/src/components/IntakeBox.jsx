// frontend/src/components/IntakeBox.jsx
// Free-text intake for Feature 003 — LLM parses, human reviews.
import { useState } from "react";
import { parseText } from "../api";

export default function IntakeBox({ onParsed }) {
  const [text, setText] = useState("Send 10 tonnes from Kochi to Alappuzha in 10 hours");
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);

  async function handleParse() {
    setLoading(true);
    try {
      const r = await parseText(text);
      setResult(r);
      if (!r.needs_review && onParsed) onParsed(r);
    } catch (e) {
      setResult({ error: e.message });
    } finally { setLoading(false); }
  }

  return (
    <div className="card section">
      <h2>Free-Text Intake <span className="muted">(Feature 003)</span></h2>
      <div className="form-group">
        <label>Shipment request (natural language)</label>
        <input
          type="text"
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="e.g. Send 10 tonnes from Kochi to Alappuzha in 10 hours"
        />
      </div>
      <button className="btn-primary" onClick={handleParse} disabled={loading}>
        {loading ? "Parsing…" : "Parse Request"}
      </button>

      {result && !result.error && (
        <div style={{ marginTop: 12 }}>
          {result.needs_review && (
            <div className="badge-review" style={{ marginBottom: 8 }}>
              ⚠ Low confidence ({(result.confidence * 100).toFixed(0)}%) — please review
            </div>
          )}
          <div className="row">
            <div className="col">
              <div className="muted">Weight</div>
              <strong>{result.weight_t ?? "—"} t</strong>
            </div>
            <div className="col">
              <div className="muted">Origin</div>
              <strong>{result.origin_raw ?? "—"}</strong>
              <div className="muted">{result.origin_node_id}</div>
            </div>
            <div className="col">
              <div className="muted">Destination</div>
              <strong>{result.destination_raw ?? "—"}</strong>
              <div className="muted">{result.destination_node_id}</div>
            </div>
            <div className="col">
              <div className="muted">Deadline</div>
              <strong>{result.deadline_h ? `${result.deadline_h} h` : result.deadline_raw ?? "—"}</strong>
            </div>
          </div>
          <div className="muted" style={{ marginTop: 6 }}>
            Method: {result.method} | Confidence: {(result.confidence * 100).toFixed(0)}%
          </div>
        </div>
      )}
      {result?.error && <div className="error">{result.error}</div>}
    </div>
  );
}
