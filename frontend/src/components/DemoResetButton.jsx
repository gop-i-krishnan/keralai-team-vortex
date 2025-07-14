// frontend/src/components/DemoResetButton.jsx
// Constitution P10: demo reset must restore deterministic seed state.
import { resetDemo } from "../api";

export default function DemoResetButton({ onReset }) {
  async function handle() {
    await resetDemo();
    if (onReset) onReset();
  }
  return (
    <button className="btn-danger" onClick={handle} title="Reset all demo state to seed data">
      ↺ Reset Demo
    </button>
  );
}
