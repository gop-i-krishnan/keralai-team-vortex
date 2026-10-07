// frontend/src/components/ui.jsx
// Shared loading / error / empty states, status badges and a tiny fetch hook.
import { useState, useEffect, useCallback, useRef } from "react";

export function Loading({ what = "Loading" }) {
  return <div className="loading" role="status">{what}…</div>;
}

export function ErrorBox({ error, onRetry }) {
  if (!error) return null;
  return (
    <div className="banner bad" role="alert">
      <strong>Something went wrong.</strong> {error.message || String(error)}
      {onRetry && <button className="btn-secondary" style={{ marginLeft: 10, padding: "2px 10px" }} onClick={onRetry}>Retry</button>}
    </div>
  );
}

export function Empty({ children }) {
  return <div className="empty">{children}</div>;
}

export function Banner({ kind = "info", title, children }) {
  return (
    <div className={`banner ${kind}`} role={kind === "bad" ? "alert" : "note"}>
      {title && <strong>{title} </strong>}{children}
    </div>
  );
}

// Text label always present; colour is secondary (P3, P11).
const STATUS_KIND = {
  verified: "ok", confirmed: "ok", completed: "ok", replanned: "info", pending: "warn",
  pending_verification: "warn", pending_review: "warn", disrupted: "bad", suspended: "bad", draft: "info",
};
const STATUS_TEXT = {
  pending_verification: "Pending verification", pending_review: "Compliance review required",
  verified: "Verified", suspended: "Suspended", confirmed: "Confirmed", pending: "Awaiting confirmation",
  disrupted: "Disrupted", replanned: "Re-planned",
};
export function StatusBadge({ status }) {
  return <span className={`status ${STATUS_KIND[status] || "info"}`}>{STATUS_TEXT[status] || status}</span>;
}

export const CLASS_LABEL = {
  general: "General", perishable: "Perishable", liquid_bulk: "Liquid bulk", flammable: "Flammable",
  explosive: "Explosive", toxic_corrosive: "Toxic/corrosive", oversized: "Oversized",
};

export function ClassBadge({ cls }) {
  const hazard = ["flammable", "explosive", "toxic_corrosive", "liquid_bulk"].includes(cls);
  return <span className={`status ${hazard ? "warn" : "info"}`}>{hazard ? "⚠ " : ""}{CLASS_LABEL[cls] || cls}</span>;
}

export const AUTHORITY_TEXT =
  "For regulatory and safety guidance on hazardous goods transport, contact IWAI, PESO, or the relevant state authority.";

export function useFetch(fn, deps = []) {
  const [state, setState] = useState({ data: null, error: null, loading: true });
  const alive = useRef(true);
  const run = useCallback(() => {
    setState((s) => ({ ...s, loading: true, error: null }));
    fn().then((data) => alive.current && setState({ data, error: null, loading: false }))
      .catch((error) => alive.current && setState({ data: null, error, loading: false }));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  useEffect(() => { alive.current = true; run(); return () => { alive.current = false; }; }, [run]);
  return { ...state, reload: run };
}

export function FieldError({ errors, name }) {
  return errors?.[name] ? <div className="field-error" role="alert">{errors[name]}</div> : null;
}

export function SubNav({ tabs, value, onChange }) {
  return (
    <div className="subnav" role="tablist">
      {tabs.map((t) => (
        <button key={t.id} role="tab" aria-selected={value === t.id}
          className={value === t.id ? "active" : ""} onClick={() => onChange(t.id)}>{t.label}</button>
      ))}
    </div>
  );
}
