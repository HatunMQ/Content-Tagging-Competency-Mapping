const PRIORITY_STYLE = {
  High: { bg: "var(--red-100)", color: "var(--red-600)" },
  Medium: { bg: "var(--amber-100)", color: "#92400e" },
  Low: { bg: "var(--slate-100)", color: "var(--slate-700)" },
};

export default function GapCard({ priority, title, description, evidence }) {
  const style = PRIORITY_STYLE[priority] || PRIORITY_STYLE.Medium;

  return (
    <div className="card" style={{ padding: "14px 16px", borderInlineStart: `4px solid ${style.color}` }}>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
        <h4 style={{ margin: 0, fontSize: 14 }}>{title}</h4>
        <span className="badge" style={{ background: style.bg, color: style.color }}>{priority} priority</span>
      </div>
      <p style={{ fontSize: 12.5, color: "var(--slate-700)", margin: "0 0 8px", lineHeight: 1.5 }}>{description}</p>
      <div className="muted" style={{ fontSize: 11.5, background: "var(--slate-50)", padding: "6px 10px", borderRadius: 6 }}>
        Evidence: {evidence}
      </div>
    </div>
  );
}
