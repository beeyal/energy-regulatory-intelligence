import { useState, useRef, useEffect } from "react";

interface Message {
  role: "user" | "assistant";
  content: string;
  streaming?: boolean;
}

const PROMPT_CHIPS = [
  "Who are the top 10 emitters in the electricity sector?",
  "Show me recent AEMO non-conformance notices",
  "Which companies have been fined the most by the AER?",
  "What are the key obligations under NER Chapter 7?",
];

export default function ChatPanel() {
  const [messages, setMessages] = useState<Message[]>([
    {
      role: "assistant",
      content:
        "Welcome to the Energy Compliance Intelligence Hub. I can help you explore Australian energy regulatory data including CER emissions, AEMO market notices, AER enforcement actions, and regulatory obligations.\n\nTry one of the prompts below or ask me anything about energy compliance.",
    },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [streaming, setStreaming] = useState(false);
  const messagesEnd = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEnd.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const send = async (text: string) => {
    if (!text.trim() || loading) return;

    const userMsg: Message = { role: "user", content: text.trim() };
    // Append user message and an empty assistant placeholder for streaming
    setMessages((prev) => [
      ...prev,
      userMsg,
      { role: "assistant", content: "", streaming: true },
    ]);
    setInput("");
    setLoading(true);
    setStreaming(true);

    try {
      const resp = await fetch("/api/chat/stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text.trim() }),
      });

      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);

      const reader = resp.body?.getReader();
      if (!reader) throw new Error("No response body");

      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        // Keep the last potentially incomplete line in the buffer
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (!line.trim()) continue;

          // SSE events: "event: <type>" or "data: <payload>"
          if (line.startsWith("event:")) {
            const eventType = line.slice(6).trim();
            if (eventType === "done") {
              // Stream complete — mark message as no longer streaming
              setMessages((prev) => {
                const updated = [...prev];
                const last = updated[updated.length - 1];
                if (last?.role === "assistant") {
                  updated[updated.length - 1] = { ...last, streaming: false };
                }
                return updated;
              });
            }
            // "intent" and "error" events are informational; we could use
            // them later but for now we just let data flow through.
            continue;
          }

          if (line.startsWith("data:")) {
            const payload = line.slice(5);
            // Empty data payload (e.g. from "done" event) — skip
            if (!payload) continue;

            // Append token to the last assistant message
            setMessages((prev) => {
              const updated = [...prev];
              const last = updated[updated.length - 1];
              if (last?.role === "assistant") {
                updated[updated.length - 1] = {
                  ...last,
                  content: last.content + payload,
                };
              }
              return updated;
            });
          }
        }
      }

      // Ensure streaming flag is cleared even if the "done" event was missed
      setMessages((prev) => {
        const updated = [...prev];
        const last = updated[updated.length - 1];
        if (last?.role === "assistant" && last.streaming) {
          updated[updated.length - 1] = { ...last, streaming: false };
        }
        return updated;
      });
    } catch (e) {
      // If streaming failed and the placeholder is still empty, replace it
      setMessages((prev) => {
        const updated = [...prev];
        const last = updated[updated.length - 1];
        if (last?.role === "assistant" && !last.content) {
          updated[updated.length - 1] = {
            role: "assistant",
            content: "Sorry, I encountered an error. Please try again.",
            streaming: false,
          };
        }
        return updated;
      });
    } finally {
      setLoading(false);
      setStreaming(false);
    }
  };

  return (
    <div className="chat-panel">
      <div className="chat-header">AI Compliance Assistant</div>

      <div className="chat-messages">
        {messages.map((msg, i) => (
          <div key={i} className={`chat-msg ${msg.role}`}>
            {msg.content}
            {msg.streaming && <span className="typing-indicator">&#9608;</span>}
          </div>
        ))}
        {loading && !streaming && (
          <div className="chat-msg assistant loading">Analysing compliance data...</div>
        )}
        <div ref={messagesEnd} />
      </div>

      <div className="prompt-chips">
        {PROMPT_CHIPS.map((chip, i) => (
          <button
            key={i}
            className="prompt-chip"
            onClick={() => send(chip)}
            disabled={loading}
          >
            {chip}
          </button>
        ))}
      </div>

      <div className="chat-input-area">
        <input
          className="chat-input"
          placeholder="Ask about emissions, notices, enforcement..."
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && send(input)}
          disabled={loading}
        />
        <button className="chat-send" onClick={() => send(input)} disabled={loading || !input.trim()}>
          Send
        </button>
      </div>
    </div>
  );
}
