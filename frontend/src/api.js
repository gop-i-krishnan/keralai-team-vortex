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
