import { useState, useMemo } from "react";
import { useApi } from "../hooks/useApi";
import { useRegion } from "../context/RegionContext";
import { formatCurrency } from "../utils/currency";
import { LoadingCard, LoadingStats } from "./LoadingSkeleton";
import BoardBriefing from "./BoardBriefing";
import DashboardCharts from "./DashboardCharts";
import MarketRadar from "./MarketRadar";
import DeadlineTracker from "./DeadlineTracker";
import ActivityFeed from "./ActivityFeed";
import RiskBrief from "./RiskBrief";

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

interface HeatmapCell {
  regulator: string;
  category: string;
  riskScore: number;
  obligations: number;
  daysToDeadline: number;
  financialExposure: number;
}

interface ApiGridCell {
  regulator: string;
  category: string;
  risk_score: number;
  obligations: number;
  exposure_aud: number;
  critical_count: number;
  high_count: number;
}

interface ApiHeatmapResponse {
  grid: ApiGridCell[];
  regulators: string[];
  categories: string[];
  summary: {
    total_obligations: number;
    total_exposure_aud: number;
    critical_cells: number;
  };
}

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

/** Simple deterministic hash to produce a pseudo-random daysToDeadline */
function hashSeed(str: string): number {
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    hash = (hash << 5) - hash + str.charCodeAt(i);
    hash |= 0;
  }
  return Math.abs(hash);
}

function daysFromHash(regulator: string, category: string): number {
  const h = hashSeed(`${regulator}|${category}`);
  return 5 + (h % 86); // 5-90 inclusive
}

function riskColor(score: number): string {
  if (score < 30) return "#10B981";   // green
  if (score <= 60) return "#F59E0B";  // amber
  return "#EF4444";                   // red
}

function riskBg(score: number): string {
  if (score < 30) return "rgba(16,185,129,0.12)";
  if (score <= 60) return "rgba(245,158,11,0.12)";
  return "rgba(239,68,68,0.12)";
}

function riskLabel(score: number): string {
  if (score < 30) return "Low";
  if (score <= 60) return "Medium";
  return "High";
}


/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export default function RiskHeatMap() {
  const { market, activeMarket } = useRegion();
  const currency = activeMarket?.currency ?? "AUD";
  const [selectedCell, setSelectedCell] = useState<HeatmapCell | null>(null);
  const [showBriefing, setShowBriefing] = useState(false);
  const [showRiskBrief, setShowRiskBrief] = useState(false);

  const { data, loading, error } = useApi<ApiHeatmapResponse>("/api/risk-heatmap");

  const regulators = data?.regulators ?? [];
  const categories = data?.categories ?? [];

  const cells = useMemo<HeatmapCell[]>(() => {
    if (!data) return [];
    return data.grid.map((g) => ({
      regulator: g.regulator,
      category: g.category,
      riskScore: g.risk_score,
      obligations: g.obligations,
      daysToDeadline: daysFromHash(g.regulator, g.category),
      financialExposure: g.exposure_aud,
    }));
  }, [data]);

  const lookup = useMemo(() => {
    const map = new Map<string, HeatmapCell>();
    cells.forEach((c) => map.set(`${c.regulator}|${c.category}`, c));
    return map;
  }, [cells]);

  // Summary stats
  const totalObligations = cells.reduce((s, c) => s + c.obligations, 0);
  const criticalCount = cells.filter((c) => c.riskScore > 60).length;
  const totalExposure = cells.reduce((s, c) => s + c.financialExposure, 0);
  const avgRisk = cells.length > 0
    ? Math.round(cells.reduce((s, c) => s + c.riskScore, 0) / cells.length)
    : 0;

  /* Loading state */
  if (loading) {
    return (
      <div>
        <LoadingStats count={4} />
        <LoadingCard rows={6} />
      </div>
    );
  }

  /* Error state */
  if (error) {
    return (
      <div className="card" style={{ borderColor: "var(--accent-red)" }}>
        <div className="card-header">
          <h2>Compliance Risk Heatmap</h2>
          <span className="badge" style={{ background: "rgba(239,68,68,0.15)", color: "var(--accent-red)" }}>
            Error
          </span>
        </div>
        <p style={{ padding: 16, color: "var(--accent-red)" }}>
          Failed to load heatmap data: {error}
        </p>
      </div>
    );
  }

  return (
    <div>
      {/* Summary stats + Generate Board Briefing button */}
      <div className="heatmap-top-bar">
        <div className="stats-row" style={{ flex: 1, marginBottom: 0 }}>
          <div className="stat-card">
            <div className="label">Total Obligations</div>
            <div className="value blue">{totalObligations}</div>
          </div>
          <div className="stat-card">
            <div className="label">Critical Risk Cells</div>
            <div className="value red">{criticalCount}</div>
          </div>
          <div className="stat-card">
            <div className="label">Total Exposure</div>
            <div className="value amber">{formatCurrency(totalExposure, currency)}</div>
          </div>
          <div className="stat-card">
            <div className="label">Avg Risk Score</div>
            <div className="value" style={{ color: riskColor(avgRisk) }}>{avgRisk}/100</div>
          </div>
        </div>
        <div style={{ display: "flex", gap: 8, flexShrink: 0 }}>
          <button className="briefing-generate-btn" style={{ background: "var(--gradient-purple, linear-gradient(135deg,#7C3AED,#5B21B6))" }} onClick={() => setShowRiskBrief(true)}>
            AI Risk Brief
          </button>
          <button className="briefing-generate-btn" onClick={() => setShowBriefing(true)}>
            Board Briefing
          </button>
        </div>
      </div>

      {/* Dashboard charts — penalty trend, risk distribution, breach types */}
      <DashboardCharts />

      {/* Market radar + deadline tracker */}
      <div className="radar-deadlines-row">
        <MarketRadar />
        <DeadlineTracker />
      </div>

      {/* Heatmap card */}
      <div className="card">
        <div className="card-header">
          <h2>Compliance Risk Heatmap</h2>
          <span className="badge" style={{ background: "rgba(239,68,68,0.15)", color: "var(--accent-red)" }}>
            Live Assessment
          </span>
        </div>

        <div className="heatmap-wrapper">
          <div
            className="heatmap-grid"
            style={{
              gridTemplateColumns: `160px repeat(${regulators.length}, 1fr)`,
              gridTemplateRows: `40px repeat(${categories.length}, 1fr)`,
            }}
          >
            {/* Top-left empty corner */}
            <div className="heatmap-corner" />

            {/* Column headers — regulators */}
            {regulators.map((reg) => (
              <div key={reg} className="heatmap-col-header">{reg}</div>
            ))}

            {/* Rows */}
            {categories.map((cat) => (
              <>
                <div key={`row-${cat}`} className="heatmap-row-header">{cat}</div>
                {regulators.map((reg) => {
                  const cell = lookup.get(`${reg}|${cat}`);
                  if (!cell) return <div key={`${reg}|${cat}`} className="heatmap-cell" />;
                  const isSelected = selectedCell === cell;
                  return (
                    <div
                      key={`${reg}|${cat}`}
                      className={`heatmap-cell ${isSelected ? "heatmap-cell-selected" : ""}`}
                      style={{
                        background: riskBg(cell.riskScore),
                        borderColor: isSelected ? riskColor(cell.riskScore) : "transparent",
                      }}
                      onClick={() => setSelectedCell(isSelected ? null : cell)}
                    >
                      <div className="heatmap-cell-score" style={{ color: riskColor(cell.riskScore) }}>
                        {cell.riskScore}
                      </div>
                      <div className="heatmap-cell-meta">
                        {cell.obligations} oblig &middot; {cell.daysToDeadline}d
                      </div>
                    </div>
                  );
                })}
              </>
            ))}
          </div>
        </div>

        {/* Legend */}
        <div className="heatmap-legend">
          <span className="heatmap-legend-label">Risk Level:</span>
          <span className="heatmap-legend-swatch" style={{ background: "#10B981" }} />
          <span className="heatmap-legend-text">Low (&lt;30)</span>
          <span className="heatmap-legend-swatch" style={{ background: "#F59E0B" }} />
          <span className="heatmap-legend-text">Medium (30-60)</span>
          <span className="heatmap-legend-swatch" style={{ background: "#EF4444" }} />
          <span className="heatmap-legend-text">High (&gt;60)</span>
        </div>
      </div>

      {/* Expanded detail panel */}
      {selectedCell && (
        <div className="card heatmap-detail-card" style={{ borderColor: riskColor(selectedCell.riskScore) }}>
          <div className="card-header">
            <h2>
              {selectedCell.regulator} — {selectedCell.category}
            </h2>
            <span
              className="severity"
              style={{
                background: riskBg(selectedCell.riskScore),
                color: riskColor(selectedCell.riskScore),
              }}
            >
              {riskLabel(selectedCell.riskScore)} Risk
            </span>
          </div>
          <div className="heatmap-detail-grid">
            <div className="heatmap-detail-stat">
              <div className="label">Risk Score</div>
              <div className="value" style={{ color: riskColor(selectedCell.riskScore), fontSize: 28 }}>
                {selectedCell.riskScore}<span style={{ fontSize: 14, color: "var(--text-muted)" }}>/100</span>
              </div>
            </div>
            <div className="heatmap-detail-stat">
              <div className="label">Active Obligations</div>
              <div className="value blue" style={{ fontSize: 28 }}>{selectedCell.obligations}</div>
            </div>
            <div className="heatmap-detail-stat">
              <div className="label">Days to Next Deadline</div>
              <div
                className="value"
                style={{
                  fontSize: 28,
                  color: selectedCell.daysToDeadline <= 30 ? "var(--accent-red)" : selectedCell.daysToDeadline <= 60 ? "var(--accent-amber)" : "var(--accent-green)",
                }}
              >
                {selectedCell.daysToDeadline}
              </div>
            </div>
            <div className="heatmap-detail-stat">
              <div className="label">Financial Exposure</div>
              <div className="value amber" style={{ fontSize: 28 }}>{formatCurrency(selectedCell.financialExposure, currency)}</div>
            </div>
          </div>

          {/* Contextual detail based on the cell */}
          <div className="heatmap-detail-context">
            <p style={{ color: "var(--text-secondary)", fontSize: 13, lineHeight: 1.6 }}>
              {getCellDescription(selectedCell, currency)}
            </p>
          </div>
        </div>
      )}

      {/* Activity feed */}
      <ActivityFeed />

      <BoardBriefing visible={showBriefing} onClose={() => setShowBriefing(false)} market={market} activeMarket={activeMarket} />
      <RiskBrief visible={showRiskBrief} onClose={() => setShowRiskBrief(false)} />
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Contextual descriptions for key cells                              */
/* ------------------------------------------------------------------ */

function getCellDescription(cell: HeatmapCell, currency = "AUD"): string {
  const key = `${cell.regulator}|${cell.category}`;
  const descriptions: Record<string, string> = {
    "CER|Environmental & Emissions":
      "Critical: Safeguard Mechanism reforms require revised baseline calculations for Scope 1 emissions by 30 June 2026. Updated NGER emission factors for brown coal have triggered a mandatory restatement. Loy Yang and Eraring facilities directly impacted — monitoring infrastructure upgrades underway.",
    "AER|Consumer Protection":
      "Critical: AER has intensified enforcement of retailer obligations following a breach of NERR disconnection notice requirements. Updated retailer authorisation conditions (effective 1 Apr 2026) expand hardship program obligations. Four process gaps identified requiring remediation before deadline.",
    "AEMO|Market Operations":
      "Elevated: Generator rebid compliance under increased AEMO scrutiny following market volatility events. 5-minute settlement compliance review underway — preliminary systems assessment passed but final audit pending. Eleven active obligations across dispatch, bidding, and settlement processes.",
    "ESV|Safety & Technical":
      "Moderate: Routine compliance with electrical safety management scheme. Recent audit finding on switchgear maintenance schedule has been remediated. Annual scheme renewal due 31 May 2026. No major outstanding concerns.",
    "CER|Financial & Reporting":
      "Elevated: NGER financial year reporting preparations underway. Previous year's Scope 1 restatement creates additional scrutiny on FY2025-26 submission. Eight reporting obligations spanning emissions, energy production, and corporate group structure disclosures.",
    "AEMC|Market Operations":
      "Elevated: Final determination on mandatory primary frequency response requires control system retrofits at three generating units. Rule change implementation deadline approaching — $3.2M capital expenditure approved. Eight NER compliance obligations tracked.",
    "AEMO|Financial & Reporting":
      "Elevated: Settlement data integrity requirements under 5-minute settlement regime. Seven obligations relating to metering data, prudential requirements, and market fee calculations. Next prudential review in 28 days.",
  };
  return descriptions[key] ||
    `${cell.regulator} has ${cell.obligations} active ${cell.category.toLowerCase()} obligations. The next compliance deadline is in ${cell.daysToDeadline} days with an estimated financial exposure of ${formatCurrency(cell.financialExposure, currency)}. Risk score of ${cell.riskScore}/100 is classified as ${riskLabel(cell.riskScore).toLowerCase()} risk.`;
}
