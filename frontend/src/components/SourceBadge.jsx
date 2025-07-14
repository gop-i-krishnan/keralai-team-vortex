// frontend/src/components/SourceBadge.jsx
// Constitution P3: every number in UI must show [sourced] or [assumed].
export default function SourceBadge({ status }) {
  if (!status) return null;
  const cls = status === "sourced" ? "badge-sourced" : "badge-assumed";
  return <span className={`tag ${cls}`}>[{status}]</span>;
}
