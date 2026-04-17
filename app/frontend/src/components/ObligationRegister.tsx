import { useState } from "react";
import { useApi } from "../hooks/useApi";
import { useRegion } from "../context/RegionContext";
import { LoadingPage } from "./LoadingSkeleton";
import EmptyState from "./EmptyState";
import ErrorState from "./ErrorState";
import { downloadCsv } from "../utils/csv";
import { formatCurrencyFull } from "../utils/currency";

interface ObligationsData {
  records: Record<string, string>[];
  body_distribution: { regulatory_body: string; count: string }[];
}

const BODIES = ["All", "AEMO", "AER", "CER", "ESV"];
const CATEGORIES = ["All", "Market", "Consumer", "Safety", "Environment", "Technical", "Financial"];
const RISK_LEVELS = ["All", "Critical", "High", "Medium", "Low"];

function riskClass(risk: string): string {
  switch ((risk || "").toLowerCase()) {
    case "critical": return "severity-critical";
    case "high": return "severity-high";
    case "medium": return "severity-medium";
    case "low": return "severity-low";
    default: return "severity-info";
  }
}

export default function ObligationRegister() {
  const { activeMarket } = useRegion();
  const currency = activeMarket?.currency ?? "AUD";
  const [body, setBody] = useState("");
  const [category, setCategory] = useState("");
  const [risk, setRisk] = useState("");
  const [search, setSearch] = useState("");
  const [expanded, setExpanded] = useState<string | null>(null);

  const params: Record<string, string> = {};
  if (body) params.regulatory_body = body;
  if (category) params.category = category;
  if (risk) params.risk_rating = risk;
  if (search) params.search = search;

  const { data, loading, error, refetch } = useApi<ObligationsData>("/api/obligations", params);

  if (loading) return <LoadingPage />;
  if (error) return <div className="card"><ErrorState message={`Failed to load obligations: ${error}`} onRetry={refetch} /></div>;

  return (
    <div>
      <div className="stats-row">
        {data?.body_distribution?.map((bd) => (
          <div className="stat-card" key={bd.regulatory_body}>
            <div className="label">{bd.regulatory_body}</div>
            <div className="value blue">{bd.count}</div>
          </div>
        ))}
      </div>

      <div className="filters">
        <input
          className="search-input"
          placeholder="Search obligations, legislation..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        {BODIES.map((b) => (
          <button
            key={b}
            className={`filter-btn ${(b === "All" ? !body : body === b) ? "active" : ""}`}
            onClick={() => setBody(b === "All" ? "" : b)}
          >
            {b}
          </button>
        ))}
      </div>
      <div className="filters">
        {CATEGORIES.map((c) => (
          <button
            key={c}
            className={`filter-btn ${(c === "All" ? !category : category === c) ? "active" : ""}`}
            onClick={() => setCategory(c === "All" ? "" : c)}
          >
            {c}
          </button>
        ))}
        <div style={{ width: 1, background: "var(--border)", margin: "0 4px" }} />
        {RISK_LEVELS.map((r) => (
          <button
            key={r}
            className={`filter-btn ${(r === "All" ? !risk : risk === r) ? "active" : ""}`}
            onClick={() => setRisk(r === "All" ? "" : r)}
          >
            {r}
          </button>
        ))}
      </div>

      <div className="card">
        <div className="card-header">
          <h2>Regulatory Obligation Register</h2>
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <span className="badge" style={{ background: "rgba(52,211,153,0.15)", color: "var(--accent-green)" }}>
              {data?.records?.length || 0} Obligations
            </span>
            <button
              onClick={() => downloadCsv(data?.records ?? [], `obligations-${new Date().toISOString().slice(0, 10)}.csv`)}
              aria-label="Download obligations data as CSV"
              style={{ fontSize: 11, padding: "3px 10px", background: "rgba(79,143,247,0.1)", color: "var(--accent-blue)", border: "1px solid rgba(79,143,247,0.2)", borderRadius: 5, cursor: "pointer" }}
            >
              ↓ CSV
            </button>
          </div>
        </div>
        <div style={{ overflowX: "auto" }}>
          <table className="data-table">
            <thead>
              <tr>
                <th>Obligation</th>
                <th>Body</th>
                <th>Category</th>
                <th>Frequency</th>
                <th>Risk</th>
                <th>Max Penalty</th>
                <th>Legislation</th>
              </tr>
            </thead>
            <tbody>
              {data?.records?.map((r) => (
                <>
                  <tr
                    key={r.obligation_id}
                    onClick={() => setExpanded(expanded === r.obligation_id ? null : r.obligation_id)}
                    style={{ cursor: "pointer" }}
                  >
                    <td style={{ fontWeight: 500 }}>{r.obligation_name}</td>
                    <td>{r.regulatory_body}</td>
                    <td>{r.category}</td>
                    <td>{r.frequency}</td>
                    <td><span className={`severity ${riskClass(r.risk_rating)}`}>{r.risk_rating}</span></td>
                    <td className="number currency">{formatCurrencyFull(r.penalty_max_aud, currency)}</td>
                    <td style={{ fontSize: 11, color: "var(--text-muted)" }}>{r.source_legislation}</td>
                  </tr>
                  {expanded === r.obligation_id && (
                    <tr key={`${r.obligation_id}-detail`}>
                      <td colSpan={7} style={{ background: "var(--bg-secondary)", padding: 16 }}>
                        <div style={{ fontSize: 13, marginBottom: 8 }}>
                          <strong>Description:</strong> {r.description}
                        </div>
                        <div style={{ fontSize: 12, color: "var(--text-secondary)" }}>
                          <strong>Key Requirements:</strong> {r.key_requirements}
                        </div>
                      </td>
                    </tr>
                  )}
                </>
              ))}
            </tbody>
          </table>
        </div>
        {(!data?.records || data.records.length === 0) && (
          <EmptyState
            icon="📋"
            message="No obligations match your filters"
            detail="Try adjusting the body, category, or risk level filters."
            actionLabel="Clear filters"
            onAction={() => setSearch("")}
          />
        )}
      </div>
    </div>
  );
}
