import { useEffect, useRef, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { useJsonData } from "../hooks/useJsonData.js";
import { useLearnerState } from "../state/LearnerStateContext.jsx";

// Same "weak competency" cutoff ProgressDashboard.jsx already uses
// (c.pct < 60), so "passed" here means the same thing "strong" means there.
const PASS_THRESHOLD = 60;

// Real interactive quiz: one question on screen at a time, a per-question
// countdown pulled straight from quizzes.json's real time_seconds column,
// a live (unrecorded, unstored) camera preview required for the whole
// attempt, and an automatic fail the instant the learner leaves this tab,
// loses focus, or turns the camera off. Scoring is computed directly
// against quizzes.json's correct_option -- nothing here is estimated.
export default function QuizPage() {
  const { quizId } = useParams();
  const { data, loading, error } = useJsonData("/data/quizzes.json");
  const { recordQuizAttempt, toggleFileComplete, isFileComplete } = useLearnerState();

  const [phase, setPhase] = useState("gate"); // gate | active | done
  const [cameraError, setCameraError] = useState(null);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [answers, setAnswers] = useState({}); // { [questionId]: optionNumber }
  const [timeLeft, setTimeLeft] = useState(0);
  const [result, setResult] = useState(null);

  const videoRef = useRef(null);
  const streamRef = useRef(null);
  const submittedRef = useRef(false); // guards against double-submit (timeout + violation racing)
  const answersRef = useRef({}); // mirrors `answers` so timers/listeners never read a stale closure

  const quiz = data?.quizzes?.find((q) => q.id === quizId);
  const question = quiz?.questions?.[currentIndex];

  useEffect(() => {
    answersRef.current = answers;
  }, [answers]);

  // --- tab-lock enforcement, active only while phase === "active" ---
  useEffect(() => {
    if (phase !== "active") return undefined;

    function onVisibilityChange() {
      if (document.hidden) failQuiz("You switched tabs or minimized the window during the quiz.");
    }
    function onBlur() {
      failQuiz("You left the quiz page during the quiz.");
    }

    document.addEventListener("visibilitychange", onVisibilityChange);
    window.addEventListener("blur", onBlur);
    return () => {
      document.removeEventListener("visibilitychange", onVisibilityChange);
      window.removeEventListener("blur", onBlur);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [phase]);

  // --- per-question countdown, resets whenever the question changes ---
  useEffect(() => {
    if (phase !== "active" || !question) return undefined;
    setTimeLeft(question.time_seconds);
    const interval = setInterval(() => {
      setTimeLeft((t) => {
        if (t <= 1) {
          clearInterval(interval);
          goToNextQuestion();
          return 0;
        }
        return t - 1;
      });
    }, 1000);
    return () => clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [phase, currentIndex, question]);

  // --- release the camera whenever we leave "active" phase, and on unmount ---
  useEffect(() => {
    if (phase !== "active" && streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    }
  }, [phase]);

  useEffect(() => {
    return () => {
      if (streamRef.current) streamRef.current.getTracks().forEach((t) => t.stop());
    };
  }, []);

  if (loading) return <main className="page-content"><div className="empty-state">Loading...</div></main>;
  if (error || !data) {
    return <main className="page-content"><div className="empty-state">Could not load <code>public/data/quizzes.json</code>.</div></main>;
  }
  if (!quiz) {
    return (
      <main className="page-content">
        <div className="empty-state">No quiz found with id "{quizId}".</div>
        <Link to="/" className="muted" style={{ fontSize: 13 }}>← Back home</Link>
      </main>
    );
  }

  async function startQuiz() {
    setCameraError(null);
    if (!navigator.mediaDevices?.getUserMedia) {
      setCameraError("This browser doesn't support camera access, so this quiz can't be taken in strict mode here.");
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: true });
      streamRef.current = stream;
      // If the learner turns the camera off from the browser's own camera
      // indicator mid-quiz, the track ends -- treat that like leaving the page.
      stream.getVideoTracks()[0].onended = () => failQuiz("Camera access was turned off during the quiz.");
      if (videoRef.current) videoRef.current.srcObject = stream;
      submittedRef.current = false;
      setAnswers({});
      setCurrentIndex(0);
      setResult(null);
      setPhase("active");
    } catch {
      setCameraError("Camera access was denied. This quiz requires your camera to stay on for the whole attempt.");
    }
  }

  function selectOption(optionNumber) {
    if (!question) return;
    setAnswers((prev) => ({ ...prev, [question.id]: optionNumber }));
  }

  function goToNextQuestion() {
    setCurrentIndex((i) => {
      const next = i + 1;
      if (next >= quiz.questions.length) {
        finishQuiz();
        return i;
      }
      return next;
    });
  }

  function finishQuiz() {
    if (submittedRef.current) return;
    submittedRef.current = true;

    const finalAnswers = answersRef.current;
    let score = 0;
    const review = quiz.questions.map((q) => {
      const selected = finalAnswers[q.id] ?? null;
      const correct = selected === q.correct_option;
      if (correct) score += 1;
      return { question: q, selected, correct };
    });

    const total = quiz.questions.length;
    const pct = total ? Math.round((score / total) * 100) : 0;
    const passed = pct >= PASS_THRESHOLD;

    const attempt = {
      score,
      total,
      pct,
      passed,
      failedByViolation: false,
      violationReason: null,
      completedAt: new Date().toISOString(),
    };

    recordQuizAttempt(quiz.id, attempt);
    // Mark the file complete on any real completed attempt (reached the
    // last question), matching how every other file's checkbox works --
    // "complete" means "went through it", not "mastered it". Mastery is
    // what the score/pct on this same attempt already shows.
    if (!isFileComplete(quiz.field, quiz.source_file)) {
      toggleFileComplete(quiz.field, quiz.source_file);
    }

    setResult({ ...attempt, review });
    setPhase("done");
  }

  function failQuiz(reason) {
    if (submittedRef.current) return;
    submittedRef.current = true;

    const attempt = {
      score: 0,
      total: quiz.questions.length,
      pct: 0,
      passed: false,
      failedByViolation: true,
      violationReason: reason,
      completedAt: new Date().toISOString(),
    };

    recordQuizAttempt(quiz.id, attempt);
    setResult({ ...attempt, review: null });
    setPhase("done");
  }

  if (phase === "gate") {
    return (
      <main className="page-content">
        <div className="page-head">
          <div>
            <div className="small"><Link to={`/field/${encodeURIComponent(quiz.field)}`} className="muted">‹ {quiz.field}</Link></div>
            <h1 style={{ margin: "4px 0 6px" }}>{quiz.short_title || quiz.title}</h1>
            <p className="lead" style={{ margin: 0 }}>{quiz.question_count} questions · {quiz.competency}</p>
          </div>
        </div>

        <div className="card" style={{ padding: "20px 22px", maxWidth: 620 }}>
          <div className="section-title">Before you start</div>
          <ul style={{ margin: "0 0 16px", paddingInlineStart: 20, fontSize: 13.5, color: "var(--slate-700)", lineHeight: 1.7 }}>
            <li>Your camera must stay on for the whole quiz — this is a live preview only, nothing is recorded or uploaded.</li>
            <li>Leaving this tab, switching windows, or turning the camera off fails the attempt immediately.</li>
            <li>Each question has its own timer; when it runs out, the question is left unanswered and you move on.</li>
            <li>Your score is final once you answer (or time out on) the last question.</li>
          </ul>
          {cameraError && (
            <div className="badge badge-bad" style={{ display: "block", padding: "10px 14px", marginBottom: 14 }}>
              {cameraError}
            </div>
          )}
          <button className="btn-primary" onClick={startQuiz}>Enable camera &amp; start quiz</button>
        </div>
      </main>
    );
  }

  if (phase === "done" && result) {
    return (
      <main className="page-content">
        <div className="page-head">
          <div>
            <div className="small"><Link to={`/field/${encodeURIComponent(quiz.field)}`} className="muted">‹ {quiz.field}</Link></div>
            <h1 style={{ margin: "4px 0 6px" }}>{quiz.short_title || quiz.title} — results</h1>
          </div>
          <span className={`badge ${result.passed ? "badge-ok" : "badge-bad"}`}>
            {result.failedByViolation ? "Failed — left the quiz" : result.passed ? "Passed" : "Not passed"}
          </span>
        </div>

        {result.failedByViolation ? (
          <div className="card" style={{ padding: "20px 22px" }}>
            <p style={{ margin: 0, fontSize: 14 }}>{result.violationReason}</p>
            <p className="muted" style={{ fontSize: 13, marginTop: 8 }}>Score recorded as 0/{result.total}. You can retake the quiz.</p>
          </div>
        ) : (
          <>
            <div className="grid-4" style={{ marginBottom: 22 }}>
              <div className="card" style={{ padding: 16, textAlign: "center" }}>
                <div style={{ fontSize: 26, fontWeight: 800 }}>{result.score}/{result.total}</div>
                <div className="small">Correct</div>
              </div>
              <div className="card" style={{ padding: 16, textAlign: "center" }}>
                <div style={{ fontSize: 26, fontWeight: 800 }}>{result.pct}%</div>
                <div className="small">Score</div>
              </div>
            </div>

            <div className="card" style={{ padding: "18px 20px" }}>
              <div className="section-title">Answer review</div>
              {result.review.map(({ question: q, selected, correct }, i) => (
                <div key={q.id} style={{ padding: "14px 0", borderTop: i === 0 ? "none" : "1px solid var(--slate-200)" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", gap: 10 }}>
                    <strong style={{ fontSize: 13.5 }}>{i + 1}. {q.text}</strong>
                    <span className={`badge ${correct ? "badge-ok" : "badge-bad"}`}>{correct ? "Correct" : "Incorrect"}</span>
                  </div>
                  <p className="muted" style={{ fontSize: 12.5, margin: "6px 0 0" }}>
                    Your answer: {selected ? q.options[selected - 1] : "(no answer — timed out)"}
                  </p>
                  {!correct && (
                    <p style={{ fontSize: 12.5, margin: "4px 0 0", color: "var(--green-600)" }}>
                      Correct answer: {q.options[q.correct_option - 1]}
                    </p>
                  )}
                  {q.explanation && (
                    <p className="muted" style={{ fontSize: 12, margin: "6px 0 0", lineHeight: 1.5 }}>{q.explanation}</p>
                  )}
                </div>
              ))}
            </div>
          </>
        )}

        <div style={{ marginTop: 18, display: "flex", gap: 12 }}>
          <button className="btn-primary" onClick={() => setPhase("gate")}>Retake quiz</button>
          <Link to={`/field/${encodeURIComponent(quiz.field)}`} className="muted" style={{ alignSelf: "center", fontSize: 13 }}>
            Back to {quiz.field}
          </Link>
        </div>
      </main>
    );
  }

  if (!question) return null;

  return (
    <main className="page-content">
      <div className="page-head">
        <div>
          <h1 style={{ margin: "4px 0 6px" }}>{quiz.short_title || quiz.title}</h1>
          <p className="lead" style={{ margin: 0 }}>Question {currentIndex + 1} of {quiz.questions.length}</p>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
          <div className={`badge ${timeLeft <= 5 ? "badge-bad" : "badge-warn"}`} style={{ fontVariantNumeric: "tabular-nums" }}>
            {timeLeft}s
          </div>
          <video ref={videoRef} autoPlay muted playsInline style={{ width: 160, height: 120, borderRadius: 8, background: "#000", objectFit: "cover", border: "2px solid var(--navy)" }} />
        </div>
      </div>

      <div className="card" style={{ padding: "22px 24px" }}>
        <p style={{ fontSize: 15.5, fontWeight: 600, margin: "0 0 18px", lineHeight: 1.5 }}>{question.text}</p>
        <div style={{ display: "grid", gap: 10 }}>
          {question.options.map((opt, i) => {
            const optionNumber = i + 1;
            const selected = answers[question.id] === optionNumber;
            return (
              <button
                key={optionNumber}
                onClick={() => selectOption(optionNumber)}
                style={{
                  textAlign: "start",
                  padding: "12px 14px",
                  borderRadius: 8,
                  border: `2px solid ${selected ? "var(--navy)" : "var(--slate-200)"}`,
                  background: selected ? "var(--teal-100)" : "#fff",
                  fontSize: 13.5,
                  color: "var(--ink)",
                  cursor: "pointer",
                }}
              >
                {opt}
              </button>
            );
          })}
        </div>

        <button
          className="btn-primary"
          style={{ marginTop: 20 }}
          disabled={answers[question.id] == null}
          onClick={goToNextQuestion}
        >
          {currentIndex + 1 === quiz.questions.length ? "Submit quiz" : "Next question"}
        </button>
      </div>
    </main>
  );
}
