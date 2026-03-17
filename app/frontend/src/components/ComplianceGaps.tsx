import { useApi } from "../hooks/useApi";

interface InsightsData {
  insights: Record<string, string>[];
  grouped: Record<string, Record<string, string>[]>;
}

function severityClass(s: string): string {
  switch ((s || "").toLowerCase()) {
    case "critical": return "severity-critical";
    case "warning": return "severity-warning";
    default: return "severity-info";
  }
}

function insightIcon(type: string): string {
  switch (type) {
    case "repeat_offender": return "!!";
    case "high_emitter": return "CO2";
    case "enforcement_trend": return "#";
    case "notice_spike": return "^";
    default: return "*";
  }
}

function insightLabel(type: string): string {
  switch (type) {
    case "repeat_offender": return "Repeat Offender";
    case "high_emitter": return "High Emitter";
    case "enforcement_trend": return "Enforcement Trend";
    case "notice_spike": return "Notice Spike";
    default: return type;
  }
}

export default function ComplianceGaps() {
  const { data, loading } = useApi<InsightsData>("/api/compliance-gaps");

  if (loading) return <div className="loading-spinner">Analysing compliance gaps...</div>;

  const grouped = data?.grouped || {};
  const categories = ["repeat_offender", "high_emitter", "enforcement_trend", "notice_spike"];

  return (
    <div>
      <div className="card alert">
        <div className="card-header">
          <h2>Compliance Intelligence Alerts</h2>
          <span className="badge" style={{ background: "rgba(245,158,11,0.2)", color: "var(--accent-amber)" }}>
            {data?.insights?.length || 0} Insights
          </span>
        </div>
        <p style={{ color: "var(--text-secondary)", fontSize: 13, marginBottom: 16 }}>
          Cross-referenced analysis of enforcement actions, emissions data, and market notices to surface compliance risks.
        </p>
      </div>

      {categories.map((cat) => {
        const items = grouped[cat];
        if (!items || items.length === 0) return null;

        return (
          <div className="card" key={cat}>
            <div className="card-header">
              <h2>
                <span style={{ marginRight: 8, fontFamily: "monospace", color: "var(--accent-amber)" }}>
                  [{insightIcon(cat)}]
                </span>
                {insightLabel(cat)}s
              </h2>
              <span className="badge" style={{ background: "rgba(245,158,11,0.15)", color: "var(--accent-amber)" }}>
                {items.length}
              </span>
            </div>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Entity</th>
                  <th>Detail</th>
                  <th>Period</th>
                  <th>Severity</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item, i) => (
                  <tr key={i}>
                    <td style={{ fontWeight: 500 }}>{item.entity_name}</td>
                    <td style={{ fontSize: 12 }}>{item.detail}</td>
                    <td>{item.period}</td>
                    <td>
                      <span className={`severity ${severityClass(item.severity)}`}>
                        {item.severity}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        );
      })}

      {(!data?.insights || data.insights.length === 0) && (
        <div className="empty-state">No compliance insights generated yet. Run data ingestion first.</div>
      )}
    </div>
  );
}
