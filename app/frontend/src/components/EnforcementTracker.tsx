import { useState } from "react";
import { useApi } from "../hooks/useApi";
import { LoadingPage } from "./LoadingSkeleton";

interface EnforcementData {
  records: Record<string, string>[];
  summary: Record<string, string>;
}

const ACTION_TYPES = ["All", "Infringement Notice", "Court Proceedings", "Enforceable Undertaking", "Compliance Audit"];

function formatCurrency(val: string | null): string {
  if (!val || val === "0" || val === "None") return "—";
  const n = parseFloat(val);
  if (isNaN(n) || n === 0) return "—";
  return `$${n.toLocaleString("en-AU")}`;
}

function formatDate(d: string | null): string {
  if (!d) return "—";
  try { return new Date(d).toLocaleDateString("en-AU", { day: "2-digit", month: "short", year: "numeric" }); }
  catch { return d; }
}

export default function EnforcementTracker() {
  const [actionType, setActionType] = useState("");
  const [sortBy, setSortBy] = useState("penalty_aud");

  const params: Record<string, string> = { sort_by: sortBy };
  if (actionType) params.action_type = actionType;

  const { data, loading } = useApi<EnforcementData>("/api/enforcement", params);

  if (loading) return <LoadingPage />;

  const summary = data?.summary || {};

  return (
    <div>
      <div className="stats-row">
        <div className="stat-card">
          <div className="label">Total Actions</div>
          <div className="value red">{summary.total_actions || 0}</div>
        </div>
        <div className="stat-card">
          <div className="label">Total Penalties</div>
          <div className="value amber">{formatCurrency(summary.total_penalties)}</div>
        </div>
        <div className="stat-card">
          <div className="label">Companies Affected</div>
          <div className="value blue">{summary.companies_affected || 0}</div>
        </div>
        <div className="stat-card">
          <div className="label">Largest Fine</div>
          <div className="value red">{formatCurrency(summary.max_penalty)}</div>
        </div>
      </div>

      <div className="filters">
        {ACTION_TYPES.map((t) => (
          <button
            key={t}
            className={`filter-btn ${(t === "All" ? !actionType : actionType === t) ? "active" : ""}`}
            onClick={() => setActionType(t === "All" ? "" : t)}
          >
            {t}
          </button>
        ))}
        <div style={{ width: 1, background: "var(--border)", margin: "0 4px" }} />
        <button
          className={`filter-btn ${sortBy === "penalty_aud" ? "active" : ""}`}
          onClick={() => setSortBy("penalty_aud")}
        >
          Sort: Penalty
        </button>
        <button
          className={`filter-btn ${sortBy === "action_date" ? "active" : ""}`}
          onClick={() => setSortBy("action_date")}
        >
          Sort: Date
        </button>
      </div>

      <div className="card">
        <div className="card-header">
          <h2>AER Enforcement Actions</h2>
          <span className="badge" style={{ background: "rgba(239,68,68,0.15)", color: "var(--accent-red)" }}>
            Real AER Data
          </span>
        </div>
        <div style={{ overflowX: "auto" }}>
          <table className="data-table">
            <thead>
              <tr>
                <th>Company</th>
                <th>Date</th>
                <th>Action Type</th>
                <th>Breach</th>
                <th>Description</th>
                <th>Penalty</th>
                <th>Outcome</th>
                <th>Reference</th>
              </tr>
            </thead>
            <tbody>
              {data?.records?.map((r, i) => (
                <tr key={i}>
                  <td style={{ fontWeight: 500, whiteSpace: "nowrap" }}>{r.company_name}</td>
                  <td style={{ whiteSpace: "nowrap" }}>{formatDate(r.action_date)}</td>
                  <td>
                    <span className={`severity ${
                      r.action_type === "Court Proceedings" ? "severity-critical" :
                      r.action_type === "Infringement Notice" ? "severity-warning" :
                      "severity-info"
                    }`}>
                      {r.action_type}
                    </span>
                  </td>
                  <td>{r.breach_type}</td>
                  <td className="truncate" title={r.breach_description}>{r.breach_description}</td>
                  <td className="number currency">{formatCurrency(r.penalty_aud)}</td>
                  <td>{r.outcome}</td>
                  <td style={{ fontSize: 11, color: "var(--text-muted)" }}>{r.regulatory_reference}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
