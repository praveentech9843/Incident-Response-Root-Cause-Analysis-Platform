import React, { useEffect, useState } from "react";
import {
  fetchIntegrationStatus,
  type IntegrationsStatusResponse,
} from "../services/api";
import { Workflow, GitBranch, Cpu, Activity, CheckCircle2, AlertTriangle, HelpCircle } from "lucide-react";

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

  const getStatusBadge = (state?: string) => {
    if (state === "CONNECTED") {
      return (
        <span className="badge badge-status-success" style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
          <CheckCircle2 size={12} /> Connected
        </span>
      );
    }
    if (state === "NOT_CONNECTED") {
      return (
        <span className="badge badge-status-partial" style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
          <HelpCircle size={12} /> Not Connected
        </span>
      );
    }
    return (
      <span className="badge badge-status-other" style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
        <AlertTriangle size={12} /> Unavailable
      </span>
    );
  };

  return (
    <div className="card" style={{ marginTop: 16, borderLeft: "4px solid var(--primary, #1d4ed8)" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
        <div>
          <h4 style={{ margin: 0, fontSize: "0.95rem", fontWeight: 700, color: "var(--text-primary, #0f172a)" }}>
            External Telemetry & Environment Context (Phase 8)
          </h4>
          <span style={{ fontSize: "0.78rem", color: "var(--text-secondary, #64748b)" }}>
            Target Service Scope: <strong style={{ color: "var(--primary, #1d4ed8)" }}>{serviceName || "All Services"}</strong>
          </span>
        </div>
        <span
          style={{
            fontSize: "0.72rem",
            background: "#eff6ff",
            border: "1px solid #dbeafe",
            padding: "3px 10px",
            borderRadius: 6,
            color: "#1d4ed8",
            fontWeight: 600,
          }}
        >
          Grounding: Strictly Real Telemetry
        </span>
      </div>

      {loading ? (
        <div style={{ padding: "1rem", textAlign: "center", color: "#64748b", fontSize: "0.85rem" }}>
          Checking external telemetry providers...
        </div>
      ) : (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 12 }}>
          {/* Deployment Context */}
          <div
            style={{
              background: "#f8fafc",
              padding: "12px",
              borderRadius: 8,
              border: "1px solid #e2e8f0",
              boxShadow: "0 1px 2px rgba(0,0,0,0.02)",
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span style={{ fontSize: "0.825rem", fontWeight: 600, color: "#0f172a", display: "inline-flex", alignItems: "center", gap: 6 }}>
                <Workflow size={14} color="#1d4ed8" /> CI/CD Deployments
              </span>
              {getStatusBadge(integrations?.integrations?.deployment?.state)}
            </div>
            <p style={{ fontSize: "0.775rem", color: "#64748b", margin: "8px 0 0" }}>
              {integrations?.integrations?.deployment?.state === "CONNECTED"
                ? "Recent release correlation available"
                : "[UNAVAILABLE] CI/CD provider not connected"}
            </p>
          </div>

          {/* Git Source Control Context */}
          <div
            style={{
              background: "#f8fafc",
              padding: "12px",
              borderRadius: 8,
              border: "1px solid #e2e8f0",
              boxShadow: "0 1px 2px rgba(0,0,0,0.02)",
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span style={{ fontSize: "0.825rem", fontWeight: 600, color: "#0f172a", display: "inline-flex", alignItems: "center", gap: 6 }}>
                <GitBranch size={14} color="#0284c7" /> Git Commits
              </span>
              {getStatusBadge(integrations?.integrations?.source_control?.state)}
            </div>
            <p style={{ fontSize: "0.775rem", color: "#64748b", margin: "8px 0 0" }}>
              {integrations?.integrations?.source_control?.state === "CONNECTED"
                ? "Recent repository commits tracked"
                : "[UNAVAILABLE] Git repository not connected"}
            </p>
          </div>

          {/* Infrastructure Context */}
          <div
            style={{
              background: "#f8fafc",
              padding: "12px",
              borderRadius: 8,
              border: "1px solid #e2e8f0",
              boxShadow: "0 1px 2px rgba(0,0,0,0.02)",
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span style={{ fontSize: "0.825rem", fontWeight: 600, color: "#0f172a", display: "inline-flex", alignItems: "center", gap: 6 }}>
                <Cpu size={14} color="#16a34a" /> Kubernetes Pods
              </span>
              {getStatusBadge(integrations?.integrations?.infrastructure?.state)}
            </div>
            <p style={{ fontSize: "0.775rem", color: "#64748b", margin: "8px 0 0" }}>
              {integrations?.integrations?.infrastructure?.state === "CONNECTED"
                ? "Pod lifecycle & restart health monitored"
                : "[UNAVAILABLE] Cluster provider not connected"}
            </p>
          </div>

          {/* Prometheus Metrics Context */}
          <div
            style={{
              background: "#f8fafc",
              padding: "12px",
              borderRadius: 8,
              border: "1px solid #e2e8f0",
              boxShadow: "0 1px 2px rgba(0,0,0,0.02)",
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span style={{ fontSize: "0.825rem", fontWeight: 600, color: "#0f172a", display: "inline-flex", alignItems: "center", gap: 6 }}>
                <Activity size={14} color="#d97706" /> Prometheus Metrics
              </span>
              {getStatusBadge(integrations?.integrations?.metrics?.state)}
            </div>
            <p style={{ fontSize: "0.775rem", color: "#64748b", margin: "8px 0 0" }}>
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
