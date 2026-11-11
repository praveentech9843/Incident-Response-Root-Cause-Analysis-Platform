import React, { useEffect, useState, useCallback } from "react";
import { fetchAuditLogs, type AuditLogItem } from "../services/api";
import { History, Search, RefreshCw, ChevronLeft, ChevronRight, Filter } from "lucide-react";

export const AuditLogPage: React.FC = () => {
  const [logs, setLogs] = useState<AuditLogItem[]>([]);
  const [total, setTotal] = useState<number>(0);
  const [page, setPage] = useState<number>(1);
  const [actionFilter, setActionFilter] = useState<string>("");
  const [entityFilter, setEntityFilter] = useState<string>("");
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const loadLogs = useCallback(
    async (p: number) => {
      setLoading(true);
      setError(null);
      try {
        const res = await fetchAuditLogs(p, 50, actionFilter || undefined, entityFilter || undefined);
        setLogs(res.items);
        setTotal(res.total);
        setPage(res.page);
      } catch (err: unknown) {
        setError(err instanceof Error ? err.message : "Failed to load audit logs");
      } finally {
        setLoading(false);
      }
    },
    [actionFilter, entityFilter],
  );

  useEffect(() => {
    let isMounted = true;
    fetchAuditLogs(1, 50, actionFilter || undefined, entityFilter || undefined)
      .then((res) => {
        if (isMounted) {
          setLogs(res.items);
          setTotal(res.total);
          setPage(res.page);
          setLoading(false);
        }
      })
      .catch((err) => {
        if (isMounted) {
          setError(err instanceof Error ? err.message : "Failed to load audit logs");
          setLoading(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, [actionFilter, entityFilter]);

  return (
    <div className="tab-page-container">
      {/* Page Header */}
      <div className="page-header-row">
        <div>
          <h2 className="page-title">Security & Compliance Audit Trail</h2>
          <p className="page-subtitle">
            Phase 8 Append-Only Security Audit Log — Tracking logins, incident assignments, resolutions, and system changes.
          </p>
        </div>
        <button
          type="button"
          className="btn btn-secondary btn-sm"
          onClick={() => loadLogs(page)}
          disabled={loading}
          style={{ display: "inline-flex", alignItems: "center", gap: 6 }}
        >
          <RefreshCw size={14} className={loading ? "spin" : ""} />
          {loading ? "Refreshing..." : "Refresh Audit Log"}
        </button>
      </div>

      {error && <div className="alert alert-error" style={{ marginBottom: 16 }}>{error}</div>}

      {/* Filter Toolbar Card */}
      <div
        className="card"
        style={{
          marginBottom: 16,
          display: "flex",
          gap: 16,
          alignItems: "flex-end",
          flexWrap: "wrap",
          padding: "16px 20px",
        }}
      >
        <div style={{ flex: "1 1 220px" }}>
          <label style={{ fontSize: "0.8rem", fontWeight: 600, color: "#475569", display: "flex", alignItems: "center", gap: 4, marginBottom: 6 }}>
            <Filter size={13} /> Filter by Action
          </label>
          <input
            type="text"
            placeholder="e.g. LOGIN, INCIDENT_ASSIGN, USER_REGISTER"
            value={actionFilter}
            onChange={(e) => setActionFilter(e.target.value)}
            className="input-field"
            style={{ width: "100%", padding: "7px 12px", borderRadius: 8, border: "1px solid #cbd5e1", background: "#ffffff", color: "#0f172a", fontSize: "0.85rem" }}
          />
        </div>

        <div style={{ flex: "1 1 220px" }}>
          <label style={{ fontSize: "0.8rem", fontWeight: 600, color: "#475569", display: "flex", alignItems: "center", gap: 4, marginBottom: 6 }}>
            <Search size={13} /> Filter by Entity
          </label>
          <input
            type="text"
            placeholder="e.g. USER, INCIDENT, ALERT_RULE"
            value={entityFilter}
            onChange={(e) => setEntityFilter(e.target.value)}
            className="input-field"
            style={{ width: "100%", padding: "7px 12px", borderRadius: 8, border: "1px solid #cbd5e1", background: "#ffffff", color: "#0f172a", fontSize: "0.85rem" }}
          />
        </div>

        <div style={{ marginLeft: "auto", fontSize: "0.85rem", color: "#64748b", alignSelf: "center" }}>
          Total Logged Entries: <strong style={{ color: "#0f172a", fontSize: "1rem" }}>{total}</strong>
        </div>
      </div>

      {/* Audit Log Table Card */}
      <div className="card">
        {logs.length === 0 ? (
          <div className="empty-state" style={{ padding: "3rem 1rem" }}>
            <History size={40} style={{ color: "#94a3b8", marginBottom: 8 }} />
            <p className="empty-title">No Audit Records Found</p>
            <p className="empty-subtitle">
              {actionFilter || entityFilter ? "No records match the applied filters." : "The append-only security log is currently clear."}
            </p>
          </div>
        ) : (
          <div className="table-responsive">
            <table className="logs-table" style={{ width: "100%", fontSize: "0.825rem" }}>
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Timestamp</th>
                  <th>Actor</th>
                  <th>Action</th>
                  <th>Entity</th>
                  <th>Entity ID</th>
                  <th>Request ID</th>
                  <th>Metadata</th>
                </tr>
              </thead>
              <tbody>
                {logs.map((log) => (
                  <tr key={log.id}>
                    <td className="log-id">#{log.id}</td>
                    <td style={{ whiteSpace: "nowrap", color: "#475569" }}>
                      {new Date(log.created_at).toLocaleString()}
                    </td>
                    <td>
                      <strong style={{ color: "#1d4ed8" }}>{log.actor}</strong>
                    </td>
                    <td>
                      <code
                        style={{
                          color: "#1e40af",
                          background: "#eff6ff",
                          border: "1px solid #dbeafe",
                          padding: "2px 6px",
                          borderRadius: 4,
                          fontWeight: 600,
                          fontSize: "0.775rem",
                        }}
                      >
                        {log.action}
                      </code>
                    </td>
                    <td>
                      <span className="badge badge-txt">{log.target_entity}</span>
                    </td>
                    <td>{log.target_id || "—"}</td>
                    <td>
                      <span style={{ fontSize: "0.75rem", color: "#64748b", fontFamily: "var(--font-mono)" }}>
                        {log.request_id ? log.request_id.slice(0, 8) + "..." : "—"}
                      </span>
                    </td>
                    <td>
                      {log.metadata && Object.keys(log.metadata).length > 0 ? (
                        <code
                          style={{
                            fontSize: "0.75rem",
                            color: "#334155",
                            background: "#f1f5f9",
                            padding: "2px 6px",
                            borderRadius: 4,
                            maxWidth: "280px",
                            display: "inline-block",
                            overflow: "hidden",
                            textOverflow: "ellipsis",
                            whiteSpace: "nowrap",
                          }}
                          title={JSON.stringify(log.metadata)}
                        >
                          {JSON.stringify(log.metadata)}
                        </code>
                      ) : (
                        "—"
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination controls */}
        {total > 50 && (
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              marginTop: 16,
              paddingTop: 12,
              borderTop: "1px solid #e2e8f0",
            }}
          >
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              disabled={page <= 1}
              onClick={() => loadLogs(page - 1)}
              style={{ display: "inline-flex", alignItems: "center", gap: 4 }}
            >
              <ChevronLeft size={14} /> Previous
            </button>
            <span style={{ fontSize: "0.85rem", color: "#64748b" }}>
              Page {page} of {Math.ceil(total / 50)}
            </span>
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              disabled={page * 50 >= total}
              onClick={() => loadLogs(page + 1)}
              style={{ display: "inline-flex", alignItems: "center", gap: 4 }}
            >
              Next <ChevronRight size={14} />
            </button>
          </div>
        )}
      </div>
    </div>
  );
};
