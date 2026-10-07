// frontend/src/components/WhatsAppChat.jsx
// Simulates an operator sending a WhatsApp-style message → AI parses → options shown.
// Makes the NLP intake tangible for judges. All simulated, no real WhatsApp API.
import { useState } from "react";
import { sendOperatorMessage } from "../api";

const OPERATOR = { id: "op-001", name: "Kerala Backwater Freight Co.", avatar: "KF" };

const SUGGESTIONS = [
  "10 tonnes from Kochi to Alappuzha in 10 hours",
  "5 tonnes coconut oil Thevara to Alleppey urgent 3 hours",
  "Send 20t rice bags from Alappuzha to Kollam by tomorrow",
];

function Bubble({ from, text, timestamp, isSystem }) {
  return (
    <div style={{
      display: "flex", justifyContent: from === "user" ? "flex-end" : "flex-start",
      marginBottom: 8,
    }}>
      {from !== "user" && (
        <div style={{
          width: 28, height: 28, borderRadius: "50%", background: "#3b82d4",
          color: "#fff", display: "flex", alignItems: "center", justifyContent: "center",
          fontSize: 10, fontWeight: 700, marginRight: 6, flexShrink: 0, alignSelf: "flex-end",
        }}>AI</div>
      )}
      <div style={{
        maxWidth: "80%", padding: "8px 12px", borderRadius: 12,
        borderBottomRightRadius: from === "user" ? 2 : 12,
        borderBottomLeftRadius: from === "user" ? 12 : 2,
        background: from === "user" ? "#dcf8c6" : isSystem ? "#f0f4ff" : "#fff",
        border: "1px solid", borderColor: isSystem ? "#bfdbfe" : "#e5e7eb",
        fontSize: 13, lineHeight: 1.5,
      }}>
        {text}
        <div style={{ fontSize: 10, color: "#57606a", marginTop: 4, textAlign: "right" }}>{timestamp}</div>
      </div>
    </div>
  );
}

function now() {
  return new Date().toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" });
}

export default function WhatsAppChat() {
  const [messages, setMessages] = useState([
    { from: "ai", text: `Hi! I'm JalSetu. Tell me about your shipment and I'll compare road vs. waterway options instantly.`, ts: "09:00", isSystem: true },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);

  function addMsg(from, text, isSystem = false) {
    setMessages(prev => [...prev, { from, text, ts: now(), isSystem }]);
  }

  async function send(text) {
    if (!text.trim()) return;
    addMsg("user", text);
    setInput("");
    setLoading(true);

    try {
      const r = await sendOperatorMessage(OPERATOR.id, text);
      const p = r.parsed;

      // Show parse result as structured message
      let parseMsg = `📋 Parsed:\n`;
      parseMsg += p.weight_t ? `• Weight: ${p.weight_t} t\n` : "";
      parseMsg += p.origin_raw ? `• From: ${p.origin_raw}\n` : "";
      parseMsg += p.destination_raw ? `• To: ${p.destination_raw}\n` : "";
      parseMsg += p.deadline_h ? `• Deadline: ${p.deadline_h} h\n` : "";
      parseMsg += `• Confidence: ${Math.round((p.confidence || 0) * 100)}%`;
      if (p.needs_review) parseMsg += `\n⚠️ Low confidence — please verify`;

      addMsg("ai", parseMsg, true);

      if (r.options) {
        const rec = r.options.recommended;
        const plan = r.options.plans[rec];
        const other = Object.keys(r.options.plans).find(k => k !== rec);
        const otherPlan = r.options.plans[other];

        let optMsg = `✅ Recommendation: ${rec === "hybrid" ? "⛵ WATERWAY" : "🚛 ROAD"}\n\n`;
        optMsg += `${rec === "hybrid" ? "⛵" : "🚛"} ${rec.toUpperCase()}: Rs ${plan.cost_inr?.toLocaleString("en-IN")}, ${plan.time_h?.toFixed(1)}h, ${plan.co2_kg?.toFixed(1)}kg CO₂\n`;
        if (otherPlan) {
          optMsg += `${other === "hybrid" ? "⛵" : "🚛"} ${other.toUpperCase()}: Rs ${otherPlan.cost_inr?.toLocaleString("en-IN")}, ${otherPlan.time_h?.toFixed(1)}h\n`;
        }
        optMsg += `\n💡 ${r.options.why}`;
        addMsg("ai", optMsg, false);
      } else {
        addMsg("ai", r.message || "Could not compute options — please try with more detail.", true);
      }
    } catch (e) {
      addMsg("ai", `Error: ${e.message}`, true);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="card" style={{ padding: 0, overflow: "hidden" }}>
      {/* Header */}
      <div style={{
        background: "#075e54", color: "#fff", padding: "10px 16px",
        display: "flex", alignItems: "center", gap: 10,
      }}>
        <div style={{
          width: 36, height: 36, borderRadius: "50%", background: "#25d366",
          display: "flex", alignItems: "center", justifyContent: "center",
          fontWeight: 700, fontSize: 12,
        }}>{OPERATOR.avatar}</div>
        <div>
          <div style={{ fontWeight: 600, fontSize: 14 }}>JalSetu AI Assistant</div>
          <div style={{ fontSize: 11, opacity: 0.8 }}>Operator interface · Simulated · No real WhatsApp · Granite integration implemented; demo uses offline adapter</div>
        </div>
      </div>

      {/* Messages */}
      <div style={{
        background: "#e5ddd5", padding: "12px 16px",
        minHeight: 300, maxHeight: 380, overflowY: "auto",
      }}>
        {messages.map((m, i) => (
          <Bubble key={i} from={m.from} text={m.text} timestamp={m.ts} isSystem={m.isSystem} />
        ))}
        {loading && (
          <div style={{ textAlign: "left", padding: "4px 16px", color: "#57606a", fontSize: 12 }}>
            JalSetu is typing…
          </div>
        )}
      </div>

      {/* Suggestions */}
      <div style={{ background: "#f0f0f0", padding: "6px 12px", display: "flex", gap: 6, flexWrap: "wrap" }}>
        {SUGGESTIONS.map((s, i) => (
          <button key={i}
            style={{
              fontSize: 11, padding: "3px 8px", borderRadius: 12,
              border: "1px solid #ccc", background: "#fff", cursor: "pointer",
              color: "#075e54", fontWeight: 500,
            }}
            onClick={() => send(s)}
          >
            {s.length > 40 ? s.slice(0, 40) + "…" : s}
          </button>
        ))}
      </div>

      {/* Input */}
      <div style={{
        background: "#f0f0f0", padding: "8px 12px",
        display: "flex", gap: 8, alignItems: "center",
      }}>
        <input
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === "Enter" && send(input)}
          placeholder="Describe your shipment…"
          style={{
            flex: 1, padding: "8px 12px", borderRadius: 20,
            border: "1px solid #ccc", fontSize: 13, outline: "none",
          }}
          disabled={loading}
        />
        <button
          onClick={() => send(input)}
          disabled={loading || !input.trim()}
          style={{
            width: 36, height: 36, borderRadius: "50%",
            background: loading ? "#ccc" : "#25d366",
            color: "#fff", border: "none", cursor: "pointer",
            fontSize: 16, display: "flex", alignItems: "center", justifyContent: "center",
          }}
        >➤</button>
      </div>
    </div>
  );
}
