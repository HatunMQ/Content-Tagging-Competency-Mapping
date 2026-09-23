import { useState } from "react";
import { resolvePath } from "../hooks/useJsonData.js";

// Same visual language as FieldContent.jsx's FileCard: teal header with the
// file name, an "Open original ↗" link to public/raw/<file_name>, and a
// done/total count — kept as its own <div className="card"> per file so the
// summary list here reads the same way the full file page does. The header
// itself is a plain <div> (not a <button>) with two separate toggle buttons
// (the title and the ▲/▼) inside it, instead of wrapping the whole header in
// one <button> — nesting the "Open original" <a> inside a <button> isn't
// valid HTML and the link wouldn't reliably work.
export default function ChapterRow({ title, sessions }) {
  const [open, setOpen] = useState(false);
  const doneCount = sessions.filter((s) => s.done).length;
  const originalUrl = resolvePath(`/raw/${encodeURIComponent(title)}`);

  return (
    <div className="card" style={{ overflow: "hidden", marginBottom: 12 }}>
      <div
        style={{
          background: "var(--teal)",
          color: "#fff",
          padding: "12px 16px",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          gap: 14,
          flexWrap: "wrap",
        }}
      >
        <button
          onClick={() => setOpen((v) => !v)}
          style={{
            background: "none",
            border: "none",
            color: "#fff",
            font: "inherit",
            fontWeight: 700,
            fontSize: 13.5,
            padding: 0,
            cursor: "pointer",
            textAlign: "left",
            flex: 1,
          }}
        >
          {title}
        </button>
        <div style={{ display: "flex", alignItems: "center", gap: 14, fontSize: 12.5 }}>
          <a
            href={originalUrl}
            target="_blank"
            rel="noreferrer"
            style={{ color: "#fff", fontWeight: 600, textDecoration: "underline" }}
          >
            Open original ↗
          </a>
          <span style={{ fontWeight: 800 }}>
            {doneCount}/{sessions.length}
          </span>
          <button
            onClick={() => setOpen((v) => !v)}
            aria-label={open ? "Collapse" : "Expand"}
            style={{ background: "none", border: "none", color: "#fff", cursor: "pointer", fontSize: 13, padding: 0 }}
          >
            {open ? "▲" : "▼"}
          </button>
        </div>
      </div>
      {open && (
        <div style={{ padding: "10px 14px 12px", display: "flex", flexDirection: "column", gap: 6 }}>
          {sessions.map((s) => (
            <div key={s.title} style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13, padding: "4px 4px" }}>
              <span
                style={{
                  width: 16,
                  height: 16,
                  borderRadius: "50%",
                  background: s.done ? "var(--green-600)" : "var(--slate-200)",
                  color: "#fff",
                  fontSize: 10,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  flexShrink: 0,
                }}
              >
                {s.done ? "Done" : ""}
              </span>
              <span style={{ color: s.done ? "var(--slate-500)" : "var(--slate-900)" }}>{s.title}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
