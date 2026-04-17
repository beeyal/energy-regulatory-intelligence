import { useState, useEffect, useRef } from "react";
import type { MarketInfo } from "../context/RegionContext";
import MarkdownRenderer from "./MarkdownRenderer";
import { formatCurrency } from "../utils/currency";

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
  const currency = activeMarket?.currency ?? "AUD";
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

  const handlePrint = () => {
    const content = document.getElementById("briefing-content");
    if (!content) return;
    const win = window.open("", "_blank", "width=900,height=700");
    if (!win) return;
    win.document.write(`<!DOCTYPE html><html><head>
      <title>Board Compliance Briefing — ${marketLabel}</title>
      <style>
        body { font-family: Georgia, serif; font-size: 13px; color: #1a1a2e; margin: 40px; background: #fff; }
        h1 { font-size: 22px; font-weight: bold; margin-bottom: 4px; }
        h2 { font-size: 15px; font-weight: bold; border-bottom: 1px solid #ddd; padding-bottom: 6px; margin-top: 28px; }
        table { width: 100%; border-collapse: collapse; margin: 12px 0; font-size: 12px; }
        th { text-align: left; padding: 6px 10px; background: #f0f2f7; font-weight: 600; border: 1px solid #ddd; }
        td { padding: 5px 10px; border: 1px solid #ddd; vertical-align: top; }
        .briefing-summary-grid { display: flex; gap: 12px; margin: 16px 0; }
        .briefing-summary-card { flex: 1; padding: 12px 16px; border: 1px solid #ddd; border-radius: 6px; }
        .briefing-summary-label { font-size: 11px; font-weight: 600; text-transform: uppercase; color: #666; }
        .briefing-summary-value { font-size: 24px; font-weight: 800; margin: 4px 0; }
        .briefing-actions { margin: 12px 0; }
        .briefing-action-item { display: flex; gap: 12px; padding: 10px; border: 1px solid #ddd; border-radius: 6px; margin-bottom: 8px; }
        .briefing-action-priority { font-weight: 800; min-width: 24px; color: #e53e3e; }
        .briefing-narrative-block { margin: 16px 0; padding: 14px; background: #f9fafb; border-left: 3px solid #4f8ff7; border-radius: 4px; }
        .briefing-narrative-label { font-size: 11px; font-weight: 700; color: #4f8ff7; text-transform: uppercase; margin-bottom: 8px; }
        .briefing-footer { margin-top: 32px; padding-top: 16px; border-top: 1px solid #ddd; font-size: 11px; color: #888; }
        .severity { padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; }
        .severity-critical { background: #fee2e2; color: #dc2626; }
        .severity-warning { background: #fef3c7; color: #d97706; }
        .severity-info { background: #dbeafe; color: #2563eb; }
        .severity-low { background: #d1fae5; color: #059669; }
        @media print { body { margin: 20px; } }
      </style>
    </head><body>${content.innerHTML}</body></html>`);
    win.document.close();
    win.focus();
    setTimeout(() => { win.print(); }, 300);
  };

  /* Derived values from API data */
  const criticalCount = data?.risk_distribution.find(
    (r) => r.risk_rating.toLowerCase() === "critical"
  )?.count ?? "0";
  const totalObligations = data
    ? data.risk_distribution.reduce((sum, r) => sum + parseInt(r.count, 10), 0)
    : 0;
  const totalPenaltyExposure = data ? formatCurrency(data.penalty_summary.total, currency) : "—";
  const penaltyCompanies = data?.penalty_summary.companies ?? "0";
  const maxPenalty = data ? formatCurrency(data.penalty_summary.max_penalty, currency) : "—";
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
            <button className="briefing-btn" onClick={handlePrint} title="Export as PDF via browser print">
              ↓ PDF
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
                        <td className="currency">{formatCurrency(e.penalty_aud, currency)}</td>
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
                        <td className="currency">{formatCurrency(o.penalty_max_aud, currency)}</td>
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
                        <td>{parseFloat(e.scope1).toLocaleString(undefined, { maximumFractionDigits: 0 })} tCO2-e</td>
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
                        <td className="currency">{formatCurrency(r.metric_value, currency)}</td>
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
