import { useState, useMemo } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
  ReferenceLine,
  Area,
  ComposedChart,
  Legend,
} from "recharts";
import { useApi } from "../hooks/useApi";
import { useRegion } from "../context/RegionContext";
import { LoadingPage } from "./LoadingSkeleton";
import { formatCurrency } from "../utils/currency";

interface YearlyForecast {
  year: number;
  baseline_tco2e: number;
  projected_tco2e: number;
  breach: boolean;
  shortfall_cost_aud: number;
}

interface CompanyForecast {
  company: string;
  current_scope1: number;
  trajectory: YearlyForecast[];
  first_breach_year: number | null;
}

interface HeadroomItem {
  company: string;
  current_tco2e: number;
  baseline_tco2e: number;
  headroom_tco2e: number;
  headroom_pct: number;
  status: "safe" | "warning" | "breach";
}

interface ForecastData {
  forecasts: CompanyForecast[];
  headroom: HeadroomItem[];
  safeguard_params: {
    baseline_decline_rate: number;
    accu_price_aud: number;
    shortfall_multiplier: number;
    note: string;
  };
}

function formatNum(val: number): string {
  if (val >= 1e6) return `${(val / 1e6).toFixed(1)}M`;
  if (val >= 1e3) return `${(val / 1e3).toFixed(0)}K`;
  return val.toFixed(0);
}

export default function EmissionsForecaster() {
  const { activeMarket } = useRegion();
  const currency = activeMarket?.currency ?? "AUD";
  const { data, loading } = useApi<ForecastData>("/api/emissions-forecast");
  const [selectedCompany, setSelectedCompany] = useState<string>("");

  const forecasts = data?.forecasts || [];
  const params = data?.safeguard_params;

  const activeCompany = selectedCompany || (forecasts.length > 0 ? forecasts[0].company : "");
  const activeForecast = forecasts.find((f) => f.company === activeCompany);

  const chartData = useMemo(() => {
    if (!activeForecast) return [];
    return activeForecast.trajectory.map((y) => ({
      year: y.year,
      baseline: y.baseline_tco2e,
      projected: y.projected_tco2e,
      shortfall: y.shortfall_cost_aud,
      breach: y.breach,
    }));
  }, [activeForecast]);

  const breachingCompanies = forecasts.filter((f) => f.first_breach_year !== null);
  const totalExposure = forecasts.reduce((sum, f) => {
    const lastYear = f.trajectory[f.trajectory.length - 1];
    return sum + (lastYear?.shortfall_cost_aud || 0);
  }, 0);
  const headroom = data?.headroom || [];

  if (loading) return <LoadingPage />;

  return (
    <div>
      <div className="stats-row">
        <div className="stat-card">
          <div className="label">Companies Tracked</div>
          <div className="value blue">{forecasts.length}</div>
        </div>
        <div className="stat-card">
          <div className="label">Will Breach Baseline</div>
          <div className="value red">{breachingCompanies.length}</div>
        </div>
        <div className="stat-card">
          <div className="label">2029 Exposure (All)</div>
          <div className="value amber">{formatCurrency(totalExposure, currency)}</div>
        </div>
        <div className="stat-card">
          <div className="label">Baseline Decline</div>
          <div className="value">{((params?.baseline_decline_rate || 0.049) * 100).toFixed(1)}%/yr</div>
        </div>
      </div>

      <div className="filters">
        {forecasts.map((f) => (
          <button
            key={f.company}
            className={`filter-btn ${f.company === activeCompany ? "active" : ""}`}
            onClick={() => setSelectedCompany(f.company)}
          >
            {f.company.length > 20 ? f.company.slice(0, 18) + "…" : f.company}
            {f.first_breach_year && (
              <span style={{ color: "var(--accent-red)", marginLeft: 4, fontSize: 10 }}>⚠</span>
            )}
          </button>
        ))}
      </div>

      {activeForecast && (
        <>
          <div className="card">
            <div className="card-header">
              <h2>Safeguard Trajectory — {activeForecast.company}</h2>
              {activeForecast.first_breach_year ? (
                <span className="badge severity-critical">
                  Breach projected {activeForecast.first_breach_year}
                </span>
              ) : (
                <span className="badge severity-info">On track</span>
              )}
            </div>
            <div className="chart-container" style={{ height: 340 }}>
              <ResponsiveContainer width="100%" height="100%">
                <ComposedChart data={chartData} margin={{ left: 20, right: 20, top: 10, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                  <XAxis dataKey="year" stroke="var(--text-muted)" fontSize={12} />
                  <YAxis
                    tickFormatter={(v) => formatNum(v)}
                    stroke="var(--text-muted)"
                    fontSize={11}
                    label={{ value: "t CO2-e", angle: -90, position: "insideLeft", style: { fill: "var(--text-muted)", fontSize: 11 } }}
                  />
                  <Tooltip
                    contentStyle={{ background: "var(--bg-card)", border: "1px solid var(--border)", borderRadius: 8, fontSize: 12 }}
                    formatter={(val: number, name: string) => [
                      formatNum(val) + (name === "shortfall" ? " AUD" : " t CO2-e"),
                      name === "baseline" ? "Safeguard Baseline" : name === "projected" ? "Projected Emissions" : "Shortfall Cost",
                    ]}
                  />
                  <Legend
                    wrapperStyle={{ fontSize: 12, color: "var(--text-secondary)" }}
                    formatter={(value) =>
                      value === "baseline" ? "Safeguard Baseline" : value === "projected" ? "Projected Emissions" : value
                    }
                  />
                  <Area
                    type="monotone"
                    dataKey="baseline"
                    fill="rgba(16, 185, 129, 0.1)"
                    stroke="transparent"
                  />
                  <Line
                    type="monotone"
                    dataKey="baseline"
                    stroke="#10B981"
                    strokeWidth={2}
                    strokeDasharray="8 4"
                    dot={false}
                    name="baseline"
                  />
                  <Line
                    type="monotone"
                    dataKey="projected"
                    stroke="var(--accent-red)"
                    strokeWidth={2.5}
                    dot={{ fill: "var(--accent-red)", r: 4 }}
                    name="projected"
                  />
                  {activeForecast.first_breach_year && (
                    <ReferenceLine
                      x={activeForecast.first_breach_year}
                      stroke="var(--accent-amber)"
                      strokeDasharray="4 4"
                      label={{ value: "Breach", fill: "var(--accent-amber)", fontSize: 11, position: "top" }}
                    />
                  )}
                </ComposedChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="card">
            <div className="card-header">
              <h2>Year-by-Year Projection</h2>
              <span className="badge" style={{ background: "rgba(79,143,247,0.15)", color: "var(--accent-blue)" }}>
                ACCU @ ${params?.accu_price_aud || 82}/t · {((params?.shortfall_multiplier || 2.75) * 100).toFixed(0)}% multiplier
              </span>
            </div>
            <div style={{ overflowX: "auto" }}>
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Year</th>
                    <th>Safeguard Baseline</th>
                    <th>Projected Emissions</th>
                    <th>Gap</th>
                    <th>Status</th>
                    <th>Shortfall Cost</th>
                  </tr>
                </thead>
                <tbody>
                  {activeForecast.trajectory.map((y) => {
                    const gap = y.projected_tco2e - y.baseline_tco2e;
                    return (
                      <tr key={y.year}>
                        <td style={{ fontWeight: 600 }}>{y.year}</td>
                        <td className="number">{formatNum(y.baseline_tco2e)} t</td>
                        <td className="number">{formatNum(y.projected_tco2e)} t</td>
                        <td className="number" style={{ color: gap > 0 ? "var(--accent-red)" : "var(--accent-green)" }}>
                          {gap > 0 ? "+" : ""}{formatNum(gap)} t
                        </td>
                        <td>
                          {y.breach ? (
                            <span className="badge severity-critical">BREACH</span>
                          ) : (
                            <span className="badge severity-info">Compliant</span>
                          )}
                        </td>
                        <td className="number" style={{ color: y.shortfall_cost_aud > 0 ? "var(--accent-red)" : "inherit" }}>
                          {y.shortfall_cost_aud > 0 ? formatCurrency(y.shortfall_cost_aud, currency) : "—"}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}

      {headroom.length > 0 && (
        <div className="card" style={{ marginTop: 16 }}>
          <div className="card-header">
            <h2>Compliance Headroom — Current Year</h2>
            <span className="badge" style={{ background: "rgba(16,185,129,0.15)", color: "#10B981" }}>
              {headroom.filter((h) => h.status === "safe").length} safe · {headroom.filter((h) => h.status === "warning").length} at risk · {headroom.filter((h) => h.status === "breach").length} breach
            </span>
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            {headroom.map((h) => {
              const safeColor = "#10B981";
              const warnColor = "var(--accent-amber)";
              const breachColor = "var(--accent-red)";
              const barColor = h.status === "safe" ? safeColor : h.status === "warning" ? warnColor : breachColor;
              const fillPct = Math.max(0, Math.min(100, h.status === "breach"
                ? 100
                : 100 - Math.abs(h.headroom_pct)));
              return (
                <div key={h.company} style={{ display: "flex", alignItems: "center", gap: 12 }}>
                  <div style={{ width: 180, fontSize: 12, color: "var(--text-secondary)", textAlign: "right", flexShrink: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {h.company.length > 22 ? h.company.slice(0, 20) + "…" : h.company}
                  </div>
                  <div style={{ flex: 1, background: "var(--bg-panel)", borderRadius: 4, height: 18, position: "relative", overflow: "hidden" }}>
                    <div style={{
                      width: `${fillPct}%`,
                      height: "100%",
                      background: barColor,
                      opacity: 0.75,
                      borderRadius: 4,
                      transition: "width 0.6s ease",
                    }} />
                    {h.status === "breach" && (
                      <div style={{
                        position: "absolute", inset: 0,
                        background: "repeating-linear-gradient(45deg, transparent, transparent 4px, rgba(0,0,0,0.15) 4px, rgba(0,0,0,0.15) 8px)",
                        borderRadius: 4,
                      }} />
                    )}
                  </div>
                  <div style={{ width: 90, fontSize: 12, flexShrink: 0, textAlign: "right" }}>
                    <span style={{ color: barColor, fontWeight: 600 }}>
                      {h.status === "breach" ? "−" : "+"}{formatNum(Math.abs(h.headroom_tco2e))} t
                    </span>
                  </div>
                  <div style={{ width: 70, fontSize: 11, flexShrink: 0 }}>
                    <span className={`badge ${h.status === "safe" ? "severity-info" : h.status === "warning" ? "severity-warning" : "severity-critical"}`}
                      style={{ fontSize: 10 }}>
                      {h.status === "breach" ? "BREACH" : h.status === "warning" ? "AT RISK" : "SAFE"}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
          <div style={{ marginTop: 12, fontSize: 11, color: "var(--text-muted)" }}>
            Bar shows % of baseline consumed. Hatched = breach threshold exceeded. AT RISK = &lt;15% headroom remaining.
          </div>
        </div>
      )}

      <div className="card" style={{ marginTop: 16, padding: "12px 16px", background: "rgba(245, 158, 11, 0.08)", border: "1px solid rgba(245, 158, 11, 0.2)", borderRadius: 8 }}>
        <p style={{ margin: 0, fontSize: 12, color: "var(--accent-amber)", lineHeight: 1.6 }}>
          <strong>Safeguard Mechanism:</strong> {params?.note || "Baselines decline 4.9% per year. Shortfall charge is 275% of prevailing ACCU price."}
          {" "}Projected emissions assume a 2% annual reduction rate — adjust based on operational plans and abatement investments.
        </p>
      </div>
    </div>
  );
}
