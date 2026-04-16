import { useState, useRef, useEffect, useCallback } from "react";
import MarkdownRenderer from "./MarkdownRenderer";
import { useChatHistory, StoredMessage } from "../hooks/useChatHistory";
import { useRole, ROLE_LABELS, UserRole } from "../hooks/useRole";
import { useRegion } from "../context/RegionContext";

function buildWelcome(regionDetail: Record<string, any> | null, marketCode: string): string {
  if (!regionDetail) {
    return "Welcome to the Regulatory Intelligence Command Center.\n\nTry one of the prompts below or ask me anything about energy compliance.";
  }
  const { name, flag, market_name, data_available, regulators = [], carbon_scheme } = regionDetail;
  const regList = regulators.slice(0, 4).map((r: any) => `**${r.code}** (${r.domain})`).join(", ");
  const dataNote = data_available
    ? `I have access to live ${name} compliance data.`
    : `${name} data is coming soon — I'll answer from regulatory knowledge in the meantime.`;

  return (
    `${flag} Welcome to the **${name}** view of the Regulatory Intelligence Command Center.\n\n` +
    `I can help you navigate the **${market_name}** — covering ${regList}.\n\n` +
    (carbon_scheme?.name ? `Carbon scheme: **${carbon_scheme.name}** (${carbon_scheme.price} ${carbon_scheme.price_unit}).\n\n` : "") +
    `${dataNote}\n\nTry one of the prompts below or ask me anything about ${name} energy compliance.`
  );
}

const DEFAULT_WELCOME: StoredMessage = {
  id: "welcome",
  role: "assistant",
  content: buildWelcome(null, "AU"),
  timestamp: new Date().toISOString(),
};

const ROLE_OPTIONS: { value: NonNullable<UserRole>; label: string; desc: string }[] = [
  { value: "cro", label: "CRO", desc: "Risk posture, board reporting, enforcement trends" },
  { value: "cfo", label: "CFO", desc: "Penalty exposure, Safeguard cost modelling, forecasts" },
  { value: "general_counsel", label: "General Counsel", desc: "Enforcement intelligence, obligation mapping" },
  { value: "head_reg_affairs", label: "Head of Reg Affairs", desc: "Obligation tracking, regulatory change radar" },
  { value: "compliance_analyst", label: "Compliance Analyst", desc: "Daily compliance operations, data queries" },
];

export default function ChatPanel() {
  const { messages, addMessage, updateLast, clearHistory, replaceWelcome } = useChatHistory(DEFAULT_WELCOME);
  const { role, setRole, chips } = useRole();
  const { market } = useRegion();

  // Update the welcome message whenever the market changes
  useEffect(() => {
    fetch(`/api/regions/${market}`)
      .then((r) => r.ok ? r.json() : Promise.reject())
      .then((detail) => replaceWelcome(buildWelcome(detail, market)))
      .catch(() => {});
  }, [market]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [showRoleSelector, setShowRoleSelector] = useState(false);
  const [showClearConfirm, setShowClearConfirm] = useState(false);
  const [waitingForToken, setWaitingForToken] = useState(false);
  const messagesEnd = useRef<HTMLDivElement>(null);
  const contentRef = useRef("");
  const rafRef = useRef<number>(0);

  useEffect(() => {
    messagesEnd.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, waitingForToken]);

  const updateStreamingMessage = useCallback((content: string) => {
    updateLast(content);
  }, [updateLast]);

  const send = async (text: string) => {
    if (!text.trim() || loading) return;

    addMessage({ role: "user", content: text.trim() });
    const assistantMsg = addMessage({ role: "assistant", content: "" });
    void assistantMsg;
    setInput("");
    setLoading(true);
    setWaitingForToken(true);
    contentRef.current = "";

    try {
      const resp = await fetch("/api/chat/stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text.trim(), market }),
      });

      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const reader = resp.body?.getReader();
      if (!reader) throw new Error("No response body");

      const decoder = new TextDecoder();
      let buffer = "";
      let currentEventType = "message";
      let pendingUpdate = false;

      const scheduleUpdate = () => {
        if (!pendingUpdate) {
          pendingUpdate = true;
          rafRef.current = requestAnimationFrame(() => {
            updateStreamingMessage(contentRef.current);
            pendingUpdate = false;
          });
        }
      };

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.replace(/\r\n/g, "\n").split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed) { currentEventType = "message"; continue; }
          if (trimmed.startsWith("event:")) { currentEventType = trimmed.slice(6).trim(); continue; }
          if (trimmed.startsWith("data:")) {
            if (currentEventType !== "message") continue;
            let raw = trimmed.slice(5);
            if (raw.startsWith(" ")) raw = raw.slice(1);
            if (!raw) continue;
            try {
              const token = JSON.parse(raw);
              if (token) {
                if (waitingForToken) setWaitingForToken(false);
                contentRef.current += token;
                scheduleUpdate();
              }
            } catch {
              contentRef.current += raw;
              scheduleUpdate();
            }
          }
        }
      }

      if (rafRef.current) cancelAnimationFrame(rafRef.current);
      updateStreamingMessage(contentRef.current);
    } catch {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
      updateLast("Sorry, I encountered an error. Please try again.");
    } finally {
      setLoading(false);
      setWaitingForToken(false);
    }
  };

  const isStreaming = loading && messages[messages.length - 1]?.role === "assistant"
    && messages[messages.length - 1]?.content.length > 0;

  return (
    <div className="chat-panel">
      {/* Header */}
      <div className="chat-header" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <span>AI Compliance Assistant</span>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          {role && (
            <span
              onClick={() => setShowRoleSelector(true)}
              title="Change role"
              style={{
                fontSize: 10, fontWeight: 600, color: "var(--accent-blue)",
                background: "rgba(79,143,247,0.12)", border: "1px solid rgba(79,143,247,0.2)",
                borderRadius: 4, padding: "2px 7px", cursor: "pointer", letterSpacing: 0.5,
              }}
            >
              {ROLE_LABELS[role]}
            </span>
          )}
          <button
            onClick={() => setShowClearConfirm(true)}
            title="Clear conversation"
            style={{
              fontSize: 11, color: "var(--text-muted)", background: "none",
              border: "none", cursor: "pointer", padding: "2px 4px",
            }}
            aria-label="Clear conversation history"
          >
            ✕ Clear
          </button>
        </div>
      </div>

      {/* Messages */}
      <div className="chat-messages" aria-live="polite" aria-label="Conversation history">
        {messages.map((msg) => (
          <div key={msg.id} className={`chat-msg ${msg.role}`}>
            {msg.role === "assistant" ? (
              msg.content ? <MarkdownRenderer content={msg.content} /> : null
            ) : (
              msg.content
            )}
          </div>
        ))}
        {/* Typing indicator — shown while waiting for first token */}
        {waitingForToken && (
          <div className="chat-msg assistant" aria-label="Assistant is thinking">
            <span className="typing-dots">
              <span /><span /><span />
            </span>
          </div>
        )}
        {/* Streaming cursor */}
        {isStreaming && (
          <span className="typing-indicator" aria-hidden="true">&#9608;</span>
        )}
        <div ref={messagesEnd} />
      </div>

      {/* Prompt chips */}
      <div className="prompt-chips">
        {chips.map((chip, i) => (
          <button
            key={i}
            className="prompt-chip"
            onClick={() => send(chip)}
            disabled={loading}
          >
            {chip}
          </button>
        ))}
        {!role && (
          <button
            className="prompt-chip"
            onClick={() => setShowRoleSelector(true)}
            style={{ borderStyle: "dashed", color: "var(--text-muted)" }}
          >
            + Personalise for my role
          </button>
        )}
      </div>

      {/* Input */}
      <div className="chat-input-area">
        <input
          className="chat-input"
          placeholder="Ask about emissions, notices, enforcement..."
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && send(input)}
          disabled={loading}
          aria-label="Chat message input"
        />
        <button
          className="chat-send"
          onClick={() => send(input)}
          disabled={loading || !input.trim()}
          aria-label="Send message"
        >
          Send
        </button>
      </div>

      {/* Role selector modal */}
      {showRoleSelector && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label="Select your role"
          style={{
            position: "fixed", inset: 0, zIndex: 200,
            background: "rgba(0,0,0,0.6)", backdropFilter: "blur(4px)",
            display: "flex", alignItems: "center", justifyContent: "center",
          }}
          onClick={() => setShowRoleSelector(false)}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            style={{
              background: "var(--bg-card-solid)", border: "1px solid var(--border-accent)",
              borderRadius: 12, padding: 24, width: 340, boxShadow: "var(--shadow-lg)",
            }}
          >
            <h3 style={{ fontSize: 15, fontWeight: 700, marginBottom: 4 }}>Personalise your experience</h3>
            <p style={{ fontSize: 12, color: "var(--text-muted)", marginBottom: 16 }}>
              Select your role to get relevant suggested prompts.
            </p>
            {ROLE_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                onClick={() => { setRole(opt.value); setShowRoleSelector(false); }}
                style={{
                  width: "100%", textAlign: "left", padding: "10px 12px", marginBottom: 6,
                  background: role === opt.value ? "rgba(79,143,247,0.12)" : "rgba(255,255,255,0.03)",
                  border: `1px solid ${role === opt.value ? "rgba(79,143,247,0.3)" : "var(--border)"}`,
                  borderRadius: 8, cursor: "pointer", color: "var(--text-primary)",
                }}
              >
                <div style={{ fontSize: 13, fontWeight: 600 }}>{opt.label}</div>
                <div style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 2 }}>{opt.desc}</div>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Clear confirmation */}
      {showClearConfirm && (
        <div
          role="dialog"
          aria-modal="true"
          style={{
            position: "fixed", inset: 0, zIndex: 200,
            background: "rgba(0,0,0,0.6)", display: "flex", alignItems: "center", justifyContent: "center",
          }}
        >
          <div style={{
            background: "var(--bg-card-solid)", border: "1px solid var(--border-accent)",
            borderRadius: 12, padding: 24, width: 320, boxShadow: "var(--shadow-lg)",
          }}>
            <h3 style={{ fontSize: 15, fontWeight: 700, marginBottom: 8 }}>Clear conversation?</h3>
            <p style={{ fontSize: 13, color: "var(--text-muted)", marginBottom: 20 }}>
              This will remove all messages from this session.
            </p>
            <div style={{ display: "flex", gap: 10, justifyContent: "flex-end" }}>
              <button
                onClick={() => setShowClearConfirm(false)}
                style={{ padding: "7px 16px", fontSize: 12, background: "none", border: "1px solid var(--border)", borderRadius: 6, color: "var(--text-secondary)", cursor: "pointer" }}
              >
                Cancel
              </button>
              <button
                onClick={() => { clearHistory(); setShowClearConfirm(false); }}
                style={{ padding: "7px 16px", fontSize: 12, background: "rgba(248,113,113,0.12)", border: "1px solid rgba(248,113,113,0.3)", borderRadius: 6, color: "var(--accent-red)", cursor: "pointer" }}
              >
                Clear
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
