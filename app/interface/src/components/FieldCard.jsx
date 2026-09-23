import { Link } from "react-router-dom";
import { useLearnerState } from "../state/LearnerStateContext.jsx";

const FIELD_COLORS = {
  "Machine Learning": "#00b8e6",
  "Data Science": "#f15bb5",
  "Generative AI": "#7c3aed",
  SQL: "#f59e0b",
};

const FIELD_ICON = {
  "Machine Learning": "ML",
  "Data Science": "DS",
  SQL: "SQL",
  "Generative AI": "AI",
};

export default function FieldCard({ field, count, fileCount, topics }) {
  const { isEnrolled, enroll, unenroll } = useLearnerState();
  const enrolled = isEnrolled(field);
  const color = FIELD_COLORS[field] || "var(--navy)";

  return (
    <article className="course-card" style={{ borderTop: `5px solid ${color}` }}>
      <Link to={`/field/${encodeURIComponent(field)}`} style={{ color: "inherit" }}>
        <div className="course-top">
          <div>
            <h3 style={{ margin: 0, fontSize: 15.5 }}>{field}</h3>
            <p className="course-meta">{count} content items · {fileCount} sources</p>
          </div>
          <div className="course-icon" style={{ background: `${color}22`, color }}>
            {FIELD_ICON[field] || field.slice(0, 2).toUpperCase()}
          </div>
        </div>
        <div className="skills">
          {topics.map((t) => (
            <span key={t} className="skill">{t}</span>
          ))}
        </div>
      </Link>
      <button
        className="btn-primary"
        style={{
          marginTop: 14,
          width: "100%",
          background: enrolled ? "var(--slate-100)" : "var(--navy)",
          color: enrolled ? "var(--slate-700)" : "#fff",
        }}
        onClick={(e) => {
          e.preventDefault();
          enrolled ? unenroll(field) : enroll(field);
        }}
      >
        {enrolled ? "Enrolled — manage in My Learning" : "Enroll"}
      </button>
    </article>
  );
}
