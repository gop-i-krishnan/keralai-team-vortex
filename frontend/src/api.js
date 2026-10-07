// frontend/src/api.js
// All backend calls go through this file.
const BASE = import.meta.env.VITE_API_URL || "http://localhost:8000/api";

export async function getOptions(payload) {
  const r = await fetch(`${BASE}/options`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function matchCargo(cargoId) {
  const r = await fetch(`${BASE}/match`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ cargo_id: cargoId }),
  });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function createBooking(payload) {
  const r = await fetch(`${BASE}/book`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function confirmBooking(bookingId) {
  const r = await fetch(`${BASE}/book/${bookingId}/confirm`, { method: "POST" });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function getBackhaul(bookingId) {
  const r = await fetch(`${BASE}/backhaul/${bookingId}`);
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function parseText(text) {
  const r = await fetch(`${BASE}/parse`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function getViability() {
  const r = await fetch(`${BASE}/viability`);
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function getAssumptions() {
  const r = await fetch(`${BASE}/config/assumptions`);
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function resetDemo() {
  const r = await fetch(`${BASE}/demo/reset`, { method: "POST" });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function sendOperatorMessage(operatorId, message) {
  const r = await fetch(`${BASE}/operator/message`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ operator_id: operatorId, message }),
  });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

// ── Role-based UI additions ───────────────────────────────────────────────────
// Structured errors: backend returns detail {error} or detail {errors:[{field,code,message}]}.
export class ApiError extends Error {
  constructor(status, detail) {
    super(friendly(status, detail));
    this.status = status;
    this.detail = detail;
    this.fieldErrors = {};
    (detail?.errors || []).forEach((e) => { this.fieldErrors[e.field] = e.message; });
    this.code = detail?.error || detail?.errors?.[0]?.code || null;
  }
}

const CODE_TEXT = {
  compliance_review_required: "Compliance review is required before this can proceed.",
  vessel_suspended: "This vessel is suspended — existing bookings unaffected; no new bookings can be made.",
  booking_not_disrupted: "This booking has no open disruption.",
  booking_not_disruptable: "Only confirmed bookings can be disrupted in the demo.",
  disruption_already_open: "A disruption is already open on this booking. Review its alternatives.",
  replan_already_confirmed: "A re-plan was already confirmed for this disruption.",
  proposal_stale: "These alternatives are out of date. Reload the alternatives.",
  unknown_alternative: "That alternative is no longer available.",
  no_proposal: "Load the alternatives first.",
  final_milestone: "Booking already at final milestone.",
  booking_disrupted: "Resolve the disruption before advancing.",
  booking_not_active: "Confirm the booking first.",
  already_delivered: "This booking was already marked delivered.",
  booking_not_deliverable: "Only confirmed bookings can be marked delivered.",
  invalid_transition: "That change is not allowed for the current vessel status.",
  warehouse_at_capacity: "The warehouse is at capacity.",
  compliance_already_reviewed: "A compliance review is already recorded.",
};

function friendly(status, detail) {
  if (detail?.errors?.length) return detail.errors.map((e) => e.message).join("; ");
  if (detail?.error) return CODE_TEXT[detail.error] || detail.message || detail.error;
  if (typeof detail === "string") return detail;
  if (status === 0) return "Cannot reach the JalSetu server. Is the backend running on port 8000?";
  return `Request failed (${status}).`;
}

async function call(method, path, body) {
  let r;
  try {
    r = await fetch(`${BASE}${path}`, {
      method,
      headers: body !== undefined ? { "Content-Type": "application/json" } : undefined,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  } catch (_) {
    throw new ApiError(0, null);
  }
  let data = null;
  try { data = await r.json(); } catch (_) { /* empty body */ }
  if (!r.ok) throw new ApiError(r.status, data?.detail ?? data);
  return data;
}

export const api = {
  nodes: () => call("GET", "/nodes"),
  operators: () => call("GET", "/operators"),
  hazardClasses: () => call("GET", "/hazard-classes"),
  cargoList: () => call("GET", "/cargo/list"),
  postCargo: (b) => call("POST", "/cargo", b),
  match: (cargo_id) => call("POST", "/match", { cargo_id }),
  vessels: () => call("GET", "/vessel/list"),
  sailings: () => call("GET", "/sailing/list"),
  book: (b) => call("POST", "/book", b),
  confirm: (id) => call("POST", `/book/${id}/confirm`),
  approveCompliance: (id, note) => call("POST", `/compliance/review/${id}/approve`, { reviewer_note: note }),
  bookings: () => call("GET", "/bookings"),
  advance: (id) => call("POST", `/demo/booking/${id}/advance`),
  scenarios: () => call("GET", "/demo/disruption-scenarios"),
  disrupt: (id, b) => call("POST", `/demo/booking/${id}/disrupt`, b),
  notify: (id) => call("POST", `/booking/${id}/notify`),
  replan: (id) => call("POST", `/replan/${id}`),
  replanConfirm: (id, alternative_id) => call("POST", `/replan/${id}/confirm`, { alternative_id }),
  replanReview: (pid, note) => call("POST", `/compliance/replan-review/${encodeURIComponent(pid)}/approve`, { reviewer_note: note }),
  deliver: (id, b) => call("POST", `/booking/${id}/deliver`, b),
  disruptionSummary: () => call("GET", "/disruptions/summary"),
  registerVessel: (b) => call("POST", "/vessel/register", b),
  parseVesselMessage: (message) => call("POST", "/vessel/parse-message", { message }),
  publishSailing: (b) => call("POST", "/sailing/publish", b),
  verifyVessel: (id) => call("POST", `/admin/vessel/${id}/verify`),
  suspendVessel: (id) => call("POST", `/admin/vessel/${id}/suspend`),
  reinstateVessel: (id) => call("POST", `/admin/vessel/${id}/reinstate`),
  operatorProfile: (id) => call("GET", `/operator/${id}/profile`),
  stage: (b) => call("POST", "/warehouse/stage", b),
  stageConfirm: (proposal_id) => call("POST", "/warehouse/stage/confirm", { proposal_id }),
  warehouses: () => call("GET", "/warehouse/list"),
  registerWarehouse: (b) => call("POST", "/warehouse/register", b),
  utilisation: () => call("GET", "/warehouse/utilisation"),
};
