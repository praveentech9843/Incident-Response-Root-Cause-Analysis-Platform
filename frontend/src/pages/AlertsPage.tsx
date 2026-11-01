import React, { useEffect, useState } from "react";
import {
  fetchAlertRules,
  fetchAlerts,
  fetchNotifications,
  type AlertRule,
  type IncidentAlert,
  type IncidentNotification,
} from "../services/api";

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
      <div className="page-header-row">
        <div>
          <h2>Alerts & Notification Dispatch</h2>
          <p className="page-subtitle">
            Phase 8 Production Alerting Architecture — Deduplicated triggers, escalation rules, and resilient delivery logs.
          </p>
        </div>
        <button
          type="button"
          className="btn btn-secondary btn-sm"
          onClick={loadData}
          disabled={loading}
        >
          {loading ? "Refreshing..." : "Refresh Alerts"}
        </button>
      </div>

      {error && <div className="alert alert-error" style={{ marginBottom: 16 }}>{error}</div>}

      {/* Alert Rules Section */}
      <div className="card" style={{ marginBottom: 20 }}>
        <h3 className="card-title" style={{ marginBottom: 8 }}>Configured Alert Rules</h3>
        <p className="card-subtitle" style={{ marginBottom: 14 }}>
          Idempotent criteria evaluated deterministically against correlated incidents.
        </p>

        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: 12 }}>
          {rules.map((rule) => (
            <div
              key={rule.id}
              style={{
                background: "#0f172a",
                border: "1px solid #334155",
                borderRadius: 8,
                padding: "12px",
                display: "flex",
                flexDirection: "column",
                justifyContent: "space-between",
              }}
            >
              <div>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <strong style={{ fontSize: "0.9rem", color: "#f8fafc" }}>{rule.name}</strong>
                  <span
                    style={{
                      fontSize: "0.7rem",
                      padding: "2px 6px",
                      borderRadius: 4,
                      background: rule.is_active ? "#065f46" : "#475569",
                      color: "#f8fafc",
                    }}
                  >
                    {rule.is_active ? "ACTIVE" : "DISABLED"}
                  </span>
                </div>
                <p style={{ fontSize: "0.8rem", color: "#94a3b8", margin: "6px 0" }}>
                  {rule.description || rule.condition_type}
                </p>
              </div>
              <div style={{ fontSize: "0.75rem", color: "#64748b", marginTop: 8 }}>
                Condition: <code style={{ color: "#38bdf8" }}>{rule.condition_type}</code>
                {rule.threshold_minutes && ` (> ${rule.threshold_minutes}m)`}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Active & Historical Alerts */}
      <div className="card" style={{ marginBottom: 20 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
          <h3 className="card-title" style={{ margin: 0 }}>Triggered Incidents Alerts</h3>
          <span style={{ fontSize: "0.8rem", color: "#94a3b8" }}>{alerts.length} Triggered</span>
        </div>

        {alerts.length === 0 ? (
          <p className="text-muted">No alerts currently triggered.</p>
        ) : (
          <div style={{ overflowX: "auto" }}>
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
                      <strong style={{ color: "#38bdf8" }}>Incident #{al.incident_id}</strong>
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
                      <code style={{ fontSize: "0.75rem", color: "#cbd5e1" }}>{al.dedup_key}</code>
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
          <h3 className="card-title" style={{ margin: 0 }}>Notification Dispatch History</h3>
          <span style={{ fontSize: "0.8rem", color: "#94a3b8" }}>{notifications.length} Attempts</span>
        </div>

        {notifications.length === 0 ? (
          <p className="text-muted">No notification delivery attempts recorded.</p>
        ) : (
          <div style={{ overflowX: "auto" }}>
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
                    <td>Incident #{notif.incident_id}</td>
                    <td>
                      <strong>{notif.channel}</strong>
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
                      <span style={{ fontSize: "0.8rem", color: notif.error_message ? "#f87171" : "#10b981" }}>
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
