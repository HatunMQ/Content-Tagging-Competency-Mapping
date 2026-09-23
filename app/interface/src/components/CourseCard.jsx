const STATUS_STYLE = {
  "In Progress": { bg: "var(--amber-100)", color: "#92400e" },
  Completed: { bg: "var(--green-100)", color: "var(--green-600)" },
  Enrolled: { bg: "var(--teal-100)", color: "var(--teal-700)" },
};

export default function CourseCard({ title, status, completion, stats }) {
  const style = STATUS_STYLE[status] || STATUS_STYLE["Enrolled"];

  return (
    <div className="card" style={{ padding: "16px 18px" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 10 }}>
        <h3 style={{ margin: 0, fontSize: 15 }}>{title}</h3>
        <span className="badge" style={{ background: style.bg, color: style.color }}>{status}</span>
      </div>

      <div style={{ display: "flex", gap: 16, marginBottom: 12, flexWrap: "wrap" }}>
        {stats.map((s) => (
          <div key={s.label} style={{ fontSize: 12.5 }}>
            <span style={{ fontWeight: 700, color: "var(--slate-900)" }}>{s.value}</span>{" "}
            <span className="muted">{s.label}</span>
          </div>
        ))}
      </div>

      <div style={{ height: 8, background: "var(--slate-100)", borderRadius: 999, overflow: "hidden" }}>
        <div style={{ height: "100%", width: `${completion}%`, background: "var(--navy)", borderRadius: 999 }} />
      </div>
      <div className="muted" style={{ fontSize: 12, marginTop: 6 }}>{completion}% complete</div>
    </div>
  );
}
