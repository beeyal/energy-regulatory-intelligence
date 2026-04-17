import { useState, useEffect, useRef } from "react";
import type { MarketInfo } from "../context/RegionContext";
import MarkdownRenderer from "./MarkdownRenderer";

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

interface BoardBriefingProps {
  visible: boolean;
  onClose: () => void;
  market?: string;
  activeMarket?: MarketInfo | null;
}

interface RiskDistribution {
  risk_rating: string;
  count: string;
}

interface PenaltySummary {
  total: string;
  count: string;
  companies: string;
  max_penalty: string;
}

interface EnforcementAction {
  company_name: string;
  action_type: string;
  penalty_aud: string;
  breach_description: string;
  action_date: string;
}

interface CriticalObligation {
  obligation_name: string;
  regulatory_body: string;
  category: string;
  penalty_max_aud: string;
  frequency: string;
}

interface TopEmitter {
  corporation_name: string;
  scope1: string;
}

interface RepeatOffender {
  entity_name: string;
  metric_value: string;
  detail: string;
}

interface ApiBoardBriefingResponse {
  generated_at: string;
  risk_distribution: RiskDistribution[];
  penalty_summary: PenaltySummary;
  recent_enforcement: EnforcementAction[];
  critical_obligations: CriticalObligation[];
  top_emitters: TopEmitter[];
  repeat_offenders: RepeatOffender[];
}

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

function SeverityBadge({ level }: { level: "critical" | "warning" | "info" | "improving" }) {
  const cls =
    level === "critical" ? "severity-critical" :
    level === "warning" ? "severity-warning" :
    level === "improving" ? "severity-low" :
    "severity-info";
  const label =
    level === "critical" ? "Critical" :
    level === "warning" ? "Warning" :
    level === "improving" ? "Improving" :
    "Info";
  return <span className={`severity ${cls}`}>{label}</span>;
}

function formatAud(val: string | number): string {
  const num = typeof val === "string" ? parseFloat(val) : val;
  if (isNaN(num)) return "$0";
  if (num >= 1e6) return `$${(num / 1e6).toFixed(1)}M`;
  if (num >= 1e3) return `$${(num / 1e3).toFixed(0)}K`;
  return `$${num.toFixed(0)}`;
}

function severityFromRating(rating: string): "critical" | "warning" | "info" {
  const lower = rating.toLowerCase();
  if (lower === "critical") return "critical";
  if (lower === "high" || lower === "warning") return "warning";
  return "info";
}

const BRIEFING_DATE = new Date().toLocaleDateString("en-AU", {
  year: "numeric",
  month: "long",
  day: "numeric",
});

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export default function BoardBriefing({ visible, onClose, market = "AU", activeMarket }: BoardBriefingProps) {
  const marketName = activeMarket?.market_name ?? activeMarket?.name ?? market;
  const marketFlag = activeMarket?.flag ?? "";
  // Derive a plausible company display name from the market
  const companyName = market === "AU"
    ? "EnergyAus Holdings Ltd"
    : `${marketName} Energy Holdings`;
  const marketLabel = `${marketFlag} ${marketName}`.trim();
  const [copied, setCopied] = useState(false);
  const [data, setData] = useState<ApiBoardBriefingResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Streaming narrative state
  const [narrative, setNarrative] = useState("");
  const [narrativeLoading, setNarrativeLoading] = useState(false);
  const [narrativeDone, setNarrativeDone] = useState(false);
  const esRef = useRef<EventSource | null>(null);

  // Fetch structured data
  useEffect(() => {
    if (!visible) return;
    let cancelled = false;
    setLoading(true);
    setError(null);

    fetch(`/api/board-briefing?market=${market}`)
      .then((resp) => {
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        return resp.json();
      })
      .then((json) => { if (!cancelled) setData(json); })
      .catch((e) => { if (!cancelled) setError(e instanceof Error ? e.message : "Unknown error"); })
      .finally(() => { if (!cancelled) setLoading(false); });

    return () => { cancelled = true; };
  }, [visible, market]);

  // Start streaming narrative
  const startNarrative = () => {
    if (esRef.current) {
      esRef.current.close();
      esRef.current = null;
    }
    setNarrative("");
    setNarrativeLoading(true);
    setNarrativeDone(false);

    const es = new EventSource(`/api/board-briefing-narrative?market=${market}`);
    esRef.current = es;

    es.onmessage = (e) => {
      try {
        const token = JSON.parse(e.data);
        setNarrative((prev) => prev + token);
      } catch {
        /* ignore parse errors */
      }
    };

    es.addEventListener("done", () => {
      setNarrativeLoading(false);
      setNarrativeDone(true);
      es.close();
      esRef.current = null;
    });

    es.addEventListener("error", () => {
      setNarrativeLoading(false);
      es.close();
      esRef.current = null;
    });
  };

  // Auto-start narrative when modal opens
  useEffect(() => {
    if (visible) {
      startNarrative();
    } else {
      // Clean up on close
      if (esRef.current) {
        esRef.current.close();
        esRef.current = null;
      }
      setNarrative("");
      setNarrativeLoading(false);
      setNarrativeDone(false);
    }
  }, [visible]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!visible) return null;

  const handleCopy = () => {
    const el = document.getElementById("briefing-content");
    if (el) {
      navigator.clipboard.writeText(el.innerText).then(() => {
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
      });
    }
  };

  /* Derived values from API data */
  const criticalCount = data?.risk_distribution.find(
    (r) => r.risk_rating.toLowerCase() === "critical"
  )?.count ?? "0";
  const totalObligations = data
    ? data.risk_distribution.reduce((sum, r) => sum + parseInt(r.count, 10), 0)
    : 0;
  const totalPenaltyExposure = data ? formatAud(data.penalty_summary.total) : "$0";
  const penaltyCompanies = data?.penalty_summary.companies ?? "0";
  const maxPenalty = data ? formatAud(data.penalty_summary.max_penalty) : "$0";
  const penaltyCount = data?.penalty_summary.count ?? "0";
  const complianceRate = totalObligations > 0
    ? Math.round(((totalObligations - parseInt(criticalCount, 10)) / totalObligations) * 100)
    : 0;

  return (
    <div className="briefing-overlay" onClick={onClose}>
      <div className="briefing-modal" onClick={(e) => e.stopPropagation()}>
        <div className="briefing-toolbar">
          <div className="briefing-toolbar-left">
            <span className="briefing-doc-icon">DOC</span>
            <span className="briefing-toolbar-title">Board Compliance Briefing — {marketLabel}</span>
          </div>
          <div className="briefing-toolbar-right">
            <button
              className="briefing-btn"
              onClick={startNarrative}
              disabled={narrativeLoading}
              title="Regenerate AI narrative"
            >
              {narrativeLoading ? "Generating…" : "Regenerate"}
            </button>
            <button className="briefing-btn" onClick={handleCopy}>
              {copied ? "Copied" : "Copy"}
            </button>
            <button className="briefing-btn briefing-btn-close" onClick={onClose}>
              Close
            </button>
          </div>
        </div>

        <div className="briefing-body" id="briefing-content">
          {/* Loading state */}
          {loading && (
            <div style={{ padding: 40, textAlign: "center" }}>
              <div className="skeleton skeleton-bar" style={{ width: 300, margin: "0 auto 16px" }} />
              <div className="skeleton skeleton-bar" style={{ width: 200, margin: "0 auto 16px" }} />
              {Array.from({ length: 6 }).map((_, i) => (
                <div
                  key={i}
                  className="skeleton skeleton-row"
                  style={{ width: `${60 + Math.random() * 30}%`, margin: "8px auto" }}
                />
              ))}
            </div>
          )}

          {/* Error state */}
          {error && !loading && (
            <div style={{ padding: 40, textAlign: "center", color: "var(--accent-red)" }}>
              <p>Failed to load briefing data: {error}</p>
            </div>
          )}

          {/* Content — only rendered when data is available */}
          {data && !loading && (
            <>
              {/* Document header */}
              <div className="briefing-doc-header">
                <div className="briefing-logo-line">
                  <span className="briefing-logo-mark" />
                  <span className="briefing-company">{companyName}</span>
                </div>
                <h1 className="briefing-title">Board Compliance Briefing</h1>
                <div className="briefing-meta">
                  <span>Market: {marketLabel}</span>
                  <span className="dot" />
                  <span>Prepared: {BRIEFING_DATE}</span>
                  <span className="dot" />
                  <span>Classification: Board Confidential</span>
                  <span className="dot" />
                  <span>Period: Q2 FY2025-26</span>
                </div>
              </div>

              {/* 1. Executive Summary — Stats + AI Narrative */}
              <section className="briefing-section">
                <h2 className="briefing-section-title">
                  <span className="briefing-section-num">1</span>
                  Executive Summary
                </h2>
                <div className="briefing-summary-grid">
                  <div className="briefing-summary-card briefing-summary-red">
                    <div className="briefing-summary-label">Overall Risk Posture</div>
                    <div className="briefing-summary-value">Elevated</div>
                    <div className="briefing-summary-detail">Up from Moderate in Q1</div>
                  </div>
                  <div className="briefing-summary-card briefing-summary-amber">
                    <div className="briefing-summary-label">Critical Obligations</div>
                    <div className="briefing-summary-value">{criticalCount}</div>
                    <div className="briefing-summary-detail">Requiring immediate attention</div>
                  </div>
                  <div className="briefing-summary-card briefing-summary-blue">
                    <div className="briefing-summary-label">Total Obligations</div>
                    <div className="briefing-summary-value">{totalObligations}</div>
                    <div className="briefing-summary-detail">Across 5 regulatory bodies</div>
                  </div>
                  <div className="briefing-summary-card briefing-summary-green">
                    <div className="briefing-summary-label">Compliance Rate</div>
                    <div className="briefing-summary-value">{complianceRate}%</div>
                    <div className="briefing-summary-detail">Target: 95%</div>
                  </div>
                </div>

                {/* AI-generated narrative */}
                <div className="briefing-narrative-block">
                  <div className="briefing-narrative-label">
                    <span className="briefing-ai-badge">AI</span>
                    Board Executive Narrative
                    {narrativeLoading && <span className="briefing-generating-pulse">Generating…</span>}
                  </div>
                  <div className="briefing-narrative-body">
                    {narrative ? (
                      <>
                        <MarkdownRenderer content={narrative} />
                        {narrativeLoading && <span className="typing-cursor" />}
                      </>
                    ) : narrativeLoading ? (
                      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                        {Array.from({ length: 4 }).map((_, i) => (
                          <div
                            key={i}
                            className="skeleton skeleton-row"
                            style={{ width: `${75 + (i % 3) * 8}%` }}
                          />
                        ))}
                      </div>
                    ) : (
                      <p className="briefing-paragraph" style={{ color: "var(--text-muted)" }}>
                        Click "Regenerate" to generate an AI executive narrative.
                      </p>
                    )}
                  </div>
                </div>
              </section>

              {/* 2. Risk Distribution */}
              <section className="briefing-section">
                <h2 className="briefing-section-title">
                  <span className="briefing-section-num">2</span>
                  Risk Distribution
                </h2>
                <table className="data-table briefing-table">
                  <thead>
                    <tr>
                      <th>Risk Rating</th>
                      <th>Count</th>
                      <th>Severity</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.risk_distribution.map((r) => (
                      <tr key={r.risk_rating}>
                        <td>{r.risk_rating}</td>
                        <td>{r.count}</td>
                        <td><SeverityBadge level={severityFromRating(r.risk_rating)} /></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </section>

              {/* 3. Compliance Incidents & Enforcement Actions */}
              <section className="briefing-section">
                <h2 className="briefing-section-title">
                  <span className="briefing-section-num">3</span>
                  Compliance Incidents &amp; Enforcement Actions
                </h2>
                <table className="data-table briefing-table">
                  <thead>
                    <tr>
                      <th>Date</th>
                      <th>Company</th>
                      <th>Action</th>
                      <th>Breach</th>
                      <th>Penalty</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.recent_enforcement.map((e, i) => (
                      <tr key={i}>
                        <td>{e.action_date}</td>
                        <td>{e.company_name}</td>
                        <td>{e.action_type}</td>
                        <td>{e.breach_description}</td>
                        <td className="currency">{formatAud(e.penalty_aud)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                <p className="briefing-paragraph" style={{ marginTop: 12 }}>
                  A total of <strong>{penaltyCount}</strong> enforcement actions have been recorded across <strong>{penaltyCompanies}</strong> companies, with cumulative penalties of <strong>{totalPenaltyExposure}</strong>. The largest single penalty exposure is <strong>{maxPenalty}</strong>. Legal counsel has been engaged for all highest-exposure items.
                </p>
              </section>

              {/* 4. Critical Obligations */}
              <section className="briefing-section">
                <h2 className="briefing-section-title">
                  <span className="briefing-section-num">4</span>
                  Critical Obligations
                </h2>
                <table className="data-table briefing-table">
                  <thead>
                    <tr>
                      <th>Obligation</th>
                      <th>Regulator</th>
                      <th>Category</th>
                      <th>Max Penalty</th>
                      <th>Frequency</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.critical_obligations.map((o, i) => (
                      <tr key={i}>
                        <td>{o.obligation_name}</td>
                        <td>{o.regulatory_body}</td>
                        <td>{o.category}</td>
                        <td className="currency">{formatAud(o.penalty_max_aud)}</td>
                        <td>{o.frequency}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </section>

              {/* 5. Top Emitters */}
              <section className="briefing-section">
                <h2 className="briefing-section-title">
                  <span className="briefing-section-num">5</span>
                  Top Emitters — Scope 1
                </h2>
                <table className="data-table briefing-table">
                  <thead>
                    <tr>
                      <th>Corporation</th>
                      <th>Scope 1 Emissions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.top_emitters.map((e, i) => (
                      <tr key={i}>
                        <td>{e.corporation_name}</td>
                        <td>{parseFloat(e.scope1).toLocaleString("en-AU", { maximumFractionDigits: 0 })} tCO2-e</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </section>

              {/* 6. Repeat Offenders */}
              <section className="briefing-section">
                <h2 className="briefing-section-title">
                  <span className="briefing-section-num">6</span>
                  Repeat Offenders
                </h2>
                <table className="data-table briefing-table">
                  <thead>
                    <tr>
                      <th>Entity</th>
                      <th>Total Penalties</th>
                      <th>Detail</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.repeat_offenders.map((r, i) => (
                      <tr key={i}>
                        <td>{r.entity_name}</td>
                        <td className="currency">{formatAud(r.metric_value)}</td>
                        <td>{r.detail}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </section>

              {/* 7. Recommended Actions */}
              <section className="briefing-section">
                <h2 className="briefing-section-title">
                  <span className="briefing-section-num">7</span>
                  Recommended Actions
                </h2>
                <div className="briefing-actions">
                  <div className="briefing-action-item briefing-action-critical">
                    <div className="briefing-action-priority">P1</div>
                    <div className="briefing-action-content">
                      <strong>Authorise external legal engagement</strong> for high-priority enforcement responses. The largest single penalty exposure is {maxPenalty}. Deadline: immediate.
                      <div className="briefing-action-owner">Owner: General Counsel / Head of Regulatory</div>
                    </div>
                  </div>
                  <div className="briefing-action-item briefing-action-critical">
                    <div className="briefing-action-priority">P1</div>
                    <div className="briefing-action-content">
                      <strong>Approve Safeguard Facility Plan project</strong> including updated emissions monitoring infrastructure at facilities identified in the Top Emitters analysis. Must be operational before 30 June 2026 submission.
                      <div className="briefing-action-owner">Owner: COO / Head of Generation</div>
                    </div>
                  </div>
                  <div className="briefing-action-item briefing-action-warning">
                    <div className="briefing-action-priority">P2</div>
                    <div className="briefing-action-content">
                      <strong>Address repeat offender patterns</strong> — {data.repeat_offenders.length} entities identified with repeated compliance failures. Targeted remediation programs should be initiated.
                      <div className="briefing-action-owner">Owner: Chief Risk Officer</div>
                    </div>
                  </div>
                  <div className="briefing-action-item briefing-action-warning">
                    <div className="briefing-action-priority">P2</div>
                    <div className="briefing-action-content">
                      <strong>Accelerate compliance program improvements</strong> to address {criticalCount} critical obligations and reduce total penalty exposure of {totalPenaltyExposure}.
                      <div className="briefing-action-owner">Owner: Head of Retail Operations</div>
                    </div>
                  </div>
                  <div className="briefing-action-item briefing-action-info">
                    <div className="briefing-action-priority">P3</div>
                    <div className="briefing-action-content">
                      <strong>Enhance compliance monitoring automation</strong> — deploy AI-powered regulatory change tracking to reduce manual monitoring burden and improve response times. Business case prepared; seeking board endorsement.
                      <div className="briefing-action-owner">Owner: Chief Risk Officer</div>
                    </div>
                  </div>
                </div>
              </section>

              {/* Footer */}
              <div className="briefing-footer">
                <p>This briefing was generated by the Energy Compliance Intelligence Hub using AI-assisted regulatory analysis. All data points should be verified against primary regulatory sources before board presentation.</p>
                <p style={{ marginTop: 8 }}>
                  <strong>Next briefing scheduled:</strong> Q3 FY2025-26 (July 2026)
                </p>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
