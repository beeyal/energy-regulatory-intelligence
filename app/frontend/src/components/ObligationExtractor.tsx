import { useState } from "react";
import { useRegion } from "../context/RegionContext";
import { formatCurrencyFull } from "../utils/currency";

interface ExtractedObligation {
  obligation_id: string;
  obligation_name: string;
  regulatory_body: string;
  category: string;
  risk_rating: string;
  penalty_max_aud: number;
  frequency: string;
  description: string;
  key_requirements: string;
  source_legislation: string;
  market: string;
  status: string;
}

interface ExtractionResult {
  obligations: ExtractedObligation[];
  count: number;
}

const EXAMPLE_REGS = [
  {
    label: "AEMC DER Rule Change",
    text: `AEMC Rule Determination — Distributed Energy Resources Integration (ERC0311)

All network service providers must comply with the following obligations:

1. DER Registration: Any distributed energy resource with installed capacity exceeding 30kW shall be registered with AEMO within 30 days of commissioning. Failure to register attracts a civil penalty of $10,000 per day.

2. Metering Standard Compliance: All DER operators must ensure metering systems comply with AS/NZS 4777.2:2020 grid connection standards. Non-compliant systems must be upgraded within 6 months. Maximum penalty: $1,000,000.

3. Five-Minute Data Reporting: Retailers and network operators must submit DER generation and consumption data in 5-minute intervals to AEMO's DER Register by 1 July 2025. Penalty: $500,000 for non-compliance.

4. Consumer Protection: Retailers offering DER services must provide standardised product disclosure statements under NERR Rule 74B. Maximum penalty: $5,000,000 per breach.`,
  },
  {
    label: "Safeguard Mechanism Amendment",
    text: `Clean Energy Legislation (Safeguard Mechanism) Amendment Act 2024

Section 22: Baseline Obligations
Covered facilities with baseline emissions exceeding 100,000 tonnes CO2-e per year must:
(a) Submit an annual Safeguard Report to the Clean Energy Regulator by 31 October each year. Civil penalty: 660 penalty units ($184,800).
(b) Surrender an equivalent number of Australian Carbon Credit Units (ACCUs) for any net emissions exceeding the safeguard baseline. Failure to surrender: $275 per excess tonne.
(c) Prepare and publish a Net Zero Plan where baseline exceeds 500,000 tonnes CO2-e, approved by the CER. Maximum penalty: $2,220,000.

Section 22XN: Record Keeping
All covered entities must maintain emissions records for 7 years. Civil penalty for record destruction: $660,000.`,
  },
  {
    label: "CDR Energy Expansion",
    text: `Consumer Data Right (Energy Sector) Rules 2023 — Phase 2 Expansion

Rule 4.1: Data Holder Obligations
Energy retailers with more than 25,000 residential customers must:
- Share standardised energy usage data via accredited data holders by 1 November 2024
- Implement consent management systems compliant with CDR Privacy Safeguards
- Respond to data requests within 3 business days
Maximum civil penalty: $10,000,000 per contravention.

Rule 4.2: Third Party Disclosure
Accredited data recipients must not use consumer energy data for purposes beyond those consented. Maximum penalty: $50,000 per breach for individuals; $250,000 for corporations.

Rule 6.5: Dispute Resolution
All data disputes must be escalated to the Australian Financial Complaints Authority (AFCA) within 10 business days. Failure: $100,000 penalty.`,
  },
];

const RISK_COLOR: Record<string, string> = {
  Critical: "#ef4444",
  High: "#f59e0b",
  Medium: "#3b82f6",
  Low: "#10b981",
};

function riskClass(r: string) {
  return { Critical: "severity-critical", High: "severity-warning", Medium: "severity-info", Low: "severity-low" }[r] ?? "severity-info";
}

export default function ObligationExtractor() {
  const { activeMarket, market } = useRegion();
  const currency = activeMarket?.currency ?? "AUD";
  const [text, setText] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<ExtractionResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState<Set<string>>(new Set());

  async function extract() {
    if (!text.trim()) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await fetch("/api/extract-obligations", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, market }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setResult(data);
    } catch {
      setError("Extraction failed — please try again.");
    } finally {
      setLoading(false);
    }
  }

  function markSaved(id: string) {
    setSaved((prev) => new Set([...prev, id]));
  }

  function downloadExtracted() {
    if (!result) return;
    const rows = result.obligations.map((o) => ({
      obligation_id: o.obligation_id,
      obligation_name: o.obligation_name,
      regulatory_body: o.regulatory_body,
      category: o.category,
      risk_rating: o.risk_rating,
      penalty_max_aud: o.penalty_max_aud,
      frequency: o.frequency,
      description: o.description,
      key_requirements: o.key_requirements,
      source_legislation: o.source_legislation,
      market: o.market,
    }));
    const headers = Object.keys(rows[0]).join(",");
    const csvRows = rows.map((r) => Object.values(r).map((v) => `"${String(v).replace(/"/g, '""')}"`).join(","));
    const csv = [headers, ...csvRows].join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `extracted-obligations-${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div>
      <div className="card">
        <div className="card-header">
          <h2>AI Obligation Extractor</h2>
          <span className="badge" style={{ background: "rgba(168,85,247,0.15)", color: "#a855f7" }}>
            G-14 · AI-Powered
          </span>
        </div>

        <p style={{ fontSize: 13, color: "var(--text-secondary)", marginBottom: 12, lineHeight: 1.6 }}>
          Paste regulation text — a rule determination, legislative instrument, or policy document.
          The AI extracts structured compliance obligations ready to add to your register.
        </p>

        <div style={{ display: "flex", gap: 8, marginBottom: 10, flexWrap: "wrap", alignItems: "center" }}>
          <span style={{ fontSize: 12, color: "var(--text-muted)" }}>Examples:</span>
          {EXAMPLE_REGS.map((ex) => (
            <button key={ex.label} className="filter-btn" style={{ fontSize: 11 }} onClick={() => setText(ex.text)}>
              {ex.label}
            </button>
          ))}
        </div>

        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Paste regulation text here…

Example: 'AEMC Rule Change ERC0311 — DER operators with installed capacity above 30kW must register with AEMO within 30 days. Failure to register: $10,000/day civil penalty…'"
          style={{
            width: "100%", minHeight: 160, padding: "10px 12px",
            background: "var(--bg-panel)", border: "1px solid var(--border)",
            borderRadius: 8, color: "var(--text-primary)", fontSize: 13,
            lineHeight: 1.6, resize: "vertical", fontFamily: "inherit",
            boxSizing: "border-box",
          }}
        />

        <div style={{ marginTop: 10, display: "flex", gap: 10, alignItems: "center" }}>
          <button
            onClick={extract}
            disabled={loading || !text.trim()}
            style={{
              padding: "8px 20px", border: "none", borderRadius: 8, fontWeight: 700, fontSize: 13,
              cursor: loading || !text.trim() ? "not-allowed" : "pointer",
              background: loading || !text.trim() ? "var(--bg-panel)" : "rgba(168,85,247,0.9)",
              color: loading || !text.trim() ? "var(--text-muted)" : "#fff",
              transition: "background 0.2s",
            }}
          >
            {loading ? "⏳ Extracting…" : "⚡ Extract Obligations"}
          </button>
          {text && (
            <button onClick={() => { setText(""); setResult(null); setError(null); }}
              style={{ fontSize: 12, color: "var(--text-muted)", background: "none", border: "none", cursor: "pointer" }}>
              Clear
            </button>
          )}
          <span style={{ fontSize: 11, color: "var(--text-muted)", marginLeft: "auto" }}>
            {text.length.toLocaleString()} / 5,000 chars
          </span>
        </div>
      </div>

      {error && (
        <div className="card" style={{ background: "rgba(239,68,68,0.05)", borderColor: "rgba(239,68,68,0.2)" }}>
          <p style={{ color: "var(--accent-red)", margin: 0, fontSize: 13 }}>⚠ {error}</p>
        </div>
      )}

      {result && (
        <div className="card">
          <div className="card-header">
            <div>
              <h2>Extracted Obligations</h2>
              <span style={{ fontSize: 12, color: "var(--text-muted)" }}>Review before adding to register</span>
            </div>
            <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
              <span className="badge" style={{ background: "rgba(16,185,129,0.15)", color: "#10b981" }}>
                {result.count} extracted
              </span>
              {result.count > 0 && (
                <button
                  onClick={downloadExtracted}
                  style={{ fontSize: 11, padding: "3px 10px", background: "rgba(79,143,247,0.1)", color: "var(--accent-blue)", border: "1px solid rgba(79,143,247,0.2)", borderRadius: 5, cursor: "pointer" }}
                >
                  ↓ CSV
                </button>
              )}
            </div>
          </div>

          {result.obligations.length === 0 ? (
            <p style={{ color: "var(--text-muted)", fontSize: 13, padding: "12px 0" }}>
              No obligations could be extracted. Try pasting text with clear compliance requirements.
            </p>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              {result.obligations.map((obl) => {
                const isSaved = saved.has(obl.obligation_id);
                return (
                  <div key={obl.obligation_id} style={{
                    padding: "14px 16px",
                    background: isSaved ? "rgba(16,185,129,0.05)" : "var(--bg-panel)",
                    borderRadius: 10,
                    border: isSaved ? "1px solid rgba(16,185,129,0.2)" : "1px solid var(--border)",
                    borderLeft: `4px solid ${RISK_COLOR[obl.risk_rating] ?? "#6b7280"}`,
                  }}>
                    <div style={{ display: "flex", gap: 10, alignItems: "flex-start" }}>
                      <div style={{ flex: 1 }}>
                        <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap", marginBottom: 6 }}>
                          <span style={{ fontSize: 13, fontWeight: 700, color: "var(--text-primary)" }}>
                            {obl.obligation_name}
                          </span>
                          <span className={`severity ${riskClass(obl.risk_rating)}`}>{obl.risk_rating}</span>
                          <span style={{
                            fontSize: 11, padding: "1px 6px", borderRadius: 3,
                            background: "rgba(79,143,247,0.1)", color: "var(--accent-blue)",
                          }}>
                            {obl.category}
                          </span>
                        </div>

                        <div style={{ fontSize: 12, color: "var(--text-secondary)", lineHeight: 1.6, marginBottom: 8 }}>
                          {obl.description}
                        </div>

                        <div style={{ display: "flex", gap: 16, fontSize: 11, color: "var(--text-muted)", flexWrap: "wrap" }}>
                          <span><strong>Body:</strong> {obl.regulatory_body}</span>
                          <span><strong>Frequency:</strong> {obl.frequency}</span>
                          <span style={{ color: RISK_COLOR[obl.risk_rating] ?? "inherit", fontWeight: 600 }}>
                            <strong>Max penalty:</strong> {formatCurrencyFull(obl.penalty_max_aud, currency)}
                          </span>
                          <span><strong>Legislation:</strong> {obl.source_legislation}</span>
                        </div>

                        {obl.key_requirements && (
                          <div style={{ marginTop: 8, fontSize: 12, color: "var(--text-muted)", lineHeight: 1.5 }}>
                            <strong>Key requirements:</strong> {obl.key_requirements}
                          </div>
                        )}
                      </div>

                      <div style={{ flexShrink: 0, display: "flex", flexDirection: "column", gap: 6 }}>
                        {!isSaved ? (
                          <button
                            onClick={() => markSaved(obl.obligation_id)}
                            style={{
                              padding: "5px 12px", borderRadius: 6, border: "none", cursor: "pointer",
                              background: "rgba(16,185,129,0.9)", color: "#fff", fontSize: 12, fontWeight: 600,
                            }}
                          >
                            + Add to Register
                          </button>
                        ) : (
                          <span style={{
                            padding: "5px 12px", borderRadius: 6, fontSize: 12, fontWeight: 600,
                            background: "rgba(16,185,129,0.15)", color: "#10b981",
                          }}>
                            ✓ Added
                          </span>
                        )}
                        <span style={{ fontSize: 10, color: "var(--text-muted)", textAlign: "center" }}>
                          {obl.obligation_id}
                        </span>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          <div style={{
            marginTop: 16, padding: "10px 14px",
            background: "rgba(168,85,247,0.06)", borderRadius: 8,
            border: "1px solid rgba(168,85,247,0.15)",
            fontSize: 12, color: "var(--text-muted)", lineHeight: 1.6,
          }}>
            <strong style={{ color: "#a855f7" }}>AI extraction note:</strong> Obligations are AI-extracted and require
            human review before adding to the official register. Verify obligation names, regulatory bodies,
            penalty values and frequencies against the source document. Extracted obligations are assigned
            provisional IDs (EXTRACTED-xxx) and marked Pending Review.
          </div>
        </div>
      )}
    </div>
  );
}
