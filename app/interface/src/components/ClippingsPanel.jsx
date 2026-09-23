import { useLearnerState } from "../state/LearnerStateContext.jsx";

// Clippings tab: chunks the learner explicitly saved from the Activities
// tab (via the pin button on an extract item), with their Arabic translation
// attached if one was saved. Scoped to the current field, matching the
// prototype's per-field content view.
export default function ClippingsPanel({ field }) {
  const { clippingsForField, removeClipping } = useLearnerState();
  const clippings = clippingsForField(field);

  if (clippings.length === 0) {
    return (
      <div className="panel">
        <h2>Clippings</h2>
        <p className="lead">
          Saved excerpts, translations, and notes on important competencies from this field's content. Click
          "Save to Clippings" on any excerpt in the Activities tab to see it here.
        </p>
        <div className="empty-state">Nothing saved here yet for this field.</div>
      </div>
    );
  }

  return (
    <div className="panel">
      <h2>Clippings</h2>
      <p className="lead">Saved excerpts, translations, and notes on important competencies from this field's content.</p>
      <div className="ai-extract-list" style={{ marginTop: 18 }}>
        {clippings.map((c) => (
          <div key={c.id} className="extract-item">
            <div className="extract-top">
              <h3>{c.fileName} — {c.sectionTitle}</h3>
              <span className="badge">{c.level}</span>
            </div>
            <div className="skills">
              <span className="skill">{c.contentType}</span>
              <span className="skill">{c.competency}</span>
              {c.translation && <span className="skill">Translation saved</span>}
            </div>
            <div className="extract-body">{c.text}</div>
            {c.translation && (
              <div dir="rtl" style={{ marginTop: 12, padding: "12px 14px", background: "var(--teal-100)", borderRadius: 8, fontSize: 14, lineHeight: 1.8 }}>
                {c.translation}
              </div>
            )}
            <button
              className="translate-btn"
              style={{ marginTop: 10 }}
              onClick={() => removeClipping(c.field, c.fileName, c.chunkId)}
            >
              Remove from Clippings
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
