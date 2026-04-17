import { useApi } from "../hooks/useApi";

interface FeedItem {
  type: "enforcement" | "notice";
  title: string;
  subtitle: string;
  description: string;
  date: string;
  severity: "critical" | "warning" | "info";
  metric: string | null;
}

interface FeedData {
  items: FeedItem[];
}

const TYPE_CONFIG = {
  enforcement: { label: "ENF", bg: "rgba(239,68,68,0.12)", color: "#EF4444" },
  notice:      { label: "NTC", bg: "rgba(59,130,246,0.12)", color: "#3B82F6" },
};

const SEVERITY_CONFIG = {
  critical: { bg: "rgba(239,68,68,0.12)", color: "#EF4444" },
  warning:  { bg: "rgba(245,158,11,0.12)", color: "#F59E0B" },
  info:     { bg: "rgba(59,130,246,0.08)", color: "#3B82F6" },
};

function formatDate(dateStr: string): string {
  if (!dateStr) return "";
  try {
    const d = new Date(dateStr);
    if (isNaN(d.getTime())) return dateStr.slice(0, 10);
    return d.toLocaleDateString("en-AU", { day: "numeric", month: "short", year: "numeric" });
  } catch {
    return dateStr.slice(0, 10);
  }
}

export default function ActivityFeed() {
  const { data, loading } = useApi<FeedData>("/api/activity-feed");

  if (loading || !data) {
    return (
      <div className="card">
        <div className="card-header">
          <h2>Recent Activity</h2>
        </div>
        <div style={{ display: "flex", gap: 12, overflowX: "auto", padding: "4px 0 8px" }}>
          {[0, 1, 2, 3, 4].map((i) => (
            <div key={i} className="skeleton-block" style={{ minWidth: 220, height: 90, borderRadius: 10, flexShrink: 0 }} />
          ))}
        </div>
      </div>
    );
  }

  const items = data.items ?? [];

  return (
    <div className="card">
      <div className="card-header">
        <h2>Recent Activity</h2>
        <span className="badge" style={{ background: "rgba(59,130,246,0.15)", color: "#3B82F6" }}>
          {items.length} events
        </span>
      </div>

      {items.length === 0 ? (
        <p style={{ color: "var(--text-muted)", padding: "8px 0", fontSize: 13 }}>No recent activity.</p>
      ) : (
        <div className="activity-feed-scroll">
          {items.map((item, i) => {
            const typeConf = TYPE_CONFIG[item.type];
            const sevConf = SEVERITY_CONFIG[item.severity];
            return (
              <div key={i} className="activity-feed-item">
                <div className="activity-feed-item-header">
                  <span style={{
                    fontSize: 10, fontWeight: 700, padding: "2px 6px", borderRadius: 4,
                    background: typeConf.bg, color: typeConf.color, flexShrink: 0,
                  }}>
                    {typeConf.label}
                  </span>
                  {item.metric && (
                    <span style={{
                      fontSize: 11, fontWeight: 700,
                      background: sevConf.bg, color: sevConf.color,
                      padding: "1px 6px", borderRadius: 4, flexShrink: 0,
                    }}>
                      {item.metric}
                    </span>
                  )}
                </div>

                <div style={{ fontSize: 12, fontWeight: 600, color: "var(--text-primary)", margin: "4px 0 2px", lineHeight: 1.3 }}>
                  {item.title}
                </div>

                {item.subtitle && (
                  <div style={{ fontSize: 11, color: "#3B82F6", fontWeight: 500, marginBottom: 3 }}>
                    {item.subtitle}
                  </div>
                )}

                {item.description && (
                  <div style={{ fontSize: 11, color: "var(--text-secondary)", lineHeight: 1.4 }}>
                    {item.description}
                  </div>
                )}

                <div style={{ fontSize: 10, color: "var(--text-muted)", marginTop: 6 }}>
                  {formatDate(item.date)}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
