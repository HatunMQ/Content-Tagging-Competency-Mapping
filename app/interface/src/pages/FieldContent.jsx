import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { useJsonData, resolvePath } from "../hooks/useJsonData.js";
import { useLearnerState } from "../state/LearnerStateContext.jsx";
import FieldFileCard from "../components/FieldFileCard.jsx";

const TABS = [
  { key: "home", label: "Home" },
  { key: "chapters", label: "Chapters" },
];

export default function FieldContent() {
  const { fieldName } = useParams();
  const field = decodeURIComponent(fieldName);
  const { data, loading, error } = useJsonData("/data/content.json");
  const { data: counts } = useJsonData("/data/field_counts.json");
  const { data: quizData } = useJsonData("/data/quizzes.json");
  const { isEnrolled, enroll, unenroll, isFileComplete, toggleFileComplete } = useLearnerState();
  const [tab, setTab] = useState("home");
  const [focusedFile, setFocusedFile] = useState(null);

  // Quiz files show their real short quiz name ("Quiz 1") everywhere on this
  // page instead of their long .xlsx filename -- the filename is still what
  // gets matched/stored, just not what's displayed.
  function displayName(fileName) {
    const quiz = quizData?.quizzes?.find((q) => q.source_file === fileName);
    return quiz?.short_title || fileName;
  }
  function isQuizFile(fileName) {
    return Boolean(quizData?.quizzes?.some((q) => q.source_file === fileName));
  }

  const fieldData = data?.fields?.find((f) => f.field === field);
  const fieldMeta = counts?.fields?.find((f) => f.field === field);
  const enrolled = isEnrolled(field);

  // Default the sidebar focus to the first file once the data is in, so the
  // Chapters tab always has a lecture selected even before the learner
  // clicks anything.
  useEffect(() => {
    if (fieldData && !focusedFile) setFocusedFile(fieldData.files[0]?.file_name || null);
  }, [fieldData, focusedFile]);

  // Opening a file (from the Home tab's file list or the Chapters sidebar)
  // switches to the Chapters tab and shows ONLY that one file's lecture
  // page — never a stacked list, never a scroll.
  function openFile(fileName) {
    setFocusedFile(fileName);
    setTab("chapters");
  }

  if (loading) return <main className="page-content"><div className="empty-state">Loading...</div></main>;
  if (error || !fieldData) {
    return (
      <main className="page-content">
        <div className="empty-state">
          Could not find "{field}" in <code>public/data/content.json</code>.
        </div>
        <Link to="/" className="muted" style={{ fontSize: 13 }}>← Back to all fields</Link>
      </main>
    );
  }

  const filesDone = fieldData.files.filter((f) => isFileComplete(field, f.file_name)).length;
  const totalItems = fieldData.files.reduce((n, f) => n + f.items.length, 0);
  const focusedFileData = fieldData.files.find((f) => f.file_name === focusedFile) || fieldData.files[0];

  return (
    <main className="page-content">
      <div className="page-head">
        <div>
          <div className="small">
            <Link to="/" className="muted">‹ All Fields</Link>
          </div>
          <h1 style={{ margin: "4px 0 6px" }}>{field}</h1>
          <p className="lead" style={{ margin: 0 }}>
            {fieldData.files.length} sources — {filesDone}/{fieldData.files.length} files completed · {totalItems} content items
          </p>
        </div>
        <div className="course-title-row">
          {fieldMeta?.level && <span className="level-pill">{fieldMeta.level}</span>}
          <button className="btn-primary" onClick={() => (enrolled ? unenroll(field) : enroll(field))}>
            {enrolled ? "Unenroll" : "Enroll"}
          </button>
        </div>
      </div>

      <div className="learning-tabs" aria-label="Field content tabs">
        {TABS.map((t) => (
          <button
            key={t.key}
            className={`learning-tab${tab === t.key ? " active" : ""}`}
            onClick={() => setTab(t.key)}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === "home" && (
        <HomeTab field={field} fieldData={fieldData} fieldMeta={fieldMeta} onOpenFile={openFile} />
      )}
      {tab === "chapters" && (
        <div className="learning-layout">
          <div>
            {focusedFileData ? (
              <div className="panel">
                <div className="lesson-header">
                  <div>
                    <h2 style={{ marginBottom: 4 }}>{displayName(focusedFileData.file_name)}</h2>
                    <div className="meta-row" style={{ marginTop: 0, borderTop: 0, paddingTop: 0 }}>
                      <span>{focusedFileData.items.length} content items</span>
                      {fieldMeta?.level && <span>{fieldMeta.level}</span>}
                    </div>
                  </div>
                  <div className="lesson-actions">
                    {!isQuizFile(focusedFileData.file_name) && (
                      <a className="download-btn" href={resolvePath(`/raw/${encodeURIComponent(focusedFileData.file_name)}`)} download>
                        Download lesson files
                      </a>
                    )}
                  </div>
                </div>

                <FieldFileCard field={field} file={focusedFileData} />
              </div>
            ) : (
              <div className="empty-state">No files in this field yet.</div>
            )}
          </div>

          <aside className="lesson-sidebar">
            <div className="sidebar-course">
              <strong>{field}</strong>
              <div className="small">{filesDone}/{fieldData.files.length} files completed</div>
            </div>
            <div className="side-section">
              <div className="side-section-title"><span>Files</span></div>
              {fieldData.files.map((file) => {
                const done = isFileComplete(field, file.file_name);
                const active = focusedFile === file.file_name;
                return (
                  <div
                    key={file.file_name}
                    className={`side-lesson${active ? " active" : ""}${done ? " done" : ""}`}
                    onClick={() => openFile(file.file_name)}
                  >
                    <span
                      className={`tiny-check${done ? " done" : ""}`}
                      onClick={(e) => {
                        e.stopPropagation();
                        toggleFileComplete(field, file.file_name);
                      }}
                    >
                      {done ? "Done" : ""}
                    </span>
                    <span>{displayName(file.file_name)}</span>
                  </div>
                );
              })}
            </div>
          </aside>
        </div>
      )}
    </main>
  );
}

function HomeTab({ field, fieldData, fieldMeta, onOpenFile }) {
  const { isFileComplete, toggleFileComplete } = useLearnerState();
  const { data: quizData } = useJsonData("/data/quizzes.json");

  function displayName(fileName) {
    const quiz = quizData?.quizzes?.find((q) => q.source_file === fileName);
    return quiz?.short_title || fileName;
  }

  return (
    <div className="overview-wrap">
      <div className="big-card">
        <h2>About this field</h2>
        <p>{fieldMeta?.description || `Content for ${field}, auto-tagged by AI across learning style, level, and competency.`}</p>
        <div className="meta-row">
          <span>{fieldData.files.length} sources</span>
          <span>{fieldData.files.reduce((n, f) => n + f.items.length, 0)} content items</span>
          {fieldMeta?.level && <span>{fieldMeta.level}</span>}
        </div>
        {fieldMeta?.topics?.length > 0 && (
          <div className="skills" style={{ marginTop: 12 }}>
            {fieldMeta.topics.map((t) => (
              <span key={t} className="skill">{t}</span>
            ))}
          </div>
        )}
      </div>

      <div className="big-card">
        <h2>File progress</h2>
        {fieldData.files.map((file) => {
          const done = isFileComplete(field, file.file_name);
          return (
            <div className="chapter-row" key={file.file_name}>
              <div onClick={() => onOpenFile(file.file_name)} style={{ cursor: "pointer" }}>
                <div className="chapter-title">{displayName(file.file_name)}</div>
                <div className="progress-track"><span style={{ width: done ? "100%" : "0%" }} /></div>
              </div>
              <button
                className="file-check"
                onClick={(e) => {
                  e.stopPropagation();
                  toggleFileComplete(field, file.file_name);
                }}
                aria-label={done ? "Mark file as not complete" : "Mark file as complete"}
                style={!done ? { background: "var(--slate-200)", boxShadow: "none" } : undefined}
              >
                {done ? "Done" : ""}
              </button>
            </div>
          );
        })}
      </div>
    </div>
  );
}
