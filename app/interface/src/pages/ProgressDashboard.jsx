import { Link } from "react-router-dom";
import { useJsonData } from "../hooks/useJsonData.js";
import { useLearnerState } from "../state/LearnerStateContext.jsx";
import StatTile from "../components/StatTile.jsx";
import CompetencyBar from "../components/CompetencyBar.jsx";
import GapCard from "../components/GapCard.jsx";
import { learningTypeLabel } from "../lib/learningTypeLabels.js";

// Every number on this page is computed live from real state: which fields
// the learner enrolled in (LearnerStateContext), which FILES they've
// checked off as complete (isFileComplete), and -- now that a real quiz
// feature exists -- their real recorded quiz attempts (getQuizAttempt /
// quizzes.json). A file's completion is used as the "done" signal for
// every content item inside it, since file-level is the real granularity
// the student interacts with on the Home tab and the Chapters sidebar.
//
// Quiz evidence only appears here for quizzes actually taken -- an
// un-attempted quiz shows an honest "Not attempted yet" line, never an
// invented score. The "Personalized Learning Plan" section is a real
// placeholder for a planned (not yet built) feature: it's shown so the
// roadmap is visible, but deliberately carries no numbers since there's
// nothing real yet.
export default function ProgressDashboard() {
  const { data, loading, error } = useJsonData("/data/content.json");
  const { data: quizData } = useJsonData("/data/quizzes.json");
  const { enrolledFields, isFileComplete, getQuizAttempt } = useLearnerState();

  if (loading) return <main className="page-content"><div className="empty-state">Loading...</div></main>;
  if (error || !data) {
    return <main className="page-content"><div className="empty-state">Could not load <code>public/data/content.json</code>.</div></main>;
  }

  const enrolledData = data.fields.filter((f) => enrolledFields.includes(f.field));

  if (enrolledData.length === 0) {
    return (
      <main className="page-content">
        <div className="page-head">
          <div>
            <h1>Progress Dashboard</h1>
            <p className="lead">Progress combines lesson completion and competency evidence from the AI-tagged learning content.</p>
          </div>
        </div>
        <div className="empty-state">
          No enrolled fields yet. <Link to="/">Enroll in a field</Link> and start checking off files to see real progress here.
        </div>
      </main>
    );
  }

  // Flatten every file across every enrolled field, tagging each with its
  // real completion state.
  const files = [];
  enrolledData.forEach((f) => {
    f.files.forEach((file) => {
      files.push({ field: f.field, file, done: isFileComplete(f.field, file.file_name) });
    });
  });

  const totalFiles = files.length;
  const doneFiles = files.filter((f) => f.done).length;
  const courseProgressPct = totalFiles ? Math.round((doneFiles / totalFiles) * 100) : 0;

  // Competency + learning-type breakdowns: every item in a file inherits
  // that file's completion state.
  const competencyTotals = {};
  const typeTotals = {};
  let totalItems = 0;
  let doneItems = 0;

  files.forEach(({ file, done }) => {
    file.items.forEach((item) => {
      totalItems += 1;
      if (done) doneItems += 1;

      const compKey = item.Competency || "Unlabeled";
      if (!competencyTotals[compKey]) competencyTotals[compKey] = { total: 0, done: 0 };
      competencyTotals[compKey].total += 1;
      if (done) competencyTotals[compKey].done += 1;

      const typeKey = item.Learning_type || "Unlabeled";
      if (!typeTotals[typeKey]) typeTotals[typeKey] = { total: 0, done: 0 };
      typeTotals[typeKey].total += 1;
      if (done) typeTotals[typeKey].done += 1;
    });
  });

  const competencies = Object.entries(competencyTotals)
    .map(([name, { total, done }]) => ({ name, total, done, pct: total ? Math.round((done / total) * 100) : 0 }))
    .sort((a, b) => b.pct - a.pct);

  const learningTypes = Object.entries(typeTotals)
    .map(([name, { total, done }]) => ({ name, total, done, pct: total ? Math.round((done / total) * 100) : 0 }))
    .sort((a, b) => b.pct - a.pct);

  const weak = competencies.filter((c) => c.pct < 60).sort((a, b) => a.pct - b.pct);
  const strongest = competencies[0];
  const contentCoveragePct = totalItems ? Math.round((doneItems / totalItems) * 100) : 0;
  const filesToReview = files.filter((f) => !f.done);

  // Real quiz evidence for enrolled fields only -- quizzes.json's own
  // "field" is the source of truth for which field a quiz belongs to, same
  // as every other file. Each entry keeps its real attempt (or null, when
  // the learner hasn't taken it yet -- an honest empty state, never a
  // made-up score).
  const enrolledQuizzes = (quizData?.quizzes || [])
    .filter((q) => enrolledFields.includes(q.field))
    .map((q) => ({ quiz: q, attempt: getQuizAttempt(q.id) }));

  // Best real quiz score per competency, used to strengthen (not replace)
  // the file-completion-based gap cards above with an actual correctness
  // signal where one exists.
  const quizPctByCompetency = {};
  enrolledQuizzes.forEach(({ quiz, attempt }) => {
    if (!attempt || attempt.failedByViolation) return;
    if (quizPctByCompetency[quiz.competency] === undefined || attempt.pct > quizPctByCompetency[quiz.competency]) {
      quizPctByCompetency[quiz.competency] = attempt.pct;
    }
  });

  return (
    <main className="page-content">
      <div className="page-head">
        <div>
          <h1>Progress Dashboard</h1>
          <p className="lead">Progress combines lesson completion and competency evidence from the AI-tagged learning content.</p>
        </div>
        <span className="level-badge">Live learner progress</span>
      </div>

      <div className="grid-4" style={{ marginBottom: 26 }}>
        <StatTile label="Course progress" value={`${courseProgressPct}%`} tone={courseProgressPct >= 60 ? "good" : "warn"} />
        <StatTile label="Content coverage" value={`${contentCoveragePct}%`} tone={contentCoveragePct >= 60 ? "good" : "warn"} />
        <StatTile label="Competency gaps" value={weak.length} tone={weak.length > 0 ? "warn" : "good"} />
        <StatTile label="Lessons to review" value={filesToReview.length} />
      </div>

      <div className="grid-2">
        <div className="card" style={{ padding: "18px 20px" }}>
          <div className="section-title">Competency mastery map</div>
          {competencies.map((c) => (
            <CompetencyBar key={c.name} name={`${c.name} (${c.done}/${c.total})`} pct={c.pct} />
          ))}
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          <div className="section-title" style={{ marginBottom: -4 }}>What needs attention</div>
          {weak.length === 0 && !strongest && <div className="card empty-state">Not enough data yet.</div>}
          {weak.map((c) => (
            <GapCard
              key={c.name}
              priority={c.pct === 0 ? "High" : "Medium"}
              title={`Gap: ${c.name}`}
              description={
                c.done === 0
                  ? `Not started yet — 0 of ${c.total} tagged items completed in this competency.`
                  : `${c.done}/${c.total} items completed (${c.pct}%). More practice needed to close this gap.`
              }
              evidence={
                quizPctByCompetency[c.name] !== undefined
                  ? `${c.total} real tagged content item${c.total === 1 ? "" : "s"} · real quiz score: ${quizPctByCompetency[c.name]}%`
                  : `${c.total} real tagged content item${c.total === 1 ? "" : "s"} across your enrolled courses`
              }
            />
          ))}
          {strongest && strongest.pct >= 60 && (
            <div className="card" style={{ padding: "14px 16px", borderInlineStart: "4px solid var(--green-600)" }}>
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
                <h4 style={{ margin: 0, fontSize: 14 }}>Strength: {strongest.name}</h4>
                <span className="badge badge-ok">Strong</span>
              </div>
              <p style={{ fontSize: 12.5, color: "var(--slate-700)", margin: "0 0 8px", lineHeight: 1.5 }}>
                {strongest.done}/{strongest.total} tagged items completed ({strongest.pct}%) — your strongest tracked competency right now.
              </p>
              <div className="muted" style={{ fontSize: 11.5, background: "var(--slate-50)", padding: "6px 10px", borderRadius: 6 }}>
                Evidence: {strongest.done} file{strongest.done === 1 ? "" : "s"} marked complete
              </div>
            </div>
          )}
        </div>
      </div>

      <div className="card" style={{ padding: "18px 20px", marginTop: 20 }}>
        <div className="section-title">Lesson &amp; competency evidence</div>
        <table>
          <thead>
            <tr><th>Lesson content</th><th>Completion</th><th>Competency</th><th>Status</th></tr>
          </thead>
          <tbody>
            {files.map(({ field, file, done }) => {
              const fileCompetencies = [...new Set(file.items.map((i) => i.Competency).filter(Boolean))];
              return (
                <tr key={`${field}::${file.file_name}`}>
                  <td>{file.file_name}</td>
                  <td>{done ? "Complete" : "Not complete"}</td>
                  <td>{fileCompetencies.join(", ") || "—"}</td>
                  <td><span className="skill">{done ? "Reviewed" : "Needs review"}</span></td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <div className="grid-2" style={{ marginTop: 20 }}>
        <div className="card" style={{ padding: "18px 20px" }}>
          <div className="section-title">Quiz results</div>
          {enrolledQuizzes.length === 0 ? (
            <div className="empty-state">No quizzes in your enrolled fields yet.</div>
          ) : (
            enrolledQuizzes.map(({ quiz, attempt }) => (
              <div key={quiz.id} style={{ padding: "10px 0", borderTop: "1px solid var(--slate-200)" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 10 }}>
                  <div>
                    <strong style={{ fontSize: 13.5 }}>{quiz.short_title || quiz.title}</strong>
                    <div className="small">{quiz.competency}</div>
                  </div>
                  {attempt ? (
                    <span className={`badge ${attempt.passed ? "badge-ok" : "badge-bad"}`}>
                      {attempt.failedByViolation ? "Failed (left quiz)" : `${attempt.score}/${attempt.total} (${attempt.pct}%)`}
                    </span>
                  ) : (
                    <span className="badge badge-warn">Not attempted yet</span>
                  )}
                </div>
              </div>
            ))
          )}
        </div>

        <div className="card" style={{ padding: "18px 20px" }}>
          <div className="section-title">Personalized Learning Plan</div>
          <div className="empty-state">
            Coming soon — a Personalized Learning Plan per competency, generated from real quiz performance once more quiz
            data exists. Not built yet; shown here so the roadmap is visible.
          </div>
        </div>
      </div>

      <div className="grid-2" style={{ marginTop: 20 }}>
        <div className="card" style={{ padding: "18px 20px" }}>
          <div className="section-title">Recommended next actions</div>
          {filesToReview.length === 0 ? (
            <div className="empty-state">Everything in your enrolled fields is marked complete — nice work.</div>
          ) : (
            <div className="step-list">
              {filesToReview.slice(0, 5).map((f, i) => (
                <div className="plan-step" key={f.file.file_name}>
                  <span className="num">{i + 1}</span>
                  <div><strong>Review:</strong> {f.file.file_name} ({f.field})</div>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="card" style={{ padding: "18px 20px" }}>
          <div className="section-title">Learning type insight</div>
          <table>
            <thead>
              <tr><th>Learning type</th><th>Progress</th><th>Items</th></tr>
            </thead>
            <tbody>
              {learningTypes.map((t) => (
                <tr key={t.name}>
                  <td>{learningTypeLabel(t.name)}</td>
                  <td>{t.pct}%</td>
                  <td>{t.done}/{t.total}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </main>
  );
}
