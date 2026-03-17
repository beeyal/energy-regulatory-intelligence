import { useState, useRef, useEffect } from "react";
import { postChat } from "../hooks/useApi";

interface Message {
  role: "user" | "assistant";
  content: string;
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
  const messagesEnd = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEnd.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const send = async (text: string) => {
    if (!text.trim() || loading) return;

    const userMsg: Message = { role: "user", content: text.trim() };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setLoading(true);

    try {
      const result = await postChat(text.trim());
      setMessages((prev) => [...prev, { role: "assistant", content: result.response }]);
    } catch (e) {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: "Sorry, I encountered an error. Please try again." },
      ]);
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
            {msg.content}
          </div>
        ))}
        {loading && (
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
