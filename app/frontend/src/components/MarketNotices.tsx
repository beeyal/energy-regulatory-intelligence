import { useState } from "react";
import { useApi } from "../hooks/useApi";

interface NoticesData {
  records: Record<string, string>[];
  type_distribution: { notice_type: string; count: string }[];
}

const TYPES = ["All", "NON-CONFORMANCE", "RECLASSIFY", "RESERVE NOTICE", "DIRECTION", "MARKET SUSPENSION"];
const REGIONS = ["All", "NSW1", "VIC1", "QLD1", "SA1", "TAS1"];

function noticeTypeClass(type: string): string {
  const t = (type || "").toLowerCase();
  if (t.includes("non-conformance")) return "notice-non-conformance";
  if (t.includes("reclassif")) return "notice-reclassify";
  if (t.includes("suspension")) return "notice-market-suspension";
  if (t.includes("direction")) return "notice-direction";
  if (t.includes("reserve")) return "notice-reserve";
  return "notice-default";
}

function formatDate(d: string | null): string {
  if (!d) return "—";
  try {
    return new Date(d).toLocaleDateString("en-AU", {
      day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit",
    });
  } catch {
    return d;
  }
}

export default function MarketNotices() {
  const [noticeType, setNoticeType] = useState("");
  const [region, setRegion] = useState("");

  const params: Record<string, string> = {};
  if (noticeType) params.notice_type = noticeType;
  if (region) params.region = region;

  const { data, loading } = useApi<NoticesData>("/api/market-notices", params);

  if (loading) return <div className="loading-spinner">Loading market notices...</div>;

  return (
    <div>
      <div className="stats-row">
        {data?.type_distribution?.slice(0, 5).map((td) => (
          <div className="stat-card" key={td.notice_type}>
            <div className="label">{td.notice_type}</div>
            <div className="value blue">{td.count}</div>
          </div>
        ))}
      </div>

      <div className="filters">
        {TYPES.map((t) => (
          <button
            key={t}
            className={`filter-btn ${(t === "All" ? !noticeType : noticeType === t) ? "active" : ""}`}
            onClick={() => setNoticeType(t === "All" ? "" : t)}
          >
            {t === "All" ? "All Types" : t}
          </button>
        ))}
      </div>
      <div className="filters">
        {REGIONS.map((r) => (
          <button
            key={r}
            className={`filter-btn ${(r === "All" ? !region : region === r) ? "active" : ""}`}
            onClick={() => setRegion(r === "All" ? "" : r)}
          >
            {r}
          </button>
        ))}
      </div>

      <div className="card">
        <div className="card-header">
          <h2>AEMO Market Notices</h2>
          <span className="badge" style={{ background: "rgba(79,143,247,0.15)", color: "var(--accent-blue)" }}>
            NEMWeb Live Data
          </span>
        </div>
        <div style={{ overflowX: "auto" }}>
          <table className="data-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>Type</th>
                <th>Date</th>
                <th>Region</th>
                <th>Reason</th>
              </tr>
            </thead>
            <tbody>
              {data?.records?.map((r, i) => (
                <tr key={i}>
                  <td className="number">{r.notice_id}</td>
                  <td>
                    <span className={`notice-type ${noticeTypeClass(r.notice_type)}`}>
                      {r.notice_type}
                    </span>
                  </td>
                  <td style={{ whiteSpace: "nowrap" }}>{formatDate(r.creation_date)}</td>
                  <td>{r.region}</td>
                  <td style={{ maxWidth: 400, fontSize: 12, lineHeight: 1.4 }}>
                    {(r.reason || "").length > 200
                      ? (r.reason || "").slice(0, 197) + "..."
                      : r.reason}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {(!data?.records || data.records.length === 0) && (
          <div className="empty-state">No notices match the current filters.</div>
        )}
      </div>
    </div>
  );
}
