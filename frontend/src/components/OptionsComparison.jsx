// frontend/src/components/OptionsComparison.jsx
import PlanCard from "./PlanCard";

export default function OptionsComparison({ result }) {
  if (!result) return null;
  const { plans, recommended, why, scores } = result;

  return (
    <div className="section">
      <h2>Plan Comparison</h2>
      <div className="why-box">{why}</div>
      <div className="row" style={{ marginTop: 12 }}>
        {Object.entries(plans).map(([mode, plan]) => (
          <div className="col" key={mode}>
            <PlanCard
              mode={mode}
              plan={plan}
              isRecommended={mode === recommended}
            />
            <div className="muted">Score: {scores?.[mode]?.toFixed(3)}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
