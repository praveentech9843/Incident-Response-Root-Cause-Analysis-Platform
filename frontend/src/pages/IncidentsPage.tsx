import React, { useState, useEffect, useCallback } from "react";
import {
  fetchIncidents,
  fetchIncidentDetail,
  correlateIncidents,
  enrichIncident,
  fetchIncidentContext,
  runIncidentRCA,
  fetchLatestRCA,
  fetchRCAHistory,
  generateRecommendations,
  fetchLatestRecommendations,
  fetchRecommendationHistory,
} from "../services/api";
import type {
  Incident,
  IncidentDetail,
  CorrelateIncidentsResponse,
  EnrichedIncidentContext,
  IncidentRCAAnalysis,
  IncidentRecommendation,
  IncidentRecommendationListResponse,
} from "../services/api";
import { InvestigationWorkspace } from "../components/InvestigationWorkspace";
import { IncidentIntegrationContext } from "../components/IncidentIntegrationContext";
import {
  Flame,
  AlertTriangle,
  CheckCircle2,
  Layers,
  RefreshCw,
  Zap,
  ShieldCheck,
  Server,
  Rocket,
  Cpu,
  Activity,
  History,
  Network,
  GitMerge,
  Info,
  Clock,
  X,
  AlertCircle,
} from "lucide-react";

export const IncidentsPage: React.FC = () => {
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [totalCount, setTotalCount] = useState<number>(0);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Status filter state
  const [statusFilter, setStatusFilter] = useState<string>("");

  // Correlation execution state
  const [isCorrelating, setIsCorrelating] = useState<boolean>(false);
  const [correlationResult, setCorrelationResult] = useState<CorrelateIncidentsResponse | null>(null);

  // Detail drawer state
  const [selectedIncidentId, setSelectedIncidentId] = useState<number | null>(null);
  const [selectedIncident, setSelectedIncident] = useState<IncidentDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState<boolean>(false);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [expandedTraces, setExpandedTraces] = useState<Record<number, boolean>>({});

  // Phase 4: Operational context enrichment state
  const [incidentContext, setIncidentContext] = useState<EnrichedIncidentContext | null>(null);
  const [contextLoading, setContextLoading] = useState<boolean>(false);
  const [contextError, setContextError] = useState<string | null>(null);
  const [isEnriching, setIsEnriching] = useState<boolean>(false);

  // Phase 5: Root Cause Analysis state
  const [rcaAnalysis, setRcaAnalysis] = useState<IncidentRCAAnalysis | null>(null);
  const [rcaLoading, setRcaLoading] = useState<boolean>(false);
  const [rcaError, setRcaError] = useState<string | null>(null);
  const [isRunningRCA, setIsRunningRCA] = useState<boolean>(false);
  const [rcaHistory, setRcaHistory] = useState<IncidentRCAAnalysis[]>([]);
  const [showRCAHistory, setShowRCAHistory] = useState<boolean>(false);
  const [loadingHistory, setLoadingHistory] = useState<boolean>(false);

  // Phase 6: Investigation & Fix Recommendations state
  const [recommendations, setRecommendations] = useState<IncidentRecommendationListResponse | null>(null);
  const [recommendationsLoading, setRecommendationsLoading] = useState<boolean>(false);
  const [recommendationsError, setRecommendationsError] = useState<string | null>(null);
  const [isGeneratingRecs, setIsGeneratingRecs] = useState<boolean>(false);
  const [recommendationHistory, setRecommendationHistory] = useState<IncidentRecommendation[]>([]);
  const [showRecHistory, setShowRecHistory] = useState<boolean>(false);
  const [loadingRecHistory, setLoadingRecHistory] = useState<boolean>(false);

  const loadIncidents = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchIncidents(statusFilter || undefined);
      setIncidents(data.items);
      setTotalCount(data.total);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load incidents");
    } finally {
      setLoading(false);
    }
  }, [statusFilter]);

  useEffect(() => {
    let isMounted = true;
    fetchIncidents(statusFilter || undefined)
      .then((data) => {
        if (isMounted) {
          setIncidents(data.items);
          setTotalCount(data.total);
          setLoading(false);
        }
      })
      .catch((err) => {
        if (isMounted) {
          setError(err instanceof Error ? err.message : "Failed to load incidents");
          setLoading(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, [statusFilter]);

  const handleRunCorrelation = async () => {
    setIsCorrelating(true);
    setError(null);
    try {
      const res = await correlateIncidents();
      setCorrelationResult(res);
      await loadIncidents();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Correlation failed");
    } finally {
      setIsCorrelating(false);
    }
  };

  const handleOpenDetail = async (incidentId: number) => {
    setSelectedIncidentId(incidentId);
    setDetailLoading(true);
    setDetailError(null);
    setContextLoading(true);
    setContextError(null);
    setRcaLoading(true);
    setRcaError(null);
    setRcaAnalysis(null);
    setShowRCAHistory(false);
    setExpandedTraces({});

    try {
      const detail = await fetchIncidentDetail(incidentId);
      setSelectedIncident(detail);
    } catch (err: unknown) {
      setDetailError(err instanceof Error ? err.message : "Failed to load incident detail");
    } finally {
      setDetailLoading(false);
    }

    try {
      const contextData = await fetchIncidentContext(incidentId);
      setIncidentContext(contextData);
    } catch (err: unknown) {
      setContextError(err instanceof Error ? err.message : "Failed to load operational context");
    } finally {
      setContextLoading(false);
    }

    try {
      const rca = await fetchLatestRCA(incidentId);
      setRcaAnalysis(rca);
    } catch (err: unknown) {
      setRcaError(err instanceof Error ? err.message : "Failed to load root cause analysis");
    } finally {
      setRcaLoading(false);
    }

    try {
      setRecommendationsLoading(true);
      const recs = await fetchLatestRecommendations(incidentId);
      setRecommendations(recs);
    } catch {
      // recommendations optional on load
    } finally {
      setRecommendationsLoading(false);
    }
  };

  const handleEnrichContext = async () => {
    if (!selectedIncidentId) return;
    setIsEnriching(true);
    setContextError(null);
    try {
      const enriched = await enrichIncident(selectedIncidentId);
      setIncidentContext(enriched);
    } catch (err: unknown) {
      setContextError(err instanceof Error ? err.message : "Context enrichment failed");
    } finally {
      setIsEnriching(false);
    }
  };

  const handleRunRCA = async () => {
    if (!selectedIncidentId) return;
    setIsRunningRCA(true);
    setRcaError(null);
    try {
      const rca = await runIncidentRCA(selectedIncidentId);
      setRcaAnalysis(rca);
    } catch (err: unknown) {
      setRcaError(err instanceof Error ? err.message : "RCA execution failed");
    } finally {
      setIsRunningRCA(false);
    }
  };

  const handleToggleHistory = async () => {
    if (!selectedIncidentId) return;
    if (!showRCAHistory) {
      setLoadingHistory(true);
      try {
        const hist = await fetchRCAHistory(selectedIncidentId);
        setRcaHistory(hist.items);
      } catch (err: unknown) {
        setRcaError(err instanceof Error ? err.message : "Failed to load RCA history");
      } finally {
        setLoadingHistory(false);
      }
    }
    setShowRCAHistory(!showRCAHistory);
  };

  const handleGenerateRecommendations = async () => {
    if (!selectedIncidentId) return;
    setIsGeneratingRecs(true);
    setRecommendationsError(null);
    try {
      const recs = await generateRecommendations(selectedIncidentId);
      setRecommendations(recs);
    } catch (err: unknown) {
      setRecommendationsError(err instanceof Error ? err.message : "Recommendation generation failed");
    } finally {
      setIsGeneratingRecs(false);
    }
  };

  const handleToggleRecHistory = async () => {
    if (!selectedIncidentId) return;
    if (!showRecHistory) {
      setLoadingRecHistory(true);
      try {
        const hist = await fetchRecommendationHistory(selectedIncidentId);
        setRecommendationHistory(hist.items);
      } catch (err: unknown) {
        setRecommendationsError(err instanceof Error ? err.message : "Failed to load recommendation history");
      } finally {
        setLoadingRecHistory(false);
      }
    }
    setShowRecHistory(!showRecHistory);
  };

  const handleCloseDetail = () => {
    setSelectedIncidentId(null);
    setSelectedIncident(null);
    setIncidentContext(null);
    setContextError(null);
    setRcaAnalysis(null);
    setRcaError(null);
    setShowRCAHistory(false);
    setRecommendations(null);
    setRecommendationsError(null);
    setShowRecHistory(false);
  };

  const toggleTrace = (eventId: number) => {
    setExpandedTraces((prev) => ({ ...prev, [eventId]: !prev[eventId] }));
  };

  const formatTimestamp = (ts: string | null) => {
    if (!ts) return "—";
    try {
      return new Date(ts).toLocaleString();
    } catch {
      return ts;
    }
  };

  const getConfidenceBadge = (confidence: number | null) => {
    if (confidence === null || confidence === undefined) return null;
    const pct = Math.round(confidence * 100);
    let colorClass = "confidence-medium";
    if (confidence >= 0.9) colorClass = "confidence-high";
    else if (confidence < 0.8) colorClass = "confidence-low";
    return <span className={`confidence-badge ${colorClass}`}>{pct}% Confidence</span>;
  };

  const renderStatusBadge = (status: string) => {
    const norm = (status || "").toUpperCase();
    if (norm === "AVAILABLE") {
      return (
        <span className="op-status-badge available">
          <CheckCircle2 size={12} />
          AVAILABLE
        </span>
      );
    }
    if (norm === "INTEGRATION_REQUIRED") {
      return (
        <span className="op-status-badge integration-required">
          <AlertTriangle size={12} />
          INTEGRATION REQUIRED
        </span>
      );
    }
    if (norm === "ERROR") {
      return (
        <span className="op-status-badge error">
          <AlertCircle size={12} />
          ERROR
        </span>
      );
    }
    return (
      <span className="op-status-badge not-connected">
        <Info size={12} />
        {norm ? norm.replace(/_/g, " ") : "NOT CONNECTED"}
      </span>
    );
  };

  const renderRCAStatusBadge = (status: string) => {
    let cls = "status-unavailable";
    if (status === "COMPLETED") cls = "status-available";
    else if (status === "INSUFFICIENT_EVIDENCE") cls = "status-integration-required";
    else if (status === "PROVIDER_UNAVAILABLE") cls = "status-not-connected";
    return <span className={`context-status-badge ${cls}`}>{status.replace("_", " ")}</span>;
  };

  const renderCausalStatusBadge = (status: string) => {
    let bg = "#e2e8f0";
    let color = "#334155";
    if (status === "CONFIRMED") {
      bg = "#dcfce7";
      color = "#15803d";
    } else if (status === "SUPPORTED") {
      bg = "#e0e7ff";
      color = "#3730a3";
    } else if (status === "HYPOTHESIS") {
      bg = "#fef3c7";
      color = "#92400e";
    }
    return (
      <span
        style={{
          display: "inline-block",
          fontSize: "0.75rem",
          fontWeight: 600,
          padding: "0.2rem 0.5rem",
          borderRadius: "4px",
          backgroundColor: bg,
          color: color,
        }}
      >
        {status}
      </span>
    );
  };

  const renderRoleBadge = (role: string) => {
    let bg = "#f1f5f9";
    let color = "#475569";
    if (role === "ROOT_CAUSE_CANDIDATE") {
      bg = "#fee2e2";
      color = "#b91c1c";
    } else if (role === "CONTRIBUTING_FACTOR") {
      bg = "#ffedd5";
      color = "#c2410c";
    } else if (role === "SYMPTOM") {
      bg = "#f3e8ff";
      color = "#6b21a8";
    }
    return (
      <span
        style={{
          display: "inline-block",
          fontSize: "0.7rem",
          fontWeight: 600,
          padding: "0.15rem 0.45rem",
          borderRadius: "4px",
          backgroundColor: bg,
          color: color,
          textTransform: "uppercase",
          letterSpacing: "0.03em",
        }}
      >
        {role.replace(/_/g, " ")}
      </span>
    );
  };

  const renderRecommendationTypeBadge = (type: string) => {
    let bg = "#f1f5f9";
    let color = "#334155";
    if (type === "INVESTIGATION") {
      bg = "#e0f2fe";
      color = "#0369a1";
    } else if (type === "DIAGNOSTIC_VERIFICATION") {
      bg = "#e0e7ff";
      color = "#4338ca";
    } else if (type === "FIX") {
      bg = "#dcfce7";
      color = "#15803d";
    } else if (type === "PREVENTION") {
      bg = "#fef3c7";
      color = "#b45309";
    } else if (type === "VERIFICATION") {
      bg = "#f3e8ff";
      color = "#7e22ce";
    }
    return (
      <span
        style={{
          display: "inline-block",
          fontSize: "0.7rem",
          fontWeight: 700,
          padding: "0.2rem 0.5rem",
          borderRadius: "4px",
          backgroundColor: bg,
          color: color,
          textTransform: "uppercase",
          letterSpacing: "0.04em",
        }}
      >
        {type.replace(/_/g, " ")}
      </span>
    );
  };

  const renderRiskBadge = (risk: string) => {
    let bg = "#f1f5f9";
    let color = "#475569";
    if (risk === "LOW") {
      bg = "#dcfce7";
      color = "#166534";
    } else if (risk === "MEDIUM") {
      bg = "#ffedd5";
      color = "#9a3412";
    } else if (risk === "HIGH") {
      bg = "#fee2e2";
      color = "#991b1b";
    }
    return (
      <span
        style={{
          display: "inline-block",
          fontSize: "0.7rem",
          fontWeight: 600,
          padding: "0.15rem 0.45rem",
          borderRadius: "4px",
          backgroundColor: bg,
          color: color,
        }}
      >
        Risk: {risk}
      </span>
    );
  };

  const renderRecStatusBadge = (status: string) => {
    let bg = "#f1f5f9";
    let color = "#475569";
    if (status === "PROPOSED") {
      bg = "#e2e8f0";
      color = "#334155";
    } else if (status === "REVIEW_REQUIRED") {
      bg = "#fef3c7";
      color = "#92400e";
    } else if (status === "DISMISSED") {
      bg = "#fee2e2";
      color = "#b91c1c";
    }
    return (
      <span
        style={{
          display: "inline-block",
          fontSize: "0.7rem",
          fontWeight: 600,
          padding: "0.15rem 0.45rem",
          borderRadius: "4px",
          backgroundColor: bg,
          color: color,
          textTransform: "uppercase",
        }}
      >
        {status.replace(/_/g, " ")}
      </span>
    );
  };

  const openCount = incidents.filter((i) => i.status !== "RESOLVED").length;
  const resolvedCount = incidents.filter((i) => i.status === "RESOLVED").length;
  const multiServiceCount = incidents.filter((i) => (i.service_count || 0) > 1).length;

  return (
    <div className="page-wrapper">
      {/* Top KPI Metric Row */}
      <div className="kpi-grid" style={{ marginBottom: 20 }}>
        <div className="card kpi-card">
          <div className="kpi-header">
            <span className="kpi-title">Total Incidents</span>
            <div className="kpi-icon-box" style={{ background: "#eff6ff", color: "#1d4ed8" }}>
              <Flame size={18} />
            </div>
          </div>
          <div className="kpi-value">{totalCount}</div>
          <span className="kpi-hint">Correlated temporal clusters</span>
        </div>

        <div className="card kpi-card">
          <div className="kpi-header">
            <span className="kpi-title">Active / Open</span>
            <div className="kpi-icon-box" style={{ background: openCount > 0 ? "#fee2e2" : "#f0fdf4", color: openCount > 0 ? "#dc2626" : "#16a34a" }}>
              <AlertTriangle size={18} />
            </div>
          </div>
          <div className="kpi-value" style={{ color: openCount > 0 ? "#dc2626" : "#16a34a" }}>
            {openCount}
          </div>
          <span className="kpi-hint">Requiring investigation</span>
        </div>

        <div className="card kpi-card">
          <div className="kpi-header">
            <span className="kpi-title">Resolved</span>
            <div className="kpi-icon-box" style={{ background: "#f0fdf4", color: "#16a34a" }}>
              <CheckCircle2 size={18} />
            </div>
          </div>
          <div className="kpi-value" style={{ color: "#16a34a" }}>{resolvedCount}</div>
          <span className="kpi-hint">Verified and closed</span>
        </div>

        <div className="card kpi-card">
          <div className="kpi-header">
            <span className="kpi-title">Cross-Service Clusters</span>
            <div className="kpi-icon-box" style={{ background: "#f0f9ff", color: "#0284c7" }}>
              <Layers size={18} />
            </div>
          </div>
          <div className="kpi-value">{multiServiceCount}</div>
          <span className="kpi-hint">Multi-service cascading impact</span>
        </div>
      </div>

      {/* Top Controls Card */}
      <section className="card">
        <div className="card-header-row">
          <div>
            <h2 className="card-title">Correlated Incidents</h2>
            <p className="card-subtitle">
              Phase 3: Deterministic correlation of parsed log events across temporal windows and shared contexts
            </p>
          </div>
          <div style={{ display: "flex", gap: "0.75rem", alignItems: "center" }}>
            <select
              className="form-control"
              style={{ width: "auto", fontSize: "0.85rem", padding: "0.35rem 0.75rem" }}
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
            >
              <option value="">All Statuses</option>
              <option value="OPEN">Open Only</option>
              <option value="RESOLVED">Resolved Only</option>
            </select>
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              onClick={loadIncidents}
              disabled={loading}
              style={{ display: "inline-flex", alignItems: "center", gap: 6 }}
            >
              <RefreshCw size={14} className={loading ? "spin" : ""} />
              {loading ? "Refreshing..." : "Refresh"}
            </button>
            <button
              type="button"
              className="btn btn-primary btn-sm"
              onClick={handleRunCorrelation}
              disabled={isCorrelating}
              style={{ display: "inline-flex", alignItems: "center", gap: 6 }}
            >
              <Zap size={14} />
              {isCorrelating ? "Correlating..." : "Run Correlation"}
            </button>
          </div>
        </div>

        {/* Informational Scope Alert */}
        <div className="alert alert-info" style={{ marginBottom: "1rem" }}>
          <strong>Correlation Boundary:</strong> Phase 3 identifies correlated incident groups from event evidence.
          It does <em>not</em> determine root cause or causality.
        </div>

        {/* Correlation Run Feedback */}
        {correlationResult && (
          <div className="alert alert-success" style={{ marginBottom: "1rem" }}>
            <strong>Correlation Complete:</strong> Evaluated {correlationResult.events_considered} candidate events.{" "}
            Created <strong>{correlationResult.incidents_created}</strong> new incident(s) and reused{" "}
            <strong>{correlationResult.incidents_existing}</strong> existing incident(s).
          </div>
        )}

        {error && (
          <div className="alert alert-error" style={{ marginBottom: "1rem" }}>
            <strong>Error:</strong> {error}
          </div>
        )}

        {/* Incidents Table */}
        {loading ? (
          <div className="empty-state" style={{ padding: "3rem 1rem" }}>
            <RefreshCw size={28} className="spin" style={{ color: "#1d4ed8", marginBottom: 8 }} />
            <p className="empty-title">Loading Incidents...</p>
            <p className="empty-subtitle">Retrieving correlated incident records from PostgreSQL.</p>
          </div>
        ) : incidents.length === 0 ? (
          <div className="empty-state" style={{ padding: "3.5rem 1rem" }}>
            <div style={{ width: 48, height: 48, borderRadius: "50%", background: "#f0fdf4", color: "#16a34a", display: "inline-flex", alignItems: "center", justifyContent: "center", marginBottom: 12 }}>
              <ShieldCheck size={28} />
            </div>
            <p className="empty-title">Clean Demonstration Environment • Zero Active Incidents</p>
            <p className="empty-subtitle" style={{ maxWidth: 520, margin: "6px auto 16px" }}>
              All systems are normal. Ingest raw log files on the Live Logs page or trigger deterministic correlation to group multi-service events.
            </p>
            <button
              type="button"
              className="btn btn-primary btn-sm"
              onClick={handleRunCorrelation}
              disabled={isCorrelating}
              style={{ display: "inline-flex", alignItems: "center", gap: 6 }}
            >
              <Zap size={14} />
              Run Correlation Now
            </button>
          </div>
        ) : (
          <div className="table-responsive">
            <table className="logs-table">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Title</th>
                  <th>Status</th>
                  <th>Event Count</th>
                  <th>Services</th>
                  <th>Correlation Reason</th>
                  <th>Confidence</th>
                  <th>Time Range</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {incidents.map((inc) => (
                  <tr key={inc.id} style={{ cursor: "pointer" }} onClick={() => handleOpenDetail(inc.id)}>
                    <td className="log-id">#{inc.id}</td>
                    <td style={{ fontWeight: 600, color: "var(--text-primary)" }}>{inc.title}</td>
                    <td>
                      <span className={`badge ${inc.status === "OPEN" ? "badge-error" : "badge-log"}`}>
                        {inc.status}
                      </span>
                    </td>
                    <td className="numeric-cell">{inc.event_count} events</td>
                    <td className="numeric-cell">{inc.service_count} service(s)</td>
                    <td style={{ maxWidth: "260px", fontSize: "0.8rem", color: "var(--text-secondary)" }}>
                      {inc.correlation_reason}
                    </td>
                    <td>{getConfidenceBadge(inc.correlation_confidence)}</td>
                    <td className="timestamp-cell">
                      {formatTimestamp(inc.started_at)}
                      {inc.ended_at && inc.ended_at !== inc.started_at && ` → ${formatTimestamp(inc.ended_at)}`}
                    </td>
                    <td>
                      <button
                        type="button"
                        className="btn btn-secondary btn-sm"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleOpenDetail(inc.id);
                        }}
                      >
                        View Events
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div style={{ padding: "0.75rem", fontSize: "0.8rem", color: "var(--text-muted)", textAlign: "right" }}>
              Total Incidents: {totalCount}
            </div>
          </div>
        )}
      </section>

      {/* Incident Detail Drawer / Panel */}
      {selectedIncidentId && (
        <section className="incident-detail-panel">
          {detailLoading && (
            <div className="empty-state" style={{ padding: "2rem" }}>
              <RefreshCw size={24} className="spin" style={{ color: "#1d4ed8", marginBottom: 8 }} />
              <p className="empty-title">Loading incident details...</p>
              <p className="empty-subtitle">Retrieving constituent events, telemetry context, and causality chains.</p>
            </div>
          )}

          {detailError && (
            <div className="alert alert-error" style={{ marginBottom: "1rem" }}>
              <AlertCircle size={16} />
              <div><strong>Error:</strong> {detailError}</div>
            </div>
          )}

          {selectedIncident && (
            <div>
              {/* 1. INCIDENT HEADER */}
              <div className="incident-header-banner">
                <div className="incident-header-top-row">
                  <div className="incident-title-block">
                    <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                      <span className="incident-id-tag">INCIDENT #{selectedIncident.id}</span>
                      <span className={`incident-status-pill status-${selectedIncident.status.toLowerCase()}`}>
                        {selectedIncident.status}
                      </span>
                    </div>
                    <h3 className="incident-main-title">{selectedIncident.title}</h3>
                  </div>
                  <button
                    type="button"
                    className="btn btn-secondary btn-sm"
                    onClick={handleCloseDetail}
                    style={{ display: "inline-flex", alignItems: "center", gap: 6 }}
                  >
                    <X size={15} /> Close Detail
                  </button>
                </div>

                {/* Horizontal Summary Bar */}
                <div className="incident-summary-bar">
                  <div className="summary-metric-segment">
                    <span className="summary-metric-label">Investigation Status</span>
                    <div className="summary-metric-value">
                      <span className={`incident-status-pill status-${selectedIncident.status.toLowerCase()}`} style={{ fontSize: "0.7rem", padding: "1px 8px" }}>
                        {selectedIncident.status}
                      </span>
                    </div>
                  </div>

                  <div className="summary-metric-segment">
                    <span className="summary-metric-label">
                      <Clock size={13} /> Start Time
                    </span>
                    <span className="summary-metric-value">
                      {formatTimestamp(selectedIncident.started_at)}
                    </span>
                  </div>

                  <div className="summary-metric-segment">
                    <span className="summary-metric-label">
                      <Clock size={13} /> End Time
                    </span>
                    <span className="summary-metric-value">
                      {selectedIncident.ended_at ? formatTimestamp(selectedIncident.ended_at) : "Ongoing"}
                    </span>
                  </div>

                  <div className="summary-metric-segment">
                    <span className="summary-metric-label">
                      <Layers size={13} /> Affected Services
                    </span>
                    <span className="summary-metric-value">
                      {selectedIncident.service_count} {selectedIncident.service_count === 1 ? "Service" : "Services"}
                    </span>
                  </div>

                  <div className="summary-metric-segment">
                    <span className="summary-metric-label">
                      <Activity size={13} /> Correlated Events
                    </span>
                    <span className="summary-metric-value">
                      {selectedIncident.event_count} Events
                    </span>
                  </div>
                </div>
              </div>

              {/* 2. DEDICATED CORRELATION INFORMATION CARD */}
              <div className="correlation-summary-card" style={{ marginTop: "1.25rem" }}>
                <div className="correlation-card-header">
                  <h4 className="correlation-card-title">
                    <GitMerge size={18} style={{ color: "var(--primary)" }} />
                    <span>Correlation Information</span>
                  </h4>
                  <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                    <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>Shared Correlation ID:</span>
                    <code className="correlation-id-badge">
                      {selectedIncident.incident_key || `CORR-INC-${selectedIncident.id}`}
                    </code>
                  </div>
                </div>

                <div className="correlation-meta-grid">
                  <div className="op-kv-pair">
                    <span className="op-kv-label">Correlation Reason</span>
                    <span className="op-kv-value">{selectedIncident.correlation_reason}</span>
                  </div>

                  <div className="op-kv-pair">
                    <span className="op-kv-label">Affected Services</span>
                    <div className="op-kv-value">
                      {selectedIncident.events && selectedIncident.events.length > 0 ? (
                        <div style={{ display: "flex", gap: "6px", flexWrap: "wrap", marginTop: "2px" }}>
                          {Array.from(new Set(selectedIncident.events.map((e) => e.service_name).filter(Boolean))).map((svc) => (
                            <span key={svc} className="badge badge-txt">{svc}</span>
                          ))}
                        </div>
                      ) : (
                        <span>{selectedIncident.service_count} service(s)</span>
                      )}
                    </div>
                  </div>

                  <div className="op-kv-pair">
                    <span className="op-kv-label">Correlated Event Count</span>
                    <span className="op-kv-value">
                      <span className="badge badge-event-count">{selectedIncident.event_count} Events</span>
                    </span>
                  </div>

                  <div className="op-kv-pair">
                    <span className="op-kv-label">Correlation Confidence</span>
                    <span className="op-kv-value">
                      {getConfidenceBadge(selectedIncident.correlation_confidence) || (
                        <span className="confidence-badge confidence-high">Deterministic (100%)</span>
                      )}
                    </span>
                  </div>
                </div>

                <div className="correlation-notice-bar">
                  <Info size={16} style={{ flexShrink: 0 }} />
                  <span>Correlation indicates related events, not confirmed causation.</span>
                </div>
              </div>

              {/* 3. OPERATIONAL CONTEXT ENRICHMENT (6 INDIVIDUAL CARDS) */}
              <div className="operational-context-section" style={{ marginTop: "1.5rem" }}>
                <div className="context-header-toolbar">
                  <div className="context-title-group">
                    <h4 className="context-main-title">
                      <span>Operational Context Enrichment</span>
                      <span className="phase-tag">Phase 4</span>
                    </h4>
                    <p className="context-subtitle">
                      Real evidence collected around the incident. Unconnected systems are explicitly declared; no operational values are fabricated.
                    </p>
                  </div>
                  <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
                    {incidentContext && (
                      <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
                        Collected: {formatTimestamp(incidentContext.collected_at)}
                      </span>
                    )}
                    <button
                      type="button"
                      className="btn btn-secondary btn-sm"
                      onClick={handleEnrichContext}
                      disabled={isEnriching || contextLoading}
                      style={{ fontSize: "0.775rem", padding: "0.3rem 0.75rem", display: "inline-flex", alignItems: "center", gap: 6 }}
                    >
                      <Zap size={13} />
                      {isEnriching ? "Enriching..." : "⚡ Re-run Enrichment"}
                    </button>
                  </div>
                </div>

                {contextError && (
                  <div className="alert alert-error" style={{ marginBottom: "1rem" }}>
                    <strong>Context Error:</strong> {contextError}
                  </div>
                )}

                {contextLoading && !incidentContext ? (
                  <div className="empty-state" style={{ padding: "2rem" }}>
                    <RefreshCw size={22} className="spin" style={{ color: "#1d4ed8", marginBottom: 6 }} />
                    <p className="empty-title">Loading Operational Context...</p>
                    <p className="empty-subtitle">Gathering infrastructure, deployment, and service telemetry.</p>
                  </div>
                ) : incidentContext ? (
                  <div className="operational-context-grid">
                    {/* Card 1: Service Context */}
                    <div className="op-context-card">
                      <div className="op-context-card-header">
                        <h5 className="op-context-card-title">
                          <Server size={16} style={{ color: "#1d4ed8" }} />
                          <span>1. Service Context</span>
                        </h5>
                        {renderStatusBadge(incidentContext.contexts.service?.status || "AVAILABLE")}
                      </div>
                      <div className="op-context-card-body">
                        <div className="op-kv-pair">
                          <span className="op-kv-label">Primary Service</span>
                          <span className="op-kv-value">
                            {incidentContext.contexts.service?.data?.service_name || "— Unavailable"}
                          </span>
                        </div>

                        <div className="op-kv-pair">
                          <span className="op-kv-label">Services Observed</span>
                          <span className="op-kv-value">
                            {incidentContext.contexts.service?.data?.services_involved?.join(", ") ||
                              (selectedIncident.events
                                ? Array.from(new Set(selectedIncident.events.map((e) => e.service_name).filter(Boolean))).join(", ")
                                : "— Unavailable")}
                          </span>
                        </div>

                        <div className="op-kv-pair">
                          <span className="op-kv-label">Language / Framework</span>
                          <span className="op-kv-value muted">
                            {incidentContext.contexts.service?.data?.language ||
                              incidentContext.contexts.service?.data?.framework ||
                              "— Unavailable (Runtime telemetry not connected)"}
                          </span>
                        </div>

                        <div className="op-kv-pair">
                          <span className="op-kv-label">Owner / Team</span>
                          <span className="op-kv-value muted">
                            {incidentContext.contexts.service?.data?.owner ||
                              incidentContext.contexts.service?.data?.team ||
                              "— Not Connected (Service catalog required)"}
                          </span>
                        </div>

                        <div className="op-kv-pair">
                          <span className="op-kv-label">Repository</span>
                          <span className="op-kv-value muted">
                            {incidentContext.contexts.service?.data?.repository || "— Not Connected (Version control integration required)"}
                          </span>
                        </div>

                        <div className="op-card-footer">
                          <span>Data Source:</span>
                          <code className="hash-code">{incidentContext.contexts.service?.source || "parsed_log_metadata"}</code>
                        </div>
                      </div>
                    </div>

                    {/* Card 2: Deployment Context */}
                    <div className="op-context-card">
                      <div className="op-context-card-header">
                        <h5 className="op-context-card-title">
                          <Rocket size={16} style={{ color: "#d97706" }} />
                          <span>2. Deployment Context</span>
                        </h5>
                        {renderStatusBadge(incidentContext.contexts.deployment?.status || "INTEGRATION_REQUIRED")}
                      </div>
                      <div className="op-context-card-body">
                        <div className="op-kv-pair">
                          <span className="op-kv-label">Deployment Version</span>
                          <span className="op-kv-value muted">
                            {incidentContext.contexts.deployment?.data?.deployment_version || "Integration Required"}
                          </span>
                        </div>

                        <div className="op-kv-pair">
                          <span className="op-kv-label">Git Commit</span>
                          <span className="op-kv-value muted">
                            {incidentContext.contexts.deployment?.data?.git_commit || "Integration Required"}
                          </span>
                        </div>

                        <div className="op-kv-pair">
                          <span className="op-kv-label">Build Number</span>
                          <span className="op-kv-value muted">
                            {incidentContext.contexts.deployment?.data?.build_number || "Integration Required"}
                          </span>
                        </div>

                        <div className="op-kv-pair">
                          <span className="op-kv-label">Deployment Time</span>
                          <span className="op-kv-value muted">
                            {incidentContext.contexts.deployment?.data?.deployed_at
                              ? formatTimestamp(incidentContext.contexts.deployment.data.deployed_at)
                              : "Integration Required"}
                          </span>
                        </div>

                        <div className="op-kv-pair">
                          <span className="op-kv-label">CI/CD Integration Status</span>
                          <span className="op-kv-value">
                            {incidentContext.contexts.deployment?.data?.connected ? (
                              <span className="badge badge-status-success">Connected</span>
                            ) : (
                              <span className="badge badge-warn">
                                {incidentContext.contexts.deployment?.data?.message || "Integration Required (GitHub / GitLab / ArgoCD)"}
                              </span>
                            )}
                          </span>
                        </div>

                        <div className="op-card-footer">
                          <span>Data Source:</span>
                          <code className="hash-code">{incidentContext.contexts.deployment?.source || "NullDeploymentProvider"}</code>
                        </div>
                      </div>
                    </div>

                    {/* Card 3: Infrastructure Context */}
                    <div className="op-context-card">
                      <div className="op-context-card-header">
                        <h5 className="op-context-card-title">
                          <Cpu size={16} style={{ color: "#475569" }} />
                          <span>3. Infrastructure Context</span>
                        </h5>
                        {renderStatusBadge(incidentContext.contexts.infrastructure?.status || "NOT_CONNECTED")}
                      </div>
                      <div className="op-context-card-body">
                        <div className="op-kv-pair">
                          <span className="op-kv-label">Kubernetes Cluster</span>
                          <span className="op-kv-value muted">
                            {incidentContext.contexts.infrastructure?.data?.cluster || "Not Connected"}
                          </span>
                        </div>

                        <div className="op-kv-pair">
                          <span className="op-kv-label">Namespace</span>
                          <span className="op-kv-value muted">
                            {incidentContext.contexts.infrastructure?.data?.namespace || "Not Connected"}
                          </span>
                        </div>

                        <div className="op-kv-pair">
                          <span className="op-kv-label">Pods / Nodes</span>
                          <span className="op-kv-value muted">
                            {incidentContext.contexts.infrastructure?.data?.pods?.length
                              ? `${incidentContext.contexts.infrastructure.data.pods.length} pods observed`
                              : "0 pods observed (Not Connected)"}
                          </span>
                        </div>

                        <div className="op-kv-pair">
                          <span className="op-kv-label">Cloud Provider</span>
                          <span className="op-kv-value muted">
                            {incidentContext.contexts.infrastructure?.data?.cloud_provider || "Not Connected"}
                          </span>
                        </div>

                        <div className="op-kv-pair">
                          <span className="op-kv-label">Infrastructure Integration Status</span>
                          <span className="op-kv-value">
                            {incidentContext.contexts.infrastructure?.data?.connected ? (
                              <span className="badge badge-status-success">Connected</span>
                            ) : (
                              <span className="badge badge-status-other">
                                {incidentContext.contexts.infrastructure?.data?.message || "Not Connected (Kubernetes engine)"}
                              </span>
                            )}
                          </span>
                        </div>

                        <div className="op-card-footer">
                          <span>Data Source:</span>
                          <code className="hash-code">{incidentContext.contexts.infrastructure?.source || "NullInfrastructureProvider"}</code>
                        </div>
                      </div>
                    </div>

                    {/* Card 4: Metrics Context */}
                    <div className="op-context-card">
                      <div className="op-context-card-header">
                        <h5 className="op-context-card-title">
                          <Activity size={16} style={{ color: "#0284c7" }} />
                          <span>4. Metrics Context</span>
                        </h5>
                        {renderStatusBadge(incidentContext.contexts.metrics?.status || "NOT_CONNECTED")}
                      </div>
                      <div className="op-context-card-body">
                        <div className="op-kv-pair">
                          <span className="op-kv-label">CPU / Memory Usage</span>
                          <span className="op-kv-value muted">
                            {incidentContext.contexts.metrics?.data?.cpu_usage ||
                              incidentContext.contexts.metrics?.data?.memory_usage ||
                              "Not Connected"}
                          </span>
                        </div>

                        <div className="op-kv-pair">
                          <span className="op-kv-label">Latency (P95/P99)</span>
                          <span className="op-kv-value muted">
                            {incidentContext.contexts.metrics?.data?.latency ||
                              (incidentContext.contexts.metrics?.data?.p95 && incidentContext.contexts.metrics?.data?.p99
                                ? `P95: ${incidentContext.contexts.metrics.data.p95}ms • P99: ${incidentContext.contexts.metrics.data.p99}ms`
                                : "Not Connected")}
                          </span>
                        </div>

                        <div className="op-kv-pair">
                          <span className="op-kv-label">Prometheus APM Status</span>
                          <span className="op-kv-value">
                            <span className="badge badge-status-other">
                              {incidentContext.contexts.metrics?.data?.prometheus || "Not Connected"}
                            </span>
                          </span>
                        </div>

                        <div className="op-kv-pair">
                          <span className="op-kv-label">Datadog APM Status</span>
                          <span className="op-kv-value">
                            <span className="badge badge-status-other">
                              {incidentContext.contexts.metrics?.data?.datadog || "Not Connected"}
                            </span>
                          </span>
                        </div>

                        <div className="op-kv-pair">
                          <span className="op-kv-label">Metrics Integration Status</span>
                          <span className="op-kv-value">
                            {incidentContext.contexts.metrics?.data?.connected ? (
                              <span className="badge badge-status-success">Connected</span>
                            ) : (
                              <span className="badge badge-status-other">
                                {incidentContext.contexts.metrics?.data?.message || "Not Connected (Real APM integration required; no synthetic data)"}
                              </span>
                            )}
                          </span>
                        </div>

                        <div className="op-card-footer">
                          <span>Data Source:</span>
                          <code className="hash-code">{incidentContext.contexts.metrics?.source || "NullMetricsProvider"}</code>
                        </div>
                      </div>
                    </div>

                    {/* Card 5: Incident History */}
                    <div className="op-context-card">
                      <div className="op-context-card-header">
                        <h5 className="op-context-card-title">
                          <History size={16} style={{ color: "#16a34a" }} />
                          <span>5. Incident History</span>
                        </h5>
                        {renderStatusBadge(incidentContext.contexts.history?.status || "AVAILABLE")}
                      </div>
                      <div className="op-context-card-body">
                        <div className="op-kv-pair">
                          <span className="op-kv-label">Previous Occurrences</span>
                          <span className="op-kv-value">
                            <strong>{incidentContext.contexts.history?.data?.previous_occurrence_count ?? 0}</strong> previous occurrence(s) matching observed services
                          </span>
                        </div>

                        <div className="op-kv-pair">
                          <span className="op-kv-label">Recurring Incident Status</span>
                          <span className="op-kv-value">
                            {incidentContext.contexts.history?.data?.recurring ? (
                              <span className="badge badge-warn">Recurring Incident</span>
                            ) : (
                              <span className="badge badge-status-success">First Recorded Occurrence (Non-recurring)</span>
                            )}
                          </span>
                        </div>

                        <div className="op-kv-pair">
                          <span className="op-kv-label">Related Incident IDs</span>
                          <div className="op-kv-value">
                            {incidentContext.contexts.history?.data?.previous_incident_ids?.length ? (
                              <div style={{ display: "flex", gap: "6px", flexWrap: "wrap", marginTop: "2px" }}>
                                {incidentContext.contexts.history.data.previous_incident_ids.map((id: number) => (
                                  <span key={id} className="badge badge-log">#{id}</span>
                                ))}
                              </div>
                            ) : (
                              <span className="op-kv-value muted">None detected in PostgreSQL history</span>
                            )}
                          </div>
                        </div>

                        <div className="op-kv-pair">
                          <span className="op-kv-label">First Occurrence</span>
                          <span className="op-kv-value">
                            {incidentContext.contexts.history?.data?.first_occurrence_timestamp
                              ? formatTimestamp(incidentContext.contexts.history.data.first_occurrence_timestamp)
                              : "This incident is the first recorded instance"}
                          </span>
                        </div>

                        <div className="op-card-footer">
                          <span>Data Source:</span>
                          <code className="hash-code">{incidentContext.contexts.history?.source || "incident_history_db (PostgreSQL)"}</code>
                        </div>
                      </div>
                    </div>

                    {/* Card 6: Dependencies Context */}
                    <div className="op-context-card">
                      <div className="op-context-card-header">
                        <h5 className="op-context-card-title">
                          <Network size={16} style={{ color: "#7e22ce" }} />
                          <span>6. Dependencies Context</span>
                        </h5>
                        {renderStatusBadge(incidentContext.contexts.dependencies?.status || "AVAILABLE")}
                      </div>
                      <div className="op-context-card-body">
                        <div className="op-kv-pair">
                          <span className="op-kv-label">Services Observed</span>
                          <span className="op-kv-value">
                            {incidentContext.contexts.dependencies?.data?.services_involved?.join(", ") ||
                              (selectedIncident.events
                                ? Array.from(new Set(selectedIncident.events.map((e) => e.service_name).filter(Boolean))).join(", ")
                                : "— Unavailable")}
                          </span>
                        </div>

                        <div className="op-kv-pair">
                          <span className="op-kv-label">Service Count</span>
                          <span className="op-kv-value">
                            <strong>{incidentContext.contexts.dependencies?.data?.service_count ?? selectedIncident.service_count}</strong> service(s) observed in correlated event cluster
                          </span>
                        </div>

                        <div className="op-kv-pair">
                          <span className="op-kv-label">Causal Dependencies</span>
                          <span className="op-kv-value muted">
                            {incidentContext.contexts.dependencies?.data?.causal_graph || "None (Unverified - topology not inferred)"}
                          </span>
                        </div>

                        <div className="op-kv-pair">
                          <span className="op-kv-label">Dependency Verification Status</span>
                          <span className="op-kv-value">
                            <span className="badge badge-status-other">
                              {incidentContext.contexts.dependencies?.data?.causality_status || "Unverified"}
                            </span>
                          </span>
                        </div>

                        <div className="op-card-notice">
                          <Info size={14} style={{ display: "inline", verticalAlign: "middle", marginRight: "6px", color: "#0284c7" }} />
                          {incidentContext.contexts.dependencies?.data?.correlation_vs_causation_notice ||
                            "Service correlation does NOT establish causation. Temporal co-occurrence does not confirm directional dependency."}
                        </div>

                        <div className="op-card-footer">
                          <span>Data Source:</span>
                          <code className="hash-code">{incidentContext.contexts.dependencies?.source || "event_correlation_graph"}</code>
                        </div>
                      </div>
                    </div>
                  </div>
                ) : null}
              </div>

              {/* Phase 5: AI Root Cause Analysis Section */}
              <div className="context-section" style={{ marginTop: "1.5rem" }}>
                <div className="context-section-header">
                  <div>
                    <h4 className="context-section-title" style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                      <span>🤖 AI Root Cause Analysis (Phase 5)</span>
                    </h4>
                    <p className="context-section-subtitle">
                      Evidence-grounded hypothesis reasoning over observed logs, exceptions, and operational contexts.
                      Correlation is not causation; all assertions require verified evidence backing.
                    </p>
                  </div>
                  <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
                    <button
                      type="button"
                      className="btn btn-secondary btn-sm"
                      onClick={handleToggleHistory}
                      disabled={loadingHistory || !selectedIncidentId}
                    >
                      {loadingHistory ? "Loading..." : showRCAHistory ? "Hide History ▲" : "📜 History ▼"}
                    </button>
                    <button
                      type="button"
                      className="btn btn-primary btn-sm"
                      onClick={handleRunRCA}
                      disabled={isRunningRCA || !selectedIncidentId}
                    >
                      {isRunningRCA ? "Analyzing Evidence..." : "🤖 Run Root Cause Analysis"}
                    </button>
                  </div>
                </div>

                {/* RCA Error */}
                {rcaError && (
                  <div className="alert alert-error" style={{ margin: "0.75rem 0" }}>
                    <strong>RCA Error:</strong> {rcaError}
                  </div>
                )}

                {/* History Drawer */}
                {showRCAHistory && (
                  <div
                    style={{
                      background: "#f8fafc",
                      border: "1px solid #e2e8f0",
                      borderRadius: "6px",
                      padding: "0.75rem",
                      marginBottom: "1rem",
                    }}
                  >
                    <h5 style={{ fontSize: "0.85rem", fontWeight: 600, margin: "0 0 0.5rem" }}>
                      Historical Analyses ({rcaHistory.length})
                    </h5>
                    {rcaHistory.length === 0 ? (
                      <p className="text-muted" style={{ fontSize: "0.8rem", margin: 0 }}>
                        No previous RCA runs found for this incident.
                      </p>
                    ) : (
                      <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
                        {rcaHistory.map((h) => (
                          <div
                            key={h.analysis_id}
                            style={{
                              padding: "0.5rem 0.75rem",
                              background: h.analysis_id === rcaAnalysis?.analysis_id ? "#eff6ff" : "#ffffff",
                              border: "1px solid #cbd5e1",
                              borderRadius: "4px",
                              display: "flex",
                              justifyContent: "space-between",
                              alignItems: "center",
                              fontSize: "0.8rem",
                            }}
                          >
                            <div>
                              <strong>{h.analysis_id}</strong> &bull; {renderRCAStatusBadge(h.analysis_status)} &bull;{" "}
                              <span className="text-muted">
                                {formatTimestamp(h.created_at)} ({h.provider} / {h.model})
                              </span>
                              <div style={{ marginTop: "0.2rem", color: "var(--text-secondary)" }}>{h.summary}</div>
                            </div>
                            <button
                              type="button"
                              className="btn btn-secondary btn-sm"
                              style={{ fontSize: "0.7rem", padding: "0.2rem 0.5rem" }}
                              onClick={() => setRcaAnalysis(h)}
                            >
                              View
                            </button>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}

                {/* RCA Loading */}
                {rcaLoading ? (
                  <p className="text-muted" style={{ padding: "1rem 0", fontSize: "0.85rem" }}>
                    Loading root cause analysis...
                  </p>
                ) : !rcaAnalysis ? (
                  <div
                    style={{
                      padding: "1.5rem",
                      textAlign: "center",
                      background: "#f8fafc",
                      borderRadius: "6px",
                      border: "1px dashed #cbd5e1",
                      color: "var(--text-secondary)",
                      fontSize: "0.85rem",
                    }}
                  >
                    No root cause analysis generated for this incident yet. Click{" "}
                    <strong>&quot;Run Root Cause Analysis&quot;</strong> above to reason over the available evidence.
                  </div>
                ) : (
                  <div>
                    {/* Header Summary & Meta */}
                    <div
                      style={{
                        background: "#ffffff",
                        border: "1px solid #e2e8f0",
                        borderRadius: "6px",
                        padding: "1rem",
                        marginBottom: "1rem",
                      }}
                    >
                      <div
                        style={{
                          display: "flex",
                          justifyContent: "space-between",
                          alignItems: "flex-start",
                          marginBottom: "0.5rem",
                        }}
                      >
                        <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
                          {renderRCAStatusBadge(rcaAnalysis.analysis_status)}
                          {rcaAnalysis.confidence !== null && (
                            <span style={{ fontSize: "0.8rem", fontWeight: 600 }}>
                              {Math.round((rcaAnalysis.confidence || 0) * 100)}% Confidence (
                              {rcaAnalysis.confidence_level || "MEDIUM"})
                            </span>
                          )}
                        </div>
                        <span className="text-muted" style={{ fontSize: "0.75rem" }}>
                          Provider: <strong>{rcaAnalysis.provider}</strong> ({rcaAnalysis.model}) &bull;{" "}
                          {formatTimestamp(rcaAnalysis.created_at)}
                        </span>
                      </div>
                      <p style={{ margin: "0.5rem 0 0", fontSize: "0.9rem", color: "var(--text-primary)" }}>
                        {rcaAnalysis.summary}
                      </p>
                    </div>

                    {/* Insufficient Evidence Notice */}
                    {rcaAnalysis.analysis_status === "INSUFFICIENT_EVIDENCE" && (
                      <div className="alert alert-info" style={{ marginBottom: "1rem" }}>
                        <strong>Insufficient Evidence:</strong> The available logs, exceptions, and operational contexts
                        do not provide sufficient data to support a definitive or plausible root cause.
                      </div>
                    )}

                    {/* Provider Unavailable Notice */}
                    {rcaAnalysis.analysis_status === "PROVIDER_UNAVAILABLE" && (
                      <div className="alert alert-warn" style={{ marginBottom: "1rem" }}>
                        <strong>AI Provider Unavailable:</strong> No external LLM provider or API key is configured.
                        Set <code>RCA_PROVIDER</code> and <code>RCA_API_KEY</code> in the backend environment to enable
                        automated reasoning.
                      </div>
                    )}

                    {/* Hypotheses List */}
                    {rcaAnalysis.hypotheses && rcaAnalysis.hypotheses.length > 0 && (
                      <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem", marginBottom: "1rem" }}>
                        <h5 style={{ fontSize: "0.85rem", fontWeight: 600, margin: 0 }}>
                          Evaluated Hypotheses ({rcaAnalysis.hypotheses.length})
                        </h5>
                        {rcaAnalysis.hypotheses.map((hyp) => (
                          <div
                            key={hyp.hypothesis_id}
                            style={{
                              border: "1px solid #e2e8f0",
                              borderRadius: "6px",
                              padding: "0.85rem",
                              background: "#ffffff",
                              boxShadow: "0 1px 2px rgba(0,0,0,0.03)",
                            }}
                          >
                            <div
                              style={{
                                display: "flex",
                                justifyContent: "space-between",
                                alignItems: "center",
                                marginBottom: "0.4rem",
                              }}
                            >
                              <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                                <span style={{ fontWeight: 600, fontSize: "0.9rem" }}>{hyp.title}</span>
                                {renderRoleBadge(hyp.role)}
                                {renderCausalStatusBadge(hyp.causal_status)}
                              </div>
                              <span style={{ fontSize: "0.75rem", fontWeight: 600, color: "var(--text-secondary)" }}>
                                {Math.round(hyp.confidence * 100)}% Confidence ({hyp.confidence_level})
                              </span>
                            </div>

                            <p style={{ fontSize: "0.85rem", margin: "0.25rem 0 0.5rem", color: "var(--text-secondary)" }}>
                              {hyp.description}
                            </p>

                            <div
                              style={{
                                background: "#f8fafc",
                                padding: "0.5rem",
                                borderRadius: "4px",
                                fontSize: "0.8rem",
                                marginBottom: "0.5rem",
                              }}
                            >
                              <strong>Reasoning:</strong> {hyp.reasoning}
                            </div>

                            {/* Supporting Evidence Chips */}
                            <div style={{ display: "flex", alignItems: "center", gap: "0.4rem", flexWrap: "wrap" }}>
                              <span style={{ fontSize: "0.75rem", fontWeight: 600, color: "var(--text-secondary)" }}>
                                Supporting Evidence:
                              </span>
                              {hyp.supporting_evidence && hyp.supporting_evidence.length > 0 ? (
                                hyp.supporting_evidence.map((evId) => (
                                  <span
                                    key={evId}
                                    style={{
                                      fontSize: "0.7rem",
                                      fontWeight: 600,
                                      padding: "0.15rem 0.4rem",
                                      background: "#e0f2fe",
                                      color: "#0369a1",
                                      borderRadius: "3px",
                                      fontFamily: "var(--font-mono)",
                                    }}
                                  >
                                    {evId}
                                  </span>
                                ))
                              ) : (
                                <span style={{ fontSize: "0.75rem", color: "var(--text-secondary)" }}>None verified</span>
                              )}
                            </div>
                          </div>
                        ))}
                      </div>
                    )}

                    {/* Limitations & Missing Evidence */}
                    {rcaAnalysis.limitations && rcaAnalysis.limitations.length > 0 && (
                      <div
                        style={{
                          background: "#fffbeb",
                          border: "1px solid #fef3c7",
                          borderRadius: "6px",
                          padding: "0.75rem 1rem",
                          fontSize: "0.8rem",
                        }}
                      >
                        <strong style={{ color: "#92400e" }}>Analysis Limitations &amp; Unverified Systems:</strong>
                        <ul style={{ margin: "0.25rem 0 0", paddingLeft: "1.25rem", color: "#78350f" }}>
                          {rcaAnalysis.limitations.map((lim, idx) => (
                            <li key={idx}>{lim}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                )}
              </div>

              {/* Phase 6: Investigation & Fix Recommendations Card */}
              <div
                style={{
                  background: "var(--card-bg, #ffffff)",
                  border: "1px solid var(--border-color, #e2e8f0)",
                  borderRadius: "8px",
                  padding: "1rem 1.25rem",
                  marginTop: "1.25rem",
                  boxShadow: "0 1px 3px rgba(0,0,0,0.05)",
                }}
              >
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    flexWrap: "wrap",
                    gap: "0.75rem",
                    marginBottom: "0.75rem",
                  }}
                >
                  <div>
                    <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                      <h4 style={{ margin: 0, fontSize: "1rem", fontWeight: 700 }}>
                        Investigation &amp; Fix Recommendations
                      </h4>
                      {recommendations && (
                        <span
                          style={{
                            background: "#e0e7ff",
                            color: "#4338ca",
                            fontSize: "0.7rem",
                            fontWeight: 700,
                            padding: "0.15rem 0.45rem",
                            borderRadius: "10px",
                          }}
                        >
                          {recommendations.total_recommendations}
                        </span>
                      )}
                    </div>
                    <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)", marginTop: "0.2rem" }}>
                      Phase 6: Grounded operational advice derived exclusively from validated RCA evidence
                    </div>
                  </div>

                  <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                    {recommendations && (
                      <button
                        type="button"
                        className="btn-secondary"
                        onClick={handleToggleRecHistory}
                        disabled={loadingRecHistory}
                        style={{ fontSize: "0.75rem", padding: "0.35rem 0.75rem" }}
                      >
                        {loadingRecHistory ? "Loading..." : showRecHistory ? "Hide History" : "View History"}
                      </button>
                    )}

                    <button
                      type="button"
                      className="btn-primary"
                      onClick={handleGenerateRecommendations}
                      disabled={isGeneratingRecs || !rcaAnalysis}
                      title={!rcaAnalysis ? "Requires validated RCA analysis first" : "Generate evidence-grounded recommendations"}
                      style={{ fontSize: "0.75rem", padding: "0.35rem 0.85rem" }}
                    >
                      {isGeneratingRecs ? "Generating..." : recommendations ? "Regenerate Recommendations" : "Generate Recommendations"}
                    </button>
                  </div>
                </div>

                {recommendationsError && (
                  <div className="alert alert-error" style={{ margin: "0.5rem 0" }}>
                    {recommendationsError}
                  </div>
                )}

                {/* History Drawer/Panel */}
                {showRecHistory && (
                  <div
                    style={{
                      background: "#f8fafc",
                      border: "1px solid #cbd5e1",
                      borderRadius: "6px",
                      padding: "0.75rem",
                      marginBottom: "1rem",
                      fontSize: "0.8rem",
                    }}
                  >
                    <div style={{ fontWeight: 600, marginBottom: "0.5rem", color: "#334155" }}>
                      Recommendation History ({recommendationHistory.length} total)
                    </div>
                    {recommendationHistory.length === 0 ? (
                      <div style={{ color: "var(--text-secondary)" }}>No prior recommendations recorded.</div>
                    ) : (
                      <div style={{ maxHeight: "200px", overflowY: "auto", display: "flex", flexDirection: "column", gap: "0.4rem" }}>
                        {recommendationHistory.map((item) => (
                          <div
                            key={item.id}
                            style={{
                              background: "#ffffff",
                              padding: "0.5rem",
                              borderRadius: "4px",
                              border: "1px solid #e2e8f0",
                              display: "flex",
                              justifyContent: "space-between",
                              alignItems: "center",
                            }}
                          >
                            <div style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}>
                              {renderRecommendationTypeBadge(item.type)}
                              <span style={{ fontWeight: 600 }}>{item.title}</span>
                            </div>
                            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", fontSize: "0.75rem" }}>
                              {renderRiskBadge(item.risk_level)}
                              <span style={{ color: "var(--text-secondary)" }}>{formatTimestamp(item.created_at)}</span>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}

                {recommendationsLoading ? (
                  <div className="empty-state" style={{ padding: "1rem 0" }}>
                    <div className="spinner" style={{ margin: "0 auto 0.5rem" }} />
                    <p style={{ margin: 0, fontSize: "0.85rem" }}>Loading recommendations...</p>
                  </div>
                ) : !recommendations ? (
                  <div
                    style={{
                      background: "#f8fafc",
                      border: "1px dashed #cbd5e1",
                      borderRadius: "6px",
                      padding: "1rem",
                      textAlign: "center",
                      color: "var(--text-secondary)",
                      fontSize: "0.85rem",
                    }}
                  >
                    {!rcaAnalysis ? (
                      <div>Run Root Cause Analysis above before generating investigation recommendations.</div>
                    ) : (
                      <div>
                        Validated RCA available. Click <strong>Generate Recommendations</strong> to formulate actionable, evidence-traceable investigation and fix steps.
                      </div>
                    )}
                  </div>
                ) : (
                  <div>
                    {/* Status & Metadata Bar */}
                    <div
                      style={{
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "space-between",
                        flexWrap: "wrap",
                        gap: "0.5rem",
                        padding: "0.5rem 0.75rem",
                        background: "#f8fafc",
                        borderRadius: "6px",
                        marginBottom: "0.75rem",
                        fontSize: "0.8rem",
                      }}
                    >
                      <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                        <span style={{ fontWeight: 600 }}>Status:</span>
                        {renderRCAStatusBadge(recommendations.status)}
                      </div>
                      <div style={{ display: "flex", alignItems: "center", gap: "1rem", color: "var(--text-secondary)" }}>
                        <span>Provider: <strong>{recommendations.provider}</strong></span>
                        <span>Model: <strong>{recommendations.model}</strong></span>
                        <span>Generated: <strong>{formatTimestamp(recommendations.generated_at)}</strong></span>
                      </div>
                    </div>

                    {/* Recommendation Cards */}
                    <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem", marginBottom: "0.75rem" }}>
                      {recommendations.recommendations.map((rec) => (
                        <div
                          key={rec.recommendation_id}
                          style={{
                            border: "1px solid #e2e8f0",
                            borderRadius: "6px",
                            padding: "0.85rem",
                            background: "#ffffff",
                          }}
                        >
                          <div
                            style={{
                              display: "flex",
                              justifyContent: "space-between",
                              alignItems: "flex-start",
                              flexWrap: "wrap",
                              gap: "0.5rem",
                              marginBottom: "0.4rem",
                            }}
                          >
                            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", flexWrap: "wrap" }}>
                              {renderRecommendationTypeBadge(rec.type)}
                              <span style={{ fontWeight: 700, fontSize: "0.95rem" }}>{rec.title}</span>
                              {renderRiskBadge(rec.risk_level)}
                              {renderRecStatusBadge(rec.status)}
                            </div>
                            <span style={{ fontSize: "0.75rem", fontWeight: 600, color: "var(--text-secondary)" }}>
                              {Math.round(rec.confidence * 100)}% Confidence ({rec.confidence_level})
                            </span>
                          </div>

                          <p style={{ fontSize: "0.85rem", margin: "0.3rem 0 0.5rem", color: "#334155" }}>
                            {rec.description}
                          </p>

                          {/* Rationale & Expected Impact */}
                          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.5rem", marginBottom: "0.5rem" }}>
                            <div
                              style={{
                                background: "#f8fafc",
                                padding: "0.5rem",
                                borderRadius: "4px",
                                fontSize: "0.8rem",
                              }}
                            >
                              <strong>Rationale:</strong> {rec.rationale}
                            </div>
                            <div
                              style={{
                                background: "#f0f9ff",
                                padding: "0.5rem",
                                borderRadius: "4px",
                                fontSize: "0.8rem",
                                color: "#0369a1",
                              }}
                            >
                              <strong>Expected Impact:</strong> {rec.expected_impact}
                            </div>
                          </div>

                          {/* Verification Steps */}
                          {rec.verification_steps && rec.verification_steps.length > 0 && (
                            <div
                              style={{
                                background: "#f0fdf4",
                                border: "1px solid #dcfce7",
                                borderRadius: "4px",
                                padding: "0.5rem 0.75rem",
                                marginBottom: "0.5rem",
                                fontSize: "0.8rem",
                              }}
                            >
                              <strong style={{ color: "#166534" }}>Verification Steps:</strong>
                              <ol style={{ margin: "0.2rem 0 0", paddingLeft: "1.25rem", color: "#15803d" }}>
                                {rec.verification_steps.map((step, idx) => (
                                  <li key={idx} style={{ marginBottom: "0.15rem" }}>{step}</li>
                                ))}
                              </ol>
                            </div>
                          )}

                          {/* Supporting Evidence Chips */}
                          <div style={{ display: "flex", alignItems: "center", gap: "0.4rem", flexWrap: "wrap" }}>
                            <span style={{ fontSize: "0.75rem", fontWeight: 600, color: "var(--text-secondary)" }}>
                              Supporting Evidence:
                            </span>
                            {rec.supporting_evidence && rec.supporting_evidence.length > 0 ? (
                              rec.supporting_evidence.map((evId) => (
                                <span
                                  key={evId}
                                  style={{
                                    fontSize: "0.7rem",
                                    fontWeight: 600,
                                    padding: "0.15rem 0.4rem",
                                    background: "#e0f2fe",
                                    color: "#0369a1",
                                    borderRadius: "3px",
                                    fontFamily: "var(--font-mono)",
                                  }}
                                >
                                  {evId}
                                </span>
                              ))
                            ) : (
                              <span style={{ fontSize: "0.75rem", color: "var(--text-secondary)" }}>None</span>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>

                    {/* Limitations & Missing Evidence */}
                    {recommendations.limitations && recommendations.limitations.length > 0 && (
                      <div
                        style={{
                          background: "#fffbeb",
                          border: "1px solid #fef3c7",
                          borderRadius: "6px",
                          padding: "0.75rem 1rem",
                          fontSize: "0.8rem",
                        }}
                      >
                        <strong style={{ color: "#92400e" }}>Recommendation Limitations &amp; Operational Caveats:</strong>
                        <ul style={{ margin: "0.25rem 0 0", paddingLeft: "1.25rem", color: "#78350f" }}>
                          {recommendations.limitations.map((lim, idx) => (
                            <li key={idx}>{lim}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                )}
              </div>

              {/* Phase 8: External Telemetry & Environment Context */}
              <IncidentIntegrationContext serviceName={selectedIncident.title} />

              {/* Phase 7: Developer Investigation Workspace */}
              <InvestigationWorkspace
                incidentId={selectedIncident.id}
                incident={selectedIncident}
                rcaAnalysis={rcaAnalysis}
                recommendations={recommendations}
                onIncidentUpdated={async () => {
                  if (selectedIncidentId) {
                    const detail = await fetchIncidentDetail(selectedIncidentId);
                    setSelectedIncident(detail);
                    await loadIncidents();
                  }
                }}
              />

              {/* Constituent Events Table */}
              <h4 style={{ fontSize: "0.95rem", fontWeight: 600, margin: "1rem 0 0.5rem" }}>
                Constituent Correlated Log Events (Chronological Order)
              </h4>
              <div className="table-responsive">
                <table className="logs-table">
                  <thead>
                    <tr>
                      <th>#</th>
                      <th>Time</th>
                      <th>Level</th>
                      <th>Service</th>
                      <th>Message</th>
                      <th>Exception / Details</th>
                      <th>Code Location</th>
                    </tr>
                  </thead>
                  <tbody>
                    {selectedIncident.events.map((evt, idx) => (
                      <React.Fragment key={evt.id}>
                        <tr>
                          <td className="log-id">{idx + 1}</td>
                          <td className="timestamp-cell">{formatTimestamp(evt.timestamp)}</td>
                          <td>
                            <span
                              className={`badge ${
                                evt.level === "ERROR" || evt.level === "CRITICAL"
                                  ? "badge-error"
                                  : evt.level === "WARN"
                                  ? "badge-warn"
                                  : "badge-log"
                              }`}
                            >
                              {evt.level || "UNKNOWN"}
                            </span>
                          </td>
                          <td>
                            <span className="badge badge-txt">{evt.service_name || "—"}</span>
                          </td>
                          <td style={{ maxWidth: "340px", wordBreak: "break-word" }}>{evt.message}</td>
                          <td>
                            {evt.exception_type ? (
                              <div>
                                <span style={{ fontWeight: 600, color: "var(--error)" }}>
                                  {evt.exception_type}
                                </span>
                                {evt.exception_message && (
                                  <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)" }}>
                                    {evt.exception_message}
                                  </div>
                                )}
                              </div>
                            ) : (
                              <span className="text-muted">—</span>
                            )}
                          </td>
                          <td>
                            {evt.source_file ? (
                              <div style={{ fontSize: "0.75rem", fontFamily: "var(--font-mono)" }}>
                                {evt.source_file}
                                {evt.line_number ? `:${evt.line_number}` : ""}
                                {evt.method_name ? ` (${evt.method_name})` : ""}
                              </div>
                            ) : (
                              <span className="text-muted">—</span>
                            )}
                          </td>
                        </tr>
                        {evt.stack_trace && (
                          <tr>
                            <td colSpan={7} style={{ padding: "0.25rem 0.75rem 0.75rem", background: "#f8fafc" }}>
                              <button
                                type="button"
                                className="btn btn-secondary btn-sm"
                                style={{ fontSize: "0.75rem", padding: "0.15rem 0.5rem" }}
                                onClick={() => toggleTrace(evt.id)}
                              >
                                {expandedTraces[evt.id] ? "Hide Stack Trace ▲" : "View Stack Trace ▼"}
                              </button>
                              {expandedTraces[evt.id] && (
                                <pre
                                  className="response-output"
                                  style={{
                                    marginTop: "0.5rem",
                                    fontSize: "0.75rem",
                                  }}
                                >
                                  {evt.stack_trace}
                                </pre>
                              )}
                            </td>
                          </tr>
                        )}
                      </React.Fragment>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </section>
      )}
    </div>
  );
};
