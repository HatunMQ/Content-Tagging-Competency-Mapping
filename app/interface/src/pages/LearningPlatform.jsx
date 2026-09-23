import { useState } from "react";
import { useJsonData } from "../hooks/useJsonData.js";
import FieldCard from "../components/FieldCard.jsx";

const TOPICS_BY_FIELD = {
  "Machine Learning": ["Decision Tree Modeling", "Machine Learning Workflow"],
  "Data Science": ["Pandas & Data Wrangling"],
  SQL: ["SQL Foundations", "Window Functions"],
  "Generative AI": ["Prompt Engineering", "RAG Systems"],
};

// Matches the prototype's search-row exactly: a subject search box, a
// "Learning type" dropdown, and a Search button. The dropdown is UI only
// for now — it doesn't filter yet. Learning_type tags (Visual lecture,
// Video, Conceptual, ...) only exist on individual content items inside a
// file, not on a whole field, so there's no real, non-fake way to say "this
// field is a Video field" today. Once there's enough real content variety
// to make that meaningful, this is the place to wire it up (e.g. compute
// each field's most common Learning_type from its real items and filter on
// that).
const LEARNING_TYPES = ["Mixed learning", "Visual", "Practical", "Reading", "Video"];

export default function LearningPlatform() {
  const { data, loading, error } = useJsonData("/data/content.json");
  const [query, setQuery] = useState("");
  const [learningType, setLearningType] = useState(LEARNING_TYPES[0]);

  const fields = data?.fields || [];
  const filtered = fields.filter(
    (f) => query.trim() === "" || f.field.toLowerCase().includes(query.toLowerCase())
  );

  return (
    <main className="page-content">
      <section className="hero">
        <h1>Everything you need to learn, all in one place</h1>
        <p className="lead">
          Browse lessons by subject, find the ones that match your level, and keep track of your progress as you
          go. Pick a field below to get started.
        </p>
      </section>

      <div className="panel">
        <h2>Looking for something specific?</h2>
        <p className="lead">Search by subject to jump straight to it.</p>
        <div className="search-row">
          <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search by subject..." aria-label="Search content" />
          <select value={learningType} onChange={(e) => setLearningType(e.target.value)} aria-label="Learning type">
            {LEARNING_TYPES.map((t) => (
              <option key={t} value={t}>{t}</option>
            ))}
          </select>
          <button type="button" className="primary">Search</button>
        </div>
      </div>

      <div className="section-title" style={{ marginTop: 24 }}>Fields</div>
      {loading && <div className="empty-state">Loading...</div>}
      {error && (
        <div className="empty-state">
          Could not load <code>public/data/content.json</code> — run <code>evaluation/build_content_export.py</code> first.
        </div>
      )}
      {!loading && !error && (
        <div className="grid course-grid">
          {filtered.map((f) => (
            <FieldCard
              key={f.field}
              field={f.field}
              count={f.count}
              fileCount={f.files.length}
              topics={TOPICS_BY_FIELD[f.field] || []}
            />
          ))}
        </div>
      )}
    </main>
  );
}
