import React, { useEffect, useState } from "react";
import {
  fetchIntegrationStatus,
  fetchRecentDeployments,
  fetchRecentCommits,
  fetchInfrastructureStatus,
  queryMetrics,
  type IntegrationsStatusResponse,
  type IntegrationStatusItem,
} from "../services/api";

export const IntegrationsPage: React.FC = () => {
  const [statusData, setStatusData] = useState<IntegrationsStatusResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Interactive probe test states
  const [activeTest, setActiveTest] = useState<string | null>(null);
  const [testResult, setTestResult] = useState<unknown | null>(null);
  const [testLoading, setTestLoading] = useState<boolean>(false);

  const loadStatus = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchIntegrationStatus();
      setStatusData(data);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load integration status");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    let isMounted = true;
    fetchIntegrationStatus()
      .then((data) => {
        if (isMounted) {
          setStatusData(data);
          setLoading(false);
        }
      })
      .catch((err) => {
        if (isMounted) {
          setError(err instanceof Error ? err.message : "Failed to load integration status");
          setLoading(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, []);

  const runDeploymentProbe = async () => {
    setActiveTest("Deployment (GitHub Actions)");
    setTestLoading(true);
    setTestResult(null);
    try {
      const res = await fetchRecentDeployments(5);
      setTestResult(res);
    } catch (err: unknown) {
      setTestResult({ error: err instanceof Error ? err.message : "Probe failed" });
    } finally {
      setTestLoading(false);
    }
  };

  const runCommitProbe = async () => {
    setActiveTest("Source Control (GitHub)");
    setTestLoading(true);
    setTestResult(null);
    try {
      const res = await fetchRecentCommits(5);
      setTestResult(res);
    } catch (err: unknown) {
      setTestResult({ error: err instanceof Error ? err.message : "Probe failed" });
    } finally {
      setTestLoading(false);
    }
  };

  const runInfraProbe = async () => {
    setActiveTest("Infrastructure (Kubernetes)");
    setTestLoading(true);
    setTestResult(null);
    try {
      const res = await fetchInfrastructureStatus();
      setTestResult(res);
    } catch (err: unknown) {
      setTestResult({ error: err instanceof Error ? err.message : "Probe failed" });
    } finally {
      setTestLoading(false);
    }
  };

  const runMetricsProbe = async () => {
    setActiveTest("Metrics (Prometheus)");
    setTestLoading(true);
    setTestResult(null);
    try {
      const res = await queryMetrics("up");
      setTestResult(res);
    } catch (err: unknown) {
      setTestResult({ error: err instanceof Error ? err.message : "Probe failed" });
    } finally {
      setTestLoading(false);
    }
  };

  const getBadgeClass = (state: string) => {
    switch (state) {
      case "CONNECTED":
        return "status-badge status-resolved";
      case "NOT_CONNECTED":
        return "status-badge status-open";
      case "UNAVAILABLE":
        return "status-badge status-investigating";
      default:
        return "status-badge";
    }
  };

  return (
    <div className="tab-page-container">
      <div className="page-header-row">
        <div>
          <h2>External Integrations & Observability</h2>
          <p className="page-subtitle">
            Phase 8 Production Integration Architecture — Strictly real connections with explicit NOT_CONNECTED states.
          </p>
        </div>
        <button
          type="button"
          className="btn btn-secondary btn-sm"
          onClick={loadStatus}
          disabled={loading}
        >
          {loading ? "Refreshing..." : "Refresh Status"}
        </button>
      </div>

      {error && <div className="alert alert-error" style={{ marginBottom: 16 }}>{error}</div>}

      {/* Summary Row */}
      {statusData && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: 12, marginBottom: 20 }}>
          <div className="card" style={{ padding: "12px 16px" }}>
            <span style={{ fontSize: "0.8rem", color: "#94a3b8" }}>Total Providers</span>
            <div style={{ fontSize: "1.4rem", fontWeight: 700, marginTop: 4 }}>{statusData.summary.total}</div>
          </div>
          <div className="card" style={{ padding: "12px 16px" }}>
            <span style={{ fontSize: "0.8rem", color: "#94a3b8" }}>Connected</span>
            <div style={{ fontSize: "1.4rem", fontWeight: 700, color: "#10b981", marginTop: 4 }}>
              {statusData.summary.connected}
            </div>
          </div>
          <div className="card" style={{ padding: "12px 16px" }}>
            <span style={{ fontSize: "0.8rem", color: "#94a3b8" }}>Not Connected</span>
            <div style={{ fontSize: "1.4rem", fontWeight: 700, color: "#f59e0b", marginTop: 4 }}>
              {statusData.summary.not_connected}
            </div>
          </div>
          <div className="card" style={{ padding: "12px 16px" }}>
            <span style={{ fontSize: "0.8rem", color: "#94a3b8" }}>Unavailable</span>
            <div style={{ fontSize: "1.4rem", fontWeight: 700, color: "#ef4444", marginTop: 4 }}>
              {statusData.summary.unavailable}
            </div>
          </div>
        </div>
      )}

      {/* Providers Grid */}
      {statusData && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(360px, 1fr))", gap: 16 }}>
          {Object.entries(statusData.integrations).map(([key, item]: [string, IntegrationStatusItem]) => (
            <div key={key} className="card" style={{ display: "flex", flexDirection: "column", justifyContent: "space-between" }}>
              <div>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 8 }}>
                  <div>
                    <h4 style={{ margin: 0, textTransform: "capitalize" }}>{key.replace("_", " ")}</h4>
                    <span style={{ fontSize: "0.75rem", color: "#64748b" }}>Provider: {item.provider}</span>
                  </div>
                  <span className={getBadgeClass(item.state)}>
                    {item.state}
                  </span>
                </div>
                <p style={{ fontSize: "0.85rem", color: "#cbd5e1", margin: "10px 0" }}>
                  {item.message}
                </p>
                {item.details && Object.keys(item.details).length > 0 && (
                  <div style={{ fontSize: "0.75rem", background: "#0f172a", padding: "8px", borderRadius: 6, margin: "8px 0" }}>
                    <div style={{ color: "#94a3b8", marginBottom: 4, fontWeight: 600 }}>Configuration Metadata:</div>
                    {Object.entries(item.details).map(([k, v]) => (
                      <div key={k} style={{ display: "flex", justifyContent: "space-between", color: "#cbd5e1" }}>
                        <span>{k}:</span>
                        <span>{String(v)}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Action Probes */}
              <div style={{ borderTop: "1px solid #334155", paddingTop: 10, marginTop: 10, display: "flex", justifyContent: "flex-end" }}>
                {key === "deployment" && (
                  <button type="button" className="btn btn-secondary btn-sm" onClick={runDeploymentProbe}>
                    Query Deployments
                  </button>
                )}
                {key === "source_control" && (
                  <button type="button" className="btn btn-secondary btn-sm" onClick={runCommitProbe}>
                    Query Commits
                  </button>
                )}
                {key === "infrastructure" && (
                  <button type="button" className="btn btn-secondary btn-sm" onClick={runInfraProbe}>
                    Query Pods
                  </button>
                )}
                {key === "metrics" && (
                  <button type="button" className="btn btn-secondary btn-sm" onClick={runMetricsProbe}>
                    Query Prometheus
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Interactive Probe Output Modal / Drawer */}
      {activeTest && (
        <div className="card" style={{ marginTop: 24, border: "1px solid #3b82f6" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
            <h4 style={{ margin: 0, color: "#60a5fa" }}>
              Live Provider Probe Output: {activeTest}
            </h4>
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              onClick={() => {
                setActiveTest(null);
                setTestResult(null);
              }}
            >
              Close Output
            </button>
          </div>
          {testLoading ? (
            <p className="text-muted">Contacting provider endpoint...</p>
          ) : (
            <pre className="response-output" style={{ maxHeight: 260, overflowY: "auto" }}>
              {JSON.stringify(testResult, null, 2)}
            </pre>
          )}
        </div>
      )}
    </div>
  );
};
