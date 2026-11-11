import React, { useState } from "react";
import { NavLink, Outlet, useNavigate, useLocation } from "react-router-dom";
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
  ChevronLeft,
  ChevronRight,
  Compass,
} from "lucide-react";

export const AppLayout: React.FC = () => {
  const { user, role, isAdmin, isDeveloper, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  // Collapsible sidebar state with local storage persistence
  const [collapsed, setCollapsed] = useState<boolean>(() => {
    return localStorage.getItem("platform_sidebar_collapsed") === "true";
  });

  const toggleSidebar = () => {
    setCollapsed((prev) => {
      const next = !prev;
      localStorage.setItem("platform_sidebar_collapsed", String(next));
      return next;
    });
  };

  const handleLogout = async () => {
    await logout();
    navigate("/login", { replace: true });
  };

  // Derive breadcrumb info from current path
  const getBreadcrumb = () => {
    const p = location.pathname;
    if (p.startsWith("/incidents")) return { section: "Detection & RCA", title: "Correlated Incidents" };
    if (p.startsWith("/logs")) return { section: "Data Pipeline", title: "Live Logs & Structured Parsing" };
    if (p.startsWith("/alerts")) return { section: "Operations", title: "Alerts & Notifications" };
    if (p.startsWith("/observability")) return { section: "Monitoring", title: "System Observability & Health" };
    if (p.startsWith("/integrations")) return { section: "Configuration", title: "External Integrations" };
    if (p.startsWith("/audit")) return { section: "Compliance", title: "Security & Operations Audit Trail" };
    return { section: "Platform", title: "Overview" };
  };

  const breadcrumb = getBreadcrumb();

  return (
    <div className={`enterprise-shell ${collapsed ? "sidebar-is-collapsed" : ""}`}>
      {/* 1. FIXED COLLAPSIBLE WHITE SIDEBAR */}
      <aside className={`enterprise-sidebar ${collapsed ? "collapsed" : ""}`} aria-label="Main Navigation">
        {/* Brand Header */}
        <div className="sidebar-brand-wrapper">
          <div className="brand-logo-badge">
            <ShieldAlert size={22} className="brand-shield-icon" />
          </div>
          {!collapsed && (
            <div className="brand-title-box">
              <span className="brand-primary-name">IncidentPulse</span>
              <span className="brand-tagline">AI RCA PLATFORM</span>
            </div>
          )}
          <button
            type="button"
            className="sidebar-collapse-btn"
            onClick={toggleSidebar}
            title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          >
            {collapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
          </button>
        </div>

        {/* Navigation Sections */}
        <div className="sidebar-scrollable-area">
          {/* Section: Monitoring & RCA */}
          <div className="nav-group">
            {!collapsed && <span className="nav-group-label">INCIDENT INTELLIGENCE</span>}
            <nav className="sidebar-nav-list">
              <NavLink
                to="/incidents"
                className={({ isActive }) => `sidebar-nav-item ${isActive ? "active" : ""}`}
                title="Correlated Incidents"
              >
                <span className="nav-item-icon-box">
                  <Flame size={18} />
                </span>
                {!collapsed && <span className="nav-item-text">Correlated Incidents</span>}
              </NavLink>

              <NavLink
                to="/logs"
                className={({ isActive }) => `sidebar-nav-item ${isActive ? "active" : ""}`}
                title="Live Logs & Parsing"
              >
                <span className="nav-item-icon-box">
                  <FileText size={18} />
                </span>
                {!collapsed && <span className="nav-item-text">Live Logs & Ingestion</span>}
              </NavLink>
            </nav>
          </div>

          {/* Section: Operations & Reliability */}
          <div className="nav-group">
            {!collapsed && <span className="nav-group-label">SYSTEM & TELEMETRY</span>}
            <nav className="sidebar-nav-list">
              <NavLink
                to="/observability"
                className={({ isActive }) => `sidebar-nav-item ${isActive ? "active" : ""}`}
                title="System Observability"
              >
                <span className="nav-item-icon-box">
                  <Activity size={18} />
                </span>
                {!collapsed && <span className="nav-item-text">Observability Probes</span>}
              </NavLink>

              {(isDeveloper || isAdmin) && (
                <NavLink
                  to="/alerts"
                  className={({ isActive }) => `sidebar-nav-item ${isActive ? "active" : ""}`}
                  title="Alerts & Notifications"
                >
                  <span className="nav-item-icon-box">
                    <Bell size={18} />
                  </span>
                  {!collapsed && <span className="nav-item-text">Alerts & Dispatch</span>}
                </NavLink>
              )}
            </nav>
          </div>

          {/* Section: Administration & Audit */}
          {isAdmin && (
            <div className="nav-group">
              {!collapsed && <span className="nav-group-label">ADMINISTRATION</span>}
              <nav className="sidebar-nav-list">
                <NavLink
                  to="/integrations"
                  className={({ isActive }) => `sidebar-nav-item ${isActive ? "active" : ""}`}
                  title="External Integrations"
                >
                  <span className="nav-item-icon-box">
                    <Workflow size={18} />
                  </span>
                  {!collapsed && <span className="nav-item-text">Integrations</span>}
                </NavLink>

                <NavLink
                  to="/audit"
                  className={({ isActive }) => `sidebar-nav-item ${isActive ? "active" : ""}`}
                  title="Security Audit Trail"
                >
                  <span className="nav-item-icon-box">
                    <History size={18} />
                  </span>
                  {!collapsed && <span className="nav-item-text">Security Audit Trail</span>}
                </NavLink>
              </nav>
            </div>
          )}
        </div>

        {/* Sidebar Footer: User Card */}
        <div className="sidebar-footer">
          {user && (
            <div className="user-profile-compact" title={`Signed in as ${user.username} (${role || "USER"})`}>
              <div className="user-avatar-circle">
                <UserIcon size={16} />
              </div>
              {!collapsed && (
                <div className="user-info-text">
                  <span className="user-display-name">{user.username}</span>
                  <span className="user-role-badge">{role || "USER"}</span>
                </div>
              )}
            </div>
          )}
        </div>
      </aside>

      {/* 2. MAIN APPLICATION CONTENT WRAPPER */}
      <div className="enterprise-main-wrapper">
        {/* CLEAN TOP NAVIGATION BAR */}
        <header className="enterprise-topbar">
          <div className="topbar-left">
            {/* Breadcrumb Navigation */}
            <div className="breadcrumb-nav">
              <span className="breadcrumb-section">
                <Compass size={14} className="breadcrumb-icon" />
                {breadcrumb.section}
              </span>
              <span className="breadcrumb-divider">/</span>
              <span className="breadcrumb-current">{breadcrumb.title}</span>
            </div>
          </div>

          <div className="topbar-right">
            {/* Live Monitoring Status Indicator */}
            <div className="system-live-pill" title="Live telemetry engine active">
              <span className="pulse-indicator">
                <span className="pulse-ring" />
                <span className="pulse-core" />
              </span>
              <span className="live-status-label">Operational</span>
            </div>

            {/* Environment Indicator */}
            <span className="env-badge">Dev Cluster</span>

            {/* Quick User Role Indicator */}
            {user && (
              <div className="topbar-user-pill">
                <span className="topbar-username">{user.username}</span>
                <span className={`topbar-role-tag ${role === "ADMIN" ? "role-admin" : "role-dev"}`}>
                  {role}
                </span>
              </div>
            )}

            {/* Sign Out Action Button */}
            <button
              type="button"
              className="topbar-signout-btn"
              onClick={handleLogout}
              title="Sign out of current session"
            >
              <LogOut size={15} />
              <span className="signout-label">Sign Out</span>
            </button>
          </div>
        </header>

        {/* MAIN OUTLET CONTAINER */}
        <main className="enterprise-page-outlet">
          <Outlet />
        </main>
      </div>
    </div>
  );
};
