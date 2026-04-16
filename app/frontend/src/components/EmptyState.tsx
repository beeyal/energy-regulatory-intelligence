interface EmptyStateProps {
  icon?: string;
  message: string;
  detail?: string;
  actionLabel?: string;
  onAction?: () => void;
}

export default function EmptyState({ icon = "○", message, detail, actionLabel, onAction }: EmptyStateProps) {
  return (
    <div style={{
      display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center",
      padding: "48px 24px", color: "var(--text-muted)", textAlign: "center",
    }}>
      <div style={{ fontSize: 32, marginBottom: 12, opacity: 0.5 }}>{icon}</div>
      <div style={{ fontSize: 14, fontWeight: 500, color: "var(--text-secondary)", marginBottom: 4 }}>{message}</div>
      {detail && <div style={{ fontSize: 12, maxWidth: 320, lineHeight: 1.5 }}>{detail}</div>}
      {actionLabel && onAction && (
        <button
          onClick={onAction}
          style={{
            marginTop: 16, padding: "6px 16px", fontSize: 12, fontWeight: 500,
            background: "rgba(79,143,247,0.12)", color: "var(--accent-blue)",
            border: "1px solid rgba(79,143,247,0.25)", borderRadius: 6, cursor: "pointer",
          }}
        >
          {actionLabel}
        </button>
      )}
    </div>
  );
}
