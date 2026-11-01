import React from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "../context/useAuth";
import {
  ShieldAlert,
  Flame,
  FileText,
  Workflow,
  Bell,
  History,
  Activity,
  LogOut,
  User as UserIcon,
} from "lucide-react";

export const AppLayout: React.FC = () => {
  const { user, role, isAdmin, isDeveloper, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = async () => {
    await logout();
    navigate("/login", { replace: true });
  };

  return (
    <div className="app-shell">
      <header className="top-navbar">
        <div className="brand-section">
          <div
            style={{
              width: 34,
              height: 34,
              borderRadius: 8,
              background: "linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              color: "#ffffff",
              boxShadow: "0 2px 4px rgba(37,99,235,0.25)",
            }}
          >
            <ShieldAlert size={20} />
          </div>
          <h1 className="brand-title">AI Incident Response & RCA</h1>
          <span className="phase-tag">v1.0 • Active Workspace</span>
        </div>

        <nav className="nav-tabs" aria-label="Main Navigation">
          <NavLink
            to="/incidents"
            className={({ isActive }) => `nav-tab-btn ${isActive ? "active" : ""}`}
            style={{ display: "inline-flex", alignItems: "center", gap: 6 }}
          >
            <Flame size={15} />
            Correlated Incidents
          </NavLink>

          <NavLink
            to="/logs"
            className={({ isActive }) => `nav-tab-btn ${isActive ? "active" : ""}`}
            style={{ display: "inline-flex", alignItems: "center", gap: 6 }}
          >
            <FileText size={15} />
            Live Logs & Parsing
          </NavLink>

          {isAdmin && (
            <NavLink
              to="/integrations"
              className={({ isActive }) => `nav-tab-btn ${isActive ? "active" : ""}`}
              style={{ display: "inline-flex", alignItems: "center", gap: 6 }}
            >
              <Workflow size={15} />
              Integrations
            </NavLink>
          )}

          {(isDeveloper || isAdmin) && (
            <NavLink
              to="/alerts"
              className={({ isActive }) => `nav-tab-btn ${isActive ? "active" : ""}`}
              style={{ display: "inline-flex", alignItems: "center", gap: 6 }}
            >
              <Bell size={15} />
              Alerts & Notifications
            </NavLink>
          )}

          {isAdmin && (
            <NavLink
              to="/audit"
              className={({ isActive }) => `nav-tab-btn ${isActive ? "active" : ""}`}
              style={{ display: "inline-flex", alignItems: "center", gap: 6 }}
            >
              <History size={15} />
              Audit Trail
            </NavLink>
          )}

          <NavLink
            to="/observability"
            className={({ isActive }) => `nav-tab-btn ${isActive ? "active" : ""}`}
            style={{ display: "inline-flex", alignItems: "center", gap: 6 }}
          >
            <Activity size={15} />
            System Observability
          </NavLink>
        </nav>

        {/* User Profile / Logout */}
        <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 10 }}>
          {user && (
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 8,
                background: "#f1f5f9",
                border: "1px solid #e2e8f0",
                padding: "4px 10px",
                borderRadius: 8,
              }}
            >
              <div
                style={{
                  width: 24,
                  height: 24,
                  borderRadius: "50%",
                  background: "#2563eb",
                  color: "#ffffff",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                }}
              >
                <UserIcon size={14} />
              </div>
              <div style={{ display: "flex", flexDirection: "column", lineHeight: 1.1 }}>
                <span style={{ fontSize: "0.825rem", fontWeight: 600, color: "#0f172a" }}>
                  {user.username}
                </span>
                <span style={{ fontSize: "0.7rem", color: "#64748b", fontWeight: 500 }}>
                  {role || "USER"}
                </span>
              </div>
            </div>
          )}

          <button
            type="button"
            className="btn btn-secondary btn-sm"
            onClick={handleLogout}
            style={{
              fontSize: "0.8rem",
              padding: "6px 10px",
              display: "inline-flex",
              alignItems: "center",
              gap: 6,
            }}
            title="Sign out of platform"
          >
            <LogOut size={14} />
            Sign Out
          </button>
        </div>
      </header>

      <main className="content-container">
        <Outlet />
      </main>
    </div>
  );
};
