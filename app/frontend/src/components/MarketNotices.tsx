import { useState, useMemo } from "react";
import { useApi } from "../hooks/useApi";
import { LoadingPage } from "./LoadingSkeleton";

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

const PAGE_SIZE = 25;

export default function MarketNotices() {
  const [noticeType, setNoticeType] = useState("");
  const [region, setRegion] = useState("");
  const [page, setPage] = useState(0);

  const params: Record<string, string> = { limit: "200" };
  if (noticeType) params.notice_type = noticeType;
  if (region) params.region = region;

  const { data, loading } = useApi<NoticesData>("/api/market-notices", params);

  const paginatedRecords = useMemo(() => {
    if (!data?.records) return [];
    const start = page * PAGE_SIZE;
    return data.records.slice(start, start + PAGE_SIZE);
  }, [data, page]);

  const totalPages = Math.ceil((data?.records?.length || 0) / PAGE_SIZE);

  if (loading) return <LoadingPage />;

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
            onClick={() => { setNoticeType(t === "All" ? "" : t); setPage(0); }}
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
            onClick={() => { setRegion(r === "All" ? "" : r); setPage(0); }}
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
              {paginatedRecords.map((r, i) => (
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
        {totalPages > 1 && (
          <div className="pagination">
            <button
              className="page-btn"
              disabled={page === 0}
              onClick={() => setPage((p) => p - 1)}
            >
              Previous
            </button>
            <span className="page-info">
              Page {page + 1} of {totalPages} ({data?.records?.length} notices)
            </span>
            <button
              className="page-btn"
              disabled={page >= totalPages - 1}
              onClick={() => setPage((p) => p + 1)}
            >
              Next
            </button>
          </div>
        )}
        {(!data?.records || data.records.length === 0) && (
          <div className="empty-state">No notices match the current filters.</div>
        )}
      </div>
    </div>
  );
}
