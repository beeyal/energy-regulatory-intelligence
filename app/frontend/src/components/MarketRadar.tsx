import {
  RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
  ResponsiveContainer, Tooltip,
} from "recharts";
import { useApi } from "../hooks/useApi";

interface MarketScore {
  market: string;
  name: string;
  flag: string;
  score: number;
}

interface MarketRiskData {
  markets: MarketScore[];
}

function riskColor(score: number): string {
  if (score >= 70) return "#EF4444";
  if (score >= 45) return "#F59E0B";
  return "#10B981";
}

const CustomDot = (props: any) => {
  const { cx, cy, payload } = props;
  if (!cx || !cy) return null;
  const color = riskColor(payload.score);
  return <circle cx={cx} cy={cy} r={4} fill={color} stroke="var(--surface)" strokeWidth={2} />;
};

const CustomTooltip = ({ active, payload }: any) => {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <div style={{
      background: "var(--surface)", border: "1px solid var(--border)",
      borderRadius: 8, padding: "8px 12px", fontSize: 12,
    }}>
      <div style={{ fontWeight: 600, marginBottom: 2 }}>{d.flag} {d.name}</div>
      <div style={{ color: riskColor(d.score) }}>Risk score: <strong>{d.score}/100</strong></div>
    </div>
  );
};

export default function MarketRadar() {
  // market param not needed — returns all markets
  const { data, loading } = useApi<MarketRiskData>("/api/market-risk-scores");

  if (loading || !data?.markets?.length) {
    return (
      <div className="chart-card" style={{ minHeight: 260 }}>
        <div className="chart-card-header">
          <h3>Multi-Market Risk Radar</h3>
          <span className="chart-subtitle">Cross-market exposure comparison</span>
        </div>
        <div className="skeleton-block" style={{ height: 200 }} />
      </div>
    );
  }

  const chartData = data.markets.map((m) => ({
    ...m,
    label: `${m.flag} ${m.market}`,
  }));

  const avgScore = Math.round(chartData.reduce((s, d) => s + d.score, 0) / chartData.length);
  const hotMarket = chartData.reduce((a, b) => (a.score > b.score ? a : b));

  return (
    <div className="chart-card">
      <div className="chart-card-header" style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
        <div>
          <h3>Multi-Market Risk Radar</h3>
          <span className="chart-subtitle">Cross-market regulatory exposure</span>
        </div>
        <div style={{ textAlign: "right", fontSize: 11 }}>
          <div style={{ color: "var(--text-muted)" }}>Avg score</div>
          <div style={{ fontSize: 20, fontWeight: 700, color: riskColor(avgScore), lineHeight: 1.2 }}>{avgScore}</div>
        </div>
      </div>

      <ResponsiveContainer width="100%" height={220}>
        <RadarChart data={chartData} margin={{ top: 10, right: 20, bottom: 10, left: 20 }}>
          <PolarGrid stroke="var(--border)" />
          <PolarAngleAxis
            dataKey="label"
            tick={{ fontSize: 11, fill: "var(--text-secondary)" }}
          />
          <PolarRadiusAxis
            domain={[0, 100]}
            tick={{ fontSize: 9, fill: "var(--text-muted)" }}
            tickCount={4}
            axisLine={false}
          />
          <Radar
            name="Risk Score"
            dataKey="score"
            stroke="#3B82F6"
            fill="#3B82F6"
            fillOpacity={0.15}
            strokeWidth={2}
            dot={<CustomDot />}
          />
          <Tooltip content={<CustomTooltip />} />
        </RadarChart>
      </ResponsiveContainer>

      <div style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 4, textAlign: "center" }}>
        Highest risk: <span style={{ color: riskColor(hotMarket.score), fontWeight: 600 }}>
          {hotMarket.flag} {hotMarket.name} ({hotMarket.score})
        </span>
      </div>
    </div>
  );
}
