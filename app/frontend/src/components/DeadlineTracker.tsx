import { useApi } from "../hooks/useApi";
import { useRegion } from "../context/RegionContext";
import { formatCurrency } from "../utils/currency";

interface Deadline {
  obligation_name: string;
  regulatory_body: string;
  category: string;
  risk_rating: string;
  penalty_max_aud: number;
  frequency: string;
  days_to_deadline: number;
  risk_score?: number;
}

interface DeadlineData {
  deadlines: Deadline[];
  overdue_count: number;
}

function urgencyColor(days: number): string {
  if (days < 0)  return "#ef4444";   // overdue — red
  if (days <= 7) return "#ef4444";   // critical — red
  if (days <= 14) return "#f87171";  // urgent — light red
  if (days <= 30) return "#f59e0b";  // warning — amber
  if (days <= 60) return "#3b82f6";  // upcoming — blue
  return "#10b981";                  // scheduled — green
}

function urgencyBg(days: number): string {
  if (days < 0)   return "rgba(239,68,68,0.15)";
  if (days <= 7)  return "rgba(239,68,68,0.12)";
  if (days <= 14) return "rgba(248,113,113,0.1)";
  if (days <= 30) return "rgba(245,158,11,0.1)";
  if (days <= 60) return "rgba(59,130,246,0.1)";
  return "rgba(16,185,129,0.1)";
}

function urgencyLabel(days: number): string {
  if (days < 0)   return "OVERDUE";
  if (days === 0) return "DUE TODAY";
  if (days <= 7)  return "CRITICAL";
  if (days <= 14) return "URGENT";
  if (days <= 30) return "DUE SOON";
  if (days <= 60) return "UPCOMING";
  return "SCHEDULED";
}

function riskDot(rating: string): string {
  return { Critical: "#ef4444", High: "#f59e0b", Medium: "#3b82f6", Low: "#10b981" }[rating] ?? "#6b7280";
}

function RiskScoreBar({ score }: { score: number }) {
  const color = score >= 70 ? "#ef4444" : score >= 45 ? "#f59e0b" : "#10b981";
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 5 }}>
      <div style={{ width: 36, height: 3, background: "var(--border)", borderRadius: 2, overflow: "hidden" }}>
        <div style={{ height: "100%", width: `${score}%`, background: color, borderRadius: 2 }} />
      </div>
      <span style={{ fontSize: 10, fontWeight: 700, color, minWidth: 20 }}>{score}</span>
    </div>
  );
}

/** Predictive risk: flag items 15-90 days out that have high risk scores.
 *  Returns "AT RISK" when urgency + risk_score signals a likely breach. */
function predictiveRisk(days: number, riskScore: number | undefined): boolean {
  if (riskScore === undefined) return false;
  if (days < 0 || days <= 14) return false; // already flagged by urgency
  if (days > 90) return false;
  // AT RISK if high risk score in the upcoming window
  if (days <= 30 && riskScore >= 55) return true;
  if (days <= 60 && riskScore >= 70) return true;
  if (days <= 90 && riskScore >= 80) return true;
  return false;
}

export default function DeadlineTracker() {
  const { activeMarket } = useRegion();
  const currency = activeMarket?.currency ?? "AUD";
  const { data, loading } = useApi<DeadlineData>("/api/upcoming-deadlines");

  if (loading || !data) {
    return (
      <div className="chart-card" style={{ minHeight: 260 }}>
        <div className="chart-card-header">
          <h3>Upcoming Deadlines</h3>
          <span className="chart-subtitle">Next 90 days</span>
        </div>
        {[0, 1, 2, 3].map((i) => (
          <div key={i} className="skeleton-line" style={{ height: 52, marginBottom: 6, borderRadius: 8 }} />
        ))}
      </div>
    );
  }

  const deadlines = data.deadlines ?? [];
  const overdueCount = data.overdue_count ?? 0;
  const urgentCount = deadlines.filter((d) => d.days_to_deadline >= 0 && d.days_to_deadline <= 14).length;
  const atRiskCount = deadlines.filter((d) => predictiveRisk(d.days_to_deadline, d.risk_score)).length;

  return (
    <div className="chart-card">
      <div className="chart-card-header" style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
        <div>
          <h3>Obligation Deadlines</h3>
          <span className="chart-subtitle">{deadlines.length} obligations — overdue + next 90 days</span>
        </div>
        <div style={{ display: "flex", gap: 6 }}>
          {overdueCount > 0 && (
            <span style={{
              background: "rgba(239,68,68,0.18)", color: "#ef4444",
              fontSize: 11, fontWeight: 700, padding: "2px 8px", borderRadius: 4,
              border: "1px solid rgba(239,68,68,0.3)",
              animation: "pulse 2s infinite",
            }}>
              {overdueCount} OVERDUE
            </span>
          )}
          {urgentCount > 0 && (
            <span style={{
              background: "rgba(245,158,11,0.15)", color: "#f59e0b",
              fontSize: 11, fontWeight: 700, padding: "2px 8px", borderRadius: 4,
            }}>
              {urgentCount} URGENT
            </span>
          )}
          {atRiskCount > 0 && (
            <span style={{
              background: "rgba(168,85,247,0.15)", color: "#a855f7",
              fontSize: 11, fontWeight: 700, padding: "2px 8px", borderRadius: 4,
            }}>
              {atRiskCount} AT RISK
            </span>
          )}
        </div>
      </div>

      {/* Overdue section */}
      {overdueCount > 0 && (
        <div style={{
          background: "rgba(239,68,68,0.06)",
          border: "1px solid rgba(239,68,68,0.2)",
          borderRadius: 6,
          padding: "6px 10px",
          marginBottom: 10,
          fontSize: 11,
          color: "#ef4444",
          fontWeight: 600,
          display: "flex",
          alignItems: "center",
          gap: 6,
        }}>
          <span style={{ fontSize: 14 }}>⚠</span>
          {overdueCount} obligation{overdueCount !== 1 ? "s" : ""} past deadline — immediate action required
        </div>
      )}

      <div className="deadline-list-scroll">
        <div className="deadline-list">
          {deadlines.map((d, i) => {
            const isOverdue = d.days_to_deadline < 0;
            const isAtRisk = predictiveRisk(d.days_to_deadline, d.risk_score);
            const pct = isOverdue
              ? 100
              : Math.max(4, Math.round((1 - d.days_to_deadline / 90) * 100));
            const borderColor = isAtRisk && !isOverdue ? "#a855f7" : urgencyColor(d.days_to_deadline);

            return (
              <div
                key={i}
                className="deadline-item"
                style={{
                  borderLeft: `3px solid ${borderColor}`,
                  background: isOverdue ? "rgba(239,68,68,0.04)" : isAtRisk ? "rgba(168,85,247,0.03)" : undefined,
                }}
              >
                <div className="deadline-item-top">
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{
                      fontSize: 12, fontWeight: 600, color: "var(--text-primary)",
                      overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
                    }}>
                      <span style={{
                        display: "inline-block", width: 7, height: 7, borderRadius: "50%",
                        background: riskDot(d.risk_rating), marginRight: 6, flexShrink: 0,
                      }} />
                      {d.obligation_name}
                    </div>
                    <div style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 1 }}>
                      {d.regulatory_body} · {d.category} · {d.frequency}
                    </div>
                  </div>
                  <div style={{ textAlign: "right", flexShrink: 0, marginLeft: 12 }}>
                    <div style={{
                      fontSize: isOverdue ? 14 : 18,
                      fontWeight: 800,
                      color: urgencyColor(d.days_to_deadline),
                      lineHeight: 1,
                    }}>
                      {isOverdue ? `${Math.abs(d.days_to_deadline)}d ago` : d.days_to_deadline}
                    </div>
                    {!isOverdue && <div style={{ fontSize: 10, color: "var(--text-muted)" }}>days</div>}
                  </div>
                </div>

                <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 6 }}>
                  <div style={{ flex: 1, height: 4, background: "var(--border)", borderRadius: 2, overflow: "hidden" }}>
                    <div style={{
                      height: "100%", width: `${pct}%`,
                      background: urgencyColor(d.days_to_deadline),
                      borderRadius: 2,
                      ...(isOverdue ? { backgroundImage: "repeating-linear-gradient(45deg, transparent, transparent 3px, rgba(0,0,0,0.1) 3px, rgba(0,0,0,0.1) 6px)" } : {}),
                    }} />
                  </div>
                  <span style={{
                    fontSize: 10, fontWeight: 700, color: urgencyColor(d.days_to_deadline),
                    background: urgencyBg(d.days_to_deadline),
                    padding: "1px 5px", borderRadius: 3, flexShrink: 0,
                  }}>
                    {urgencyLabel(d.days_to_deadline)}
                  </span>
                  {isAtRisk && (
                    <span style={{
                      fontSize: 10, fontWeight: 700, color: "#a855f7",
                      background: "rgba(168,85,247,0.12)",
                      padding: "1px 5px", borderRadius: 3, flexShrink: 0,
                    }}>
                      ⚡ AT RISK
                    </span>
                  )}
                  {d.risk_score !== undefined && <RiskScoreBar score={d.risk_score} />}
                  <span style={{ fontSize: 10, color: "var(--text-muted)", flexShrink: 0 }}>
                    max {formatCurrency(d.penalty_max_aud, currency)}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
