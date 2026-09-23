import { Navigate, Link } from "react-router-dom";
import { useJsonData } from "../hooks/useJsonData.js";
import { useLearnerState } from "../state/LearnerStateContext.jsx";

// "My Learning" works for any enrolled field, not just one:
//  - 0 enrolled fields: prompt to go enroll.
//  - 1 enrolled field: skip the picker and go straight into that field's
//    content page (Home/Chapters tabs), same as before.
//  - 2+ enrolled fields: show a picker listing every enrolled course (same
//    info shown on the Home page's field cards — sources, content items,
//    level, topics), and clicking one opens that field's content page.
export default function MyLearning() {
  const { data, loading, error } = useJsonData("/data/content.json");
  const { data: counts } = useJsonData("/data/field_counts.json");
  const { enrolledFields } = useLearnerState();

  if (loading) return <main className="page-content"><div className="empty-state">Loading...</div></main>;
  if (error || !data) {
    return (
      <main className="page-content">
        <div className="empty-state">Could not load <code>public/data/content.json</code>.</div>
      </main>
    );
  }

  const enrolledData = data.fields.filter((f) => enrolledFields.includes(f.field));

  if (enrolledData.length === 0) {
    return (
      <main className="page-content">
        <h1 style={{ fontSize: 22 }}>My Learning</h1>
        <div className="empty-state">
          You haven't enrolled in any field yet. <Link to="/">Go to the Learning Platform</Link> and click Enroll to start.
        </div>
      </main>
    );
  }

  if (enrolledData.length === 1) {
    return <Navigate to={`/field/${encodeURIComponent(enrolledData[0].field)}`} replace />;
  }

  return (
    <main className="page-content">
      <h1 style={{ fontSize: 22, margin: "0 0 4px" }}>My Learning</h1>
      <p className="muted" style={{ fontSize: 13.5, margin: "0 0 22px" }}>
        You're enrolled in {enrolledData.length} courses. Pick one to continue.
      </p>

      <div className="grid-2">
        {enrolledData.map((field) => {
          const meta = counts?.fields?.find((f) => f.field === field.field);
          const totalItems = field.files.reduce((n, f) => n + f.items.length, 0);
          return (
            <Link key={field.field} to={`/field/${encodeURIComponent(field.field)}`} className="card" style={{ display: "block", padding: 20 }}>
              <h2 style={{ margin: "0 0 6px", fontSize: 18 }}>{field.field}</h2>
              <div className="meta-row" style={{ marginTop: 0, borderTop: 0, paddingTop: 0, marginBottom: meta?.topics?.length ? 10 : 0 }}>
                <span>{field.files.length} sources</span>
                <span>{totalItems} content items</span>
                {meta?.level && <span>{meta.level}</span>}
              </div>
              {meta?.topics?.length > 0 && (
                <div className="skills">
                  {meta.topics.map((t) => (
                    <span key={t} className="skill">{t}</span>
                  ))}
                </div>
              )}
            </Link>
          );
        })}
      </div>
    </main>
  );
}
