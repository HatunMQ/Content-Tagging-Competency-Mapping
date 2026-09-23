import { useState } from "react";
import { translateToArabic } from "../lib/translate.js";
import { learningTypeLabel } from "../lib/learningTypeLabels.js";

// One AI-tagged content chunk: always visible (no expand/collapse), with a
// Translate button — matches the prototype's extract-item exactly.
export default function ExtractItem({ item }) {
  const [translation, setTranslation] = useState(null);
  const [translating, setTranslating] = useState(false);
  const [translateError, setTranslateError] = useState(null);
  const [translateProgress, setTranslateProgress] = useState(null); // { current, total } while translating

  async function handleTranslate() {
    setTranslating(true);
    setTranslateError(null);
    setTranslateProgress(null);
    try {
      setTranslation(
        await translateToArabic(item.text, (current, total) => setTranslateProgress({ current, total }))
      );
    } catch (e) {
      setTranslateError(e.message);
    } finally {
      setTranslating(false);
      setTranslateProgress(null);
    }
  }

  return (
    <div className="extract-item">
      <div className="extract-top">
        <h3>{item.section_title || item.chunk_id}</h3>
        <span className="level-badge">{item.Level}</span>
      </div>
      <div className="skills">
        <span className="skill">{item.content_type}</span>
        <span className="skill">{learningTypeLabel(item.Learning_type)}</span>
        <span className="skill">{item.Competency}</span>
      </div>
      <div className="extract-body">{item.text}</div>

      <button className="translate-btn" onClick={handleTranslate} disabled={translating}>
        {translating
          ? translateProgress && translateProgress.total > 1
            ? `Translating (${translateProgress.current}/${translateProgress.total})...`
            : "Translating..."
          : "Translate to Arabic"}
      </button>

      {translateError && (
        <p style={{ fontSize: 12, marginTop: 8, color: "var(--red-600)" }}>
          Translation failed: {translateError}.
        </p>
      )}
      {translation && (
        <div dir="rtl" style={{ marginTop: 12, padding: "12px 14px", background: "var(--teal-100)", borderRadius: 8, fontSize: 14, lineHeight: 1.8, whiteSpace: "pre-line" }}>
          {translation}
        </div>
      )}
    </div>
  );
}
