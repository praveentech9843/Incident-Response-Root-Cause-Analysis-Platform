import React, { useEffect, useState } from "react";
import {
  fetchHealth,
  fetchHealthLive,
  fetchHealthReady,
  type HealthResponse,
  type HealthProbeResponse,
} from "../services/api";
import { Activity, RefreshCw, AlertCircle, Server, ShieldCheck, HeartPulse } from "lucide-react";

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

  return (
    <div className="health-section-wrapper">
      <div className="page-header" style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: "1rem" }}>
        <div>
          <h2>System Observability & Health Probes</h2>
          <p className="page-description">
            Real-time infrastructure probes, microservice liveness, and readiness verification.
          </p>
        </div>
        <button
          type="button"
          className="btn btn-secondary btn-sm"
          onClick={loadHealth}
          disabled={healthLoading}
          style={{ display: "inline-flex", alignItems: "center", gap: "6px" }}
        >
          <RefreshCw size={14} className={healthLoading ? "spin" : ""} />
          {healthLoading ? "Probing..." : "Refresh Probes"}
        </button>
      </div>

      <section className="card">
        <div className="card-header-row" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <div style={{ padding: "8px", borderRadius: "8px", background: "#eff6ff", color: "#2563eb" }}>
              <HeartPulse size={20} />
            </div>
            <div>
              <h3 className="card-title" style={{ margin: 0 }}>Cluster Health Checks</h3>
              <p className="card-subtitle" style={{ margin: 0, fontSize: "0.85rem", color: "#64748b" }}>
                FastAPI Gateway, PostgreSQL connection, and asynchronous workers
              </p>
            </div>
          </div>
          <span className={`status-pill ${healthError ? "status-pill-error" : "status-pill-success"}`}>
            {healthLoading ? "Checking" : healthError ? "Degraded" : "All Systems Healthy"}
          </span>
        </div>

        {healthLoading && (
          <div style={{ padding: "1.5rem", textAlign: "center", color: "#64748b" }}>
            <Activity size={24} className="spin" style={{ marginBottom: "8px" }} />
            <p style={{ margin: 0 }}>Probing backend endpoints...</p>
          </div>
        )}

        {healthError && (
          <div className="alert alert-error" style={{ display: "flex", alignItems: "flex-start", gap: "10px", marginTop: "1rem" }}>
            <AlertCircle size={18} style={{ flexShrink: 0, marginTop: "2px" }} />
            <div>
              <strong>Backend Connectivity Issue:</strong>
              <p className="alert-message" style={{ margin: "4px 0 0" }}>{healthError}</p>
            </div>
          </div>
        )}

        {!healthLoading && (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", gap: "1rem", marginTop: "1.25rem" }}>
            {/* Main Health */}
            <div
              style={{
                border: "1px solid #e2e8f0",
                borderRadius: "10px",
                padding: "1.25rem",
                background: "#ffffff",
                boxShadow: "0 1px 3px rgba(0,0,0,0.02)",
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.75rem" }}>
                <span style={{ fontWeight: 600, fontSize: "0.9rem", display: "inline-flex", alignItems: "center", gap: "6px" }}>
                  <Server size={16} color="#2563eb" />
                  Primary Gateway (/health)
                </span>
                <span
                  style={{
                    padding: "3px 8px",
                    borderRadius: "12px",
                    fontSize: "0.75rem",
                    fontWeight: 600,
                    background: healthData?.status === "ok" || healthData?.status === "healthy" ? "#dcfce7" : "#fee2e2",
                    color: healthData?.status === "ok" || healthData?.status === "healthy" ? "#15803d" : "#b91c1c",
                  }}
                >
                  {healthData?.status || "Unavailable"}
                </span>
              </div>
              <pre
                className="response-output"
                style={{
                  fontSize: "0.75rem",
                  background: "#f8fafc",
                  border: "1px solid #e2e8f0",
                  padding: "0.75rem",
                  borderRadius: "6px",
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
                borderRadius: "10px",
                padding: "1.25rem",
                background: "#ffffff",
                boxShadow: "0 1px 3px rgba(0,0,0,0.02)",
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.75rem" }}>
                <span style={{ fontWeight: 600, fontSize: "0.9rem", display: "inline-flex", alignItems: "center", gap: "6px" }}>
                  <Activity size={16} color="#0891b2" />
                  Liveness Probe (/health/live)
                </span>
                <span
                  style={{
                    padding: "3px 8px",
                    borderRadius: "12px",
                    fontSize: "0.75rem",
                    fontWeight: 600,
                    background: liveData?.status === "ok" || liveData?.status === "healthy" ? "#dcfce7" : "#fee2e2",
                    color: liveData?.status === "ok" || liveData?.status === "healthy" ? "#15803d" : "#b91c1c",
                  }}
                >
                  {liveData?.status || "Unavailable"}
                </span>
              </div>
              <pre
                className="response-output"
                style={{
                  fontSize: "0.75rem",
                  background: "#f8fafc",
                  border: "1px solid #e2e8f0",
                  padding: "0.75rem",
                  borderRadius: "6px",
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
                borderRadius: "10px",
                padding: "1.25rem",
                background: "#ffffff",
                boxShadow: "0 1px 3px rgba(0,0,0,0.02)",
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.75rem" }}>
                <span style={{ fontWeight: 600, fontSize: "0.9rem", display: "inline-flex", alignItems: "center", gap: "6px" }}>
                  <ShieldCheck size={16} color="#16a34a" />
                  Readiness Probe (/health/ready)
                </span>
                <span
                  style={{
                    padding: "3px 8px",
                    borderRadius: "12px",
                    fontSize: "0.75rem",
                    fontWeight: 600,
                    background: readyData?.status === "ok" || readyData?.status === "ready" ? "#dcfce7" : "#fee2e2",
                    color: readyData?.status === "ok" || readyData?.status === "ready" ? "#15803d" : "#b91c1c",
                  }}
                >
                  {readyData?.status || "Unavailable"}
                </span>
              </div>
              <pre
                className="response-output"
                style={{
                  fontSize: "0.75rem",
                  background: "#f8fafc",
                  border: "1px solid #e2e8f0",
                  padding: "0.75rem",
                  borderRadius: "6px",
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
