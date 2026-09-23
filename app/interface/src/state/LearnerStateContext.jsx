import { createContext, useContext, useEffect, useState } from "react";

const STORAGE_KEY = "beamdata_learner_state_v1";

function loadState() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return { enrolledFields: [], completedItems: {}, quizAttempts: {} };
    const parsed = JSON.parse(raw);
    return {
      enrolledFields: Array.isArray(parsed.enrolledFields) ? parsed.enrolledFields : [],
      completedItems: parsed.completedItems && typeof parsed.completedItems === "object" ? parsed.completedItems : {},
      // One stored attempt per quiz id -- { [quizId]: { score, total, pct,
      // passed, failedByViolation, violationReason, completedAt } }. Only
      // ever written by QuizPage.jsx after a real scored (or real-failed)
      // attempt, never speculatively.
      quizAttempts: parsed.quizAttempts && typeof parsed.quizAttempts === "object" ? parsed.quizAttempts : {},
    };
  } catch {
    return { enrolledFields: [], completedItems: {}, quizAttempts: {} };
  }
}

const LearnerStateContext = createContext(null);

export function LearnerStateProvider({ children }) {
  const [state, setState] = useState(loadState);

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
    } catch {
      // localStorage unavailable — state stays in memory for this session only
    }
  }, [state]);

  function enroll(field) {
    setState((prev) =>
      prev.enrolledFields.includes(field) ? prev : { ...prev, enrolledFields: [...prev.enrolledFields, field] }
    );
  }

  function unenroll(field) {
    setState((prev) => ({ ...prev, enrolledFields: prev.enrolledFields.filter((f) => f !== field) }));
  }

  function isEnrolled(field) {
    return state.enrolledFields.includes(field);
  }

  function itemKey(field, fileName, chunkId) {
    return `${field}::${fileName}::${chunkId}`;
  }

  function isComplete(field, fileName, chunkId) {
    return Boolean(state.completedItems[itemKey(field, fileName, chunkId)]);
  }

  function toggleComplete(field, fileName, chunkId) {
    const key = itemKey(field, fileName, chunkId);
    setState((prev) => {
      const next = { ...prev.completedItems };
      if (next[key]) delete next[key];
      else next[key] = true;
      return { ...prev, completedItems: next };
    });
  }

  // File-level completion: ONE manual checkbox per file ("I finished this
  // file"), separate from per-item tracking above. Stored under its own key
  // shape (…::__file__) inside the same completedItems map so it persists
  // the same way. This is what the Chapters tab's file-check and the Home
  // tab's file-progress checkboxes both read/write.
  function fileKey(field, fileName) {
    return `${field}::${fileName}::__file__`;
  }

  function isFileComplete(field, fileName) {
    return Boolean(state.completedItems[fileKey(field, fileName)]);
  }

  function toggleFileComplete(field, fileName) {
    const key = fileKey(field, fileName);
    setState((prev) => {
      const next = { ...prev.completedItems };
      if (next[key]) delete next[key];
      else next[key] = true;
      return { ...prev, completedItems: next };
    });
  }

  // Quiz results -- recorded once per completed (or violation-failed) real
  // attempt by QuizPage.jsx. Overwrites any previous attempt for the same
  // quiz id, so this always reflects the learner's most recent real result.
  function recordQuizAttempt(quizId, attempt) {
    setState((prev) => ({
      ...prev,
      quizAttempts: { ...prev.quizAttempts, [quizId]: attempt },
    }));
  }

  function getQuizAttempt(quizId) {
    return state.quizAttempts[quizId] || null;
  }

  const value = {
    enrolledFields: state.enrolledFields,
    enroll,
    unenroll,
    isEnrolled,
    isComplete,
    toggleComplete,
    isFileComplete,
    toggleFileComplete,
    quizAttempts: state.quizAttempts,
    recordQuizAttempt,
    getQuizAttempt,
  };

  return <LearnerStateContext.Provider value={value}>{children}</LearnerStateContext.Provider>;
}

export function useLearnerState() {
  const ctx = useContext(LearnerStateContext);
  if (!ctx) throw new Error("useLearnerState must be used within LearnerStateProvider");
  return ctx;
}
