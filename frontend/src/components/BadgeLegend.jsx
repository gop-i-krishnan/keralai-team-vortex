// frontend/src/components/BadgeLegend.jsx
// One-line explanation of the three tags, so a first-time viewer knows what they mean (P3, P13).
export default function BadgeLegend() {
  return (
    <div className="muted" style={{ marginBottom: 10 }}>
      Tags next to numbers:{" "}
      <span className="badge-sourced">[sourced]</span> from a cited source ·{" "}
      <span className="badge-assumed">[assumed]</span> our estimate, to be verified ·{" "}
      <span className="badge-simulated">[simulated]</span> demo data, not real
    </div>
  );
}
