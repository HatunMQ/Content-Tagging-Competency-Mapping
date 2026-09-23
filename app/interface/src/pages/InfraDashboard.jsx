import { useJsonData } from "../hooks/useJsonData.js";
import LatencyBar from "../components/LatencyBar.jsx";
import HealthTable from "../components/HealthTable.jsx";
import ArchitectureDiagram from "../components/ArchitectureDiagram.jsx";

// Model slots this page will look for, in order. Adding a model (like the
// new "E") means dropping metrics_summary_modelX.json and
// accuracy_summary_modelX.json into public/data/ — nothing here needs to
// change, as long as its tag is already in this list. There's no way for a
// static frontend to list a folder's contents at runtime, so this list is
// the closest thing to "automatic": it's just pre-allocated slots (A
// through J, 10 of them) that only render when their files actually exist
// (see the `available`/`accuracyModels` filters below). If you ever need
// an 11th model, add its tag here and the two useJsonData lines for it.
const MODEL_TAGS = ["modelA", "modelB", "modelC", "modelD", "modelE", "modelF", "modelG", "modelH", "modelI", "modelJ"];

const MODEL_COLORS = {
  modelA: "#0f766e",
  modelB: "#2563eb",
  modelC: "#7c3aed",
  modelD: "#d97706",
  modelE: "#db2777",
  modelF: "#059669",
  modelG: "#dc2626",
  modelH: "#0891b2",
  modelI: "#4338ca",
  modelJ: "#92400e",
};

// "modelA" -> "Model A". Fully derived from the tag, so a new tag never
// needs a new entry anywhere just to get a short label.
function shortLabel(tag) {
  return tag.replace(/^model/, "Model ");
}

function pickHighestLevel(metrics) {
  if (!metrics?.levels?.length) return null;
  return metrics.levels.reduce((max, l) => (l.concurrency > max.concurrency ? l : max), metrics.levels[0]);
}

// Tri-state SLO check: true = meets the target, false = breaches it, null = no
// target was ever defined for this model/metric, so there's nothing to judge.
function slocheck(lvl, metKey, targetKey) {
  const target = lvl?.slo?.[targetKey];
  if (target === undefined || target === null) return null;
  return Boolean(lvl?.slo?.[metKey]);
}

export default function InfraDashboard() {
  // Fixed, unrolled hook calls (one pair per slot in MODEL_TAGS) — this has
  // to be a flat list rather than a .map() over useJsonData, since React
  // hooks must be called the same number of times, in the same order, on
  // every render.
  const modelA = useJsonData("/data/metrics_summary_modelA.json");
  const modelB = useJsonData("/data/metrics_summary_modelB.json");
  const modelC = useJsonData("/data/metrics_summary_modelC.json");
  const modelD = useJsonData("/data/metrics_summary_modelD.json");
  const modelE = useJsonData("/data/metrics_summary_modelE.json");
  const modelF = useJsonData("/data/metrics_summary_modelF.json");
  const modelG = useJsonData("/data/metrics_summary_modelG.json");
  const modelH = useJsonData("/data/metrics_summary_modelH.json");
  const modelI = useJsonData("/data/metrics_summary_modelI.json");
  const modelJ = useJsonData("/data/metrics_summary_modelJ.json");

  const accModelA = useJsonData("/data/accuracy_summary_modelA.json");
  const accModelB = useJsonData("/data/accuracy_summary_modelB.json");
  const accModelC = useJsonData("/data/accuracy_summary_modelC.json");
  const accModelD = useJsonData("/data/accuracy_summary_modelD.json");
  const accModelE = useJsonData("/data/accuracy_summary_modelE.json");
  const accModelF = useJsonData("/data/accuracy_summary_modelF.json");
  const accModelG = useJsonData("/data/accuracy_summary_modelG.json");
  const accModelH = useJsonData("/data/accuracy_summary_modelH.json");
  const accModelI = useJsonData("/data/accuracy_summary_modelI.json");
  const accModelJ = useJsonData("/data/accuracy_summary_modelJ.json");

  const metricsByTag = { modelA, modelB, modelC, modelD, modelE, modelF, modelG, modelH, modelI, modelJ };
  const accuracyByTag = {
    modelA: accModelA, modelB: accModelB, modelC: accModelC, modelD: accModelD, modelE: accModelE,
    modelF: accModelF, modelG: accModelG, modelH: accModelH, modelI: accModelI, modelJ: accModelJ,
  };

  const models = MODEL_TAGS.map((tag) => ({ key: tag, ...metricsByTag[tag] }));
  const available = models.filter((m) => m.data);

  // The real model name (e.g. "Qwen2.5-VL-7B-Instruct") lives inside each
  // metrics_summary file's own "model" field — not something we have to
  // maintain a separate mapping for.
  const realName = (tag) => metricsByTag[tag]?.data?.model || null;

  const accuracyModels = MODEL_TAGS.map((tag) => ({ key: tag, ...accuracyByTag[tag] })).filter((m) => m.data && !m.error);

  const healthRows = available
    .map((m) => {
      const lvl = pickHighestLevel(m.data);
      return {
        metric: `${shortLabel(m.key)} — TTFT p95`,
        current: lvl ? `${lvl.ttft_s.p95}s` : "—",
        threshold: lvl?.slo?.ttft_p95_target_s ? `≤ ${lvl.slo.ttft_p95_target_s}s` : "—",
        ok: slocheck(lvl, "ttft_p95_met", "ttft_p95_target_s"),
      };
    })
    .concat(
      available.map((m) => {
        const lvl = pickHighestLevel(m.data);
        return {
          metric: `${shortLabel(m.key)} — E2E latency p95`,
          current: lvl ? `${lvl.e2e_latency_s.p95}s` : "—",
          threshold: lvl?.slo?.e2e_p95_target_s ? `≤ ${lvl.slo.e2e_p95_target_s}s` : "—",
          ok: slocheck(lvl, "e2e_p95_met", "e2e_p95_target_s"),
        };
      })
    );

  return (
    <main className="page-content">
      <h1 style={{ fontSize: 22, margin: "0 0 4px" }}>Infra Dashboard</h1>
      <p className="muted" style={{ fontSize: 13.5, margin: "0 0 14px" }}>
        Numbers come directly from <code>evaluation/metrics_summary_*.json</code> and <code>accuracy_summary_*.json</code> —
        copy them from the server into <code>public/data/</code> and this page updates automatically, for any model
        slot from Model A through Model J.
      </p>

      {available.length > 0 && (
        <div className="skills" style={{ marginBottom: 22 }}>
          {available.map((m) => (
            <span key={m.key} className="skill">
              {shortLabel(m.key)} — {realName(m.key) || "unnamed model"}
            </span>
          ))}
        </div>
      )}

      <div className="card" style={{ padding: "18px 20px", marginBottom: 20 }}>
        <div className="section-title">Latency comparison across models</div>
        {available.length === 0 && (
          <div className="empty-state">
            No data yet. Run <code>benchmark_load.py</code> and copy <code>metrics_summary_modelX.json</code> into <code>public/data/</code>.
          </div>
        )}
        {available.map((m) => {
          const lvl = pickHighestLevel(m.data);
          const gen = Math.max(lvl.e2e_latency_s.p50 - lvl.ttft_s.p50, 0.01);
          const name = realName(m.key);
          return (
            <LatencyBar
              key={m.key}
              label={`${shortLabel(m.key)}${name ? ` — ${name}` : ""} (concurrency=${lvl.concurrency})`}
              totalLabel={`e2e p50 = ${lvl.e2e_latency_s.p50}s`}
              segments={[
                { name: "TTFT (queue + prompt)", value: lvl.ttft_s.p50, color: MODEL_COLORS[m.key] || "#64748b" },
                { name: "Generation", value: Number(gen.toFixed(3)), color: `${MODEL_COLORS[m.key] || "#64748b"}55` },
              ]}
            />
          );
        })}
      </div>

      <div className="section-title">Serving health</div>
      <div style={{ marginBottom: 24 }}>
        {healthRows.length > 0 ? <HealthTable rows={healthRows} /> : <div className="card empty-state">No SLO data yet.</div>}
      </div>

      <div className="section-title">Task accuracy — ground truth comparison</div>
      <div className="card" style={{ padding: "18px 20px", marginBottom: 24 }}>
        <p className="muted" style={{ fontSize: 12.5, margin: "0 0 14px" }}>
          Each model's predicted tags were scored field-by-field against <code>evaluation/eval_sample.csv</code> (the
          team's human-labeled ground truth), using <code>evaluation/compare_results.py</code> — this is real task
          accuracy, not just whether the model returned valid JSON.
        </p>
        {accuracyModels.length === 0 ? (
          <div className="empty-state">No accuracy data yet.</div>
        ) : (
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
              <thead>
                <tr>
                  <th style={{ textAlign: "left", padding: "8px 10px", borderBottom: "2px solid var(--line)" }}>Field</th>
                  {accuracyModels.map((m) => (
                    <th key={m.key} style={{ textAlign: "right", padding: "8px 10px", borderBottom: "2px solid var(--line)", whiteSpace: "nowrap" }}>
                      {shortLabel(m.key)}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {["Field", "Learning_type", "Level", "Competency"].map((f) => (
                  <tr key={f}>
                    <td style={{ padding: "7px 10px", borderBottom: "1px solid var(--line)" }}>{f} accuracy</td>
                    {accuracyModels.map((m) => (
                      <td key={m.key} style={{ textAlign: "right", padding: "7px 10px", borderBottom: "1px solid var(--line)" }}>
                        {m.data.per_field_accuracy?.[f]?.accuracy_pct ?? "—"}%
                      </td>
                    ))}
                  </tr>
                ))}
                <tr>
                  <td style={{ padding: "7px 10px", fontWeight: 700 }}>Full exact match (all 4 fields)</td>
                  {accuracyModels.map((m) => (
                    <td key={m.key} style={{ textAlign: "right", padding: "7px 10px", fontWeight: 700 }}>
                      {m.data.full_exact_match?.accuracy_pct ?? "—"}%
                    </td>
                  ))}
                </tr>
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="section-title">Deployment architecture</div>
      <div className="card" style={{ padding: "18px 20px" }}>
        <ArchitectureDiagram
          modelServingDetail={available.length > 0 ? `vLLM — ${available.map((m) => shortLabel(m.key)).join(", ")}` : null}
        />
      </div>
    </main>
  );
}
