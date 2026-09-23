export default function CompetencyBar({ name, pct }) {
  const color = pct >= 75 ? "var(--green-600)" : pct >= 45 ? "#d97706" : "var(--red-600)";

  return (
    <div style={{ marginBottom: 12 }}>
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 13, marginBottom: 4 }}>
        <span style={{ fontWeight: 600 }}>{name}</span>
        <span className="muted">{pct}%</span>
      </div>
      <div style={{ height: 8, background: "var(--slate-100)", borderRadius: 999, overflow: "hidden" }}>
        <div style={{ height: "100%", width: `${pct}%`, background: color, borderRadius: 999 }} />
      </div>
    </div>
  );
}
