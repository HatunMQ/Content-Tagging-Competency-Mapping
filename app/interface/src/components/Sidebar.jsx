import { Link } from "react-router-dom";

export default function Sidebar({ open, onClose }) {
  return (
    <>
      <div
        className="drawer-backdrop"
        style={{ opacity: open ? 1 : 0, pointerEvents: open ? "auto" : "none" }}
        onClick={onClose}
      />
      <aside
        className="drawer"
        style={{ transform: open ? "translateX(0)" : "translateX(-104%)" }}
        aria-label="Learning menu"
      >
        <div className="drawer-head">
          <div>
            <strong style={{ fontSize: 14 }}>Learning Menu</strong>
            <div className="small">Personal learning views and progress tools</div>
          </div>
          <button
            onClick={onClose}
            aria-label="Close menu"
            style={{ border: "none", background: "none", fontSize: 20, lineHeight: 1, color: "var(--slate-500)" }}
          >
            ×
          </button>
        </div>

        <div className="drawer-title">Learner workspace</div>
        <Link to="/my-learning" onClick={onClose} className="drawer-item">
          <strong>My Learning</strong>
          <div>The courses you've enrolled in, and their real content.</div>
        </Link>
        <Link to="/progress" onClick={onClose} className="drawer-item">
          <strong>Progress Dashboard</strong>
          <div>Competency mastery computed from what you've actually completed.</div>
        </Link>
      </aside>
    </>
  );
}
