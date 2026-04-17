import { useApi } from "../hooks/useApi";

interface Deadline {
  obligation_name: string;
  regulatory_body: string;
  category: string;
  risk_rating: string;
  penalty_max_aud: number;
  frequency: string;
  days_to_deadline: number;
}

interface DeadlineData {
  deadlines: Deadline[];
}

function urgencyColor(days: number): string {
  if (days <= 14) return "#EF4444";
  if (days <= 30) return "#F59E0B";
  if (days <= 60) return "#3B82F6";
  return "#10B981";
}

function urgencyBg(days: number): string {
  if (days <= 14) return "rgba(239,68,68,0.1)";
  if (days <= 30) return "rgba(245,158,11,0.1)";
  if (days <= 60) return "rgba(59,130,246,0.1)";
  return "rgba(16,185,129,0.1)";
}

function urgencyLabel(days: number): string {
  if (days <= 14) return "URGENT";
  if (days <= 30) return "DUE SOON";
  if (days <= 60) return "UPCOMING";
  return "SCHEDULED";
}

function formatPenalty(val: number): string {
  if (val >= 1e6) return `$${(val / 1e6).toFixed(1)}M`;
  if (val >= 1e3) return `$${(val / 1e3).toFixed(0)}K`;
  return `$${val}`;
}

function riskDot(rating: string): string {
  return { Critical: "#EF4444", High: "#F59E0B", Medium: "#3B82F6", Low: "#10B981" }[rating] ?? "#6B7280";
}

export default function DeadlineTracker() {
  const { data, loading } = useApi<DeadlineData>("/api/upcoming-deadlines");

  if (loading || !data) {
    return (
      <div className="chart-card" style={{ minHeight: 260 }}>
        <div className="chart-card-header">
          <h3>Upcoming Deadlines</h3>
          <span className="chart-subtitle">Next 90 days</span>
        </div>
        {[0, 1, 2, 3].map((i) => (
          <div key={i} className="skeleton-line" style={{ height: 44, marginBottom: 6, borderRadius: 8 }} />
        ))}
      </div>
    );
  }

  const deadlines = data.deadlines ?? [];
  const urgent = deadlines.filter((d) => d.days_to_deadline <= 14).length;

  return (
    <div className="chart-card">
      <div className="chart-card-header" style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
        <div>
          <h3>Upcoming Deadlines</h3>
          <span className="chart-subtitle">Next 90 days — {deadlines.length} obligations</span>
        </div>
        {urgent > 0 && (
          <span style={{
            background: "rgba(239,68,68,0.15)", color: "#EF4444",
            fontSize: 11, fontWeight: 700, padding: "2px 8px", borderRadius: 4,
          }}>
            {urgent} URGENT
          </span>
        )}
      </div>

      <div className="deadline-list">
        {deadlines.map((d, i) => {
          const pct = Math.max(4, Math.round((1 - d.days_to_deadline / 90) * 100));
          return (
            <div key={i} className="deadline-item" style={{ borderLeft: `3px solid ${urgencyColor(d.days_to_deadline)}` }}>
              <div className="deadline-item-top">
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 12, fontWeight: 600, color: "var(--text-primary)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    <span style={{
                      display: "inline-block", width: 8, height: 8, borderRadius: "50%",
                      background: riskDot(d.risk_rating), marginRight: 6, flexShrink: 0,
                    }} />
                    {d.obligation_name}
                  </div>
                  <div style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 1 }}>
                    {d.regulatory_body} · {d.category} · {d.frequency}
                  </div>
                </div>
                <div style={{ textAlign: "right", flexShrink: 0, marginLeft: 12 }}>
                  <div style={{ fontSize: 18, fontWeight: 700, color: urgencyColor(d.days_to_deadline), lineHeight: 1 }}>
                    {d.days_to_deadline}
                  </div>
                  <div style={{ fontSize: 10, color: "var(--text-muted)" }}>days</div>
                </div>
              </div>

              <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 6 }}>
                <div style={{ flex: 1, height: 4, background: "var(--border)", borderRadius: 2, overflow: "hidden" }}>
                  <div style={{
                    height: "100%", width: `${pct}%`,
                    background: urgencyColor(d.days_to_deadline),
                    borderRadius: 2, transition: "width 0.3s ease",
                  }} />
                </div>
                <span style={{
                  fontSize: 10, fontWeight: 600, color: urgencyColor(d.days_to_deadline),
                  background: urgencyBg(d.days_to_deadline),
                  padding: "1px 5px", borderRadius: 3, flexShrink: 0,
                }}>
                  {urgencyLabel(d.days_to_deadline)}
                </span>
                <span style={{ fontSize: 10, color: "var(--text-muted)", flexShrink: 0 }}>
                  max {formatPenalty(d.penalty_max_aud)}
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
