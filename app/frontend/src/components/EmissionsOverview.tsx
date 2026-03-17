import { useState, useMemo } from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from "recharts";
import { useApi } from "../hooks/useApi";
import { LoadingPage } from "./LoadingSkeleton";

interface EmissionsData {
  records: Record<string, string>[];
  state_summary: Record<string, string>[];
}

const STATES = ["All", "NSW", "VIC", "QLD", "SA", "WA", "TAS"];
const FUELS = ["All", "Coal", "Gas", "Hydro"];

function formatNum(val: string | number | null): string {
  if (val == null) return "—";
  const n = typeof val === "string" ? parseFloat(val) : val;
  if (isNaN(n)) return "—";
  if (n >= 1e6) return `${(n / 1e6).toFixed(1)}M`;
  if (n >= 1e3) return `${(n / 1e3).toFixed(0)}K`;
  return n.toFixed(0);
}

export default function EmissionsOverview() {
  const [state, setState] = useState("");
  const [fuel, setFuel] = useState("");

  const params: Record<string, string> = {};
  if (state) params.state = state;
  if (fuel) params.fuel_source = fuel;

  const { data, loading } = useApi<EmissionsData>("/api/emissions-overview", params);

  const chartData = useMemo(() => {
    if (!data?.records) return [];
    return data.records.slice(0, 15).map((r) => ({
      name: (r.corporation_name || "").length > 25
        ? (r.corporation_name || "").slice(0, 22) + "..."
        : r.corporation_name || "",
      scope1: parseFloat(r.scope1_emissions_tco2e || "0"),
    }));
  }, [data]);

  if (loading) return <LoadingPage />;

  const totalScope1 = data?.records?.reduce(
    (sum, r) => sum + parseFloat(r.scope1_emissions_tco2e || "0"), 0
  ) || 0;

  return (
    <div>
      <div className="stats-row">
        <div className="stat-card">
          <div className="label">Entities</div>
          <div className="value blue">{data?.records?.length || 0}</div>
        </div>
        <div className="stat-card">
          <div className="label">Total Scope 1</div>
          <div className="value red">{formatNum(totalScope1)} t CO2-e</div>
        </div>
        <div className="stat-card">
          <div className="label">States</div>
          <div className="value blue">{data?.state_summary?.length || 0}</div>
        </div>
      </div>

      <div className="filters">
        {STATES.map((s) => (
          <button
            key={s}
            className={`filter-btn ${(s === "All" ? !state : state === s) ? "active" : ""}`}
            onClick={() => setState(s === "All" ? "" : s)}
          >
            {s}
          </button>
        ))}
        <div style={{ width: 1, background: "var(--border)", margin: "0 4px" }} />
        {FUELS.map((f) => (
          <button
            key={f}
            className={`filter-btn ${(f === "All" ? !fuel : fuel.toLowerCase() === f.toLowerCase()) ? "active" : ""}`}
            onClick={() => setFuel(f === "All" ? "" : f)}
          >
            {f}
          </button>
        ))}
      </div>

      <div className="card">
        <div className="card-header">
          <h2>Top Emitters — Scope 1 (t CO2-e)</h2>
          <span className="badge" style={{ background: "rgba(79,143,247,0.15)", color: "var(--accent-blue)" }}>
            CER NGER Data
          </span>
        </div>
        <div className="chart-container">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chartData} layout="vertical" margin={{ left: 160, right: 20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis type="number" tickFormatter={(v) => formatNum(v)} stroke="var(--text-muted)" fontSize={11} />
              <YAxis type="category" dataKey="name" width={150} stroke="var(--text-muted)" fontSize={11} />
              <Tooltip
                formatter={(val: number) => [`${formatNum(val)} t CO2-e`, "Scope 1"]}
                contentStyle={{ background: "var(--bg-card)", border: "1px solid var(--border)", borderRadius: 8, fontSize: 12 }}
              />
              <Bar dataKey="scope1" fill="var(--accent-red)" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="card">
        <div className="card-header">
          <h2>Detailed Emissions Data</h2>
        </div>
        <div style={{ overflowX: "auto" }}>
          <table className="data-table">
            <thead>
              <tr>
                <th>Corporation</th>
                <th>Facility</th>
                <th>State</th>
                <th>Scope 1 (t CO2-e)</th>
                <th>Scope 2 (t CO2-e)</th>
                <th>Fuel Source</th>
              </tr>
            </thead>
            <tbody>
              {data?.records?.map((r, i) => (
                <tr key={i}>
                  <td>{r.corporation_name}</td>
                  <td className="truncate">{r.facility_name || "—"}</td>
                  <td>{r.state}</td>
                  <td className="number emissions-val">{formatNum(r.scope1_emissions_tco2e)}</td>
                  <td className="number">{formatNum(r.scope2_emissions_tco2e)}</td>
                  <td>{r.primary_fuel_source || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
