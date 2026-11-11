import React, { useEffect, useState } from "react";
import {
  fetchHealth,
  fetchHealthLive,
  fetchHealthReady,
  type HealthResponse,
  type HealthProbeResponse,
} from "../services/api";
import { Activity, RefreshCw, AlertCircle, Server, ShieldCheck, HeartPulse, Cpu, Database } from "lucide-react";

export const ObservabilityPage: React.FC = () => {
  const [healthData, setHealthData] = useState<HealthResponse | null>(null);
  const [liveData, setLiveData] = useState<HealthProbeResponse | null>(null);
  const [readyData, setReadyData] = useState<HealthProbeResponse | null>(null);
  const [healthError, setHealthError] = useState<string | null>(null);
  const [healthLoading, setHealthLoading] = useState<boolean>(true);

  const loadHealth = async () => {
    setHealthLoading(true);
    setHealthError(null);
    try {
      const [h, l, r] = await Promise.all([
        fetchHealth(),
        fetchHealthLive().catch(() => null),
        fetchHealthReady().catch(() => null),
      ]);
      setHealthData(h);
      setLiveData(l);
      setReadyData(r);
    } catch (err: unknown) {
      setHealthError(err instanceof Error ? err.message : "Failed to connect to backend.");
    } finally {
      setHealthLoading(false);
    }
  };

  useEffect(() => {
    let isMounted = true;
    Promise.all([
      fetchHealth(),
      fetchHealthLive().catch(() => null),
      fetchHealthReady().catch(() => null),
    ])
      .then(([h, l, r]) => {
        if (isMounted) {
          setHealthData(h);
          setLiveData(l);
          setReadyData(r);
          setHealthLoading(false);
        }
      })
      .catch((err) => {
        if (isMounted) {
          setHealthError(err instanceof Error ? err.message : "Failed to connect to backend.");
          setHealthLoading(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, []);

  const isHealthy = healthData?.status === "ok" || healthData?.status === "healthy";

  return (
    <div className="tab-page-container">
      {/* Page Header */}
      <div className="page-header-row">
        <div>
          <h2 className="page-title">System Observability & Health Probes</h2>
          <p className="page-subtitle">
            Real-time infrastructure probes, microservice liveness, and PostgreSQL readiness verification.
          </p>
        </div>
        <button
          type="button"
          className="btn btn-secondary btn-sm"
          onClick={loadHealth}
          disabled={healthLoading}
          style={{ display: "inline-flex", alignItems: "center", gap: 6 }}
        >
          <RefreshCw size={14} className={healthLoading ? "spin" : ""} />
          {healthLoading ? "Probing..." : "Refresh Probes"}
        </button>
      </div>

      {/* KPI Status Row */}
      <div className="kpi-grid" style={{ marginBottom: 20 }}>
        <div className="card kpi-card">
          <div className="kpi-header">
            <span className="kpi-title">Cluster Status</span>
            <div className="kpi-icon-box" style={{ background: isHealthy ? "#f0fdf4" : "#fef2f2", color: isHealthy ? "#16a34a" : "#dc2626" }}>
              <HeartPulse size={18} />
            </div>
          </div>
          <div className="kpi-value" style={{ color: isHealthy ? "#16a34a" : "#dc2626" }}>
            {healthLoading ? "Probing..." : isHealthy ? "Healthy" : "Degraded"}
          </div>
          <span className="kpi-hint">Gateway, DB & worker tier</span>
        </div>

        <div className="card kpi-card">
          <div className="kpi-header">
            <span className="kpi-title">App Version</span>
            <div className="kpi-icon-box" style={{ background: "#eff6ff", color: "#1d4ed8" }}>
              <Server size={18} />
            </div>
          </div>
          <div className="kpi-value">{healthData?.version || "v0.1.0"}</div>
          <span className="kpi-hint">Release channel: Stable</span>
        </div>

        <div className="card kpi-card">
          <div className="kpi-header">
            <span className="kpi-title">Runtime Environment</span>
            <div className="kpi-icon-box" style={{ background: "#f0fdf4", color: "#16a34a" }}>
              <Cpu size={18} />
            </div>
          </div>
          <div className="kpi-value" style={{ textTransform: "capitalize" }}>
            {healthData?.environment || "Development"}
          </div>
          <span className="kpi-hint">Isolated cluster mode</span>
        </div>

        <div className="card kpi-card">
          <div className="kpi-header">
            <span className="kpi-title">PostgreSQL Readiness</span>
            <div className="kpi-icon-box" style={{ background: "#eff6ff", color: "#0284c7" }}>
              <Database size={18} />
            </div>
          </div>
          <div className="kpi-value" style={{ color: "#0284c7" }}>
            {readyData?.status === "ok" || readyData?.status === "ready" ? "Connected" : "Probing"}
          </div>
          <span className="kpi-hint">Connection pool active</span>
        </div>
      </div>

      {healthError && (
        <div className="alert alert-error" style={{ display: "flex", alignItems: "flex-start", gap: 10, marginBottom: 20 }}>
          <AlertCircle size={18} style={{ flexShrink: 0, marginTop: 2 }} />
          <div>
            <strong>Backend Connectivity Issue:</strong>
            <p className="alert-message" style={{ margin: "4px 0 0" }}>{healthError}</p>
          </div>
        </div>
      )}

      {/* Main Probes Section */}
      <section className="card">
        <div className="card-header-row" style={{ marginBottom: 16 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <div style={{ padding: 8, borderRadius: 8, background: "#eff6ff", color: "#1d4ed8" }}>
              <HeartPulse size={20} />
            </div>
            <div>
              <h3 className="card-title" style={{ margin: 0 }}>Microservice Health Probes</h3>
              <p className="card-subtitle" style={{ margin: 0 }}>
                FastAPI Gateway, PostgreSQL connection, and asynchronous workers
              </p>
            </div>
          </div>
          <span
            style={{
              padding: "4px 12px",
              borderRadius: 20,
              fontSize: "0.775rem",
              fontWeight: 600,
              display: "inline-flex",
              alignItems: "center",
              gap: 6,
              background: healthLoading ? "#f1f5f9" : isHealthy ? "#dcfce7" : "#fee2e2",
              color: healthLoading ? "#475569" : isHealthy ? "#15803d" : "#b91c1c",
              border: isHealthy ? "1px solid #bbf7d0" : "1px solid #e2e8f0",
            }}
          >
            <span
              style={{
                width: 6,
                height: 6,
                borderRadius: "50%",
                background: healthLoading ? "#94a3b8" : isHealthy ? "#16a34a" : "#dc2626",
              }}
            />
            {healthLoading ? "Probing..." : isHealthy ? "All Probes Passing" : "Degraded"}
          </span>
        </div>

        {healthLoading && (
          <div style={{ padding: "2.5rem 1rem", textAlign: "center", color: "#64748b" }}>
            <Activity size={28} className="spin" style={{ marginBottom: 8, color: "#1d4ed8" }} />
            <p style={{ margin: 0, fontWeight: 500 }}>Querying backend telemetry endpoints...</p>
          </div>
        )}

        {!healthLoading && (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", gap: 16, marginTop: 8 }}>
            {/* Primary Health */}
            <div
              style={{
                border: "1px solid #e2e8f0",
                borderRadius: 10,
                padding: "16px",
                background: "#f8fafc",
                boxShadow: "0 1px 2px rgba(0,0,0,0.02)",
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
                <span style={{ fontWeight: 600, fontSize: "0.9rem", color: "#0f172a", display: "inline-flex", alignItems: "center", gap: 6 }}>
                  <Server size={16} color="#1d4ed8" />
                  Primary Gateway (/health)
                </span>
                <span
                  style={{
                    padding: "3px 8px",
                    borderRadius: 12,
                    fontSize: "0.75rem",
                    fontWeight: 600,
                    background: isHealthy ? "#dcfce7" : "#fee2e2",
                    color: isHealthy ? "#15803d" : "#b91c1c",
                    border: isHealthy ? "1px solid #bbf7d0" : "1px solid #fecaca",
                  }}
                >
                  {healthData?.status || "Unavailable"}
                </span>
              </div>
              <pre
                className="response-output"
                style={{
                  fontSize: "0.75rem",
                  background: "#ffffff",
                  border: "1px solid #e2e8f0",
                  color: "#0f172a",
                  padding: "12px",
                  borderRadius: 8,
                  maxHeight: "160px",
                  overflow: "auto",
                }}
              >
                {JSON.stringify(healthData || { error: "No response" }, null, 2)}
              </pre>
            </div>

            {/* Liveness Probe */}
            <div
              style={{
                border: "1px solid #e2e8f0",
                borderRadius: 10,
                padding: "16px",
                background: "#f8fafc",
                boxShadow: "0 1px 2px rgba(0,0,0,0.02)",
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
                <span style={{ fontWeight: 600, fontSize: "0.9rem", color: "#0f172a", display: "inline-flex", alignItems: "center", gap: 6 }}>
                  <Activity size={16} color="#0284c7" />
                  Liveness Probe (/health/live)
                </span>
                <span
                  style={{
                    padding: "3px 8px",
                    borderRadius: 12,
                    fontSize: "0.75rem",
                    fontWeight: 600,
                    background: liveData?.status === "ok" || liveData?.status === "healthy" || liveData?.status === "alive" ? "#dcfce7" : "#fee2e2",
                    color: liveData?.status === "ok" || liveData?.status === "healthy" || liveData?.status === "alive" ? "#15803d" : "#b91c1c",
                    border: liveData?.status === "ok" || liveData?.status === "healthy" || liveData?.status === "alive" ? "1px solid #bbf7d0" : "1px solid #fecaca",
                  }}
                >
                  {liveData?.status || "Unavailable"}
                </span>
              </div>
              <pre
                className="response-output"
                style={{
                  fontSize: "0.75rem",
                  background: "#ffffff",
                  border: "1px solid #e2e8f0",
                  color: "#0f172a",
                  padding: "12px",
                  borderRadius: 8,
                  maxHeight: "160px",
                  overflow: "auto",
                }}
              >
                {JSON.stringify(liveData || { error: "No response" }, null, 2)}
              </pre>
            </div>

            {/* Readiness Probe */}
            <div
              style={{
                border: "1px solid #e2e8f0",
                borderRadius: 10,
                padding: "16px",
                background: "#f8fafc",
                boxShadow: "0 1px 2px rgba(0,0,0,0.02)",
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
                <span style={{ fontWeight: 600, fontSize: "0.9rem", color: "#0f172a", display: "inline-flex", alignItems: "center", gap: 6 }}>
                  <ShieldCheck size={16} color="#16a34a" />
                  Readiness Probe (/health/ready)
                </span>
                <span
                  style={{
                    padding: "3px 8px",
                    borderRadius: 12,
                    fontSize: "0.75rem",
                    fontWeight: 600,
                    background: readyData?.status === "ok" || readyData?.status === "ready" ? "#dcfce7" : "#fee2e2",
                    color: readyData?.status === "ok" || readyData?.status === "ready" ? "#15803d" : "#b91c1c",
                    border: readyData?.status === "ok" || readyData?.status === "ready" ? "1px solid #bbf7d0" : "1px solid #fecaca",
                  }}
                >
                  {readyData?.status || "Unavailable"}
                </span>
              </div>
              <pre
                className="response-output"
                style={{
                  fontSize: "0.75rem",
                  background: "#ffffff",
                  border: "1px solid #e2e8f0",
                  color: "#0f172a",
                  padding: "12px",
                  borderRadius: 8,
                  maxHeight: "160px",
                  overflow: "auto",
                }}
              >
                {JSON.stringify(readyData || { error: "No response" }, null, 2)}
              </pre>
            </div>
          </div>
        )}
      </section>
    </div>
  );
};
