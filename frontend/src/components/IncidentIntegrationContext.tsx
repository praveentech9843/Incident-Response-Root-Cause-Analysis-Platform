import React, { useEffect, useState } from "react";
import {
  fetchIntegrationStatus,
  type IntegrationsStatusResponse,
} from "../services/api";

interface IncidentIntegrationContextProps {
  serviceName: string;
}

export const IncidentIntegrationContext: React.FC<IncidentIntegrationContextProps> = ({ serviceName }) => {
  const [integrations, setIntegrations] = useState<IntegrationsStatusResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let isMounted = true;
    fetchIntegrationStatus()
      .then((res) => {
        if (isMounted) {
          setIntegrations(res);
          setLoading(false);
        }
      })
      .catch(() => {
        if (isMounted) setLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, []);

  return (
    <div className="card" style={{ marginTop: 16, borderLeft: "4px solid #3b82f6" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
        <div>
          <h4 style={{ margin: 0, fontSize: "0.95rem" }}>
            External Telemetry & Environment Context (Phase 8)
          </h4>
          <span style={{ fontSize: "0.78rem", color: "#94a3b8" }}>
            Target Service: <strong>{serviceName || "All Services"}</strong>
          </span>
        </div>
        <span style={{ fontSize: "0.72rem", background: "#1e293b", padding: "2px 8px", borderRadius: 4, color: "#94a3b8" }}>
          Grounding: Strictly Real Telemetry
        </span>
      </div>

      {loading ? (
        <p className="text-muted" style={{ fontSize: "0.85rem" }}>Checking external telemetry providers...</p>
      ) : (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 10 }}>
          {/* Deployment Context */}
          <div style={{ background: "#0f172a", padding: "10px", borderRadius: 6, border: "1px solid #334155" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span style={{ fontSize: "0.8rem", fontWeight: 600, color: "#f8fafc" }}>CI/CD Deployments</span>
              <span style={{ fontSize: "0.68rem", color: integrations?.integrations?.deployment?.state === "CONNECTED" ? "#10b981" : "#f59e0b" }}>
                {integrations?.integrations?.deployment?.state || "NOT_CONNECTED"}
              </span>
            </div>
            <p style={{ fontSize: "0.75rem", color: "#94a3b8", margin: "6px 0 0" }}>
              {integrations?.integrations?.deployment?.state === "CONNECTED"
                ? "Recent release correlation available"
                : "[UNAVAILABLE] CI/CD provider not connected"}
            </p>
          </div>

          {/* Git Source Control Context */}
          <div style={{ background: "#0f172a", padding: "10px", borderRadius: 6, border: "1px solid #334155" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span style={{ fontSize: "0.8rem", fontWeight: 600, color: "#f8fafc" }}>Git Commits</span>
              <span style={{ fontSize: "0.68rem", color: integrations?.integrations?.source_control?.state === "CONNECTED" ? "#10b981" : "#f59e0b" }}>
                {integrations?.integrations?.source_control?.state || "NOT_CONNECTED"}
              </span>
            </div>
            <p style={{ fontSize: "0.75rem", color: "#94a3b8", margin: "6px 0 0" }}>
              {integrations?.integrations?.source_control?.state === "CONNECTED"
                ? "Recent repository commits tracked"
                : "[UNAVAILABLE] Git repository not connected"}
            </p>
          </div>

          {/* Infrastructure Context */}
          <div style={{ background: "#0f172a", padding: "10px", borderRadius: 6, border: "1px solid #334155" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span style={{ fontSize: "0.8rem", fontWeight: 600, color: "#f8fafc" }}>Kubernetes Pods</span>
              <span style={{ fontSize: "0.68rem", color: integrations?.integrations?.infrastructure?.state === "CONNECTED" ? "#10b981" : "#f59e0b" }}>
                {integrations?.integrations?.infrastructure?.state || "NOT_CONNECTED"}
              </span>
            </div>
            <p style={{ fontSize: "0.75rem", color: "#94a3b8", margin: "6px 0 0" }}>
              {integrations?.integrations?.infrastructure?.state === "CONNECTED"
                ? "Pod lifecycle & restart health monitored"
                : "[UNAVAILABLE] Cluster cluster provider not connected"}
            </p>
          </div>

          {/* Prometheus Metrics Context */}
          <div style={{ background: "#0f172a", padding: "10px", borderRadius: 6, border: "1px solid #334155" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span style={{ fontSize: "0.8rem", fontWeight: 600, color: "#f8fafc" }}>Prometheus Metrics</span>
              <span style={{ fontSize: "0.68rem", color: integrations?.integrations?.metrics?.state === "CONNECTED" ? "#10b981" : "#f59e0b" }}>
                {integrations?.integrations?.metrics?.state || "NOT_CONNECTED"}
              </span>
            </div>
            <p style={{ fontSize: "0.75rem", color: "#94a3b8", margin: "6px 0 0" }}>
              {integrations?.integrations?.metrics?.state === "CONNECTED"
                ? "Time-series CPU, memory, error rates queried"
                : "[UNAVAILABLE] Prometheus endpoint not configured"}
            </p>
          </div>
        </div>
      )}
    </div>
  );
};
