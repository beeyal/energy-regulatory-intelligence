export function LoadingCard({ rows = 5 }: { rows?: number }) {
  return (
    <div className="card">
      <div className="card-header">
        <div className="skeleton skeleton-bar" style={{ width: 200 }} />
      </div>
      {Array.from({ length: rows }).map((_, i) => (
        <div
          key={i}
          className="skeleton skeleton-row"
          style={{ width: `${70 + Math.random() * 30}%` }}
        />
      ))}
    </div>
  );
}

export function LoadingStats({ count = 3 }: { count?: number }) {
  return (
    <div className="stats-row">
      {Array.from({ length: count }).map((_, i) => (
        <div className="stat-card" key={i}>
          <div className="skeleton skeleton-row" style={{ width: 60 }} />
          <div className="skeleton skeleton-bar" style={{ width: 80, marginTop: 8 }} />
        </div>
      ))}
    </div>
  );
}

export function LoadingPage() {
  return (
    <div>
      <LoadingStats />
      <div className="card">
        <div className="card-header">
          <div className="skeleton skeleton-bar" style={{ width: 200 }} />
        </div>
        <div className="skeleton skeleton-chart" />
      </div>
      <LoadingCard />
    </div>
  );
}
