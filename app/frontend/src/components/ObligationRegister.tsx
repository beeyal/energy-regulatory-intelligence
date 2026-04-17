import { useState, useEffect, useCallback } from "react";
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

export type AssignmentStatus = "Unassigned" | "Assigned" | "In Progress" | "Complete" | "Escalated";

export interface AuditEntry {
  timestamp: string;
  from_status: AssignmentStatus | "";
  to_status: AssignmentStatus;
  owner: string;
  note: string;
}

interface Assignment {
  owner: string;
  status: AssignmentStatus;
  due_date: string;
  notes: string;
  updated_at: string;
  history?: AuditEntry[];
}

type Assignments = Record<string, Assignment>;

const ASSIGNMENT_KEY = "obl_assignments_v1";

function loadAssignments(): Assignments {
  try {
    return JSON.parse(localStorage.getItem(ASSIGNMENT_KEY) || "{}");
  } catch {
    return {};
  }
}

function saveAssignments(a: Assignments): void {
  localStorage.setItem(ASSIGNMENT_KEY, JSON.stringify(a));
}

const STATUS_META: Record<AssignmentStatus, { color: string; bg: string }> = {
  Unassigned: { color: "#6b7280", bg: "rgba(107,114,128,0.12)" },
  Assigned:   { color: "#3b82f6", bg: "rgba(59,130,246,0.12)" },
  "In Progress": { color: "#f59e0b", bg: "rgba(245,158,11,0.12)" },
  Complete:   { color: "#10b981", bg: "rgba(16,185,129,0.12)" },
  Escalated:  { color: "#ef4444", bg: "rgba(239,68,68,0.12)" },
};

const STATUSES: AssignmentStatus[] = ["Unassigned", "Assigned", "In Progress", "Complete", "Escalated"];

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

function RiskScore({ score }: { score: number | string | undefined }) {
  const n = typeof score === "string" ? parseInt(score, 10) : (score ?? 0);
  if (!n) return <span style={{ color: "var(--text-muted)" }}>—</span>;
  const color = n >= 70 ? "#ef4444" : n >= 45 ? "#f59e0b" : "#10b981";
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 5 }}>
      <div style={{
        width: 40, height: 5, background: "var(--border)",
        borderRadius: 3, overflow: "hidden", flexShrink: 0,
      }}>
        <div style={{ height: "100%", width: `${n}%`, background: color, borderRadius: 3 }} />
      </div>
      <span style={{ fontSize: 11, fontWeight: 700, color, minWidth: 24 }}>{n}</span>
    </div>
  );
}

function AssignmentBadge({ a }: { a: Assignment | undefined }) {
  if (!a || a.status === "Unassigned") {
    return (
      <span style={{ fontSize: 11, color: "var(--text-muted)" }}>—</span>
    );
  }
  const meta = STATUS_META[a.status];
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
      <span style={{
        fontSize: 10, fontWeight: 700, padding: "1px 6px", borderRadius: 3,
        background: meta.bg, color: meta.color, display: "inline-block",
      }}>
        {a.status}
      </span>
      {a.owner && <span style={{ fontSize: 10, color: "var(--text-muted)" }}>{a.owner}</span>}
    </div>
  );
}

interface AssignModalProps {
  obligationId: string;
  obligationName: string;
  current: Assignment | undefined;
  onSave: (id: string, a: Assignment) => void;
  onClose: () => void;
}

function AssignModal({ obligationId, obligationName, current, onSave, onClose }: AssignModalProps) {
  const [owner, setOwner] = useState(current?.owner ?? "");
  const [status, setStatus] = useState<AssignmentStatus>(current?.status ?? "Assigned");
  const [dueDate, setDueDate] = useState(current?.due_date ?? "");
  const [notes, setNotes] = useState(current?.notes ?? "");

  function handleSave() {
    onSave(obligationId, {
      owner,
      status,
      due_date: dueDate,
      notes,
      updated_at: new Date().toISOString(),
    });
    onClose();
  }

  return (
    <div style={{
      position: "fixed", inset: 0, zIndex: 1000,
      background: "rgba(0,0,0,0.55)", display: "flex",
      alignItems: "center", justifyContent: "center",
    }}
      onClick={onClose}
    >
      <div
        style={{
          background: "var(--bg-card)", borderRadius: 12, padding: 24,
          width: 420, maxWidth: "calc(100vw - 32px)", boxShadow: "0 20px 60px rgba(0,0,0,0.4)",
          border: "1px solid var(--border)",
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <h3 style={{ margin: "0 0 4px", fontSize: 15, fontWeight: 700 }}>Assign Obligation</h3>
        <p style={{ margin: "0 0 16px", fontSize: 12, color: "var(--text-muted)", lineHeight: 1.5 }}>
          {obligationName}
        </p>

        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          <div>
            <label style={{ fontSize: 12, fontWeight: 600, display: "block", marginBottom: 4 }}>Owner</label>
            <input
              value={owner}
              onChange={(e) => setOwner(e.target.value)}
              placeholder="e.g. Jane Smith / Compliance Team"
              style={{
                width: "100%", padding: "7px 10px", boxSizing: "border-box",
                background: "var(--bg-panel)", border: "1px solid var(--border)",
                borderRadius: 6, color: "var(--text-primary)", fontSize: 13,
              }}
            />
          </div>

          <div>
            <label style={{ fontSize: 12, fontWeight: 600, display: "block", marginBottom: 4 }}>Status</label>
            <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
              {STATUSES.map((s) => (
                <button
                  key={s}
                  onClick={() => setStatus(s)}
                  style={{
                    padding: "4px 10px", borderRadius: 5, border: "none", cursor: "pointer", fontSize: 12,
                    fontWeight: 600,
                    background: status === s ? STATUS_META[s].bg : "var(--bg-panel)",
                    color: status === s ? STATUS_META[s].color : "var(--text-muted)",
                    outline: status === s ? `1px solid ${STATUS_META[s].color}` : "1px solid transparent",
                  }}
                >
                  {s}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label style={{ fontSize: 12, fontWeight: 600, display: "block", marginBottom: 4 }}>Due Date</label>
            <input
              type="date"
              value={dueDate}
              onChange={(e) => setDueDate(e.target.value)}
              style={{
                padding: "7px 10px", background: "var(--bg-panel)",
                border: "1px solid var(--border)", borderRadius: 6,
                color: "var(--text-primary)", fontSize: 13,
              }}
            />
          </div>

          <div>
            <label style={{ fontSize: 12, fontWeight: 600, display: "block", marginBottom: 4 }}>Notes</label>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Action taken, blockers, references…"
              rows={3}
              style={{
                width: "100%", padding: "7px 10px", boxSizing: "border-box",
                background: "var(--bg-panel)", border: "1px solid var(--border)",
                borderRadius: 6, color: "var(--text-primary)", fontSize: 13,
                resize: "vertical", fontFamily: "inherit",
              }}
            />
          </div>
        </div>

        <div style={{ display: "flex", gap: 8, marginTop: 18, justifyContent: "flex-end" }}>
          <button onClick={onClose} style={{
            padding: "7px 16px", background: "var(--bg-panel)", border: "1px solid var(--border)",
            borderRadius: 6, color: "var(--text-secondary)", fontSize: 13, cursor: "pointer",
          }}>
            Cancel
          </button>
          <button onClick={handleSave} style={{
            padding: "7px 20px", background: "rgba(79,143,247,0.9)", border: "none",
            borderRadius: 6, color: "#fff", fontWeight: 700, fontSize: 13, cursor: "pointer",
          }}>
            Save
          </button>
        </div>
      </div>
    </div>
  );
}

export default function ObligationRegister() {
  const { activeMarket } = useRegion();
  const currency = activeMarket?.currency ?? "AUD";
  const [body, setBody] = useState("");
  const [category, setCategory] = useState("");
  const [risk, setRisk] = useState("");
  const [search, setSearch] = useState("");
  const [expanded, setExpanded] = useState<string | null>(null);
  const [assignments, setAssignments] = useState<Assignments>(loadAssignments);
  const [assigningId, setAssigningId] = useState<string | null>(null);
  const [assignFilter, setAssignFilter] = useState<AssignmentStatus | "">("");

  const saveAssignment = useCallback((id: string, a: Assignment) => {
    const prev = assignments[id];
    const entry: AuditEntry = {
      timestamp: new Date().toISOString(),
      from_status: prev?.status ?? "",
      to_status: a.status,
      owner: a.owner,
      note: a.notes,
    };
    const withHistory: Assignment = {
      ...a,
      history: [...(prev?.history ?? []), entry],
    };
    const updated = { ...assignments, [id]: withHistory };
    setAssignments(updated);
    saveAssignments(updated);
  }, [assignments]);

  const params: Record<string, string> = {};
  if (body) params.regulatory_body = body;
  if (category) params.category = category;
  if (risk) params.risk_rating = risk;
  if (search) params.search = search;

  const { data, loading, error, refetch } = useApi<ObligationsData>("/api/obligations", params);

  if (loading) return <LoadingPage />;
  if (error) return <div className="card"><ErrorState message={`Failed to load obligations: ${error}`} onRetry={refetch} /></div>;

  const assigningRecord = assigningId ? data?.records?.find((r) => r.obligation_id === assigningId) : null;

  // Assignment stats
  const assignedCount = Object.values(assignments).filter((a) => a.status !== "Unassigned").length;
  const inProgressCount = Object.values(assignments).filter((a) => a.status === "In Progress").length;
  const escalatedCount = Object.values(assignments).filter((a) => a.status === "Escalated").length;

  const filteredRecords = (data?.records ?? []).filter((r) => {
    if (!assignFilter) return true;
    const a = assignments[r.obligation_id];
    const status: AssignmentStatus = a?.status ?? "Unassigned";
    return status === assignFilter;
  });

  return (
    <div>
      {assigningRecord && (
        <AssignModal
          obligationId={assigningId!}
          obligationName={assigningRecord.obligation_name}
          current={assignments[assigningId!]}
          onSave={saveAssignment}
          onClose={() => setAssigningId(null)}
        />
      )}

      <div className="stats-row">
        {data?.body_distribution?.map((bd) => (
          <div className="stat-card" key={bd.regulatory_body}>
            <div className="label">{bd.regulatory_body}</div>
            <div className="value blue">{bd.count}</div>
          </div>
        ))}
        <div className="stat-card">
          <div className="label">Assigned</div>
          <div className="value blue">{assignedCount}</div>
        </div>
        {inProgressCount > 0 && (
          <div className="stat-card">
            <div className="label">In Progress</div>
            <div className="value amber">{inProgressCount}</div>
          </div>
        )}
        {escalatedCount > 0 && (
          <div className="stat-card">
            <div className="label">Escalated</div>
            <div className="value red">{escalatedCount}</div>
          </div>
        )}
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
        <div style={{ width: 1, background: "var(--border)", margin: "0 4px" }} />
        <button
          className={`filter-btn ${!assignFilter ? "active" : ""}`}
          onClick={() => setAssignFilter("")}
          style={{ fontSize: 11 }}
        >
          All Assigned
        </button>
        {STATUSES.map((s) => (
          <button
            key={s}
            className={`filter-btn ${assignFilter === s ? "active" : ""}`}
            onClick={() => setAssignFilter(s)}
            style={{ fontSize: 11 }}
          >
            {s}
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
                <th>Score</th>
                <th>Max Penalty</th>
                <th>Assignment</th>
                <th>Legislation</th>
              </tr>
            </thead>
            <tbody>
              {filteredRecords.map((r) => (
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
                    <td><RiskScore score={r.risk_score} /></td>
                    <td className="number currency">{formatCurrencyFull(r.penalty_max_aud, currency)}</td>
                    <td onClick={(e) => e.stopPropagation()}>
                      <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
                        <AssignmentBadge a={assignments[r.obligation_id]} />
                        <button
                          onClick={() => setAssigningId(r.obligation_id)}
                          style={{
                            fontSize: 10, padding: "2px 7px", borderRadius: 4,
                            background: "rgba(79,143,247,0.1)", color: "var(--accent-blue)",
                            border: "1px solid rgba(79,143,247,0.2)", cursor: "pointer",
                          }}
                        >
                          {assignments[r.obligation_id]?.status && assignments[r.obligation_id].status !== "Unassigned" ? "Edit" : "Assign"}
                        </button>
                      </div>
                    </td>
                    <td style={{ fontSize: 11, color: "var(--text-muted)" }}>{r.source_legislation}</td>
                  </tr>
                  {expanded === r.obligation_id && (
                    <tr key={`${r.obligation_id}-detail`}>
                      <td colSpan={9} style={{ background: "var(--bg-secondary)", padding: 16 }}>
                        <div style={{ fontSize: 13, marginBottom: 8 }}>
                          <strong>Description:</strong> {r.description}
                        </div>
                        <div style={{ fontSize: 12, color: "var(--text-secondary)", marginBottom: assignments[r.obligation_id] ? 10 : 0 }}>
                          <strong>Key Requirements:</strong> {r.key_requirements}
                        </div>
                        {assignments[r.obligation_id] && assignments[r.obligation_id].status !== "Unassigned" && (
                          <div style={{
                            marginTop: 10, padding: "8px 12px",
                            background: "var(--bg-card)", borderRadius: 6,
                            border: "1px solid var(--border)", fontSize: 12,
                          }}>
                            <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 6 }}>
                              <strong>Assignment</strong>
                              {assignments[r.obligation_id].owner && <span style={{ color: "var(--text-secondary)" }}>{assignments[r.obligation_id].owner}</span>}
                              <span style={{
                                fontSize: 11, fontWeight: 700, padding: "1px 6px", borderRadius: 3,
                                background: STATUS_META[assignments[r.obligation_id].status].bg,
                                color: STATUS_META[assignments[r.obligation_id].status].color,
                              }}>
                                {assignments[r.obligation_id].status}
                              </span>
                              {assignments[r.obligation_id].due_date && (
                                <span style={{ color: "var(--text-muted)", fontSize: 11 }}>Due {assignments[r.obligation_id].due_date}</span>
                              )}
                            </div>
                            {assignments[r.obligation_id].notes && (
                              <div style={{ color: "var(--text-secondary)", marginBottom: 8 }}>
                                {assignments[r.obligation_id].notes}
                              </div>
                            )}
                            {(assignments[r.obligation_id].history?.length ?? 0) > 0 && (
                              <div style={{ marginTop: 8, borderTop: "1px solid var(--border)", paddingTop: 8 }}>
                                <div style={{ fontSize: 11, fontWeight: 700, color: "var(--text-muted)", marginBottom: 6, letterSpacing: "0.06em", textTransform: "uppercase" }}>
                                  Audit Trail
                                </div>
                                {[...(assignments[r.obligation_id].history ?? [])].reverse().slice(0, 5).map((entry, ei) => (
                                  <div key={ei} style={{ display: "flex", gap: 8, fontSize: 11, color: "var(--text-muted)", marginBottom: 4 }}>
                                    <span style={{ flexShrink: 0 }}>{new Date(entry.timestamp).toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}</span>
                                    <span style={{ color: "var(--text-secondary)" }}>
                                      {entry.from_status ? `${entry.from_status} → ` : ""}
                                      <span style={{ fontWeight: 600, color: STATUS_META[entry.to_status]?.color }}>{entry.to_status}</span>
                                    </span>
                                    {entry.owner && <span>by {entry.owner}</span>}
                                  </div>
                                ))}
                              </div>
                            )}
                          </div>
                        )}
                      </td>
                    </tr>
                  )}
                </>
              ))}
            </tbody>
          </table>
        </div>
        {filteredRecords.length === 0 && (
          <EmptyState
            icon="📋"
            message="No obligations match your filters"
            detail="Try adjusting the body, category, risk level, or assignment status filters."
            actionLabel="Clear filters"
            onAction={() => { setSearch(""); setAssignFilter(""); }}
          />
        )}
      </div>
    </div>
  );
}
