import React, { useEffect, useState, useCallback } from "react";
import { fetchAuditLogs, type AuditLogItem } from "../services/api";

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
      <div className="page-header-row">
        <div>
          <h2>Security & Compliance Audit Trail</h2>
          <p className="page-subtitle">
            Phase 8 Append-Only Security Audit Log — Tracking logins, incident assignments, resolutions, and system changes.
          </p>
        </div>
        <button
          type="button"
          className="btn btn-secondary btn-sm"
          onClick={() => loadLogs(page)}
          disabled={loading}
        >
          {loading ? "Refreshing..." : "Refresh Audit Log"}
        </button>
      </div>

      {error && <div className="alert alert-error" style={{ marginBottom: 16 }}>{error}</div>}

      {/* Filters */}
      <div className="card" style={{ marginBottom: 16, display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
        <div>
          <label style={{ fontSize: "0.8rem", color: "#94a3b8", display: "block", marginBottom: 4 }}>Filter Action</label>
          <input
            type="text"
            placeholder="e.g. USER_LOGIN or INCIDENT_RESOLVED"
            value={actionFilter}
            onChange={(e) => setActionFilter(e.target.value)}
            style={{ padding: "6px 10px", borderRadius: 6, border: "1px solid #334155", background: "#0f172a", color: "#f8fafc", fontSize: "0.85rem" }}
          />
        </div>

        <div>
          <label style={{ fontSize: "0.8rem", color: "#94a3b8", display: "block", marginBottom: 4 }}>Filter Entity</label>
          <input
            type="text"
            placeholder="e.g. incident or user"
            value={entityFilter}
            onChange={(e) => setEntityFilter(e.target.value)}
            style={{ padding: "6px 10px", borderRadius: 6, border: "1px solid #334155", background: "#0f172a", color: "#f8fafc", fontSize: "0.85rem" }}
          />
        </div>

        <div style={{ marginLeft: "auto", fontSize: "0.85rem", color: "#94a3b8", alignSelf: "flex-end" }}>
          Total Logged Entries: <strong>{total}</strong>
        </div>
      </div>

      {/* Audit Log Table */}
      <div className="card">
        {logs.length === 0 ? (
          <p className="text-muted">No audit log records found.</p>
        ) : (
          <div style={{ overflowX: "auto" }}>
            <table className="logs-table" style={{ width: "100%", fontSize: "0.82rem" }}>
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
                    <td>#{log.id}</td>
                    <td style={{ whiteSpace: "nowrap" }}>{new Date(log.created_at).toLocaleString()}</td>
                    <td>
                      <strong style={{ color: "#38bdf8" }}>{log.actor}</strong>
                    </td>
                    <td>
                      <code style={{ color: "#f59e0b", background: "#0f172a", padding: "2px 5px", borderRadius: 4 }}>
                        {log.action}
                      </code>
                    </td>
                    <td>{log.target_entity}</td>
                    <td>{log.target_id || "—"}</td>
                    <td>
                      <span style={{ fontSize: "0.75rem", color: "#64748b" }}>
                        {log.request_id ? log.request_id.slice(0, 8) + "..." : "—"}
                      </span>
                    </td>
                    <td>
                      {log.metadata && Object.keys(log.metadata).length > 0 ? (
                        <code style={{ fontSize: "0.75rem", color: "#cbd5e1" }}>
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
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: 14 }}>
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              disabled={page <= 1}
              onClick={() => loadLogs(page - 1)}
            >
              Previous
            </button>
            <span style={{ fontSize: "0.85rem", color: "#94a3b8" }}>
              Page {page} of {Math.ceil(total / 50)}
            </span>
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              disabled={page * 50 >= total}
              onClick={() => loadLogs(page + 1)}
            >
              Next
            </button>
          </div>
        )}
      </div>
    </div>
  );
};
