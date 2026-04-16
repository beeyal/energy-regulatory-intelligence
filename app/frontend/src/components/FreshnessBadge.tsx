interface FreshnessBadgeProps {
  timestamp: string | null | undefined;
}

function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

export default function FreshnessBadge({ timestamp }: FreshnessBadgeProps) {
  if (!timestamp) return null;

  const diff = Date.now() - new Date(timestamp).getTime();
  const hrs = diff / 3600000;

  const color = hrs < 1 ? "var(--accent-green)" : hrs < 24 ? "var(--accent-amber)" : "var(--accent-red)";
  const bg = hrs < 1 ? "rgba(52,211,153,0.1)" : hrs < 24 ? "rgba(251,191,36,0.1)" : "rgba(248,113,113,0.1)";
  const label = hrs > 24 ? `Updated ${relativeTime(timestamp)} — may be stale` : `Updated ${relativeTime(timestamp)}`;

  return (
    <span
      title={new Date(timestamp).toISOString()}
      style={{
        fontSize: 11, fontWeight: 500, color, background: bg,
        border: `1px solid ${color}30`, borderRadius: 4, padding: "2px 7px",
      }}
    >
      {label}
    </span>
  );
}
