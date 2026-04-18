/**
 * App shell: sticky header + tabbed bottom nav that fits iPhone safe-area insets.
 */
import { NavLink, Outlet } from "react-router-dom";


export function Layout() {
  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="brand">
          <span className="brand-mark">AMG</span>
          <span className="brand-sub">Mobile Command</span>
        </div>
        <NavLink to="/settings" className="header-btn" aria-label="Settings">
          <span aria-hidden="true">⚙</span>
        </NavLink>
      </header>

      <main className="app-main">
        <Outlet />
      </main>

      <nav className="app-nav" aria-label="Primary">
        <NavLink to="/" end className="nav-tab">
          <span className="nav-icon" aria-hidden="true">◉</span>
          <span className="nav-label">Command</span>
        </NavLink>
        <NavLink to="/voice" className="nav-tab">
          <span className="nav-icon" aria-hidden="true">◯</span>
          <span className="nav-label">Voice</span>
        </NavLink>
        <NavLink to="/settings" className="nav-tab">
          <span className="nav-icon" aria-hidden="true">☰</span>
          <span className="nav-label">Settings</span>
        </NavLink>
      </nav>
    </div>
  );
}
