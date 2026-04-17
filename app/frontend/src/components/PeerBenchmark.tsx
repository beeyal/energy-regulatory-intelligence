import { useState } from "react";
import {
  RadarChart,
  Radar,
  PolarGrid,
  PolarAngleAxis,
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Cell,
} from "recharts";
import { useApi } from "../hooks/useApi";
import { useRegion } from "../context/RegionContext";
import { LoadingPage } from "./LoadingSkeleton";
import { formatCurrency } from "../utils/currency";

interface CompanyBenchmark {
  name: string;
  actions: number;
  total_penalties: number;
  scope1: number;
  scope2: number;
  scope3: number;
  actions_pct: number;
  penalties_pct: number;
  emissions_pct: number;
  compliance_score: number;
}

interface BenchmarkData {
  companies: CompanyBenchmark[];
  market_averages: {
    avg_enforcement_actions: number;
    avg_scope1_tco2e: number;
    avg_compliance_score: number;
  };
}

type SortKey = "compliance_score" | "actions" | "total_penalties" | "scope1";

function ScoreBadge({ score }: { score: number }) {
  const color = score >= 70 ? "#10b981" : score >= 45 ? "#f59e0b" : "#ef4444";
  const label = score >= 70 ? "Low Risk" : score >= 45 ? "Moderate" : "High Risk";
  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 2 }}>
      <svg width={48} height={48} viewBox="0 0 48 48">
        <circle cx={24} cy={24} r={20} fill="none" stroke="var(--border)" strokeWidth={4} />
        <circle
          cx={24} cy={24} r={20} fill="none" stroke={color} strokeWidth={4}
          strokeDasharray={`${score * 1.257} 125.7`}
          strokeLinecap="round"
          style={{ transform: "rotate(-90deg)", transformOrigin: "center" }}
        />
        <text x={24} y={28} textAnchor="middle" fontSize={12} fontWeight={800} fill={color}>{score}</text>
      </svg>
      <span style={{ fontSize: 9, fontWeight: 700, color, textTransform: "uppercase" }}>{label}</span>
    </div>
  );
}

function PercentileBar({ pct, inverse = false }: { pct: number; inverse?: boolean }) {
  const effective = inverse ? 100 - pct : pct;
  const color = effective >= 70 ? "#ef4444" : effective >= 40 ? "#f59e0b" : "#10b981";
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
      <div style={{ width: 60, height: 6, background: "var(--border)", borderRadius: 3, overflow: "hidden" }}>
        <div style={{ height: "100%", width: `${pct}%`, background: color, borderRadius: 3 }} />
      </div>
      <span style={{ fontSize: 10, color: "var(--text-muted)", minWidth: 28 }}>{pct}th</span>
    </div>
  );
}

function formatNum(n: number): string {
  if (n >= 1e6) return `${(n / 1e6).toFixed(1)}M`;
  if (n >= 1e3) return `${(n / 1e3).toFixed(0)}K`;
  return n.toFixed(0);
}

export default function PeerBenchmark() {
  const { activeMarket, market } = useRegion();
  const currency = activeMarket?.currency ?? "AUD";
  const [sortBy, setSortBy] = useState<SortKey>("compliance_score");
  const [selectedCompany, setSelectedCompany] = useState<string | null>(null);
  const { data, loading } = useApi<BenchmarkData>("/api/peer-benchmark", { market });

  if (loading) return <LoadingPage />;

  const companies = [...(data?.companies ?? [])].sort((a, b) => {
    if (sortBy === "compliance_score") return b.compliance_score - a.compliance_score;
    if (sortBy === "actions") return b.actions - a.actions;
    if (sortBy === "total_penalties") return b.total_penalties - a.total_penalties;
    return b.scope1 - a.scope1;
  });

  const avgs = data?.market_averages;
  const selected = selectedCompany ? companies.find((c) => c.name === selectedCompany) : null;

  const radarData = selected ? [
    { metric: "Compliance", value: selected.compliance_score, avg: avgs?.avg_compliance_score ?? 0 },
    { metric: "Low Enforcement", value: 100 - Math.min(100, selected.actions * 20), avg: 100 - Math.min(100, (avgs?.avg_enforcement_actions ?? 0) * 20) },
    { metric: "Low Penalties", value: Math.max(0, 100 - selected.penalties_pct), avg: 50 },
    { metric: "Low Emissions", value: Math.max(0, 100 - selected.emissions_pct), avg: 50 },
    { metric: "Peer Standing", value: companies.findIndex((c) => c.name === selected.name) <= companies.length / 3 ? 85 : 40, avg: 50 },
  ] : [];

  const chartData = companies.slice(0, 12).map((c) => ({
    name: c.name.length > 14 ? c.name.slice(0, 12) + "…" : c.name,
    fullName: c.name,
    score: c.compliance_score,
  }));

  return (
    <div>
      {/* Summary tiles */}
      <div className="stats-row">
        <div className="stat-card">
          <div className="label">Companies Benchmarked</div>
          <div className="value blue">{companies.length}</div>
        </div>
        <div className="stat-card">
          <div className="label">Avg Compliance Score</div>
          <div className="value" style={{ color: "#10b981" }}>{avgs?.avg_compliance_score ?? 0}</div>
        </div>
        <div className="stat-card">
          <div className="label">Avg Enforcement Actions</div>
          <div className="value amber">{avgs?.avg_enforcement_actions ?? 0}</div>
        </div>
        <div className="stat-card">
          <div className="label">Avg Scope 1 Emissions</div>
          <div className="value red">{formatNum(avgs?.avg_scope1_tco2e ?? 0)} t CO2-e</div>
        </div>
      </div>

      {/* Sort controls */}
      <div className="filters">
        <span style={{ fontSize: 12, color: "var(--text-muted)", alignSelf: "center" }}>Sort:</span>
        {(["compliance_score", "actions", "total_penalties", "scope1"] as SortKey[]).map((k) => (
          <button
            key={k}
            className={`filter-btn ${sortBy === k ? "active" : ""}`}
            onClick={() => setSortBy(k)}
          >
            {k === "compliance_score" ? "Compliance Score" : k === "actions" ? "Enforcement Actions" : k === "total_penalties" ? "Total Penalties" : "Scope 1 Emissions"}
          </button>
        ))}
      </div>

      <div style={{ display: "grid", gridTemplateColumns: selected ? "1fr 1fr" : "1fr", gap: 16 }}>
        {/* Company table */}
        <div className="card">
          <div className="card-header">
            <h2>Compliance Benchmark Rankings</h2>
            <span className="badge" style={{ background: "rgba(168,85,247,0.15)", color: "#a855f7" }}>
              G-16 · Peer Analysis
            </span>
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            {companies.slice(0, 15).map((c, i) => (
              <div
                key={c.name}
                onClick={() => setSelectedCompany(selectedCompany === c.name ? null : c.name)}
                style={{
                  display: "flex", gap: 12, alignItems: "center", padding: "8px 12px",
                  borderRadius: 8, cursor: "pointer",
                  background: selectedCompany === c.name ? "rgba(79,143,247,0.08)" : "var(--bg-panel)",
                  border: selectedCompany === c.name ? "1px solid rgba(79,143,247,0.3)" : "1px solid transparent",
                  transition: "background 0.15s",
                }}
              >
                <span style={{ fontSize: 13, fontWeight: 700, color: "var(--text-muted)", width: 20, flexShrink: 0 }}>
                  {i + 1}
                </span>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 13, fontWeight: 600, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {c.name}
                  </div>
                  <div style={{ fontSize: 11, color: "var(--text-muted)", display: "flex", gap: 10, marginTop: 2 }}>
                    <span>{c.actions} actions</span>
                    <span>{formatCurrency(c.total_penalties, currency)} penalties</span>
                    {c.scope1 > 0 && <span>{formatNum(c.scope1)} t S1</span>}
                  </div>
                </div>
                <div style={{ display: "flex", gap: 12, alignItems: "center", flexShrink: 0 }}>
                  <div>
                    <div style={{ fontSize: 10, color: "var(--text-muted)", marginBottom: 2 }}>Enforcement</div>
                    <PercentileBar pct={c.actions_pct} inverse />
                  </div>
                  <div>
                    <div style={{ fontSize: 10, color: "var(--text-muted)", marginBottom: 2 }}>Penalties</div>
                    <PercentileBar pct={c.penalties_pct} inverse />
                  </div>
                  <ScoreBadge score={c.compliance_score} />
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Drill-down panel */}
        {selected && (
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            <div className="card">
              <div className="card-header">
                <h2>{selected.name}</h2>
                <button
                  onClick={() => setSelectedCompany(null)}
                  style={{ fontSize: 11, padding: "2px 8px", background: "var(--bg-panel)", border: "1px solid var(--border)", borderRadius: 4, cursor: "pointer", color: "var(--text-muted)" }}
                >
                  ✕ Close
                </button>
              </div>
              <div style={{ height: 240 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <RadarChart data={radarData}>
                    <PolarGrid stroke="var(--border)" />
                    <PolarAngleAxis dataKey="metric" tick={{ fontSize: 11, fill: "var(--text-muted)" }} />
                    <Radar name="Company" dataKey="value" stroke="var(--accent-blue)" fill="rgba(79,143,247,0.2)" strokeWidth={2} />
                    <Radar name="Market Avg" dataKey="avg" stroke="#10b981" fill="rgba(16,185,129,0.1)" strokeWidth={1.5} strokeDasharray="4 2" />
                    <Tooltip contentStyle={{ background: "var(--bg-card)", border: "1px solid var(--border)", borderRadius: 8, fontSize: 12 }} />
                  </RadarChart>
                </ResponsiveContainer>
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, marginTop: 4 }}>
                {[
                  { label: "Enforcement Actions", value: selected.actions, market: avgs?.avg_enforcement_actions ?? 0, lower_is_better: true },
                  { label: "Total Penalties", value: formatCurrency(selected.total_penalties, currency), market: formatCurrency((avgs?.avg_enforcement_actions ?? 0) * 100_000, currency), lower_is_better: true },
                  { label: "Scope 1 (t CO2-e)", value: formatNum(selected.scope1), market: formatNum(avgs?.avg_scope1_tco2e ?? 0), lower_is_better: true },
                  { label: "Compliance Score", value: selected.compliance_score, market: avgs?.avg_compliance_score ?? 0, lower_is_better: false },
                ].map((item) => (
                  <div key={item.label} style={{ padding: "8px 10px", background: "var(--bg-panel)", borderRadius: 6 }}>
                    <div style={{ fontSize: 10, color: "var(--text-muted)", marginBottom: 3 }}>{item.label}</div>
                    <div style={{ fontSize: 14, fontWeight: 700, color: "var(--text-primary)" }}>{item.value}</div>
                    <div style={{ fontSize: 10, color: "var(--text-muted)" }}>Market avg: {item.market}</div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Score bar chart */}
      <div className="card" style={{ marginTop: 16 }}>
        <div className="card-header">
          <h2>Compliance Scores — All Companies</h2>
          <span style={{ fontSize: 12, color: "var(--text-muted)" }}>Higher = lower enforcement/emissions risk</span>
        </div>
        <div style={{ height: 220 }}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chartData} margin={{ left: 8, right: 8 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis dataKey="name" stroke="var(--text-muted)" fontSize={10} />
              <YAxis domain={[0, 100]} stroke="var(--text-muted)" fontSize={11} />
              <Tooltip
                formatter={(val: number, _: string, props) => [val, props.payload.fullName]}
                contentStyle={{ background: "var(--bg-card)", border: "1px solid var(--border)", borderRadius: 8, fontSize: 12 }}
              />
              <Bar dataKey="score" radius={[4, 4, 0, 0]}>
                {chartData.map((entry, i) => (
                  <Cell
                    key={i}
                    fill={entry.score >= 70 ? "#10b981" : entry.score >= 45 ? "#f59e0b" : "#ef4444"}
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}
