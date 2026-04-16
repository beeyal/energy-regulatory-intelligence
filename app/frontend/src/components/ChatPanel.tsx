import { useState, useRef, useEffect, useCallback } from "react";
import MarkdownRenderer from "./MarkdownRenderer";

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
        "Welcome to the Regulatory Intelligence Command Center. I can help you explore Australian energy regulatory data including CER emissions, AEMO market notices, AER enforcement actions, and regulatory obligations.\n\nTry one of the prompts below or ask me anything about energy compliance.",
    },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const messagesEnd = useRef<HTMLDivElement>(null);
  // Accumulated content ref — avoids per-token React state updates
  const contentRef = useRef("");
  const rafRef = useRef<number>(0);

  useEffect(() => {
    messagesEnd.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const updateStreamingMessage = useCallback((content: string, done: boolean) => {
    setMessages((prev) => {
      const updated = [...prev];
      const last = updated[updated.length - 1];
      if (last?.role === "assistant") {
        updated[updated.length - 1] = { ...last, content, streaming: !done };
      }
      return updated;
    });
  }, []);

  const send = async (text: string) => {
    if (!text.trim() || loading) return;

    const userMsg: Message = { role: "user", content: text.trim() };
    setMessages((prev) => [
      ...prev,
      userMsg,
      { role: "assistant", content: "", streaming: true },
    ]);
    setInput("");
    setLoading(true);
    contentRef.current = "";

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
      let currentEventType = "message";
      let pendingUpdate = false;

      const scheduleUpdate = () => {
        if (!pendingUpdate) {
          pendingUpdate = true;
          rafRef.current = requestAnimationFrame(() => {
            updateStreamingMessage(contentRef.current, false);
            pendingUpdate = false;
          });
        }
      };

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        // Split on newlines, handling both \r\n and \n
        const lines = buffer.replace(/\r\n/g, "\n").split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed) {
            // Empty line = end of SSE event, reset type
            currentEventType = "message";
            continue;
          }

          if (trimmed.startsWith("event:")) {
            currentEventType = trimmed.slice(6).trim();
            continue;
          }

          if (trimmed.startsWith("data:")) {
            // Skip non-text events (intent, done, error)
            if (currentEventType !== "message") continue;

            // Extract payload: strip "data:" and the optional single space per SSE spec
            let raw = trimmed.slice(5);
            if (raw.startsWith(" ")) raw = raw.slice(1);
            if (!raw) continue;

            // Server JSON-encodes tokens to preserve newlines in SSE transport
            try {
              const token = JSON.parse(raw);
              if (token) {
                contentRef.current += token;
                scheduleUpdate();
              }
            } catch {
              // If not valid JSON, use raw (fallback)
              contentRef.current += raw;
              scheduleUpdate();
            }
          }
        }
      }

      // Cancel any pending RAF and do final update with markdown rendering
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
      updateStreamingMessage(contentRef.current, true);

    } catch {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
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
    }
  };

  return (
    <div className="chat-panel">
      <div className="chat-header">AI Compliance Assistant</div>

      <div className="chat-messages">
        {messages.map((msg, i) => (
          <div key={i} className={`chat-msg ${msg.role}`}>
            {msg.role === "assistant" ? (
              msg.streaming ? (
                <>
                  <span className="streaming-text">{msg.content}</span>
                  <span className="typing-indicator">&#9608;</span>
                </>
              ) : (
                <MarkdownRenderer content={msg.content} />
              )
            ) : (
              msg.content
            )}
          </div>
        ))}
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
