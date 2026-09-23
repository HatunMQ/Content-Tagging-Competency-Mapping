import { useState } from "react";
import { useLearnerState } from "../state/LearnerStateContext.jsx";

// Chapters tab: one collapsible block per file (our data has no week/day
// split like the prototype's course did, so each source FILE stands in for
// a "chapter" — its content chunks are the outline underneath). Read-only
// outline: the actual "mark done" toggle lives on the file card in the
// Activities tab (one checkbox per file), not per line here.
export default function ChaptersOutline({ field, files }) {
  const [openFiles, setOpenFiles] = useState(() => new Set(files.map((f) => f.file_name)));
  const { isFileComplete } = useLearnerState();

  function toggle(fileName) {
    setOpenFiles((prev) => {
      const next = new Set(prev);
      if (next.has(fileName)) next.delete(fileName);
      else next.add(fileName);
      return next;
    });
  }

  function collapseAll() {
    setOpenFiles(new Set());
  }

  function expandAll() {
    setOpenFiles(new Set(files.map((f) => f.file_name)));
  }

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginBottom: 12 }}>
        <button className="download-btn" onClick={expandAll}>Expand All</button>
        <button className="download-btn" onClick={collapseAll}>Collapse All</button>
      </div>

      {files.map((file, idx) => {
        const open = openFiles.has(file.file_name);
        const done = isFileComplete(field, file.file_name);
        return (
          <div key={file.file_name} className={`chapter-full${open ? " open" : ""}`}>
            <div className="chapter-full-head" onClick={() => toggle(file.file_name)}>
              <span>
                File {idx + 1}: {file.file_name}
                {done && <span className="badge badge-ok" style={{ marginRight: 8 }}>Complete</span>}
              </span>
              <span>{open ? "⌃" : "⌄"}</span>
            </div>
            {open &&
              file.items.map((item) => (
                <div key={item.chunk_id} className="activity-line">
                  <span className="tiny-check" />
                  <span>▱</span>
                  <span>{item.section_title || item.chunk_id}</span>
                  <span className="mini-tag" style={{ marginRight: "auto" }}>{item.Level}</span>
                </div>
              ))}
          </div>
        );
      })}
    </div>
  );
}
