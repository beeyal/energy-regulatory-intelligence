import { useState } from "react";
import { useApi } from "../hooks/useApi";
import { useRegion } from "../context/RegionContext";
import { LoadingPage } from "./LoadingSkeleton";

// ── Types ────────────────────────────────────────────────────────────────────

interface HorizonItem {
  id: string;
  type: "market_notice" | "obligation";
  category: string;
  severity: string;
  title: string;
  body: string;
  source: string;
  date: string;
  reference: string;
}

interface HorizonData {
  items: HorizonItem[];
  summary: {
    total: number;
    critical: number;
    enforcement: number;
    by_category: Record<string, number>;
  };
}

// ── Helpers ───────────────────────────────────────────────────────────────────

const CATEGORY_META: Record<string, { icon: string; color: string; bg: string }> = {
  "Enforcement":       { icon: "⚖", color: "#ef4444", bg: "rgba(239,68,68,0.12)" },
  "Critical Alert":   { icon: "🚨", color: "#ef4444", bg: "rgba(239,68,68,0.1)" },
  "Grid Alert":       { icon: "⚡", color: "#f59e0b", bg: "rgba(245,158,11,0.12)" },
  "Policy Change":    { icon: "📜", color: "#a78bfa", bg: "rgba(167,139,250,0.12)" },
  "Obligation Watch": { icon: "🔔", color: "#22d3ee", bg: "rgba(34,211,238,0.12)" },
  "Market Update":    { icon: "📊", color: "#4f8ff7", bg: "rgba(79,143,247,0.12)" },
};

function catMeta(category: string) {
  return CATEGORY_META[category] ?? { icon: "●", color: "var(--accent-blue)", bg: "rgba(79,143,247,0.1)" };
}

function severityColor(s: string): string {
  switch ((s || "").toLowerCase()) {
    case "critical": return "#ef4444";
    case "warning":  return "#f59e0b";
    default:         return "#4f8ff7";
  }
}

function formatDate(d: string): string {
  if (!d) return "Standing";
  try {
    return new Date(d).toLocaleDateString("en-AU", { day: "numeric", month: "short", year: "numeric" });
  } catch {
    return d;
  }
}

function daysAgo(d: string): string {
  if (!d) return "";
  try {
    const diff = Math.round((Date.now() - new Date(d).getTime()) / 86400000);
    if (diff === 0) return "Today";
    if (diff === 1) return "Yesterday";
    if (diff < 0) return "Upcoming";
    return `${diff}d ago`;
  } catch {
    return "";
  }
}

// ── KPI strip ─────────────────────────────────────────────────────────────────

function KpiStrip({ summary }: { summary: HorizonData["summary"] }) {
  const cats = Object.entries(summary.by_category).sort((a, b) => b[1] - a[1]);
  return (
    <div style={{ display: "flex", gap: 10, flexWrap: "wrap", marginBottom: 16 }}>
      <div style={{
        flex: "0 0 auto",
        background: "rgba(239,68,68,0.08)",
        border: "1px solid rgba(239,68,68,0.2)",
        borderRadius: 10,
        padding: "12px 18px",
        minWidth: 100,
      }}>
        <div style={{ fontSize: 11, fontWeight: 600, color: "#ef4444", textTransform: "uppercase", letterSpacing: "0.06em" }}>Critical</div>
        <div style={{ fontSize: 26, fontWeight: 800, color: "#ef4444", lineHeight: 1.2 }}>{summary.critical}</div>
      </div>
      <div style={{
        flex: "0 0 auto",
        background: "rgba(245,158,11,0.08)",
        border: "1px solid rgba(245,158,11,0.2)",
        borderRadius: 10,
        padding: "12px 18px",
        minWidth: 100,
      }}>
        <div style={{ fontSize: 11, fontWeight: 600, color: "#f59e0b", textTransform: "uppercase", letterSpacing: "0.06em" }}>Enforcement</div>
        <div style={{ fontSize: 26, fontWeight: 800, color: "#f59e0b", lineHeight: 1.2 }}>{summary.enforcement}</div>
      </div>
      <div style={{
        flex: "0 0 auto",
        background: "var(--bg-card)",
        border: "1px solid var(--border)",
        borderRadius: 10,
        padding: "12px 18px",
        minWidth: 100,
      }}>
        <div style={{ fontSize: 11, fontWeight: 600, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.06em" }}>Total Items</div>
        <div style={{ fontSize: 26, fontWeight: 800, color: "var(--text-primary)", lineHeight: 1.2 }}>{summary.total}</div>
      </div>
      {cats.slice(0, 4).map(([cat, count]) => {
        const m = catMeta(cat);
        return (
          <div key={cat} style={{
            flex: "0 0 auto",
            background: m.bg,
            border: `1px solid ${m.color}22`,
            borderRadius: 10,
            padding: "12px 18px",
            minWidth: 90,
          }}>
            <div style={{ fontSize: 11, fontWeight: 600, color: m.color, textTransform: "uppercase", letterSpacing: "0.06em" }}>
              {m.icon} {cat.split(" ")[0]}
            </div>
            <div style={{ fontSize: 26, fontWeight: 800, color: m.color, lineHeight: 1.2 }}>{count}</div>
          </div>
        );
      })}
    </div>
  );
}

// ── Horizon feed item ─────────────────────────────────────────────────────────

function HorizonCard({ item, expanded, onToggle }: {
  item: HorizonItem;
  expanded: boolean;
  onToggle: () => void;
}) {
  const m = catMeta(item.category);
  return (
    <div
      onClick={onToggle}
      style={{
        display: "flex",
        gap: 12,
        padding: "14px 16px",
        borderBottom: "1px solid var(--border)",
        cursor: "pointer",
        transition: "background 0.15s",
        background: expanded ? "var(--bg-card-hover)" : "transparent",
      }}
    >
      {/* Category icon column */}
      <div style={{
        flexShrink: 0,
        width: 36,
        height: 36,
        borderRadius: 8,
        background: m.bg,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        fontSize: 16,
        border: `1px solid ${m.color}33`,
      }}>
        {m.icon}
      </div>

      {/* Content */}
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 8 }}>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{
              fontSize: 13,
              fontWeight: 600,
              color: "var(--text-primary)",
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: expanded ? "normal" : "nowrap",
            }}>
              {item.title}
            </div>
            {!expanded && (
              <div style={{
                fontSize: 12,
                color: "var(--text-secondary)",
                marginTop: 2,
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
              }}>
                {item.body || item.reference}
              </div>
            )}
            {expanded && item.body && (
              <div style={{ fontSize: 12, color: "var(--text-secondary)", marginTop: 6, lineHeight: 1.6 }}>
                {item.body}
                {item.reference && (
                  <div style={{ marginTop: 4, fontSize: 11, color: "var(--text-muted)" }}>
                    Ref: {item.reference}
                  </div>
                )}
              </div>
            )}
          </div>
          <div style={{ flexShrink: 0, textAlign: "right" }}>
            <div style={{ fontSize: 11, color: "var(--text-muted)" }}>{formatDate(item.date)}</div>
            {item.date && <div style={{ fontSize: 10, color: "var(--text-muted)", marginTop: 1 }}>{daysAgo(item.date)}</div>}
          </div>
        </div>

        <div style={{ display: "flex", gap: 6, marginTop: 7, alignItems: "center" }}>
          <span style={{
            fontSize: 10, fontWeight: 700, padding: "1px 7px",
            borderRadius: 8, background: m.bg, color: m.color,
          }}>
            {item.category}
          </span>
          <span style={{
            fontSize: 10, fontWeight: 600, padding: "1px 6px",
            borderRadius: 8,
            background: item.severity === "Critical" ? "rgba(239,68,68,0.12)" : "rgba(245,158,11,0.1)",
            color: severityColor(item.severity),
          }}>
            {item.severity}
          </span>
          <span style={{ fontSize: 11, color: "var(--text-muted)" }}>{item.source}</span>
        </div>
      </div>
    </div>
  );
}

// ── Filter bar ────────────────────────────────────────────────────────────────

type CategoryFilter = "All" | string;

const SEVERITY_FILTERS = ["All", "Critical", "Warning", "Info"] as const;

// ── Main ──────────────────────────────────────────────────────────────────────

export default function RegulatoryHorizon() {
  const { market } = useRegion();
  const { data, loading } = useApi<HorizonData>("/api/regulatory-horizon", { market });
  const [catFilter, setCatFilter] = useState<CategoryFilter>("All");
  const [sevFilter, setSevFilter] = useState<string>("All");
  const [search, setSearch] = useState("");
  const [expandedId, setExpandedId] = useState<string | null>(null);

  if (loading) return <LoadingPage />;

  const items = data?.items ?? [];
  const summary = data?.summary ?? { total: 0, critical: 0, enforcement: 0, by_category: {} };

  const categories: CategoryFilter[] = ["All", ...Object.keys(summary.by_category).sort()];

  const filtered = items.filter((item) => {
    if (catFilter !== "All" && item.category !== catFilter) return false;
    if (sevFilter !== "All" && item.severity !== sevFilter) return false;
    if (search) {
      const s = search.toLowerCase();
      return (
        item.title.toLowerCase().includes(s) ||
        item.body.toLowerCase().includes(s) ||
        item.source.toLowerCase().includes(s) ||
        item.reference.toLowerCase().includes(s)
      );
    }
    return true;
  });

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 0 }}>

      {/* KPI strip */}
      <KpiStrip summary={summary} />

      {/* Main panel */}
      <div style={{
        background: "var(--bg-card)",
        border: "1px solid var(--border)",
        borderRadius: "var(--radius-lg)",
        overflow: "hidden",
      }}>
        {/* Header + filters */}
        <div style={{
          padding: "16px 20px",
          borderBottom: "1px solid var(--border)",
          background: "var(--bg-card)",
        }}>
          <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 12, flexWrap: "wrap", marginBottom: 12 }}>
            <div>
              <div style={{ fontSize: 14, fontWeight: 700, color: "var(--text-primary)" }}>
                Regulatory Horizon
              </div>
              <div style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 2 }}>
                {filtered.length} of {items.length} items — regulatory notices, enforcement & obligation watch
              </div>
            </div>
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search notices, references..."
              className="search-input"
              style={{ width: 220, margin: 0 }}
            />
          </div>

          {/* Category filter */}
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 8 }}>
            {categories.map((cat) => {
              const count = cat === "All" ? items.length : (summary.by_category[cat] ?? 0);
              const m = cat !== "All" ? catMeta(cat) : null;
              const isActive = catFilter === cat;
              return (
                <button
                  key={cat}
                  onClick={() => setCatFilter(cat)}
                  style={{
                    padding: "3px 11px",
                    borderRadius: 20,
                    border: isActive
                      ? `1px solid ${m ? m.color + "66" : "var(--accent-blue)"}`
                      : "1px solid var(--border)",
                    background: isActive
                      ? (m ? m.bg : "rgba(79,143,247,0.12)")
                      : "transparent",
                    color: isActive ? (m ? m.color : "var(--accent-blue)") : "var(--text-muted)",
                    fontSize: 11,
                    fontWeight: 600,
                    cursor: "pointer",
                  }}
                >
                  {cat !== "All" && m ? `${m.icon} ` : ""}{cat}
                  {count > 0 && <span style={{ opacity: 0.6, marginLeft: 3 }}>({count})</span>}
                </button>
              );
            })}
          </div>

          {/* Severity filter */}
          <div style={{ display: "flex", gap: 6 }}>
            {SEVERITY_FILTERS.map((sev) => {
              const isActive = sevFilter === sev;
              const color = sev === "Critical" ? "#ef4444" : sev === "Warning" ? "#f59e0b" : sev === "Info" ? "#4f8ff7" : "var(--text-secondary)";
              return (
                <button
                  key={sev}
                  onClick={() => setSevFilter(sev)}
                  style={{
                    padding: "2px 10px",
                    borderRadius: 12,
                    border: isActive ? `1px solid ${color}44` : "1px solid var(--border)",
                    background: isActive ? `${color}14` : "transparent",
                    color: isActive ? color : "var(--text-muted)",
                    fontSize: 11,
                    fontWeight: 600,
                    cursor: "pointer",
                  }}
                >
                  {sev}
                </button>
              );
            })}
          </div>
        </div>

        {/* Feed */}
        <div style={{ maxHeight: 640, overflowY: "auto" }}>
          {filtered.length === 0 ? (
            <div style={{ padding: 40, textAlign: "center", color: "var(--text-muted)", fontSize: 13 }}>
              No items match your filters.
            </div>
          ) : (
            filtered.map((item) => (
              <HorizonCard
                key={item.id || item.title}
                item={item}
                expanded={expandedId === (item.id || item.title)}
                onToggle={() => setExpandedId(expandedId === (item.id || item.title) ? null : (item.id || item.title))}
              />
            ))
          )}
        </div>
      </div>
    </div>
  );
}
