import { useState } from "react";
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, BarChart, Bar, Cell,
} from "recharts";
import { useApi } from "../hooks/useApi";
import { useRegion } from "../context/RegionContext";
import { formatCurrency } from "../utils/currency";

// ── Types ────────────────────────────────────────────────────────────────────

interface Insight {
  insight_type: string;
  entity_name: string;
  detail: string;
  metric_value: number;
  period: string;
  severity: string;
}

interface OffenderEntry {
  rank: number;
  company_name: string;
  total_penalty: number;
  action_count: number;
  last_action: string;
  pct_of_max: number;
  severity: string;
}

interface SectorEntry {
  breach_type: string;
  total_penalty: number;
  count: number;
  pct_of_max: number;
}

interface EmissionsEntry {
  corporation_name: string;
  scope1: number;
  scope2: number;
  total: number;
  pct_of_max: number;
}

interface InsightsData {
  insights: Insight[];
  grouped: Record<string, Insight[]>;
  summary: {
    total_exposure: number;
    critical_count: number;
    warning_count: number;
    total_actions: number;
    top_offender: string | null;
    yoy_change: number | null;
  };
  penalty_timeline: { year: string; total_penalty: number; action_count: number }[];
  offenders_leaderboard: OffenderEntry[];
  sector_breakdown: SectorEntry[];
  emissions_profile: EmissionsEntry[];
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function severityColor(s: string): string {
  switch ((s || "").toLowerCase()) {
    case "critical": return "var(--accent-red)";
    case "warning":  return "var(--accent-amber)";
    default:         return "var(--accent-blue)";
  }
}

function severityBg(s: string): string {
  switch ((s || "").toLowerCase()) {
    case "critical": return "rgba(248,113,113,0.12)";
    case "warning":  return "rgba(251,191,36,0.12)";
    default:         return "rgba(79,143,247,0.12)";
  }
}

function insightMeta(type: string): { label: string; icon: string; color: string; bg: string } {
  switch (type) {
    case "repeat_offender":
      return { label: "Repeat Offender", icon: "⚡", color: "var(--accent-red)", bg: "rgba(248,113,113,0.1)" };
    case "high_emitter":
      return { label: "High Emitter", icon: "🌡", color: "var(--accent-amber)", bg: "rgba(251,191,36,0.1)" };
    case "enforcement_trend":
      return { label: "Enforcement Action", icon: "⚖", color: "var(--accent-purple)", bg: "rgba(167,139,250,0.1)" };
    case "notice_spike":
      return { label: "Obligation Watch", icon: "🔔", color: "var(--accent-cyan)", bg: "rgba(34,211,238,0.1)" };
    default:
      return { label: type, icon: "●", color: "var(--accent-blue)", bg: "rgba(79,143,247,0.1)" };
  }
}

function formatEmissions(val: number): string {
  if (val >= 1e6) return `${(val / 1e6).toFixed(1)}Mt`;
  if (val >= 1e3) return `${(val / 1e3).toFixed(0)}kt`;
  return `${val.toFixed(0)}t`;
}

function formatMillions(val: number): string {
  if (val >= 1e9) return `$${(val / 1e9).toFixed(1)}B`;
  if (val >= 1e6) return `$${(val / 1e6).toFixed(1)}M`;
  if (val >= 1e3) return `$${(val / 1e3).toFixed(0)}K`;
  return `$${val}`;
}

// ── KPI tile ──────────────────────────────────────────────────────────────────

function KpiTile({
  label, value, sub, accent, glow,
}: {
  label: string; value: string; sub?: string; accent: string; glow: string;
}) {
  return (
    <div style={{
      background: "var(--bg-card)",
      border: `1px solid ${accent}33`,
      borderRadius: "var(--radius-lg)",
      padding: "20px 24px",
      display: "flex",
      flexDirection: "column",
      gap: 6,
      boxShadow: `0 0 24px ${glow}`,
      flex: 1,
      minWidth: 0,
    }}>
      <div style={{ fontSize: 11, fontWeight: 600, letterSpacing: "0.08em", color: accent, textTransform: "uppercase" }}>
        {label}
      </div>
      <div style={{ fontSize: 26, fontWeight: 800, color: "var(--text-primary)", lineHeight: 1.1 }}>
        {value}
      </div>
      {sub && (
        <div style={{ fontSize: 12, color: "var(--text-muted)" }}>{sub}</div>
      )}
    </div>
  );
}

// ── Penalty Timeline Chart ────────────────────────────────────────────────────

function PenaltyTimeline({ data, currency }: { data: InsightsData["penalty_timeline"]; currency: string }) {
  if (!data || data.length === 0) return null;
  return (
    <div style={{
      background: "var(--bg-card)",
      border: "1px solid var(--border)",
      borderRadius: "var(--radius-lg)",
      padding: "20px 24px",
    }}>
      <div style={{ marginBottom: 16 }}>
        <div style={{ fontSize: 13, fontWeight: 700, color: "var(--text-primary)" }}>Enforcement Penalty Timeline</div>
        <div style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 2 }}>Total penalties imposed per year</div>
      </div>
      <ResponsiveContainer width="100%" height={180}>
        <AreaChart data={data} margin={{ top: 4, right: 16, left: 0, bottom: 4 }}>
          <defs>
            <linearGradient id="penaltyGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#f87171" stopOpacity={0.35} />
              <stop offset="95%" stopColor="#f87171" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
          <XAxis dataKey="year" tick={{ fontSize: 11, fill: "var(--text-muted)" }} axisLine={false} tickLine={false} />
          <YAxis
            tickFormatter={formatMillions}
            tick={{ fontSize: 11, fill: "var(--text-muted)" }}
            axisLine={false}
            tickLine={false}
            width={52}
          />
          <Tooltip
            formatter={(val: number, name: string) => [
              name === "total_penalty" ? formatCurrency(val, currency) : val,
              name === "total_penalty" ? "Total Penalties" : "Actions",
            ]}
            contentStyle={{
              background: "var(--bg-card-solid)",
              border: "1px solid var(--border-accent)",
              borderRadius: 8,
              fontSize: 12,
            }}
            labelStyle={{ color: "var(--text-primary)", fontWeight: 600 }}
          />
          <Area
            type="monotone"
            dataKey="total_penalty"
            stroke="#f87171"
            strokeWidth={2}
            fill="url(#penaltyGrad)"
            dot={{ fill: "#f87171", r: 3, strokeWidth: 0 }}
            activeDot={{ r: 5, fill: "#f87171" }}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

// ── Offenders Leaderboard ─────────────────────────────────────────────────────

function OffendersLeaderboard({ data, currency }: { data: OffenderEntry[]; currency: string }) {
  if (!data || data.length === 0) return null;
  return (
    <div style={{
      background: "var(--bg-card)",
      border: "1px solid var(--border)",
      borderRadius: "var(--radius-lg)",
      padding: "20px 24px",
    }}>
      <div style={{ marginBottom: 16 }}>
        <div style={{ fontSize: 13, fontWeight: 700, color: "var(--text-primary)" }}>Top Offenders Leaderboard</div>
        <div style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 2 }}>Ranked by cumulative penalties</div>
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        {data.map((entry) => (
          <div key={entry.rank} style={{ display: "flex", alignItems: "center", gap: 12 }}>
            {/* Rank badge */}
            <div style={{
              width: 28,
              height: 28,
              borderRadius: "50%",
              background: entry.rank <= 3 ? severityBg(entry.severity) : "var(--border)",
              border: `1px solid ${entry.rank <= 3 ? severityColor(entry.severity) + "44" : "transparent"}`,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: 11,
              fontWeight: 800,
              color: entry.rank <= 3 ? severityColor(entry.severity) : "var(--text-muted)",
              flexShrink: 0,
            }}>
              {entry.rank}
            </div>

            {/* Name + bar */}
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 4 }}>
                <span style={{
                  fontSize: 13,
                  fontWeight: 600,
                  color: "var(--text-primary)",
                  whiteSpace: "nowrap",
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  maxWidth: "60%",
                }}>
                  {entry.company_name}
                </span>
                <span style={{ fontSize: 12, fontWeight: 700, color: severityColor(entry.severity), flexShrink: 0, marginLeft: 8 }}>
                  {formatCurrency(entry.total_penalty, currency)}
                </span>
              </div>
              {/* Progress bar */}
              <div style={{
                height: 4,
                background: "var(--border)",
                borderRadius: 2,
                overflow: "hidden",
              }}>
                <div style={{
                  height: "100%",
                  width: `${entry.pct_of_max}%`,
                  background: `linear-gradient(90deg, ${severityColor(entry.severity)}, ${severityColor(entry.severity)}88)`,
                  borderRadius: 2,
                  transition: "width 0.6s ease",
                }} />
              </div>
            </div>

            {/* Actions badge */}
            <div style={{
              flexShrink: 0,
              fontSize: 11,
              fontWeight: 600,
              padding: "2px 8px",
              borderRadius: 10,
              background: severityBg(entry.severity),
              color: severityColor(entry.severity),
            }}>
              {entry.action_count}×
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Sector Breakdown ──────────────────────────────────────────────────────────

function SectorBreakdown({ data, currency }: { data: SectorEntry[]; currency: string }) {
  if (!data || data.length === 0) return null;
  const COLORS = ["#f87171", "#fbbf24", "#a78bfa", "#22d3ee", "#34d399", "#4f8ff7", "#fb923c", "#e879f9"];
  return (
    <div style={{
      background: "var(--bg-card)",
      border: "1px solid var(--border)",
      borderRadius: "var(--radius-lg)",
      padding: "20px 24px",
    }}>
      <div style={{ marginBottom: 16 }}>
        <div style={{ fontSize: 13, fontWeight: 700, color: "var(--text-primary)" }}>Breach Type Exposure</div>
        <div style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 2 }}>Penalty value by violation category</div>
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        {data.map((entry, i) => (
          <div key={entry.breach_type}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 5 }}>
              <span style={{
                fontSize: 12,
                color: "var(--text-secondary)",
                whiteSpace: "nowrap",
                overflow: "hidden",
                textOverflow: "ellipsis",
                maxWidth: "65%",
              }}>
                {entry.breach_type}
              </span>
              <div style={{ display: "flex", gap: 8, alignItems: "center", flexShrink: 0 }}>
                <span style={{ fontSize: 11, color: "var(--text-muted)" }}>{entry.count} cases</span>
                <span style={{ fontSize: 12, fontWeight: 700, color: COLORS[i % COLORS.length] }}>
                  {formatCurrency(entry.total_penalty, currency)}
                </span>
              </div>
            </div>
            <div style={{ height: 5, background: "var(--border)", borderRadius: 3, overflow: "hidden" }}>
              <div style={{
                height: "100%",
                width: `${entry.pct_of_max}%`,
                background: COLORS[i % COLORS.length],
                borderRadius: 3,
                opacity: 0.8,
              }} />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Emissions Profile ─────────────────────────────────────────────────────────

function EmissionsProfile({ data }: { data: EmissionsEntry[] }) {
  if (!data || data.length === 0) return null;
  return (
    <div style={{
      background: "var(--bg-card)",
      border: "1px solid var(--border)",
      borderRadius: "var(--radius-lg)",
      padding: "20px 24px",
    }}>
      <div style={{ marginBottom: 16 }}>
        <div style={{ fontSize: 13, fontWeight: 700, color: "var(--text-primary)" }}>Emissions Profile</div>
        <div style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 2 }}>Scope 1 + 2 by corporation (tCO₂-e)</div>
      </div>
      <ResponsiveContainer width="100%" height={200}>
        <BarChart
          data={data}
          layout="vertical"
          margin={{ top: 4, right: 60, left: 0, bottom: 4 }}
        >
          <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" horizontal={false} />
          <XAxis
            type="number"
            tickFormatter={formatEmissions}
            tick={{ fontSize: 10, fill: "var(--text-muted)" }}
            axisLine={false}
            tickLine={false}
          />
          <YAxis
            type="category"
            dataKey="corporation_name"
            tick={{ fontSize: 10, fill: "var(--text-secondary)" }}
            axisLine={false}
            tickLine={false}
            width={130}
            tickFormatter={(v: string) => v.length > 18 ? v.slice(0, 17) + "…" : v}
          />
          <Tooltip
            formatter={(val: number, name: string) => [
              formatEmissions(val),
              name === "scope1" ? "Scope 1" : "Scope 2",
            ]}
            contentStyle={{
              background: "var(--bg-card-solid)",
              border: "1px solid var(--border-accent)",
              borderRadius: 8,
              fontSize: 12,
            }}
            labelStyle={{ color: "var(--text-primary)", fontWeight: 600 }}
          />
          <Bar dataKey="scope1" stackId="a" fill="#fbbf24" fillOpacity={0.85} radius={[0, 0, 0, 0]} />
          <Bar dataKey="scope2" stackId="a" fill="#34d399" fillOpacity={0.7} radius={[0, 3, 3, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

// ── Insight Card ──────────────────────────────────────────────────────────────

function InsightCard({ item, currency, expanded, onToggle }: {
  item: Insight;
  currency: string;
  expanded: boolean;
  onToggle: () => void;
}) {
  const meta = insightMeta(item.insight_type);
  const isEmission = item.insight_type === "high_emitter";

  return (
    <div
      onClick={onToggle}
      style={{
        background: expanded ? "var(--bg-card-hover)" : "var(--bg-card)",
        border: `1px solid ${expanded ? meta.color + "44" : "var(--border)"}`,
        borderRadius: "var(--radius)",
        padding: "14px 16px",
        cursor: "pointer",
        transition: "all 0.2s ease",
        position: "relative",
        overflow: "hidden",
      }}
    >
      {/* Left accent bar */}
      <div style={{
        position: "absolute",
        left: 0,
        top: 0,
        bottom: 0,
        width: 3,
        background: meta.color,
        borderRadius: "var(--radius) 0 0 var(--radius)",
      }} />

      <div style={{ paddingLeft: 8 }}>
        <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 8 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, minWidth: 0 }}>
            {/* Severity pulse dot */}
            <div style={{ position: "relative", flexShrink: 0 }}>
              <div style={{
                width: 8,
                height: 8,
                borderRadius: "50%",
                background: severityColor(item.severity),
                boxShadow: `0 0 6px ${severityColor(item.severity)}`,
              }} />
            </div>
            <span style={{
              fontSize: 13,
              fontWeight: 600,
              color: "var(--text-primary)",
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
            }}>
              {item.entity_name}
            </span>
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: 8, flexShrink: 0 }}>
            <span style={{
              fontSize: 13,
              fontWeight: 800,
              color: meta.color,
            }}>
              {isEmission
                ? formatEmissions(item.metric_value)
                : formatCurrency(item.metric_value, currency)
              }
            </span>
            <span style={{
              fontSize: 10,
              fontWeight: 600,
              padding: "2px 7px",
              borderRadius: 10,
              background: severityBg(item.severity),
              color: severityColor(item.severity),
              letterSpacing: "0.04em",
            }}>
              {item.severity}
            </span>
          </div>
        </div>

        {/* Category + period row */}
        <div style={{ display: "flex", gap: 6, marginTop: 6, alignItems: "center" }}>
          <span style={{
            fontSize: 10,
            fontWeight: 600,
            padding: "1px 7px",
            borderRadius: 8,
            background: meta.bg,
            color: meta.color,
          }}>
            {meta.icon} {meta.label}
          </span>
          <span style={{ fontSize: 11, color: "var(--text-muted)" }}>{item.period}</span>
        </div>

        {/* Expanded detail */}
        {expanded && (
          <div style={{
            marginTop: 10,
            paddingTop: 10,
            borderTop: "1px solid var(--border)",
            fontSize: 12,
            color: "var(--text-secondary)",
            lineHeight: 1.6,
          }}>
            {item.detail}
          </div>
        )}
      </div>
    </div>
  );
}

// ── Filter tabs ───────────────────────────────────────────────────────────────

type FilterTab = "all" | "critical" | "warning" | "info" | "repeat_offender" | "high_emitter" | "enforcement_trend" | "notice_spike";

const FILTER_TABS: { key: FilterTab; label: string; color?: string }[] = [
  { key: "all", label: "All" },
  { key: "critical", label: "Critical", color: "var(--accent-red)" },
  { key: "warning", label: "Warning", color: "var(--accent-amber)" },
  { key: "repeat_offender", label: "Offenders" },
  { key: "high_emitter", label: "Emissions" },
  { key: "enforcement_trend", label: "Penalties" },
  { key: "notice_spike", label: "Obligations" },
];

function filterInsights(insights: Insight[], tab: FilterTab): Insight[] {
  if (tab === "all") return insights;
  if (tab === "critical") return insights.filter((i) => i.severity === "Critical");
  if (tab === "warning") return insights.filter((i) => i.severity === "Warning");
  if (tab === "info") return insights.filter((i) => i.severity === "Info");
  return insights.filter((i) => i.insight_type === tab);
}

// ── Main component ────────────────────────────────────────────────────────────

export default function ComplianceGaps() {
  const { data, loading } = useApi<InsightsData>("/api/compliance-gaps");
  const { activeMarket } = useRegion();
  const currency = activeMarket?.currency ?? "AUD";

  const [activeTab, setActiveTab] = useState<FilterTab>("all");
  const [expandedIdx, setExpandedIdx] = useState<number | null>(null);

  if (loading) {
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
        {/* KPI skeleton */}
        <div style={{ display: "flex", gap: 12 }}>
          {[0, 1, 2, 3].map((i) => (
            <div key={i} style={{ flex: 1, height: 96, background: "var(--bg-card)", borderRadius: "var(--radius-lg)", padding: 20 }}>
              <div className="skeleton-line" style={{ width: "50%", height: 12, marginBottom: 10 }} />
              <div className="skeleton-line" style={{ width: "70%", height: 24 }} />
            </div>
          ))}
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
          {[0, 1].map((i) => (
            <div key={i} style={{ height: 240, background: "var(--bg-card)", borderRadius: "var(--radius-lg)" }} />
          ))}
        </div>
      </div>
    );
  }

  if (!data || !data.insights || data.insights.length === 0) {
    return (
      <div className="empty-state">No compliance insights generated yet. Ensure data is loaded for this market.</div>
    );
  }

  const { summary, penalty_timeline, offenders_leaderboard, sector_breakdown, emissions_profile } = data;
  const filteredInsights = filterInsights(data.insights, activeTab);

  const yoyLabel = summary.yoy_change !== null && summary.yoy_change !== undefined
    ? `${summary.yoy_change >= 0 ? "+" : ""}${summary.yoy_change}% YoY`
    : "trend n/a";

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>

      {/* ── KPI tiles ───────────────────────────────────────────────────────── */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12 }}>
        <KpiTile
          label="Total Penalty Exposure"
          value={formatCurrency(summary.total_exposure, currency)}
          sub={`${summary.total_actions} enforcement actions`}
          accent="var(--accent-red)"
          glow="rgba(248,113,113,0.08)"
        />
        <KpiTile
          label="Critical Alerts"
          value={String(summary.critical_count)}
          sub={`${summary.warning_count} warnings`}
          accent="var(--accent-amber)"
          glow="rgba(251,191,36,0.08)"
        />
        <KpiTile
          label="Top Offender"
          value={summary.top_offender ?? "—"}
          sub="by cumulative penalties"
          accent="var(--accent-purple)"
          glow="rgba(167,139,250,0.08)"
        />
        <KpiTile
          label="Penalty Trend"
          value={yoyLabel}
          sub="vs prior year"
          accent={summary.yoy_change !== null && summary.yoy_change !== undefined && summary.yoy_change > 0 ? "var(--accent-red)" : "var(--accent-green)"}
          glow="rgba(52,211,153,0.08)"
        />
      </div>

      {/* ── Charts row ──────────────────────────────────────────────────────── */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
        <PenaltyTimeline data={penalty_timeline} currency={currency} />
        <EmissionsProfile data={emissions_profile} />
      </div>

      {/* ── Leaderboard + sector row ─────────────────────────────────────────── */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
        <OffendersLeaderboard data={offenders_leaderboard} currency={currency} />
        <SectorBreakdown data={sector_breakdown} currency={currency} />
      </div>

      {/* ── Insight cards ────────────────────────────────────────────────────── */}
      <div style={{
        background: "var(--bg-card)",
        border: "1px solid var(--border)",
        borderRadius: "var(--radius-lg)",
        overflow: "hidden",
      }}>
        {/* Header */}
        <div style={{
          padding: "16px 20px",
          borderBottom: "1px solid var(--border)",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          flexWrap: "wrap",
          gap: 10,
        }}>
          <div>
            <div style={{ fontSize: 13, fontWeight: 700, color: "var(--text-primary)" }}>
              Intelligence Alerts
            </div>
            <div style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 1 }}>
              {filteredInsights.length} of {data.insights.length} insights — click to expand
            </div>
          </div>

          {/* Filter tabs */}
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
            {FILTER_TABS.map((tab) => {
              const count = tab.key === "all"
                ? data.insights.length
                : filterInsights(data.insights, tab.key).length;
              if (count === 0 && tab.key !== "all") return null;
              const isActive = activeTab === tab.key;
              return (
                <button
                  key={tab.key}
                  onClick={(e) => {
                    e.stopPropagation();
                    setActiveTab(tab.key);
                    setExpandedIdx(null);
                  }}
                  style={{
                    padding: "4px 12px",
                    borderRadius: 20,
                    border: isActive
                      ? `1px solid ${tab.color ?? "var(--accent-blue)"}66`
                      : "1px solid var(--border)",
                    background: isActive
                      ? `${tab.color ?? "var(--accent-blue)"}18`
                      : "transparent",
                    color: isActive ? (tab.color ?? "var(--accent-blue)") : "var(--text-muted)",
                    fontSize: 11,
                    fontWeight: 600,
                    cursor: "pointer",
                    transition: "all 0.15s ease",
                  }}
                >
                  {tab.label} {count > 0 && <span style={{ opacity: 0.7 }}>({count})</span>}
                </button>
              );
            })}
          </div>
        </div>

        {/* Card grid */}
        <div style={{
          padding: 16,
          display: "grid",
          gridTemplateColumns: "repeat(2, 1fr)",
          gap: 10,
        }}>
          {filteredInsights.map((item, i) => (
            <InsightCard
              key={`${item.insight_type}-${item.entity_name}-${i}`}
              item={item}
              currency={currency}
              expanded={expandedIdx === i}
              onToggle={() => setExpandedIdx(expandedIdx === i ? null : i)}
            />
          ))}
        </div>

        {filteredInsights.length === 0 && (
          <div style={{ padding: 32, textAlign: "center", color: "var(--text-muted)", fontSize: 13 }}>
            No insights match this filter.
          </div>
        )}
      </div>
    </div>
  );
}
