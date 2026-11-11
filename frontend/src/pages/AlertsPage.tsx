import React, { useEffect, useState } from "react";
import {
  fetchAlertRules,
  fetchAlerts,
  fetchNotifications,
  type AlertRule,
  type IncidentAlert,
  type IncidentNotification,
} from "../services/api";
import { Bell, RefreshCw, ShieldAlert, CheckCircle2, Clock, Send } from "lucide-react";

export const AlertsPage: React.FC = () => {
  const [rules, setRules] = useState<AlertRule[]>([]);
  const [alerts, setAlerts] = useState<IncidentAlert[]>([]);
  const [notifications, setNotifications] = useState<IncidentNotification[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [rulesData, alertsData, notifsData] = await Promise.all([
        fetchAlertRules(),
        fetchAlerts(),
        fetchNotifications(),
      ]);
      setRules(rulesData);
      setAlerts(alertsData);
      setNotifications(notifsData);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load alerts and notifications");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    let isMounted = true;
    Promise.all([
      fetchAlertRules(),
      fetchAlerts(),
      fetchNotifications(),
    ])
      .then(([rulesData, alertsData, notifsData]) => {
        if (isMounted) {
          setRules(rulesData);
          setAlerts(alertsData);
          setNotifications(notifsData);
          setLoading(false);
        }
      })
      .catch((err) => {
        if (isMounted) {
          setError(err instanceof Error ? err.message : "Failed to load alerts and notifications");
          setLoading(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, []);

  return (
    <div className="tab-page-container">
      {/* Page Header */}
      <div className="page-header-row">
        <div>
          <h2 className="page-title">Alerts & Notification Dispatch</h2>
          <p className="page-subtitle">
            Phase 8 Production Alerting Architecture — Deduplicated triggers, escalation rules, and resilient delivery logs.
          </p>
        </div>
        <button
          type="button"
          className="btn btn-secondary btn-sm"
          onClick={loadData}
          disabled={loading}
          style={{ display: "inline-flex", alignItems: "center", gap: 6 }}
        >
          <RefreshCw size={14} className={loading ? "spin" : ""} />
          {loading ? "Refreshing..." : "Refresh Alerts"}
        </button>
      </div>

      {error && <div className="alert alert-error" style={{ marginBottom: 16 }}>{error}</div>}

      {/* KPI Stats Cards */}
      <div className="kpi-grid" style={{ marginBottom: 20 }}>
        <div className="card kpi-card">
          <div className="kpi-header">
            <span className="kpi-title">Active Alert Rules</span>
            <div className="kpi-icon-box" style={{ background: "#eff6ff", color: "#1d4ed8" }}>
              <Bell size={18} />
            </div>
          </div>
          <div className="kpi-value">{rules.filter((r) => r.is_active).length}</div>
          <span className="kpi-hint">{rules.length} total configured</span>
        </div>

        <div className="card kpi-card">
          <div className="kpi-header">
            <span className="kpi-title">Triggered Alerts</span>
            <div className="kpi-icon-box" style={{ background: "#fef3c7", color: "#b45309" }}>
              <ShieldAlert size={18} />
            </div>
          </div>
          <div className="kpi-value">{alerts.length}</div>
          <span className="kpi-hint">
            {alerts.filter((a) => a.status === "ACTIVE").length} currently active
          </span>
        </div>

        <div className="card kpi-card">
          <div className="kpi-header">
            <span className="kpi-title">Dispatched Notifications</span>
            <div className="kpi-icon-box" style={{ background: "#f0fdf4", color: "#16a34a" }}>
              <Send size={18} />
            </div>
          </div>
          <div className="kpi-value">{notifications.length}</div>
          <span className="kpi-hint">
            {notifications.filter((n) => n.status === "SENT").length} delivered successfully
          </span>
        </div>
      </div>

      {/* Alert Rules Section */}
      <div className="card" style={{ marginBottom: 20 }}>
        <div className="card-header-row" style={{ marginBottom: 12 }}>
          <div>
            <h3 className="card-title">Configured Alert Rules</h3>
            <p className="card-subtitle">
              Idempotent criteria evaluated deterministically against correlated incidents.
            </p>
          </div>
          <span className="badge badge-json">{rules.length} Defined</span>
        </div>

        {rules.length === 0 ? (
          <div className="empty-state" style={{ padding: "2rem 1rem" }}>
            <Bell size={32} style={{ color: "#94a3b8", marginBottom: 8 }} />
            <p className="empty-title">No Alert Rules Configured</p>
            <p className="empty-subtitle">Rules trigger notifications when critical incidents occur or exceed time thresholds.</p>
          </div>
        ) : (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: 12 }}>
            {rules.map((rule) => (
              <div
                key={rule.id}
                style={{
                  background: "#f8fafc",
                  border: "1px solid #e2e8f0",
                  borderRadius: 10,
                  padding: "14px",
                  display: "flex",
                  flexDirection: "column",
                  justifyContent: "space-between",
                  boxShadow: "0 1px 2px rgba(0,0,0,0.02)",
                }}
              >
                <div>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <strong style={{ fontSize: "0.9rem", color: "#0f172a" }}>{rule.name}</strong>
                    <span
                      style={{
                        fontSize: "0.7rem",
                        padding: "2px 8px",
                        borderRadius: 6,
                        fontWeight: 600,
                        background: rule.is_active ? "#dcfce7" : "#f1f5f9",
                        color: rule.is_active ? "#15803d" : "#64748b",
                        border: rule.is_active ? "1px solid #bbf7d0" : "1px solid #e2e8f0",
                      }}
                    >
                      {rule.is_active ? "ACTIVE" : "DISABLED"}
                    </span>
                  </div>
                  <p style={{ fontSize: "0.8rem", color: "#475569", margin: "8px 0" }}>
                    {rule.description || rule.condition_type}
                  </p>
                </div>
                <div style={{ fontSize: "0.75rem", color: "#64748b", marginTop: 8, borderTop: "1px solid #e2e8f0", paddingTop: 8 }}>
                  Condition: <code style={{ color: "#1d4ed8", background: "#eff6ff", padding: "2px 5px", borderRadius: 4 }}>{rule.condition_type}</code>
                  {rule.threshold_minutes && ` (> ${rule.threshold_minutes}m)`}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Active & Historical Alerts */}
      <div className="card" style={{ marginBottom: 20 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
          <div>
            <h3 className="card-title" style={{ margin: 0 }}>Triggered Incidents Alerts</h3>
            <p className="card-subtitle" style={{ margin: "2px 0 0" }}>
              Real-time alert events with automated deduplication keys.
            </p>
          </div>
          <span className="badge badge-log">{alerts.length} Triggered</span>
        </div>

        {alerts.length === 0 ? (
          <div className="empty-state" style={{ padding: "2.5rem 1rem" }}>
            <CheckCircle2 size={36} style={{ color: "#16a34a", marginBottom: 8 }} />
            <p className="empty-title">All Systems Quiet</p>
            <p className="empty-subtitle">Zero triggered alerts at this moment.</p>
          </div>
        ) : (
          <div className="table-responsive">
            <table className="logs-table" style={{ width: "100%", fontSize: "0.85rem" }}>
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Incident ID</th>
                  <th>Type</th>
                  <th>Severity</th>
                  <th>Status</th>
                  <th>Deduplication Key</th>
                  <th>Triggered At</th>
                </tr>
              </thead>
              <tbody>
                {alerts.map((al) => (
                  <tr key={al.id}>
                    <td>#{al.id}</td>
                    <td>
                      <strong style={{ color: "var(--primary, #1d4ed8)" }}>Incident #{al.incident_id}</strong>
                    </td>
                    <td>{al.alert_type}</td>
                    <td>
                      <span className="severity-badge">{al.severity}</span>
                    </td>
                    <td>
                      <span
                        className={
                          al.status === "RESOLVED"
                            ? "status-badge status-resolved"
                            : "status-badge status-open"
                        }
                      >
                        {al.status}
                      </span>
                    </td>
                    <td>
                      <code className="hash-code">{al.dedup_key}</code>
                    </td>
                    <td>{new Date(al.created_at).toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Notifications Delivery Log */}
      <div className="card">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
          <div>
            <h3 className="card-title" style={{ margin: 0 }}>Notification Dispatch History</h3>
            <p className="card-subtitle" style={{ margin: "2px 0 0" }}>
              Audited delivery receipts across Slack, Email, and PagerDuty channels.
            </p>
          </div>
          <span className="badge badge-txt">{notifications.length} Attempts</span>
        </div>

        {notifications.length === 0 ? (
          <div className="empty-state" style={{ padding: "2.5rem 1rem" }}>
            <Clock size={36} style={{ color: "#94a3b8", marginBottom: 8 }} />
            <p className="empty-title">No Dispatch Records</p>
            <p className="empty-subtitle">No notification delivery attempts have been logged yet.</p>
          </div>
        ) : (
          <div className="table-responsive">
            <table className="logs-table" style={{ width: "100%", fontSize: "0.85rem" }}>
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Incident</th>
                  <th>Channel</th>
                  <th>Recipient</th>
                  <th>Status</th>
                  <th>Retries</th>
                  <th>Result / Error</th>
                  <th>Dispatched At</th>
                </tr>
              </thead>
              <tbody>
                {notifications.map((notif) => (
                  <tr key={notif.id}>
                    <td>#{notif.id}</td>
                    <td>
                      <strong>Incident #{notif.incident_id}</strong>
                    </td>
                    <td>
                      <span className="badge badge-txt">{notif.channel}</span>
                    </td>
                    <td>{notif.recipient}</td>
                    <td>
                      <span
                        className={
                          notif.status === "SENT"
                            ? "status-badge status-resolved"
                            : notif.status === "NOT_CONNECTED"
                            ? "status-badge status-open"
                            : "status-badge status-investigating"
                        }
                      >
                        {notif.status}
                      </span>
                    </td>
                    <td>{notif.retry_count}</td>
                    <td>
                      <span style={{ fontSize: "0.8rem", color: notif.error_message ? "#dc2626" : "#16a34a", fontWeight: 500 }}>
                        {notif.error_message || "Delivered successfully"}
                      </span>
                    </td>
                    <td>{new Date(notif.created_at).toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};
