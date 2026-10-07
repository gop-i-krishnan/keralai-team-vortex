// frontend/src/components/SourceBadge.jsx
// Constitution P3 / P13: every number shows a text badge: [sourced], [assumed] or [simulated].
export default function SourceBadge({ status }) {
  if (!status) return null;
  const cls = status === "sourced"
    ? "badge-sourced"
    : status === "simulated" || status === "recorded" ? "badge-simulated" : "badge-assumed";
  return <span className={`tag ${cls}`}>[{status}]</span>;
}
