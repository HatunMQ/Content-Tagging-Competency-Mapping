export default function StatTile({ label, value, sub, tone = "default" }) {
  const toneColor = {
    default: "var(--slate-900)",
    good: "var(--green-600)",
    warn: "#92400e",
    bad: "var(--red-600)",
  }[tone];

  return (
    <div className="card" style={{ padding: "16px 18px" }}>
      <div className="muted" style={{ fontSize: 12.5, fontWeight: 600, marginBottom: 6 }}>{label}</div>
      <div style={{ fontSize: 24, fontWeight: 800, color: toneColor, lineHeight: 1.1 }}>{value}</div>
      {sub && <div className="muted" style={{ fontSize: 12, marginTop: 4 }}>{sub}</div>}
    </div>
  );
}
