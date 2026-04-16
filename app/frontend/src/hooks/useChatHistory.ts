import { useState, useEffect } from "react";

export interface StoredMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: string;
}

const STORAGE_KEY = "compliance_chat_history";
const MAX_MESSAGES = 50;

export function useChatHistory(initialMessage: StoredMessage) {
  const [messages, setMessages] = useState<StoredMessage[]>(() => {
    try {
      const stored = sessionStorage.getItem(STORAGE_KEY);
      if (stored) {
        const parsed: StoredMessage[] = JSON.parse(stored);
        if (parsed.length > 0) return parsed;
      }
    } catch { /* ignore */ }
    return [initialMessage];
  });

  useEffect(() => {
    try {
      const toStore = messages.slice(-MAX_MESSAGES);
      sessionStorage.setItem(STORAGE_KEY, JSON.stringify(toStore));
    } catch { /* ignore quota errors */ }
  }, [messages]);

  const addMessage = (msg: Omit<StoredMessage, "id" | "timestamp">) => {
    const full: StoredMessage = {
      ...msg,
      id: `${Date.now()}-${Math.random().toString(36).slice(2)}`,
      timestamp: new Date().toISOString(),
    };
    setMessages((prev) => [...prev.slice(-(MAX_MESSAGES - 1)), full]);
    return full;
  };

  const updateLast = (content: string) => {
    setMessages((prev) => {
      const updated = [...prev];
      updated[updated.length - 1] = { ...updated[updated.length - 1], content };
      return updated;
    });
  };

  const clearHistory = () => {
    sessionStorage.removeItem(STORAGE_KEY);
    setMessages([initialMessage]);
  };

  const replaceWelcome = (content: string) => {
    setMessages((prev) => {
      const welcome: StoredMessage = {
        id: "welcome",
        role: "assistant",
        content,
        timestamp: new Date().toISOString(),
      };
      // Keep welcome as first message, preserve conversation that follows
      if (prev.length <= 1) return [welcome];
      return [welcome, ...prev.slice(1)];
    });
  };

  return { messages, addMessage, updateLast, clearHistory, replaceWelcome };
}
