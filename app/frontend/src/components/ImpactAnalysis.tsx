import { useState } from "react";
import { useRegion } from "../context/RegionContext";

interface AffectedObligation {
  id: string;
  name: string;
  reason: string;
  action: string;
  urgency: "Immediate" | "Short-term" | "Medium-term";
}

interface ImpactResult {
  impact_summary: string;
  risk_level: "Critical" | "High" | "Medium" | "Low";
  affected_obligations: AffectedObligation[];
  new_obligations: string[];
  recommendations: string[];
}

const EXAMPLE_TEXTS = [
  {
    label: "Safeguard Mechanism Reform",
    text: "The Safeguard Mechanism (Crediting) Amendment Act 2023 introduces mandatory 4.9% annual decline in Safeguard baselines, new Net Zero Plans for facilities over 100kt CO2-e, and compulsory ACCU surrender for any shortfall exceeding 5% of baseline.",
  },
  {
    label: "DER Integration Rule Change",
    text: "AEMC Rule Change ERC0311: Distributed Energy Resources (DER) operators with installed capacity above 30kW must register with AEMO, comply with new AS/NZS 4777.2 grid connection standards, and report metering data in 5-minute intervals from 1 July 2025.",
  },
  {
    label: "CDR Energy Data Sharing",
    text: "Consumer Data Right (CDR) energy expansion requires all retailers with more than 25,000 customers to share standardised energy usage data via accredited data holders by 1 November 2024, with penalties up to $10M for non-compliance.",
  },
];

const URGENCY_COLOR: Record<string, string> = {
  Immediate: "#ef4444",
  "Short-term": "#f59e0b",
  "Medium-term": "#3b82f6",
};

const RISK_COLOR: Record<string, string> = {
  Critical: "#ef4444",
  High: "#f59e0b",
  Medium: "#3b82f6",
  Low: "#10b981",
};

export default function ImpactAnalysis() {
  const { market } = useRegion();
  const [text, setText] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<ImpactResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function analyze() {
    if (!text.trim()) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await fetch("/api/impact-analysis", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ regulation_text: text, market }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setResult(data);
    } catch (e) {
      setError("Analysis failed — please try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <div className="card">
        <div className="card-header">
          <h2>AI Regulatory Change Impact Analysis</h2>
          <span className="badge" style={{ background: "rgba(168,85,247,0.15)", color: "#a855f7" }}>
            G-18 · AI-Powered
          </span>
        </div>

        <p style={{ fontSize: 13, color: "var(--text-secondary)", marginBottom: 12, lineHeight: 1.6 }}>
          Paste the text of a proposed or recent regulatory change. The AI will identify which
          obligations in your register are affected, explain why, and recommend actions.
        </p>

        <div style={{ display: "flex", gap: 8, marginBottom: 10, flexWrap: "wrap" }}>
          <span style={{ fontSize: 12, color: "var(--text-muted)", alignSelf: "center" }}>Try an example:</span>
          {EXAMPLE_TEXTS.map((ex) => (
            <button
              key={ex.label}
              className="filter-btn"
              onClick={() => setText(ex.text)}
              style={{ fontSize: 11 }}
            >
              {ex.label}
            </button>
          ))}
        </div>

        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Paste regulatory change text here… (e.g. an AEMC rule determination, CER legislative instrument, AEMO procedure change)"
          style={{
            width: "100%",
            minHeight: 130,
            padding: "10px 12px",
            background: "var(--bg-panel)",
            border: "1px solid var(--border)",
            borderRadius: 8,
            color: "var(--text-primary)",
            fontSize: 13,
            lineHeight: 1.6,
            resize: "vertical",
            fontFamily: "inherit",
            boxSizing: "border-box",
          }}
        />

        <div style={{ marginTop: 10, display: "flex", gap: 10, alignItems: "center" }}>
          <button
            onClick={analyze}
            disabled={loading || !text.trim()}
            style={{
              padding: "8px 20px",
              background: loading || !text.trim() ? "var(--bg-panel)" : "rgba(168,85,247,0.9)",
              color: loading || !text.trim() ? "var(--text-muted)" : "#fff",
              border: "none",
              borderRadius: 8,
              fontWeight: 700,
              fontSize: 13,
              cursor: loading || !text.trim() ? "not-allowed" : "pointer",
              transition: "background 0.2s",
            }}
          >
            {loading ? "⏳ Analysing…" : "⚡ Analyse Impact"}
          </button>
          {text && (
            <button
              onClick={() => { setText(""); setResult(null); setError(null); }}
              style={{ fontSize: 12, color: "var(--text-muted)", background: "none", border: "none", cursor: "pointer" }}
            >
              Clear
            </button>
          )}
          <span style={{ fontSize: 11, color: "var(--text-muted)", marginLeft: "auto" }}>
            {text.length} / 3000 chars
          </span>
        </div>
      </div>

      {error && (
        <div className="card" style={{ background: "rgba(239,68,68,0.05)", borderColor: "rgba(239,68,68,0.2)" }}>
          <p style={{ color: "var(--accent-red)", margin: 0, fontSize: 13 }}>⚠ {error}</p>
        </div>
      )}

      {result && (
        <>
          {/* Summary banner */}
          <div className="card" style={{
            background: `rgba(${result.risk_level === "Critical" ? "239,68,68" : result.risk_level === "High" ? "245,158,11" : result.risk_level === "Medium" ? "59,130,246" : "16,185,129"}, 0.06)`,
            border: `1px solid rgba(${result.risk_level === "Critical" ? "239,68,68" : result.risk_level === "High" ? "245,158,11" : result.risk_level === "Medium" ? "59,130,246" : "16,185,129"}, 0.25)`,
          }}>
            <div style={{ display: "flex", gap: 12, alignItems: "flex-start" }}>
              <div style={{
                fontSize: 20, width: 36, height: 36, borderRadius: 8, flexShrink: 0,
                background: `rgba(${result.risk_level === "Critical" ? "239,68,68" : result.risk_level === "High" ? "245,158,11" : result.risk_level === "Medium" ? "59,130,246" : "16,185,129"}, 0.15)`,
                display: "flex", alignItems: "center", justifyContent: "center",
              }}>
                {result.risk_level === "Critical" ? "🚨" : result.risk_level === "High" ? "⚠" : result.risk_level === "Medium" ? "📋" : "✓"}
              </div>
              <div style={{ flex: 1 }}>
                <div style={{ display: "flex", gap: 10, alignItems: "center", marginBottom: 6 }}>
                  <span style={{
                    fontSize: 12, fontWeight: 700, padding: "2px 8px", borderRadius: 4,
                    background: `rgba(${result.risk_level === "Critical" ? "239,68,68" : result.risk_level === "High" ? "245,158,11" : result.risk_level === "Medium" ? "59,130,246" : "16,185,129"}, 0.2)`,
                    color: RISK_COLOR[result.risk_level],
                  }}>
                    {result.risk_level} Impact
                  </span>
                  <span style={{ fontSize: 12, color: "var(--text-muted)" }}>
                    {result.affected_obligations.length} obligation{result.affected_obligations.length !== 1 ? "s" : ""} affected
                  </span>
                </div>
                <p style={{ margin: 0, fontSize: 13, color: "var(--text-primary)", lineHeight: 1.7 }}>
                  {result.impact_summary}
                </p>
              </div>
            </div>
          </div>

          {/* Affected obligations */}
          {result.affected_obligations.length > 0 && (
            <div className="card">
              <div className="card-header">
                <h2>Affected Obligations</h2>
                <span className="badge" style={{ background: "rgba(245,158,11,0.15)", color: "var(--accent-amber)" }}>
                  {result.affected_obligations.length} identified
                </span>
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                {result.affected_obligations.map((obl, i) => (
                  <div key={i} style={{
                    padding: "12px 14px",
                    background: "var(--bg-panel)",
                    borderRadius: 8,
                    borderLeft: `3px solid ${URGENCY_COLOR[obl.urgency] || "#6b7280"}`,
                  }}>
                    <div style={{ display: "flex", gap: 10, alignItems: "flex-start" }}>
                      <span style={{
                        fontSize: 11, fontWeight: 700, padding: "2px 6px", borderRadius: 4, flexShrink: 0,
                        background: `rgba(${obl.urgency === "Immediate" ? "239,68,68" : obl.urgency === "Short-term" ? "245,158,11" : "59,130,246"}, 0.15)`,
                        color: URGENCY_COLOR[obl.urgency] || "#6b7280",
                      }}>
                        {obl.urgency}
                      </span>
                      <div style={{ flex: 1 }}>
                        <div style={{ fontSize: 12, fontWeight: 600, color: "var(--text-primary)" }}>
                          {obl.id && <span style={{ color: "var(--text-muted)", marginRight: 6 }}>{obl.id}</span>}
                          {obl.name}
                        </div>
                        <div style={{ fontSize: 12, color: "var(--text-secondary)", marginTop: 3, lineHeight: 1.5 }}>
                          <strong>Why:</strong> {obl.reason}
                        </div>
                        <div style={{
                          fontSize: 12, color: "var(--accent-blue)", marginTop: 4, lineHeight: 1.5,
                          background: "rgba(79,143,247,0.06)", padding: "4px 8px", borderRadius: 4,
                        }}>
                          <strong>Action:</strong> {obl.action}
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* New obligations */}
          {result.new_obligations.length > 0 && (
            <div className="card">
              <div className="card-header">
                <h2>Potential New Obligations</h2>
                <span className="badge" style={{ background: "rgba(168,85,247,0.15)", color: "#a855f7" }}>
                  {result.new_obligations.length} implied
                </span>
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                {result.new_obligations.map((n, i) => (
                  <div key={i} style={{
                    padding: "10px 14px",
                    background: "rgba(168,85,247,0.06)",
                    borderRadius: 8,
                    border: "1px solid rgba(168,85,247,0.15)",
                    fontSize: 13,
                    color: "var(--text-primary)",
                    lineHeight: 1.6,
                  }}>
                    <span style={{ color: "#a855f7", marginRight: 8 }}>+</span>{n}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Recommendations */}
          {result.recommendations.length > 0 && (
            <div className="card">
              <div className="card-header">
                <h2>Recommended Actions</h2>
              </div>
              <ol style={{ margin: 0, paddingLeft: 22, display: "flex", flexDirection: "column", gap: 8 }}>
                {result.recommendations.map((rec, i) => (
                  <li key={i} style={{ fontSize: 13, color: "var(--text-primary)", lineHeight: 1.6 }}>
                    {rec}
                  </li>
                ))}
              </ol>
            </div>
          )}
        </>
      )}
    </div>
  );
}
