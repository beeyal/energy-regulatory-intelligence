import { useState } from "react";
import { useApi } from "../hooks/useApi";
import { formatCurrency } from "../utils/currency";

// ── Types ─────────────────────────────────────────────────────────────────────

interface MarketStat {
  code: string;
  name: string;
  flag: string;
  currency: string;
  market_name: string;
  data_available: string;
  enforcement_count: number;
  total_penalty: number;
  last_enforcement: string;
  critical_obligations: number;
  total_obligations: number;
  avg_risk_score: number;
  headroom_pct: number | null;
  recent_notices: number;
  status: "Critical" | "Attention" | "Compliant";
}

interface PostureData {
  markets: MarketStat[];
  summary: {
    total_markets: number;
    data_available: number;
    critical_markets: number;
    attention_markets: number;
    total_global_exposure: number;
  };
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function statusColor(s: string): string {
  return s === "Critical" ? "#ef4444" : s === "Attention" ? "#f59e0b" : "#10b981";
}
function statusBg(s: string): string {
  return s === "Critical" ? "rgba(239,68,68,0.1)" : s === "Attention" ? "rgba(245,158,11,0.1)" : "rgba(16,185,129,0.1)";
}
function scoreColor(n: number): string {
  return n >= 65 ? "#ef4444" : n >= 45 ? "#f59e0b" : "#10b981";
}

// ── Risk arc gauge ────────────────────────────────────────────────────────────

function RiskArc({ score }: { score: number }) {
  const r = 22;
  const circ = 2 * Math.PI * r;
  const arc = (score / 100) * circ * 0.75; // 270° sweep
  const color = scoreColor(score);
  return (
    <svg width={56} height={44} viewBox="0 0 56 44">
      {/* background arc */}
      <circle cx={28} cy={32} r={r} fill="none" stroke="var(--border)" strokeWidth={4}
        strokeDasharray={`${circ * 0.75} ${circ}`}
        strokeLinecap="round"
        transform="rotate(135 28 32)" />
      {/* foreground arc */}
      <circle cx={28} cy={32} r={r} fill="none" stroke={color} strokeWidth={4}
        strokeDasharray={`${arc} ${circ}`}
        strokeLinecap="round"
        transform="rotate(135 28 32)" />
      <text x={28} y={35} textAnchor="middle" fontSize={12} fontWeight={800} fill={color}>{score}</text>
    </svg>
  );
}

// ── Market card ───────────────────────────────────────────────────────────────

function MarketCard({ m, selected, onClick }: { m: MarketStat; selected: boolean; onClick: () => void }) {
  const hasData = m.data_available === "true";
  const sc = statusColor(m.status);
  const sb = statusBg(m.status);

  return (
    <div
      onClick={onClick}
      style={{
        background: selected ? "var(--bg-card-hover)" : "var(--bg-card)",
        border: selected ? `1px solid ${sc}66` : "1px solid var(--border)",
        borderRadius: "var(--radius-lg)",
        padding: "16px 18px",
        cursor: "pointer",
        transition: "all 0.15s ease",
        position: "relative",
        overflow: "hidden",
      }}
    >
      {/* Status indicator strip */}
      <div style={{
        position: "absolute", top: 0, left: 0, right: 0, height: 3,
        background: sc, opacity: 0.8,
      }} />

      {/* Top row: flag + name + status */}
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 10 }}>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 7 }}>
            <span style={{ fontSize: 22 }}>{m.flag}</span>
            <div>
              <div style={{ fontSize: 13, fontWeight: 700, color: "var(--text-primary)", lineHeight: 1.2 }}>{m.name}</div>
              <div style={{ fontSize: 10, color: "var(--text-muted)" }}>{m.market_name}</div>
            </div>
          </div>
        </div>
        <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 4 }}>
          <span style={{
            fontSize: 10, fontWeight: 700, padding: "2px 8px",
            borderRadius: 10, background: sb, color: sc,
            letterSpacing: "0.05em",
          }}>
            {m.status.toUpperCase()}
          </span>
          {!hasData && (
            <span style={{ fontSize: 9, color: "var(--text-muted)", background: "var(--border)", padding: "1px 5px", borderRadius: 4 }}>
              PREVIEW
            </span>
          )}
        </div>
      </div>

      {/* Risk gauge + key stats */}
      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
        <RiskArc score={m.avg_risk_score} />
        <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 5 }}>
          <div style={{ display: "flex", justifyContent: "space-between" }}>
            <span style={{ fontSize: 11, color: "var(--text-muted)" }}>Critical Obs</span>
            <span style={{
              fontSize: 11, fontWeight: 700,
              color: m.critical_obligations > 0 ? "#ef4444" : "var(--text-secondary)",
            }}>
              {m.critical_obligations}/{m.total_obligations}
            </span>
          </div>
          <div style={{ display: "flex", justifyContent: "space-between" }}>
            <span style={{ fontSize: 11, color: "var(--text-muted)" }}>Enforcement</span>
            <span style={{ fontSize: 11, fontWeight: 700, color: m.enforcement_count > 5 ? "#f59e0b" : "var(--text-secondary)" }}>
              {m.enforcement_count}
            </span>
          </div>
          <div style={{ display: "flex", justifyContent: "space-between" }}>
            <span style={{ fontSize: 11, color: "var(--text-muted)" }}>Penalties</span>
            <span style={{ fontSize: 11, fontWeight: 700, color: "var(--text-secondary)" }}>
              {formatCurrency(m.total_penalty, m.currency)}
            </span>
          </div>
        </div>
      </div>

      {/* Emissions headroom bar */}
      {m.headroom_pct !== null && (
        <div style={{ marginTop: 10 }}>
          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 3 }}>
            <span style={{ fontSize: 10, color: "var(--text-muted)" }}>Emissions headroom</span>
            <span style={{
              fontSize: 10, fontWeight: 700,
              color: m.headroom_pct < 0 ? "#ef4444" : m.headroom_pct < 10 ? "#f59e0b" : "#10b981",
            }}>
              {m.headroom_pct > 0 ? "+" : ""}{m.headroom_pct.toFixed(1)}%
            </span>
          </div>
          <div style={{ height: 4, background: "var(--border)", borderRadius: 2, overflow: "hidden" }}>
            <div style={{
              height: "100%",
              width: `${Math.min(100, Math.max(0, 50 + m.headroom_pct))}%`,
              background: m.headroom_pct < 0 ? "#ef4444" : m.headroom_pct < 10 ? "#f59e0b" : "#10b981",
              borderRadius: 2,
            }} />
          </div>
        </div>
      )}
    </div>
  );
}

// ── Detail panel ──────────────────────────────────────────────────────────────

function MarketDetail({ m }: { m: MarketStat }) {
  const sc = statusColor(m.status);
  return (
    <div style={{
      background: "var(--bg-card)",
      border: `1px solid ${sc}33`,
      borderRadius: "var(--radius-lg)",
      padding: "20px 24px",
      marginTop: 16,
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 16 }}>
        <span style={{ fontSize: 32 }}>{m.flag}</span>
        <div>
          <div style={{ fontSize: 16, fontWeight: 800, color: "var(--text-primary)" }}>{m.name} — {m.market_name}</div>
          <div style={{ fontSize: 12, color: "var(--text-muted)" }}>{m.code} · {m.currency}</div>
        </div>
        <div style={{ marginLeft: "auto" }}>
          <span style={{
            fontSize: 11, fontWeight: 700, padding: "4px 12px",
            borderRadius: 12, background: statusBg(m.status), color: sc,
          }}>
            {m.status}
          </span>
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12 }}>
        {[
          { label: "Risk Score", value: String(m.avg_risk_score), color: scoreColor(m.avg_risk_score) },
          { label: "Critical Obligations", value: `${m.critical_obligations} / ${m.total_obligations}`, color: m.critical_obligations > 0 ? "#ef4444" : "#10b981" },
          { label: "Enforcement Actions", value: String(m.enforcement_count), color: m.enforcement_count > 5 ? "#f59e0b" : "var(--text-primary)" },
          { label: "Total Penalties", value: formatCurrency(m.total_penalty, m.currency), color: "var(--text-primary)" },
        ].map((stat) => (
          <div key={stat.label} style={{
            background: "var(--bg-secondary)",
            borderRadius: "var(--radius)",
            padding: "12px 14px",
          }}>
            <div style={{ fontSize: 11, color: "var(--text-muted)", marginBottom: 4, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em" }}>
              {stat.label}
            </div>
            <div style={{ fontSize: 20, fontWeight: 800, color: stat.color }}>{stat.value}</div>
          </div>
        ))}
      </div>

      {m.headroom_pct !== null && (
        <div style={{ marginTop: 14, padding: "12px 14px", background: "var(--bg-secondary)", borderRadius: "var(--radius)" }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 8 }}>
            Emissions Compliance Headroom (Current Year)
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <div style={{ flex: 1, height: 8, background: "var(--border)", borderRadius: 4, overflow: "hidden" }}>
              <div style={{
                height: "100%",
                width: `${Math.min(100, Math.max(2, 50 + m.headroom_pct))}%`,
                background: m.headroom_pct < 0 ? "#ef4444" : m.headroom_pct < 10 ? "#f59e0b" : "#10b981",
                borderRadius: 4,
                transition: "width 0.5s ease",
              }} />
            </div>
            <span style={{
              fontWeight: 800, fontSize: 16,
              color: m.headroom_pct < 0 ? "#ef4444" : m.headroom_pct < 10 ? "#f59e0b" : "#10b981",
            }}>
              {m.headroom_pct > 0 ? "+" : ""}{m.headroom_pct.toFixed(1)}%
            </span>
            <span style={{ fontSize: 12, color: "var(--text-muted)" }}>
              {m.headroom_pct < 0 ? "In breach — requires offsets" : m.headroom_pct < 10 ? "Near limit" : "Compliant"}
            </span>
          </div>
        </div>
      )}

      {m.last_enforcement && (
        <div style={{ marginTop: 10, fontSize: 12, color: "var(--text-muted)" }}>
          Last enforcement action: <strong style={{ color: "var(--text-secondary)" }}>{m.last_enforcement}</strong>
        </div>
      )}
    </div>
  );
}

// ── Summary bar ───────────────────────────────────────────────────────────────

function SummaryBar({ summary }: { summary: PostureData["summary"] }) {
  return (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 10, marginBottom: 16 }}>
      {[
        { label: "Markets Tracked", value: summary.total_markets, color: "var(--accent-blue)" },
        { label: "Data Available", value: summary.data_available, color: "var(--accent-green)" },
        { label: "Critical Markets", value: summary.critical_markets, color: "#ef4444" },
        { label: "Attention Needed", value: summary.attention_markets, color: "#f59e0b" },
        { label: "Total APJ Exposure", value: formatCurrency(summary.total_global_exposure, "AUD"), color: "var(--accent-purple)" },
      ].map((s) => (
        <div key={s.label} style={{
          background: "var(--bg-card)",
          border: "1px solid var(--border)",
          borderRadius: "var(--radius-lg)",
          padding: "14px 16px",
        }}>
          <div style={{ fontSize: 11, fontWeight: 600, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 4 }}>
            {s.label}
          </div>
          <div style={{ fontSize: 22, fontWeight: 800, color: s.color, lineHeight: 1.2 }}>{s.value}</div>
        </div>
      ))}
    </div>
  );
}

// ── Main ──────────────────────────────────────────────────────────────────────

type SortKey = "status" | "risk" | "enforcement" | "obligations";

export default function MarketPosture() {
  const { data, loading } = useApi<PostureData>("/api/market-posture");
  const [selected, setSelected] = useState<string | null>(null);
  const [sortBy, setSortBy] = useState<SortKey>("status");

  if (loading || !data) {
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 10 }}>
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} style={{ height: 80, background: "var(--bg-card)", borderRadius: "var(--radius-lg)" }} />
          ))}
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12 }}>
          {Array.from({ length: 8 }).map((_, i) => (
            <div key={i} style={{ height: 180, background: "var(--bg-card)", borderRadius: "var(--radius-lg)" }} />
          ))}
        </div>
      </div>
    );
  }

  const STATUS_ORDER = { Critical: 0, Attention: 1, Compliant: 2 };
  const sorted = [...data.markets].sort((a, b) => {
    if (sortBy === "status") return (STATUS_ORDER[a.status] ?? 3) - (STATUS_ORDER[b.status] ?? 3);
    if (sortBy === "risk") return b.avg_risk_score - a.avg_risk_score;
    if (sortBy === "enforcement") return b.enforcement_count - a.enforcement_count;
    if (sortBy === "obligations") return b.critical_obligations - a.critical_obligations;
    return 0;
  });

  const selectedMarket = selected ? data.markets.find((m) => m.code === selected) : null;

  return (
    <div>
      <SummaryBar summary={data.summary} />

      {/* Sort controls */}
      <div style={{ display: "flex", gap: 6, marginBottom: 12, alignItems: "center" }}>
        <span style={{ fontSize: 11, color: "var(--text-muted)", fontWeight: 600 }}>Sort by:</span>
        {(["status", "risk", "enforcement", "obligations"] as SortKey[]).map((key) => (
          <button
            key={key}
            onClick={() => setSortBy(key)}
            style={{
              padding: "3px 11px",
              borderRadius: 14,
              border: sortBy === key ? "1px solid var(--accent-blue)" : "1px solid var(--border)",
              background: sortBy === key ? "rgba(79,143,247,0.12)" : "transparent",
              color: sortBy === key ? "var(--accent-blue)" : "var(--text-muted)",
              fontSize: 11,
              fontWeight: 600,
              cursor: "pointer",
              textTransform: "capitalize",
            }}
          >
            {key}
          </button>
        ))}
      </div>

      {/* 4-column grid of market cards */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12 }}>
        {sorted.map((m) => (
          <MarketCard
            key={m.code}
            m={m}
            selected={selected === m.code}
            onClick={() => setSelected(selected === m.code ? null : m.code)}
          />
        ))}
      </div>

      {/* Detail panel for selected market */}
      {selectedMarket && <MarketDetail m={selectedMarket} />}
    </div>
  );
}
