// frontend/src/components/PlanCard.jsx
import SourceBadge from "./SourceBadge";

export default function PlanCard({ mode, plan, isRecommended }) {
  return (
    <div className={`card ${isRecommended ? "recommended" : ""}`}>
      <h3>
        {mode.toUpperCase()}
        {isRecommended && <span style={{ marginLeft: 8, color: "#3b82d4" }}>★ Recommended</span>}
      </h3>
      <div className="row" style={{ marginTop: 8 }}>
        <div className="col">
          <div className="muted">Cost</div>
          <strong>Rs {plan.cost_inr?.toLocaleString("en-IN")}</strong>
          <SourceBadge status={plan.source_status} />
        </div>
        <div className="col">
          <div className="muted">Time</div>
          <strong>{plan.time_h?.toFixed(1)} h</strong>
          <SourceBadge status={plan.source_status} />
        </div>
        <div className="col">
          <div className="muted">CO₂</div>
          <strong>{plan.co2_kg?.toFixed(1)} kg</strong>
          <SourceBadge status={plan.source_status} />
        </div>
      </div>
      {plan.wait_h !== undefined && plan.wait_h !== null && (
        <div className="muted" style={{ marginTop: 6 }}>
          Wait {plan.wait_h?.toFixed(1)} h + sail {plan.sail_time_h?.toFixed(1)} h
          {plan.subsidy_applied && <span className="badge-assumed" style={{ marginLeft: 6 }}>[subsidy applied]</span>}
        </div>
      )}
      {plan.note && <div className="muted" style={{ marginTop: 4 }}>{plan.note}</div>}
    </div>
  );
}
