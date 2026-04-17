import { useState } from "react";
import { useApi } from "../hooks/useApi";
import { useRegion } from "../context/RegionContext";
import { LoadingPage } from "./LoadingSkeleton";

interface MetricsAndTargets {
  scope1_tco2e: number;
  scope2_tco2e: number;
  scope3_tco2e: number;
  total_tco2e?: number;
  total_ghg_tco2e?: number;
  reporting_period: string;
  baseline_year?: string;
  target: string;
  intensity_metric?: string;
  carbon_credits_used?: number;
  internal_carbon_price_sgd?: number;
}

interface DisclosureData {
  standard: string;
  mandatory_from: string;
  framework: string;
  reporting_period: string;
  sections: {
    governance: Record<string, string>;
    strategy: Record<string, string | string[]>;
    risk_management: Record<string, string>;
    metrics_and_targets: MetricsAndTargets;
  };
  entity_breakdown: {
    entity: string;
    scope1_tco2e: number;
    scope2_tco2e: number;
    scope3_tco2e: number;
    total_tco2e: number;
  }[];
}

function formatNum(n: number): string {
  if (n >= 1e6) return `${(n / 1e6).toFixed(2)}M`;
  if (n >= 1e3) return `${(n / 1e3).toFixed(1)}K`;
  return n.toFixed(0);
}

function SectionBlock({ title, data }: { title: string; data: Record<string, string | string[]> }) {
  return (
    <div style={{ marginBottom: 16 }}>
      <div style={{
        fontSize: 11, fontWeight: 700, letterSpacing: "0.08em", textTransform: "uppercase",
        color: "var(--text-muted)", marginBottom: 8,
      }}>
        {title}
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
        {Object.entries(data).map(([key, val]) => (
          <div key={key} style={{ display: "flex", gap: 10, alignItems: "flex-start" }}>
            <div style={{
              fontSize: 12, color: "var(--text-muted)", flexShrink: 0, width: 220,
              textTransform: "capitalize",
            }}>
              {key.replace(/_/g, " ")}
            </div>
            <div style={{ fontSize: 12, color: "var(--text-primary)", flex: 1, lineHeight: 1.6 }}>
              {Array.isArray(val)
                ? <ul style={{ margin: 0, paddingLeft: 16 }}>{val.map((v, i) => <li key={i}>{v}</li>)}</ul>
                : val}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function ESGDisclosure() {
  const { market } = useRegion();
  const [standard, setStandard] = useState("ASX");
  const { data, loading } = useApi<DisclosureData>("/api/esg-disclosure", { market, standard });

  if (loading) return <LoadingPage />;

  const metrics = data?.sections?.metrics_and_targets;
  const total = metrics?.total_tco2e ?? metrics?.total_ghg_tco2e ?? 0;

  function downloadJson() {
    if (!data) return;
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `esg-disclosure-${standard.toLowerCase()}-${market}-${new Date().toISOString().slice(0, 10)}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div>
      {/* Standard selector */}
      <div className="card">
        <div className="card-header">
          <h2>ESG Disclosure Template</h2>
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <span className="badge" style={{ background: "rgba(16,185,129,0.15)", color: "#10b981" }}>
              G-17 · APAC Disclosure
            </span>
            <button
              onClick={downloadJson}
              style={{ fontSize: 11, padding: "3px 10px", background: "rgba(79,143,247,0.1)", color: "var(--accent-blue)", border: "1px solid rgba(79,143,247,0.2)", borderRadius: 5, cursor: "pointer" }}
            >
              ↓ JSON
            </button>
          </div>
        </div>

        <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
          {["ASX", "SGX"].map((s) => (
            <button
              key={s}
              className={`filter-btn ${standard === s ? "active" : ""}`}
              onClick={() => setStandard(s)}
            >
              {s === "ASX" ? "🇦🇺 ASX ASRS 1/2" : "🇸🇬 SGX TCFD"}
            </button>
          ))}
        </div>

        <div style={{
          padding: "10px 14px",
          background: "rgba(16,185,129,0.06)",
          border: "1px solid rgba(16,185,129,0.2)",
          borderRadius: 8,
          fontSize: 12,
          lineHeight: 1.6,
          display: "flex",
          gap: 16,
          flexWrap: "wrap",
        }}>
          <div><strong>Standard:</strong> {data?.standard}</div>
          <div><strong>Framework:</strong> {data?.framework}</div>
          <div><strong>Mandatory from:</strong> {data?.mandatory_from}</div>
          <div><strong>Period:</strong> {data?.reporting_period}</div>
        </div>
      </div>

      {/* Emissions summary tiles */}
      {metrics && (
        <div className="stats-row">
          <div className="stat-card">
            <div className="label">Scope 1</div>
            <div className="value red">{formatNum(metrics.scope1_tco2e)} t CO2-e</div>
          </div>
          <div className="stat-card">
            <div className="label">Scope 2</div>
            <div className="value amber">{formatNum(metrics.scope2_tco2e)} t CO2-e</div>
          </div>
          <div className="stat-card">
            <div className="label">Scope 3</div>
            <div className="value" style={{ color: "#a78bfa" }}>{formatNum(metrics.scope3_tco2e)} t CO2-e</div>
          </div>
          <div className="stat-card">
            <div className="label">Total GHG</div>
            <div className="value blue">{formatNum(total)} t CO2-e</div>
          </div>
        </div>
      )}

      {/* Disclosure sections */}
      {data && (
        <div className="card">
          <div className="card-header">
            <h2>Disclosure Sections</h2>
          </div>

          <div style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))",
            gap: 20,
          }}>
            <div>
              <SectionBlock
                title="1. Governance"
                data={data.sections.governance}
              />
            </div>
            <div>
              <SectionBlock
                title="2. Strategy"
                data={data.sections.strategy as Record<string, string | string[]>}
              />
            </div>
            <div>
              <SectionBlock
                title="3. Risk Management"
                data={data.sections.risk_management}
              />
            </div>
            <div>
              <SectionBlock
                title="4. Metrics & Targets"
                data={{
                  ...Object.fromEntries(
                    Object.entries(data.sections.metrics_and_targets).map(([k, v]) => [k, String(v)])
                  ),
                }}
              />
            </div>
          </div>
        </div>
      )}

      {/* Entity breakdown table */}
      {data?.entity_breakdown && data.entity_breakdown.length > 0 && (
        <div className="card">
          <div className="card-header">
            <h2>Entity-Level Emissions Breakdown</h2>
            <span style={{ fontSize: 12, color: "var(--text-muted)" }}>{data.reporting_period}</span>
          </div>
          <div style={{ overflowX: "auto" }}>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Entity</th>
                  <th>Scope 1 (t CO2-e)</th>
                  <th>Scope 2 (t CO2-e)</th>
                  <th>Scope 3 (t CO2-e)</th>
                  <th>Total (t CO2-e)</th>
                  <th>% of Total</th>
                </tr>
              </thead>
              <tbody>
                {data.entity_breakdown.map((e, i) => (
                  <tr key={i}>
                    <td style={{ fontWeight: 500 }}>{e.entity}</td>
                    <td className="number" style={{ color: "var(--accent-red)" }}>{formatNum(e.scope1_tco2e)}</td>
                    <td className="number" style={{ color: "var(--accent-amber)" }}>{formatNum(e.scope2_tco2e)}</td>
                    <td className="number" style={{ color: "#a78bfa" }}>{formatNum(e.scope3_tco2e)}</td>
                    <td className="number">{formatNum(e.total_tco2e)}</td>
                    <td className="number" style={{ color: "var(--text-muted)" }}>
                      {total > 0 ? `${((e.total_tco2e / total) * 100).toFixed(1)}%` : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div style={{
            marginTop: 12, padding: "10px 14px",
            background: "rgba(79,143,247,0.06)", borderRadius: 8,
            fontSize: 12, color: "var(--text-muted)", lineHeight: 1.6,
          }}>
            <strong>Disclosure note:</strong> Scope 1 = direct combustion and process emissions.
            Scope 2 = purchased electricity and heat (market-based method).
            Scope 3 = material upstream and downstream value chain emissions (Category 1 & 11).
            All figures in metric tonnes CO2 equivalent (t CO2-e). Reporting period: {data.reporting_period}.
          </div>
        </div>
      )}
    </div>
  );
}
