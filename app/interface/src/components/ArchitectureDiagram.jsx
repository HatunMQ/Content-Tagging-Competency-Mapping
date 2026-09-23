// "Model Serving" is the one stage whose label can actually go stale — the
// rest describe fixed pipeline scripts/files that don't change. Its detail
// text is passed in from InfraDashboard, computed live from whichever
// metrics_summary_modelX.json files actually exist, so it always lists the
// real currently-deployed models instead of a hardcoded set of letters.
function stages(modelServingDetail) {
  return [
    { title: "Extractors", detail: "pptx / ipynb / md / xlsx" },
    { title: "Chunk Store", detail: "extracted_chunks.jsonl" },
    { title: "Prompt Builder", detail: "tag_chunks.py" },
    { title: "Model Serving", detail: modelServingDetail || "No models available yet" },
    { title: "Tagged Output", detail: "tagged_chunks_*.jsonl" },
    { title: "Scoring", detail: "compare_results.py" },
  ];
}

export default function ArchitectureDiagram({ modelServingDetail }) {
  const STAGES = stages(modelServingDetail);
  return (
    <div
      style={{
        display: "flex",
        alignItems: "stretch",
        gap: 4,
        overflowX: "auto",
        padding: "6px 2px",
      }}
    >
      {STAGES.map((s, i) => (
        <div key={s.title} style={{ display: "flex", alignItems: "center", flexShrink: 0 }}>
          <div
            className="card"
            style={{
              padding: "12px 14px",
              minWidth: 128,
              textAlign: "center",
              borderColor: "var(--teal-600)",
              background: "var(--teal-100)",
            }}
          >
            <div style={{ fontWeight: 700, fontSize: 12.5, color: "var(--teal-900)" }}>{s.title}</div>
            <div className="muted" style={{ fontSize: 10.5, marginTop: 3 }}>{s.detail}</div>
          </div>
          {i < STAGES.length - 1 && (
            <span style={{ color: "var(--slate-400)", fontSize: 18, padding: "0 6px" }}>→</span>
          )}
        </div>
      ))}
    </div>
  );
}
