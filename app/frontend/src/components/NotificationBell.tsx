import { useState, useEffect, useRef } from "react";
import { useRegion } from "../context/RegionContext";

interface Alert {
  type: "overdue" | "enforcement" | "risk";
  severity: "critical" | "high" | "warning";
  title: string;
  body: string;
  action: string;
  ts: string;
}

interface NotificationData {
  alerts: Alert[];
  unread: number;
}

const SEV_COLOR: Record<string, string> = {
  critical: "#ef4444",
  high: "#f59e0b",
  warning: "#3b82f6",
};

const SEV_ICON: Record<string, string> = {
  critical: "🚨",
  high: "⚠",
  warning: "📋",
};

export default function NotificationBell() {
  const { market } = useRegion();
  const [open, setOpen] = useState(false);
  const [data, setData] = useState<NotificationData | null>(null);
  const [dismissed, setDismissed] = useState<Set<number>>(new Set());
  const [teamsSending, setTeamsSending] = useState(false);
  const [teamsStatus, setTeamsStatus] = useState<"idle" | "sent" | "skipped" | "error">("idle");
  const panelRef = useRef<HTMLDivElement>(null);

  async function sendToTeams() {
    setTeamsSending(true);
    try {
      const res = await fetch(`/api/alerts/send-teams?market=${market}`, { method: "POST" });
      const json = await res.json();
      setTeamsStatus(json.status === "sent" ? "sent" : json.status === "skipped" ? "skipped" : "error");
    } catch {
      setTeamsStatus("error");
    } finally {
      setTeamsSending(false);
      setTimeout(() => setTeamsStatus("idle"), 4000);
    }
  }

  useEffect(() => {
    fetch(`/api/notifications?market=${market}`)
      .then((r) => r.ok ? r.json() : Promise.reject())
      .then((d) => setData(d))
      .catch(() => {});
  }, [market]);

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (panelRef.current && !panelRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    if (open) document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [open]);

  const alerts = data?.alerts ?? [];
  const visible = alerts.filter((_, i) => !dismissed.has(i));
  const unread = visible.length;

  return (
    <div ref={panelRef} style={{ position: "relative" }}>
      <button
        onClick={() => setOpen((v) => !v)}
        aria-label="Notifications"
        style={{
          position: "relative",
          padding: "6px 10px",
          background: open ? "rgba(239,68,68,0.12)" : "var(--bg-panel)",
          border: "1px solid var(--border)",
          borderRadius: 8,
          cursor: "pointer",
          color: "var(--text-primary)",
          fontSize: 16,
          lineHeight: 1,
          display: "flex",
          alignItems: "center",
          gap: 5,
        }}
      >
        🔔
        {unread > 0 && (
          <span style={{
            position: "absolute", top: -4, right: -4,
            background: "#ef4444", color: "#fff",
            fontSize: 10, fontWeight: 800,
            padding: "1px 4px", borderRadius: 8,
            minWidth: 16, textAlign: "center",
            lineHeight: 1.4,
          }}>
            {unread}
          </span>
        )}
      </button>

      {open && (
        <div style={{
          position: "absolute", top: "calc(100% + 8px)", right: 0, zIndex: 200,
          width: 360, maxHeight: 480, overflowY: "auto",
          background: "var(--bg-card)", border: "1px solid var(--border)",
          borderRadius: 12, boxShadow: "0 12px 40px rgba(0,0,0,0.3)",
        }}>
          <div style={{
            padding: "12px 16px", borderBottom: "1px solid var(--border)",
            display: "flex", justifyContent: "space-between", alignItems: "center",
          }}>
            <span style={{ fontSize: 14, fontWeight: 700 }}>Alerts ({unread})</span>
            <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
              <button
                onClick={sendToTeams}
                disabled={teamsSending}
                title="Send alerts to Microsoft Teams"
                style={{
                  fontSize: 10, fontWeight: 600,
                  padding: "2px 7px", borderRadius: 4,
                  border: "1px solid rgba(79,143,247,0.3)",
                  background: teamsStatus === "sent" ? "rgba(16,185,129,0.15)" : "rgba(79,143,247,0.08)",
                  color: teamsStatus === "sent" ? "#10b981" : teamsStatus === "error" ? "#ef4444" : "var(--accent-blue)",
                  cursor: teamsSending ? "not-allowed" : "pointer",
                  whiteSpace: "nowrap",
                }}
              >
                {teamsSending ? "…" : teamsStatus === "sent" ? "✓ Sent" : teamsStatus === "skipped" ? "⚠ Not configured" : teamsStatus === "error" ? "✕ Error" : "📣 Teams"}
              </button>
              {unread > 0 && (
                <button
                  onClick={() => setDismissed(new Set(alerts.map((_, i) => i)))}
                  style={{ fontSize: 11, color: "var(--text-muted)", background: "none", border: "none", cursor: "pointer" }}
                >
                  Dismiss all
                </button>
              )}
            </div>
          </div>

          {visible.length === 0 ? (
            <div style={{ padding: 24, textAlign: "center", color: "var(--text-muted)", fontSize: 13 }}>
              No active alerts
            </div>
          ) : (
            <div>
              {alerts.map((alert, i) => {
                if (dismissed.has(i)) return null;
                const color = SEV_COLOR[alert.severity] ?? "#6b7280";
                return (
                  <div key={i} style={{
                    padding: "12px 16px", borderBottom: "1px solid var(--border)",
                    borderLeft: `3px solid ${color}`,
                  }}>
                    <div style={{ display: "flex", gap: 8, alignItems: "flex-start" }}>
                      <span style={{ fontSize: 16, flexShrink: 0 }}>{SEV_ICON[alert.severity]}</span>
                      <div style={{ flex: 1 }}>
                        <div style={{ fontSize: 13, fontWeight: 600, color: "var(--text-primary)", lineHeight: 1.4 }}>
                          {alert.title}
                        </div>
                        <div style={{ fontSize: 12, color: "var(--text-secondary)", marginTop: 3, lineHeight: 1.5 }}>
                          {alert.body}
                        </div>
                        <div style={{ fontSize: 11, color: color, marginTop: 4, fontWeight: 500 }}>
                          → {alert.action}
                        </div>
                        {alert.ts && (
                          <div style={{ fontSize: 10, color: "var(--text-muted)", marginTop: 3 }}>{alert.ts}</div>
                        )}
                      </div>
                      <button
                        onClick={() => setDismissed((prev) => new Set([...prev, i]))}
                        style={{ fontSize: 12, color: "var(--text-muted)", background: "none", border: "none", cursor: "pointer", flexShrink: 0 }}
                        aria-label="Dismiss"
                      >
                        ✕
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
