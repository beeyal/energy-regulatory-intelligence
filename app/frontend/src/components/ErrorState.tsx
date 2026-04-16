interface ErrorStateProps {
  message?: string;
  onRetry?: () => void;
}

export default function ErrorState({ message = "Unable to load data", onRetry }: ErrorStateProps) {
  return (
    <div style={{
      display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center",
      padding: "48px 24px", textAlign: "center",
    }}>
      <div style={{ fontSize: 28, marginBottom: 12 }}>⚠</div>
      <div style={{ fontSize: 14, fontWeight: 500, color: "var(--accent-amber)", marginBottom: 4 }}>{message}</div>
      <div style={{ fontSize: 12, color: "var(--text-muted)", maxWidth: 320, lineHeight: 1.5, marginBottom: 16 }}>
        Try refreshing the page. If this persists, check that the Databricks warehouse is running.
      </div>
      {onRetry && (
        <button
          onClick={onRetry}
          style={{
            padding: "6px 16px", fontSize: 12, fontWeight: 500,
            background: "rgba(251,191,36,0.1)", color: "var(--accent-amber)",
            border: "1px solid rgba(251,191,36,0.25)", borderRadius: 6, cursor: "pointer",
          }}
        >
          Retry
        </button>
      )}
    </div>
  );
}
