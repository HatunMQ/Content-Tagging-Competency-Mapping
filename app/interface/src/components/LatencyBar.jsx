export default function LatencyBar({ label, segments, totalLabel }) {
  const total = segments.reduce((sum, s) => sum + s.value, 0);

  return (
    <div style={{ marginBottom: 16 }}>
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 13, marginBottom: 6 }}>
        <span style={{ fontWeight: 700 }}>{label}</span>
        <span className="muted">{totalLabel}</span>
      </div>
      <div style={{ display: "flex", height: 22, borderRadius: 6, overflow: "hidden", background: "var(--slate-100)" }}>
        {segments.map((s) => (
          <div
            key={s.name}
            title={`${s.name}: ${s.value}s`}
            style={{ width: `${(s.value / total) * 100}%`, background: s.color }}
          />
        ))}
      </div>
      <div style={{ display: "flex", gap: 14, marginTop: 6, flexWrap: "wrap" }}>
        {segments.map((s) => (
          <span key={s.name} style={{ fontSize: 11.5, display: "flex", alignItems: "center", gap: 5, color: "var(--slate-600)" }}>
            <span style={{ width: 9, height: 9, borderRadius: 2, background: s.color, display: "inline-block" }} />
            {s.name} ({s.value}s)
          </span>
        ))}
      </div>
    </div>
  );
}
