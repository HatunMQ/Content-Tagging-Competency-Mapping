export default function HealthTable({ rows }) {
  return (
    <div className="card" style={{ overflow: "hidden" }}>
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
        <thead>
          <tr style={{ background: "var(--slate-50)", textAlign: "start" }}>
            {["Metric", "Current", "Threshold", "Status"].map((h) => (
              <th key={h} style={{ padding: "10px 16px", fontSize: 11.5, color: "var(--slate-500)", fontWeight: 700, textTransform: "uppercase", letterSpacing: 0.3 }}>
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => {
            // r.ok is tri-state: true = meets the target, false = breaches it,
            // null = no target was ever defined for this model/metric, so
            // there's nothing to judge — shown as a neutral "Not measured"
            // badge instead of a false "OK".
            const badgeText = r.ok === null ? "Not measured" : r.ok ? "OK" : "Breach";
            const badgeClass = r.ok === null ? "badge-neutral" : r.ok ? "badge-ok" : "badge-bad";
            const badgeStyle = r.ok === null ? { background: "var(--slate-100)", color: "var(--slate-500)" } : undefined;
            return (
              <tr key={r.metric} style={{ borderTop: "1px solid var(--slate-200)" }}>
                <td style={{ padding: "10px 16px", fontWeight: 600 }}>{r.metric}</td>
                <td style={{ padding: "10px 16px" }}>{r.current}</td>
                <td style={{ padding: "10px 16px", color: "var(--slate-500)" }}>{r.threshold}</td>
                <td style={{ padding: "10px 16px" }}>
                  <span className={`badge ${badgeClass}`} style={badgeStyle}>{badgeText}</span>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
