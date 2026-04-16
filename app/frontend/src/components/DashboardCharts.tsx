import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Cell, PieChart, Pie, Legend,
} from "recharts";
import { useApi } from "../hooks/useApi";

interface ChartsData {
  penalty_trend: { year: string; total_penalty: number; count: number }[];
  risk_distribution: { rating: string; count: number }[];
  breach_types: { breach_type: string; total_penalty: number; count: number }[];
}

const RISK_COLORS: Record<string, string> = {
  Critical: "#EF4444",
  High:     "#F59E0B",
  Medium:   "#3B82F6",
  Low:      "#10B981",
};

function formatMillions(val: number): string {
  if (val >= 1e6) return `$${(val / 1e6).toFixed(1)}M`;
  if (val >= 1e3) return `$${(val / 1e3).toFixed(0)}K`;
  return `$${val}`;
}

function PenaltyTrendChart({ data }: { data: ChartsData["penalty_trend"] }) {
  return (
    <div className="chart-card">
      <div className="chart-card-header">
        <h3>Enforcement Penalty Trend</h3>
        <span className="chart-subtitle">Total penalties imposed by year</span>
      </div>
      <ResponsiveContainer width="100%" height={200}>
        <BarChart data={data} margin={{ top: 4, right: 12, left: 0, bottom: 4 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
          <XAxis dataKey="year" tick={{ fontSize: 11, fill: "var(--text-muted)" }} axisLine={false} tickLine={false} />
          <YAxis tickFormatter={formatMillions} tick={{ fontSize: 11, fill: "var(--text-muted)" }} axisLine={false} tickLine={false} width={50} />
          <Tooltip
            formatter={(val: number) => [formatMillions(val), "Total Penalty"]}
            contentStyle={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 8, fontSize: 12 }}
            labelStyle={{ color: "var(--text-primary)" }}
          />
          <Bar dataKey="total_penalty" radius={[4, 4, 0, 0]}>
            {data.map((_, i) => (
              <Cell key={i} fill={i === data.length - 1 ? "#EF4444" : "#3B82F6"} fillOpacity={i === data.length - 1 ? 1 : 0.7} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

function RiskDistributionChart({ data }: { data: ChartsData["risk_distribution"] }) {
  const total = data.reduce((s, d) => s + d.count, 0);
  return (
    <div className="chart-card">
      <div className="chart-card-header">
        <h3>Obligation Risk Profile</h3>
        <span className="chart-subtitle">{total} obligations by risk rating</span>
      </div>
      <ResponsiveContainer width="100%" height={200}>
        <PieChart>
          <Pie
            data={data}
            dataKey="count"
            nameKey="rating"
            cx="50%"
            cy="50%"
            innerRadius={52}
            outerRadius={80}
            paddingAngle={3}
          >
            {data.map((entry) => (
              <Cell key={entry.rating} fill={RISK_COLORS[entry.rating] ?? "#6B7280"} />
            ))}
          </Pie>
          <Tooltip
            formatter={(val: number, name: string) => [`${val} (${Math.round((val / total) * 100)}%)`, name]}
            contentStyle={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 8, fontSize: 12 }}
          />
          <Legend
            iconType="circle"
            iconSize={8}
            wrapperStyle={{ fontSize: 11, color: "var(--text-secondary)" }}
          />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}

function BreachTypesChart({ data }: { data: ChartsData["breach_types"] }) {
  const truncated = data.map((d) => ({
    ...d,
    short: d.breach_type.length > 22 ? d.breach_type.slice(0, 20) + "…" : d.breach_type,
  }));
  return (
    <div className="chart-card">
      <div className="chart-card-header">
        <h3>Top Breach Categories</h3>
        <span className="chart-subtitle">Ranked by total penalty value</span>
      </div>
      <ResponsiveContainer width="100%" height={200}>
        <BarChart data={truncated} layout="vertical" margin={{ top: 4, right: 40, left: 0, bottom: 4 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" horizontal={false} />
          <XAxis type="number" tickFormatter={formatMillions} tick={{ fontSize: 10, fill: "var(--text-muted)" }} axisLine={false} tickLine={false} />
          <YAxis type="category" dataKey="short" tick={{ fontSize: 10, fill: "var(--text-secondary)" }} axisLine={false} tickLine={false} width={120} />
          <Tooltip
            formatter={(val: number) => [formatMillions(val), "Total Penalty"]}
            labelFormatter={(label) => data.find((d) => d.breach_type.startsWith(label.replace("…", "")))?.breach_type ?? label}
            contentStyle={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 8, fontSize: 12 }}
            labelStyle={{ color: "var(--text-primary)" }}
          />
          <Bar dataKey="total_penalty" fill="#F59E0B" fillOpacity={0.85} radius={[0, 4, 4, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export default function DashboardCharts() {
  const { data, loading } = useApi<ChartsData>("/api/dashboard-charts");

  if (loading || !data) {
    return (
      <div className="charts-row">
        {[0, 1, 2].map((i) => (
          <div key={i} className="chart-card chart-card-skeleton">
            <div className="skeleton-line" style={{ width: "60%", height: 16, marginBottom: 8 }} />
            <div className="skeleton-line" style={{ width: "40%", height: 12, marginBottom: 24 }} />
            <div className="skeleton-block" style={{ height: 150 }} />
          </div>
        ))}
      </div>
    );
  }

  const hasData = data.penalty_trend.length > 0 || data.risk_distribution.length > 0 || data.breach_types.length > 0;
  if (!hasData) return null;

  return (
    <div className="charts-row">
      {data.penalty_trend.length > 0 && <PenaltyTrendChart data={data.penalty_trend} />}
      {data.risk_distribution.length > 0 && <RiskDistributionChart data={data.risk_distribution} />}
      {data.breach_types.length > 0 && <BreachTypesChart data={data.breach_types} />}
    </div>
  );
}
