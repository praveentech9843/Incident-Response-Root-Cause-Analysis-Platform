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
import { Workflow, RefreshCw, CheckCircle2, HelpCircle, AlertTriangle, Terminal, X } from "lucide-react";

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
      {/* Page Header */}
      <div className="page-header-row">
        <div>
          <h2 className="page-title">External Integrations & Observability</h2>
          <p className="page-subtitle">
            Phase 8 Production Integration Architecture — Strictly real connections with explicit NOT_CONNECTED states.
          </p>
        </div>
        <button
          type="button"
          className="btn btn-secondary btn-sm"
          onClick={loadStatus}
          disabled={loading}
          style={{ display: "inline-flex", alignItems: "center", gap: 6 }}
        >
          <RefreshCw size={14} className={loading ? "spin" : ""} />
          {loading ? "Refreshing..." : "Refresh Status"}
        </button>
      </div>

      {error && <div className="alert alert-error" style={{ marginBottom: 16 }}>{error}</div>}

      {/* Summary KPI Row */}
      {statusData && (
        <div className="kpi-grid" style={{ marginBottom: 20 }}>
          <div className="card kpi-card">
            <div className="kpi-header">
              <span className="kpi-title">Total Providers</span>
              <div className="kpi-icon-box" style={{ background: "#eff6ff", color: "#1d4ed8" }}>
                <Workflow size={18} />
              </div>
            </div>
            <div className="kpi-value">{statusData.summary.total}</div>
            <span className="kpi-hint">External services</span>
          </div>

          <div className="card kpi-card">
            <div className="kpi-header">
              <span className="kpi-title">Connected</span>
              <div className="kpi-icon-box" style={{ background: "#f0fdf4", color: "#16a34a" }}>
                <CheckCircle2 size={18} />
              </div>
            </div>
            <div className="kpi-value" style={{ color: "#16a34a" }}>
              {statusData.summary.connected}
            </div>
            <span className="kpi-hint">Healthy telemetry sources</span>
          </div>

          <div className="card kpi-card">
            <div className="kpi-header">
              <span className="kpi-title">Not Connected</span>
              <div className="kpi-icon-box" style={{ background: "#fffbeb", color: "#b45309" }}>
                <HelpCircle size={18} />
              </div>
            </div>
            <div className="kpi-value" style={{ color: "#d97706" }}>
              {statusData.summary.not_connected}
            </div>
            <span className="kpi-hint">Optional provider hooks</span>
          </div>

          <div className="card kpi-card">
            <div className="kpi-header">
              <span className="kpi-title">Unavailable</span>
              <div className="kpi-icon-box" style={{ background: "#fef2f2", color: "#dc2626" }}>
                <AlertTriangle size={18} />
              </div>
            </div>
            <div className="kpi-value" style={{ color: "#dc2626" }}>
              {statusData.summary.unavailable}
            </div>
            <span className="kpi-hint">Unreachable endpoints</span>
          </div>
        </div>
      )}

      {/* Providers Grid */}
      {statusData && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(360px, 1fr))", gap: 16 }}>
          {Object.entries(statusData.integrations).map(([key, item]: [string, IntegrationStatusItem]) => (
            <div
              key={key}
              className="card"
              style={{
                display: "flex",
                flexDirection: "column",
                justifyContent: "space-between",
                borderTop: "3px solid var(--primary, #1d4ed8)",
              }}
            >
              <div>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 8 }}>
                  <div>
                    <h4 style={{ margin: 0, textTransform: "capitalize", fontSize: "1rem", fontWeight: 700, color: "#0f172a" }}>
                      {key.replace("_", " ")}
                    </h4>
                    <span style={{ fontSize: "0.75rem", color: "#64748b" }}>Provider: {item.provider}</span>
                  </div>
                  <span className={getBadgeClass(item.state)}>
                    {item.state}
                  </span>
                </div>
                <p style={{ fontSize: "0.85rem", color: "#475569", margin: "10px 0" }}>
                  {item.message}
                </p>
                {item.details && Object.keys(item.details).length > 0 && (
                  <div
                    style={{
                      fontSize: "0.75rem",
                      background: "#f8fafc",
                      border: "1px solid #e2e8f0",
                      padding: "10px",
                      borderRadius: 8,
                      margin: "10px 0",
                    }}
                  >
                    <div style={{ color: "#334155", marginBottom: 6, fontWeight: 600 }}>Configuration Metadata:</div>
                    {Object.entries(item.details).map(([k, v]) => (
                      <div key={k} style={{ display: "flex", justifyContent: "space-between", color: "#475569", padding: "2px 0" }}>
                        <span style={{ fontFamily: "var(--font-mono)" }}>{k}:</span>
                        <span style={{ fontWeight: 500 }}>{String(v)}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Action Probes */}
              <div style={{ borderTop: "1px solid #e2e8f0", paddingTop: 12, marginTop: 12, display: "flex", justifyContent: "flex-end" }}>
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
        <div className="card" style={{ marginTop: 24, border: "1px solid #bfdbfe", background: "#f8fafc" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <Terminal size={18} color="#1d4ed8" />
              <h4 style={{ margin: 0, color: "#1d4ed8", fontSize: "0.95rem", fontWeight: 700 }}>
                Live Provider Probe Output: {activeTest}
              </h4>
            </div>
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              onClick={() => {
                setActiveTest(null);
                setTestResult(null);
              }}
              style={{ display: "inline-flex", alignItems: "center", gap: 4 }}
            >
              <X size={14} /> Close Output
            </button>
          </div>
          {testLoading ? (
            <p className="text-muted" style={{ padding: "1rem 0" }}>Contacting provider endpoint...</p>
          ) : (
            <pre
              className="response-output"
              style={{
                maxHeight: 260,
                overflowY: "auto",
                background: "#ffffff",
                border: "1px solid #e2e8f0",
                color: "#0f172a",
                padding: "12px",
                borderRadius: 8,
              }}
            >
              {JSON.stringify(testResult, null, 2)}
            </pre>
          )}
        </div>
      )}
    </div>
  );
};
