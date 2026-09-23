import { Link } from "react-router-dom";
import ExtractItem from "./ExtractItem.jsx";
import { useJsonData, resolvePath } from "../hooks/useJsonData.js";
import { useLearnerState } from "../state/LearnerStateContext.jsx";

// Stable DOM id for a file's card (kept for potential deep-linking even
// though the Chapters tab now shows one file at a time instead of a
// scrollable stack).
export function fileCardId(field, fileName) {
  return `file-card-${encodeURIComponent(field)}-${encodeURIComponent(fileName)}`;
}

// file-card / viewer / ai-extract-list layout, ported from
// team7-learning-platform-prototype/index.html: a Download button for the
// real source file, an embedded viewer with page/zoom/search controls, and
// the AI-tagged outline listed below with a Translate button per item. The
// "Complete lesson" toggle lives one level up, in the lesson header.
//
// The viewer's page controls (‹ N of M ›, zoom, search) and the slide
// preview itself are SHAPE ONLY right now — static, not wired up. Real
// content needs each raw file converted to PDF first (pptx/xlsx via
// LibreOffice, ipynb via nbconvert, md via pandoc), which isn't set up yet.
// Once that pipeline exists, swap the placeholder block below for an
// <iframe> pointed at the converted PDF and wire the ‹/› buttons to it.
// "Download original" only works today for files actually present under
// public/raw/ — right now that's just Decision Trees Revised.pptx.
//
// Quiz files (.xlsx quizzes tagged content_type "Quiz" in content.json) are
// the one exception to all of the above: instead of the AI-tagged text
// outline, they show a real launch card for the interactive quiz page
// (QuizPage.jsx) — a raw "Question: ... / Correct answer: 2" text dump is
// not a usable quiz, so it's not shown here at all once a real quiz exists.
export default function FieldFileCard({ field, file }) {
  const pageCount = file.items.length;
  const isQuiz = file.items.some((item) => item.content_type === "Quiz");

  const { data: quizData } = useJsonData("/data/quizzes.json");
  const quiz = quizData?.quizzes?.find((q) => q.source_file === file.file_name);

  // Real PDF preview, converted from the actual raw file by
  // convert_previews.sh (run as part of ingest_pipeline.sh). A file only
  // ever appears here if its conversion genuinely succeeded -- the
  // manifest is written from real conversion results, never guessed.
  const { data: pdfManifest } = useJsonData("/data/pdf_previews.json");
  const hasPdf = Boolean(pdfManifest?.files?.includes(file.file_name));
  const pdfUrl = hasPdf
    ? resolvePath(`/raw_pdf/${encodeURIComponent(file.file_name.replace(/\.[^.]+$/, ".pdf"))}`)
    : null;

  if (isQuiz) {
    return (
      <div className="file-card" id={fileCardId(field, file.file_name)}>
        <div className="file-card-head">
          <div>
            <h2 style={{ margin: "0 0 2px", fontSize: 16 }}>{quiz?.short_title || file.file_name}</h2>
            <div className="small">Interactive quiz — real scoring, camera + tab-lock required.</div>
          </div>
        </div>
        <QuizLaunchCard quiz={quiz} />
      </div>
    );
  }

  return (
    <div className="file-card" id={fileCardId(field, file.file_name)}>
      <div className="file-card-head">
        <div>
          <h2 style={{ margin: "0 0 2px", fontSize: 16 }}>{file.file_name}</h2>
          <div className="small">
            AI-generated tagged outline — not a replacement for the file. Real preview and download are the source of truth.
          </div>
        </div>
      </div>

      <div className="viewer" aria-label="File preview">
        <div className="viewer-bar">
          <strong>{hasPdf ? "File preview" : "Slide preview"}</strong>
          {hasPdf && (
            <div className="viewer-controls">
              <a className="viewer-btn" href={pdfUrl} target="_blank" rel="noreferrer">Open in new tab</a>
            </div>
          )}
        </div>
        {hasPdf ? (
          <iframe
            src={pdfUrl}
            title={`${file.file_name} preview`}
            style={{ width: "100%", height: 560, border: "none", display: "block" }}
          />
        ) : (
          <div className="preview-page">
            <div className="slide-mock">
              <h3>Preview not connected yet</h3>
              <p>This file hasn't been converted to a PDF preview yet — run <code>./convert_previews.sh</code> on the server.</p>
              <p>Use "Download" above to open the actual file for now.</p>
            </div>
          </div>
        )}
      </div>

      <div className="ai-extract-list">
        {file.items.map((item) => (
          <ExtractItem key={item.chunk_id} item={item} />
        ))}
      </div>
    </div>
  );
}

function QuizLaunchCard({ quiz }) {
  const { getQuizAttempt } = useLearnerState();

  if (!quiz) {
    return (
      <div className="empty-state">
        This file is tagged as a quiz, but no matching entry was found in <code>public/data/quizzes.json</code>.
      </div>
    );
  }

  const attempt = getQuizAttempt(quiz.id);

  return (
    <div style={{ padding: 20 }}>
      <div className="meta-row" style={{ borderTop: 0, marginTop: 0, paddingTop: 0 }}>
        <span>{quiz.question_count} questions</span>
        <span>{quiz.competency}</span>
      </div>

      {attempt && (
        <div
          className="card"
          style={{
            padding: "12px 16px",
            marginTop: 14,
            borderInlineStart: `4px solid ${attempt.passed ? "var(--green-600)" : "var(--red-600)"}`,
          }}
        >
          <strong style={{ fontSize: 13 }}>
            Last attempt: {attempt.score}/{attempt.total} ({attempt.pct}%){" "}
            {attempt.failedByViolation ? "— failed (left the quiz)" : attempt.passed ? "— passed" : "— not passed yet"}
          </strong>
        </div>
      )}

      <Link
        to={`/quiz/${quiz.id}`}
        className="btn-primary"
        style={{ display: "inline-block", marginTop: 16, textDecoration: "none" }}
      >
        {attempt ? "Retake quiz" : "Start quiz"}
      </Link>
    </div>
  );
}
