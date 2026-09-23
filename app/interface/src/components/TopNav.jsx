import { Link, useLocation, useNavigate } from "react-router-dom";

export default function TopNav({ onMenuClick }) {
  const location = useLocation();
  const navigate = useNavigate();
  const onInfra = location.pathname === "/infra";

  return (
    <header className="topbar">
      <div className="brand-area">
        <button className="menu-btn" aria-label="Open learning menu" onClick={onMenuClick}>
          <span className="hamburger"><span></span><span></span><span></span></span>
        </button>
        <Link to="/" style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <div className="brand-mark">CT</div>
          <div className="brand">
            <strong>Content Tagging &amp; Competency Mapping</strong>
            <span>AI-powered learning content platform</span>
          </div>
        </Link>
      </div>

      <nav className="top-nav" aria-label="Main navigation">
        <button className={`nav-btn ${!onInfra ? "active" : ""}`} onClick={() => navigate("/")}>
          Learning Platform
        </button>
        <button className={`nav-btn ${onInfra ? "active" : ""}`} onClick={() => navigate("/infra")}>
          Infra Dashboard
        </button>
      </nav>
    </header>
  );
}
