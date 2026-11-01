import React, { useState, useEffect, useCallback } from "react";
import type {
  IncidentDetail,
  IncidentRCAAnalysis,
  IncidentRecommendationListResponse,
  Investigation,
  InvestigationNote,
  InvestigationAction,
  RecommendationReview,
  VerificationStep,
  TimelineEvent,
  ActionType,
  RecommendationReviewDecision,
  VerificationStatus,
  RootCauseConfirmed,
} from "../services/api";
import {
  startInvestigation,
  fetchInvestigation,
  updateInvestigation,
  createInvestigationNote,
  fetchInvestigationNotes,
  createInvestigationAction,
  fetchInvestigationActions,
  reviewRecommendation,
  fetchRecommendationReviews,
  createVerificationStep,
  fetchVerificationSteps,
  updateVerificationStep,
  resolveIncident,
  reopenIncident,
  fetchIncidentTimeline,
} from "../services/api";

import { useAuth } from "../context/useAuth";

interface Props {
  incidentId: number;
  incident: IncidentDetail;
  rcaAnalysis: IncidentRCAAnalysis | null;
  recommendations: IncidentRecommendationListResponse | null;
  onIncidentUpdated: () => Promise<void>;
}

export const InvestigationWorkspace: React.FC<Props> = ({
  incidentId,
  incident,
  rcaAnalysis,
  recommendations,
  onIncidentUpdated,
}) => {
  const { user, isViewer } = useAuth();

  // Active Investigation
  const [investigation, setInvestigation] = useState<Investigation | null>(null);
  const [invLoading, setInvLoading] = useState<boolean>(true);
  const [invError, setInvError] = useState<string | null>(null);

  // Assignment form state
  const [assigneeId, setAssigneeId] = useState<string>(user?.username || "");
  const [assigneeName, setAssigneeName] = useState<string>(user?.username || "");
  const [isAssigning, setIsAssigning] = useState<boolean>(false);

  // Notes state
  const [notes, setNotes] = useState<InvestigationNote[]>([]);
  const [noteAuthor, setNoteAuthor] = useState<string>("");
  const [noteText, setNoteText] = useState<string>("");
  const [noteEvidence, setNoteEvidence] = useState<string>("");
  const [isSubmittingNote, setIsSubmittingNote] = useState<boolean>(false);
  const [noteError, setNoteError] = useState<string | null>(null);

  // Actions state
  const [actions, setActions] = useState<InvestigationAction[]>([]);
  const [actionType, setActionType] = useState<ActionType>("DIAGNOSTIC_CHECK");
  const [actionDesc, setActionDesc] = useState<string>("");
  const [actionPerformedBy, setActionPerformedBy] = useState<string>("");
  const [actionResult, setActionResult] = useState<string>("");
  const [actionEvidence, setActionEvidence] = useState<string>("");
  const [isSubmittingAction, setIsSubmittingAction] = useState<boolean>(false);
  const [actionError, setActionError] = useState<string | null>(null);

  // Recommendation Reviews state
  const [reviews, setReviews] = useState<Record<string, RecommendationReview>>({});
  const [reviewReasonInputs, setReviewReasonInputs] = useState<Record<string, string>>({});
  const [reviewerName, setReviewerName] = useState<string>("");
  const [reviewingRecId, setReviewingRecId] = useState<string | null>(null);
  const [reviewError, setReviewError] = useState<string | null>(null);

  // Verification Checklist state
  const [verificationSteps, setVerificationSteps] = useState<VerificationStep[]>([]);
  const [newStepTitle, setNewStepTitle] = useState<string>("");
  const [newStepDesc, setNewStepDesc] = useState<string>("");
  const [newStepRequired, setNewStepRequired] = useState<boolean>(true);
  const [newStepEvidence, setNewStepEvidence] = useState<string>("");
  const [isAddingStep, setIsAddingStep] = useState<boolean>(false);
  const [updatingStepId, setUpdatingStepId] = useState<number | null>(null);
  const [stepResultInputs, setStepResultInputs] = useState<Record<number, string>>({});
  const [verificationError, setVerificationError] = useState<string | null>(null);

  // Resolution state
  const [resolvedBy, setResolvedBy] = useState<string>("");
  const [resolutionSummary, setResolutionSummary] = useState<string>("");
  const [rootCauseConfirmed, setRootCauseConfirmed] = useState<RootCauseConfirmed>("CONFIRMED");
  const [isResolving, setIsResolving] = useState<boolean>(false);
  const [resolutionError, setResolutionError] = useState<string | null>(null);

  // Reopen state
  const [reopenedBy, setReopenedBy] = useState<string>("");
  const [reopenReason, setReopenReason] = useState<string>("");
  const [isReopening, setIsReopening] = useState<boolean>(false);
  const [reopenError, setReopenError] = useState<string | null>(null);

  // Timeline state
  const [timelineEvents, setTimelineEvents] = useState<TimelineEvent[]>([]);
  const [timelineLoading, setTimelineLoading] = useState<boolean>(false);

  // Load all workspace data
  const loadWorkspaceData = useCallback(async () => {
    setInvError(null);
    try {
      // 1. Fetch or initialize investigation
      let inv: Investigation;
      try {
        inv = await fetchInvestigation(incidentId);
      } catch {
        // Automatically initialize investigation workspace if none exists yet
        inv = await startInvestigation(incidentId, {});
      }
      setInvestigation(inv);
      if (inv.assigned_to) {
        setAssigneeId(inv.assigned_to);
        setAssigneeName(inv.assigned_to_name || "");
        setNoteAuthor((prev) => prev || inv.assigned_to_name || inv.assigned_to || user?.username || "");
        setActionPerformedBy((prev) => prev || inv.assigned_to_name || inv.assigned_to || user?.username || "");
        setReviewerName((prev) => prev || inv.assigned_to_name || inv.assigned_to || user?.username || "");
        setResolvedBy((prev) => prev || inv.assigned_to_name || inv.assigned_to || user?.username || "");
        setReopenedBy((prev) => prev || inv.assigned_to_name || inv.assigned_to || user?.username || "");
      } else if (user?.username) {
        setAssigneeId(user.username);
        setAssigneeName(user.username);
        setNoteAuthor(user.username);
        setActionPerformedBy(user.username);
        setReviewerName(user.username);
        setResolvedBy(user.username);
        setReopenedBy(user.username);
      }

      // 2. Fetch notes
      const notesData = await fetchInvestigationNotes(incidentId);
      setNotes(notesData.notes);

      // 3. Fetch actions
      const actionsData = await fetchInvestigationActions(incidentId);
      setActions(actionsData.actions);

      // 4. Fetch recommendation reviews
      const reviewsData = await fetchRecommendationReviews(incidentId);
      const revMap: Record<string, RecommendationReview> = {};
      reviewsData.reviews.forEach((r) => {
        revMap[r.recommendation_id] = r;
      });
      setReviews(revMap);

      // 5. Fetch verification steps
      const stepsData = await fetchVerificationSteps(incidentId);
      setVerificationSteps(stepsData.steps);

      // 6. Fetch timeline
      setTimelineLoading(true);
      const timelineData = await fetchIncidentTimeline(incidentId);
      setTimelineEvents(timelineData.events);
      setTimelineLoading(false);
    } catch (err: unknown) {
      setInvError(err instanceof Error ? err.message : "Failed to load investigation workspace");
    } finally {
      setInvLoading(false);
    }
  }, [incidentId, user]);

  useEffect(() => {
    const timer = setTimeout(() => {
      void loadWorkspaceData();
    }, 0);
    return () => clearTimeout(timer);
  }, [loadWorkspaceData]);

  // Handle assignment
  const handleAssignDeveloper = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!assigneeId.trim()) return;
    setIsAssigning(true);
    setInvError(null);
    try {
      const updated = await updateInvestigation(incidentId, {
        assigned_to: assigneeId.trim(),
        assigned_to_name: assigneeName.trim() || undefined,
        status: "INVESTIGATING",
      });
      setInvestigation(updated);
      await onIncidentUpdated();
      await loadWorkspaceData();
    } catch (err: unknown) {
      setInvError(err instanceof Error ? err.message : "Failed to update assignment");
    } finally {
      setIsAssigning(false);
    }
  };

  // Handle note submission
  const handleAddNote = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!noteText.trim()) return;
    setIsSubmittingNote(true);
    setNoteError(null);
    try {
      const evidenceList = noteEvidence
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean);

      await createInvestigationNote(incidentId, {
        author: noteAuthor.trim() || "developer",
        note: noteText.trim(),
        evidence_references: evidenceList.length ? evidenceList : undefined,
      });

      setNoteText("");
      setNoteEvidence("");
      await loadWorkspaceData();
    } catch (err: unknown) {
      setNoteError(err instanceof Error ? err.message : "Failed to add note");
    } finally {
      setIsSubmittingNote(false);
    }
  };

  // Handle action submission
  const handleAddAction = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!actionDesc.trim() || !actionResult.trim()) return;
    setIsSubmittingAction(true);
    setActionError(null);
    try {
      const evidenceList = actionEvidence
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean);

      await createInvestigationAction(incidentId, {
        action_type: actionType,
        description: actionDesc.trim(),
        performed_by: actionPerformedBy.trim() || "developer",
        result: actionResult.trim(),
        evidence_references: evidenceList.length ? evidenceList : undefined,
      });

      setActionDesc("");
      setActionResult("");
      setActionEvidence("");
      await loadWorkspaceData();
    } catch (err: unknown) {
      setActionError(err instanceof Error ? err.message : "Failed to record action");
    } finally {
      setIsSubmittingAction(false);
    }
  };

  // Handle recommendation review
  const handleReviewRecommendation = async (
    recId: string | number,
    decision: RecommendationReviewDecision,
  ) => {
    const reason = reviewReasonInputs[String(recId)] || "";
    if ((decision === "REJECTED" || decision === "DEFERRED") && !reason.trim()) {
      setReviewError(`Please enter a justification reason before marking recommendation as ${decision}.`);
      return;
    }
    setReviewingRecId(String(recId));
    setReviewError(null);
    try {
      const rev = await reviewRecommendation(incidentId, recId, {
        reviewed_by: reviewerName.trim() || "developer",
        decision: decision,
        reason: reason.trim() || undefined,
      });
      setReviews((prev) => ({ ...prev, [rev.recommendation_id]: rev }));
      await loadWorkspaceData();
    } catch (err: unknown) {
      setReviewError(err instanceof Error ? err.message : "Failed to review recommendation");
    } finally {
      setReviewingRecId(null);
    }
  };

  // Handle create verification step
  const handleAddVerificationStep = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newStepTitle.trim()) return;
    setIsAddingStep(true);
    setVerificationError(null);
    try {
      const evidenceList = newStepEvidence
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean);

      await createVerificationStep(incidentId, {
        title: newStepTitle.trim(),
        description: newStepDesc.trim() || undefined,
        is_required: newStepRequired,
        evidence_references: evidenceList.length ? evidenceList : undefined,
      });

      setNewStepTitle("");
      setNewStepDesc("");
      setNewStepEvidence("");
      await loadWorkspaceData();
    } catch (err: unknown) {
      setVerificationError(err instanceof Error ? err.message : "Failed to create verification step");
    } finally {
      setIsAddingStep(false);
    }
  };

  // Handle update verification step status
  const handleUpdateVerificationStep = async (stepId: number, status: VerificationStatus) => {
    setUpdatingStepId(stepId);
    setVerificationError(null);
    try {
      const resultText = stepResultInputs[stepId] || (status === "PASSED" ? "Verified successfully" : "");
      await updateVerificationStep(incidentId, stepId, {
        status: status,
        result: resultText || undefined,
        verified_by: assigneeName || assigneeId || "developer",
      });
      await loadWorkspaceData();
    } catch (err: unknown) {
      setVerificationError(err instanceof Error ? err.message : "Failed to update verification step");
    } finally {
      setUpdatingStepId(null);
    }
  };

  // Handle incident resolution
  const handleResolveIncident = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!resolutionSummary.trim()) {
      setResolutionError("A resolution summary is required before resolving the incident.");
      return;
    }
    setIsResolving(true);
    setResolutionError(null);
    try {
      await resolveIncident(incidentId, {
        resolved_by: resolvedBy.trim() || "developer",
        resolution_summary: resolutionSummary.trim(),
        root_cause_confirmed: rootCauseConfirmed,
      });
      await onIncidentUpdated();
      await loadWorkspaceData();
    } catch (err: unknown) {
      setResolutionError(err instanceof Error ? err.message : "Resolution failed");
    } finally {
      setIsResolving(false);
    }
  };

  // Handle incident reopen
  const handleReopenIncident = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!reopenReason.trim()) {
      setReopenError("A reason is required to reopen the incident.");
      return;
    }
    setIsReopening(true);
    setReopenError(null);
    try {
      await reopenIncident(incidentId, {
        reopened_by: reopenedBy.trim() || "developer",
        reason: reopenReason.trim(),
      });
      setReopenReason("");
      await onIncidentUpdated();
      await loadWorkspaceData();
    } catch (err: unknown) {
      setReopenError(err instanceof Error ? err.message : "Failed to reopen incident");
    } finally {
      setIsReopening(false);
    }
  };

  // Compute verification stats
  const requiredSteps = verificationSteps.filter((s) => s.is_required);
  const passedRequiredSteps = requiredSteps.filter((s) => s.status === "PASSED");
  const pendingRequiredSteps = requiredSteps.filter((s) => s.status === "PENDING");
  const failedRequiredSteps = requiredSteps.filter((s) => s.status === "FAILED");
  const canResolve =
    requiredSteps.length > 0 &&
    pendingRequiredSteps.length === 0 &&
    failedRequiredSteps.length === 0;

  // Extract all valid evidence tokens for easy helper tags
  const validEvidenceTokens: string[] = [];
  incident.events.forEach((ev) => {
    validEvidenceTokens.push(`EVT-${ev.event_index}`);
    if (ev.exception_type) validEvidenceTokens.push(`EXC-${ev.event_index}`);
    if (ev.stack_trace) validEvidenceTokens.push(`ST-${ev.event_index}`);
  });
  if (rcaAnalysis?.analysis_id) validEvidenceTokens.push(rcaAnalysis.analysis_id);
  recommendations?.recommendations.forEach((r) => {
    validEvidenceTokens.push(r.recommendation_id);
  });
  const uniqueEvidenceTokens = Array.from(new Set(validEvidenceTokens));

  const formatTime = (ts: string | null | undefined) => {
    if (!ts) return "—";
    try {
      return new Date(ts).toLocaleString();
    } catch {
      return ts;
    }
  };

  const getDecisionBadge = (decision: RecommendationReviewDecision) => {
    let bg = "#e2e8f0";
    let color = "#334155";
    if (decision === "ACCEPTED") {
      bg = "#dcfce7";
      color = "#15803d";
    } else if (decision === "REJECTED") {
      bg = "#fee2e2";
      color = "#b91c1c";
    } else if (decision === "DEFERRED") {
      bg = "#fef3c7";
      color = "#b45309";
    }
    return (
      <span
        style={{
          display: "inline-block",
          fontSize: "0.75rem",
          fontWeight: 700,
          padding: "0.2rem 0.5rem",
          borderRadius: "4px",
          backgroundColor: bg,
          color: color,
        }}
      >
        {decision}
      </span>
    );
  };

  const getVerificationStatusBadge = (status: VerificationStatus) => {
    let bg = "#f1f5f9";
    let color = "#475569";
    if (status === "PASSED") {
      bg = "#dcfce7";
      color = "#15803d";
    } else if (status === "FAILED") {
      bg = "#fee2e2";
      color = "#b91c1c";
    } else if (status === "PENDING") {
      bg = "#fef3c7";
      color = "#b45309";
    }
    return (
      <span
        style={{
          display: "inline-block",
          fontSize: "0.75rem",
          fontWeight: 700,
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

  return (
    <div
      style={{
        marginTop: "2rem",
        borderTop: "2px solid #e2e8f0",
        paddingTop: "1.5rem",
      }}
    >
      {/* Workspace Header */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: "1rem",
          marginBottom: "1.25rem",
        }}
      >
        <div>
          <h3
            style={{
              margin: 0,
              fontSize: "1.25rem",
              fontWeight: 700,
              display: "flex",
              alignItems: "center",
              gap: "0.6rem",
              color: "var(--text-primary)",
            }}
          >
            <span>🛠️ Developer Investigation Workspace</span>
            <span className="phase-tag">Phase 7</span>
          </h3>
          <p
            style={{
              margin: "0.3rem 0 0",
              fontSize: "0.825rem",
              color: "var(--text-secondary)",
            }}
          >
            Human-in-the-loop triage, diagnostic tracking, recommendation decisions, and verified resolution.
            <strong style={{ marginLeft: "0.4rem", color: "#b45309" }}>
              RECOMMENDATION ≠ EXECUTION: The system does NOT execute commands automatically.
            </strong>
          </p>
        </div>

        {/* Current Investigation Status Badge */}
        {investigation && (
          <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
            <span style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>Workspace Status:</span>
            <span
              style={{
                fontSize: "0.85rem",
                fontWeight: 700,
                padding: "0.25rem 0.75rem",
                borderRadius: "6px",
                background: investigation.status === "RESOLVED" ? "#dcfce7" : "#eff6ff",
                color: investigation.status === "RESOLVED" ? "#15803d" : "#1d4ed8",
                border: "1px solid",
                borderColor: investigation.status === "RESOLVED" ? "#bbf7d0" : "#bfdbfe",
              }}
            >
              {investigation.status}
            </span>
          </div>
        )}
      </div>

      {invError && (
        <div className="alert alert-error" style={{ marginBottom: "1rem" }}>
          <strong>Error:</strong> {invError}
        </div>
      )}

      {isViewer && (
        <div className="alert alert-warning" style={{ marginBottom: "1rem", borderLeft: "4px solid #f59e0b" }}>
          👁️ <strong>Read-Only Mode:</strong> You are authenticated as a <strong>VIEWER</strong>. Investigation actions, reviews, and resolution are reserved for DEVELOPER and ADMIN accounts.
        </div>
      )}

      {invLoading && !investigation ? (
        <div style={{ padding: "2rem", textAlign: "center", color: "var(--text-muted)" }}>
          Loading investigation workspace...
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
          {/* =========================================================================
              SECTION 1: Incident Assignment & Investigation Ownership
             ========================================================================= */}
          <div
            className="context-card"
            style={{
              padding: "1rem",
              background: "#ffffff",
              border: "1px solid #e2e8f0",
              borderRadius: "8px",
            }}
          >
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                marginBottom: "0.75rem",
              }}
            >
              <h4 style={{ margin: 0, fontSize: "0.95rem", fontWeight: 700 }}>
                1. Incident Assignment & Investigation Ownership
              </h4>
              <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
                Started: {formatTime(investigation?.started_at)}
              </span>
            </div>

            <form
              onSubmit={handleAssignDeveloper}
              style={{
                display: "flex",
                gap: "0.75rem",
                flexWrap: "wrap",
                alignItems: "flex-end",
              }}
            >
              <div style={{ flex: "1 1 180px" }}>
                <label style={{ display: "block", fontSize: "0.75rem", fontWeight: 600, marginBottom: "0.2rem" }}>
                  Developer Identifier (e.g. dev-sarah)
                </label>
                <input
                  type="text"
                  className="input-field"
                  style={{ width: "100%", padding: "0.4rem 0.6rem", fontSize: "0.85rem" }}
                  placeholder="dev-username"
                  value={assigneeId}
                  onChange={(e) => setAssigneeId(e.target.value)}
                  required
                />
              </div>

              <div style={{ flex: "1 1 220px" }}>
                <label style={{ display: "block", fontSize: "0.75rem", fontWeight: 600, marginBottom: "0.2rem" }}>
                  Display Name (optional)
                </label>
                <input
                  type="text"
                  className="input-field"
                  style={{ width: "100%", padding: "0.4rem 0.6rem", fontSize: "0.85rem" }}
                  placeholder="Sarah Chen"
                  value={assigneeName}
                  onChange={(e) => setAssigneeName(e.target.value)}
                />
              </div>

              <button
                type="submit"
                className="btn btn-primary btn-sm"
                disabled={isAssigning || !assigneeId.trim()}
                style={{ height: "34px", padding: "0 1rem" }}
              >
                {isAssigning ? "Saving..." : investigation?.assigned_to ? "Reassign Ownership" : "Assign Incident"}
              </button>
            </form>

            {investigation?.assigned_to && (
              <div
                style={{
                  marginTop: "0.75rem",
                  fontSize: "0.8rem",
                  color: "#1e293b",
                  background: "#f8fafc",
                  padding: "0.5rem 0.75rem",
                  borderRadius: "4px",
                  borderLeft: "3px solid #3b82f6",
                }}
              >
                Currently assigned to: <strong>{investigation.assigned_to_name || investigation.assigned_to}</strong>{" "}
                (<code>{investigation.assigned_to}</code>) &bull; Assigned at: {formatTime(investigation.assigned_at)}
              </div>
            )}
          </div>

          {/* =========================================================================
              SECTION 4: Recommendation Review & Decision Tracking
             ========================================================================= */}
          <div
            className="context-card"
            style={{
              padding: "1rem",
              background: "#ffffff",
              border: "1px solid #e2e8f0",
              borderRadius: "8px",
            }}
          >
            <div style={{ marginBottom: "0.75rem" }}>
              <h4 style={{ margin: 0, fontSize: "0.95rem", fontWeight: 700 }}>
                2. Phase 6 Recommendation Review & Decision Tracking
              </h4>
              <p style={{ margin: "0.2rem 0 0", fontSize: "0.775rem", color: "var(--text-secondary)" }}>
                Developers decide and record decisions on AI recommendations. Original recommendations remain immutable.
              </p>
            </div>

            {reviewError && (
              <div className="alert alert-error" style={{ marginBottom: "0.75rem" }}>
                {reviewError}
              </div>
            )}

            {!recommendations || recommendations.recommendations.length === 0 ? (
              <p className="text-muted" style={{ fontSize: "0.85rem", fontStyle: "italic" }}>
                No Phase 6 recommendations have been generated for this incident yet.
              </p>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
                {recommendations.recommendations.map((rec) => {
                  const currentReview = reviews[rec.recommendation_id];
                  const reasonVal = reviewReasonInputs[rec.recommendation_id] ?? "";

                  return (
                    <div
                      key={rec.recommendation_id}
                      style={{
                        padding: "0.75rem",
                        border: "1px solid #e2e8f0",
                        borderRadius: "6px",
                        background: currentReview ? "#fafafa" : "#ffffff",
                      }}
                    >
                      <div
                        style={{
                          display: "flex",
                          justifyContent: "space-between",
                          alignItems: "flex-start",
                          gap: "0.5rem",
                          flexWrap: "wrap",
                          marginBottom: "0.4rem",
                        }}
                      >
                        <div>
                          <span style={{ fontWeight: 700, fontSize: "0.9rem", marginRight: "0.5rem" }}>
                            {rec.title}
                          </span>
                          <span style={{ fontSize: "0.75rem", color: "var(--text-muted)", fontFamily: "var(--font-mono)" }}>
                            ({rec.recommendation_id})
                          </span>
                        </div>
                        {currentReview && (
                          <div style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}>
                            <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>Decision:</span>
                            {getDecisionBadge(currentReview.decision)}
                          </div>
                        )}
                      </div>

                      <div style={{ fontSize: "0.8rem", color: "var(--text-secondary)", marginBottom: "0.4rem" }}>
                        <strong>Rationale:</strong> {rec.rationale}
                      </div>

                      {rec.supporting_evidence?.length > 0 && (
                        <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginBottom: "0.4rem" }}>
                          Supporting Evidence:{" "}
                          {rec.supporting_evidence.map((ev) => (
                            <code key={ev} style={{ marginRight: "0.3rem", background: "#f1f5f9", padding: "0.1rem 0.3rem" }}>
                              {ev}
                            </code>
                          ))}
                        </div>
                      )}

                      {/* Review Details if already reviewed */}
                      {currentReview && (
                        <div
                          style={{
                            background: "#f0fdf4",
                            border: "1px solid #bbf7d0",
                            borderRadius: "4px",
                            padding: "0.4rem 0.6rem",
                            fontSize: "0.775rem",
                            marginBottom: "0.5rem",
                            color: "#166534",
                          }}
                        >
                          Reviewed by <strong>{currentReview.reviewed_by}</strong> on{" "}
                          {formatTime(currentReview.created_at)}
                          {currentReview.reason && <span> &bull; Reason: &ldquo;{currentReview.reason}&rdquo;</span>}
                        </div>
                      )}

                      {/* Decision Controls */}
                      <div
                        style={{
                          display: "flex",
                          gap: "0.5rem",
                          alignItems: "center",
                          flexWrap: "wrap",
                          paddingTop: "0.4rem",
                          borderTop: "1px dashed #e2e8f0",
                        }}
                      >
                        <input
                          type="text"
                          placeholder="Reason / justification (required for reject/defer)..."
                          className="input-field"
                          style={{ flex: "1 1 240px", fontSize: "0.775rem", padding: "0.25rem 0.5rem" }}
                          value={reasonVal}
                          onChange={(e) =>
                            setReviewReasonInputs((prev) => ({
                              ...prev,
                              [rec.recommendation_id]: e.target.value,
                            }))
                          }
                        />

                        <button
                          type="button"
                          className="btn btn-secondary btn-sm"
                          style={{ fontSize: "0.75rem", color: "#15803d", borderColor: "#86efac" }}
                          disabled={reviewingRecId === rec.recommendation_id}
                          onClick={() => handleReviewRecommendation(rec.recommendation_id, "ACCEPTED")}
                        >
                          ✓ Accept
                        </button>
                        <button
                          type="button"
                          className="btn btn-secondary btn-sm"
                          style={{ fontSize: "0.75rem", color: "#b91c1c", borderColor: "#fca5a5" }}
                          disabled={reviewingRecId === rec.recommendation_id}
                          onClick={() => handleReviewRecommendation(rec.recommendation_id, "REJECTED")}
                        >
                          ✕ Reject
                        </button>
                        <button
                          type="button"
                          className="btn btn-secondary btn-sm"
                          style={{ fontSize: "0.75rem", color: "#b45309", borderColor: "#fde68a" }}
                          disabled={reviewingRecId === rec.recommendation_id}
                          onClick={() => handleReviewRecommendation(rec.recommendation_id, "DEFERRED")}
                        >
                          ⏳ Defer
                        </button>
                        <button
                          type="button"
                          className="btn btn-secondary btn-sm"
                          style={{ fontSize: "0.75rem", color: "#475569" }}
                          disabled={reviewingRecId === rec.recommendation_id}
                          onClick={() => handleReviewRecommendation(rec.recommendation_id, "NOT_APPLICABLE")}
                        >
                          N/A
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* =========================================================================
              SECTION 5 & 6: Investigation Notes & External Investigation Actions
             ========================================================================= */}
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(400px, 1fr))",
              gap: "1.25rem",
            }}
          >
            {/* Notes Column */}
            <div
              className="context-card"
              style={{
                padding: "1rem",
                background: "#ffffff",
                border: "1px solid #e2e8f0",
                borderRadius: "8px",
              }}
            >
              <h4 style={{ margin: "0 0 0.5rem", fontSize: "0.95rem", fontWeight: 700 }}>
                3. Investigation Notes ({notes.length})
              </h4>
              <p style={{ margin: "0 0 0.75rem", fontSize: "0.775rem", color: "var(--text-secondary)" }}>
                Persistent developer triage notes. Reference real evidence tokens.
              </p>

              {noteError && (
                <div className="alert alert-error" style={{ marginBottom: "0.75rem" }}>
                  {noteError}
                </div>
              )}

              {/* Note input form */}
              <form onSubmit={handleAddNote} style={{ marginBottom: "1rem" }}>
                <div style={{ marginBottom: "0.5rem" }}>
                  <textarea
                    rows={3}
                    className="input-field"
                    style={{ width: "100%", padding: "0.4rem 0.6rem", fontSize: "0.825rem" }}
                    placeholder="E.g., Checked application logs around 14:02. Connection pool spike confirmed."
                    value={noteText}
                    onChange={(e) => setNoteText(e.target.value)}
                    required
                  />
                </div>
                <div style={{ display: "flex", gap: "0.5rem", marginBottom: "0.5rem" }}>
                  <input
                    type="text"
                    className="input-field"
                    style={{ flex: 1, fontSize: "0.75rem", padding: "0.3rem 0.5rem" }}
                    placeholder="Evidence references (e.g. EVT-1, EXC-1)"
                    value={noteEvidence}
                    onChange={(e) => setNoteEvidence(e.target.value)}
                  />
                  <input
                    type="text"
                    className="input-field"
                    style={{ width: "130px", fontSize: "0.75rem", padding: "0.3rem 0.5rem" }}
                    placeholder="Author"
                    value={noteAuthor}
                    onChange={(e) => setNoteAuthor(e.target.value)}
                  />
                </div>
                <button
                  type="submit"
                  className="btn btn-primary btn-sm"
                  disabled={isSubmittingNote || !noteText.trim()}
                  style={{ width: "100%" }}
                >
                  {isSubmittingNote ? "Saving Note..." : "+ Add Investigation Note"}
                </button>
              </form>

              {/* Notes list */}
              <div style={{ maxHeight: "280px", overflowY: "auto", display: "flex", flexDirection: "column", gap: "0.5rem" }}>
                {notes.length === 0 ? (
                  <p className="text-muted" style={{ fontSize: "0.8rem", fontStyle: "italic", margin: 0 }}>
                    No notes recorded yet.
                  </p>
                ) : (
                  notes.map((n) => (
                    <div
                      key={n.id}
                      style={{
                        padding: "0.6rem",
                        background: "#f8fafc",
                        border: "1px solid #e2e8f0",
                        borderRadius: "4px",
                        fontSize: "0.8rem",
                      }}
                    >
                      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "0.2rem" }}>
                        <strong style={{ color: "#1e293b" }}>{n.author}</strong>
                        <span style={{ fontSize: "0.7rem", color: "var(--text-muted)" }}>{formatTime(n.created_at)}</span>
                      </div>
                      <div style={{ color: "#334155", whiteSpace: "pre-wrap" }}>{n.note}</div>
                      {n.evidence_references?.length > 0 && (
                        <div style={{ marginTop: "0.3rem", fontSize: "0.7rem" }}>
                          {n.evidence_references.map((ev) => (
                            <code key={ev} style={{ marginRight: "0.25rem", background: "#e2e8f0", padding: "0.1rem 0.25rem" }}>
                              {ev}
                            </code>
                          ))}
                        </div>
                      )}
                    </div>
                  ))
                )}
              </div>
            </div>

            {/* Actions Column */}
            <div
              className="context-card"
              style={{
                padding: "1rem",
                background: "#ffffff",
                border: "1px solid #e2e8f0",
                borderRadius: "8px",
              }}
            >
              <h4 style={{ margin: "0 0 0.5rem", fontSize: "0.95rem", fontWeight: 700 }}>
                4. External Investigation Actions ({actions.length})
              </h4>
              <p style={{ margin: "0 0 0.75rem", fontSize: "0.775rem", color: "var(--text-secondary)" }}>
                Record external diagnostic checks or fixes performed by the developer.
              </p>

              {actionError && (
                <div className="alert alert-error" style={{ marginBottom: "0.75rem" }}>
                  {actionError}
                </div>
              )}

              {/* Action input form */}
              <form onSubmit={handleAddAction} style={{ marginBottom: "1rem" }}>
                <div style={{ display: "flex", gap: "0.5rem", marginBottom: "0.4rem" }}>
                  <select
                    className="input-field"
                    style={{ flex: 1, fontSize: "0.75rem", padding: "0.3rem 0.5rem" }}
                    value={actionType}
                    onChange={(e) => setActionType(e.target.value as ActionType)}
                  >
                    <option value="DIAGNOSTIC_CHECK">DIAGNOSTIC_CHECK</option>
                    <option value="LOG_REVIEW">LOG_REVIEW</option>
                    <option value="METRIC_REVIEW">METRIC_REVIEW</option>
                    <option value="CONFIG_REVIEW">CONFIG_REVIEW</option>
                    <option value="DEPENDENCY_CHECK">DEPENDENCY_CHECK</option>
                    <option value="OBSERVATION">OBSERVATION</option>
                    <option value="FIX_APPLIED">FIX_APPLIED</option>
                    <option value="VERIFICATION">VERIFICATION</option>
                    <option value="OTHER">OTHER</option>
                  </select>
                  <input
                    type="text"
                    className="input-field"
                    style={{ width: "130px", fontSize: "0.75rem", padding: "0.3rem 0.5rem" }}
                    placeholder="Performed by"
                    value={actionPerformedBy}
                    onChange={(e) => setActionPerformedBy(e.target.value)}
                  />
                </div>

                <div style={{ marginBottom: "0.4rem" }}>
                  <input
                    type="text"
                    className="input-field"
                    style={{ width: "100%", fontSize: "0.8rem", padding: "0.35rem 0.5rem" }}
                    placeholder="Action description (e.g. Checked RDS pool metric)..."
                    value={actionDesc}
                    onChange={(e) => setActionDesc(e.target.value)}
                    required
                  />
                </div>

                <div style={{ marginBottom: "0.4rem" }}>
                  <input
                    type="text"
                    className="input-field"
                    style={{ width: "100%", fontSize: "0.8rem", padding: "0.35rem 0.5rem" }}
                    placeholder="Observed outcome / result (e.g. Pool saturation confirmed)..."
                    value={actionResult}
                    onChange={(e) => setActionResult(e.target.value)}
                    required
                  />
                </div>

                <div style={{ display: "flex", gap: "0.5rem", marginBottom: "0.5rem" }}>
                  <input
                    type="text"
                    className="input-field"
                    style={{ flex: 1, fontSize: "0.75rem", padding: "0.3rem 0.5rem" }}
                    placeholder="Evidence references (e.g. EVT-1, EXC-1)"
                    value={actionEvidence}
                    onChange={(e) => setActionEvidence(e.target.value)}
                  />
                </div>

                <button
                  type="submit"
                  className="btn btn-primary btn-sm"
                  disabled={isSubmittingAction || !actionDesc.trim() || !actionResult.trim()}
                  style={{ width: "100%" }}
                >
                  {isSubmittingAction ? "Recording Action..." : "+ Record Investigation Action"}
                </button>
              </form>

              {/* Actions list */}
              <div style={{ maxHeight: "240px", overflowY: "auto", display: "flex", flexDirection: "column", gap: "0.5rem" }}>
                {actions.length === 0 ? (
                  <p className="text-muted" style={{ fontSize: "0.8rem", fontStyle: "italic", margin: 0 }}>
                    No investigation actions recorded yet.
                  </p>
                ) : (
                  actions.map((act) => (
                    <div
                      key={act.id}
                      style={{
                        padding: "0.6rem",
                        background: "#f8fafc",
                        border: "1px solid #e2e8f0",
                        borderRadius: "4px",
                        fontSize: "0.8rem",
                      }}
                    >
                      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "0.2rem" }}>
                        <span
                          style={{
                            fontSize: "0.7rem",
                            fontWeight: 700,
                            padding: "0.1rem 0.35rem",
                            borderRadius: "3px",
                            background: "#e0e7ff",
                            color: "#3730a3",
                          }}
                        >
                          {act.action_type}
                        </span>
                        <span style={{ fontSize: "0.7rem", color: "var(--text-muted)" }}>
                          {act.performed_by} &bull; {formatTime(act.created_at)}
                        </span>
                      </div>
                      <div style={{ fontWeight: 600, color: "#1e293b" }}>{act.description}</div>
                      <div style={{ color: "#475569", fontSize: "0.775rem", marginTop: "0.15rem" }}>
                        <strong>Result:</strong> {act.result}
                      </div>
                      {act.evidence_references?.length > 0 && (
                        <div style={{ marginTop: "0.25rem", fontSize: "0.7rem" }}>
                          {act.evidence_references.map((ev) => (
                            <code key={ev} style={{ marginRight: "0.25rem", background: "#e2e8f0", padding: "0.1rem 0.25rem" }}>
                              {ev}
                            </code>
                          ))}
                        </div>
                      )}
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>

          {/* =========================================================================
              SECTION 7: Available Evidence References Helper
             ========================================================================= */}
          <div
            style={{
              padding: "0.75rem 1rem",
              background: "#f8fafc",
              border: "1px dashed #cbd5e1",
              borderRadius: "6px",
              fontSize: "0.775rem",
            }}
          >
            <div style={{ fontWeight: 600, marginBottom: "0.3rem", color: "#475569" }}>
              🔍 Ground-Truth Incident Evidence Tokens (Valid Reference Tokens):
            </div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: "0.35rem" }}>
              {uniqueEvidenceTokens.map((tok) => (
                <span
                  key={tok}
                  style={{
                    background: "#ffffff",
                    border: "1px solid #cbd5e1",
                    padding: "0.15rem 0.4rem",
                    borderRadius: "3px",
                    fontFamily: "var(--font-mono)",
                    color: "#0f172a",
                  }}
                >
                  {tok}
                </span>
              ))}
            </div>
          </div>

          {/* =========================================================================
              SECTION 8: Verification Checklist
             ========================================================================= */}
          <div
            className="context-card"
            style={{
              padding: "1rem",
              background: "#ffffff",
              border: "1px solid #e2e8f0",
              borderRadius: "8px",
            }}
          >
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                flexWrap: "wrap",
                gap: "0.5rem",
                marginBottom: "0.75rem",
              }}
            >
              <div>
                <h4 style={{ margin: 0, fontSize: "0.95rem", fontWeight: 700 }}>
                  5. Verification Checklist ({passedRequiredSteps.length}/{requiredSteps.length} required passed)
                </h4>
                <p style={{ margin: "0.2rem 0 0", fontSize: "0.775rem", color: "var(--text-secondary)" }}>
                  Resolution condition: ALL required verification steps must be explicitly marked PASSED with developer verification results.
                </p>
              </div>

              {/* Progress pill */}
              <div
                style={{
                  fontSize: "0.8rem",
                  fontWeight: 600,
                  padding: "0.25rem 0.6rem",
                  borderRadius: "20px",
                  background: canResolve ? "#dcfce7" : "#fef3c7",
                  color: canResolve ? "#15803d" : "#b45309",
                }}
              >
                {canResolve
                  ? "✓ Verification Complete"
                  : `${pendingRequiredSteps.length + failedRequiredSteps.length} required step(s) pending/failed`}
              </div>
            </div>

            {verificationError && (
              <div className="alert alert-error" style={{ marginBottom: "0.75rem" }}>
                {verificationError}
              </div>
            )}

            {/* Checklist items */}
            <div style={{ display: "flex", flexDirection: "column", gap: "0.6rem", marginBottom: "1rem" }}>
              {verificationSteps.length === 0 ? (
                <p className="text-muted" style={{ fontSize: "0.825rem", fontStyle: "italic", margin: 0 }}>
                  No verification steps defined. Add at least one required step before resolving.
                </p>
              ) : (
                verificationSteps.map((step) => {
                  const resultVal = stepResultInputs[step.id] ?? "";

                  return (
                    <div
                      key={step.id}
                      style={{
                        padding: "0.65rem 0.85rem",
                        border: "1px solid",
                        borderColor: step.status === "PASSED" ? "#bbf7d0" : step.status === "FAILED" ? "#fecaca" : "#e2e8f0",
                        borderRadius: "6px",
                        background: step.status === "PASSED" ? "#f0fdf4" : step.status === "FAILED" ? "#fef2f2" : "#ffffff",
                      }}
                    >
                      <div
                        style={{
                          display: "flex",
                          justifyContent: "space-between",
                          alignItems: "center",
                          flexWrap: "wrap",
                          gap: "0.5rem",
                          marginBottom: "0.25rem",
                        }}
                      >
                        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                          <span style={{ fontWeight: 600, fontSize: "0.875rem" }}>{step.title}</span>
                          {step.is_required && (
                            <span
                              style={{
                                fontSize: "0.65rem",
                                fontWeight: 700,
                                background: "#fee2e2",
                                color: "#b91c1c",
                                padding: "0.1rem 0.35rem",
                                borderRadius: "3px",
                              }}
                            >
                              REQUIRED
                            </span>
                          )}
                        </div>
                        {getVerificationStatusBadge(step.status)}
                      </div>

                      {step.description && (
                        <div style={{ fontSize: "0.8rem", color: "var(--text-secondary)", marginBottom: "0.3rem" }}>
                          {step.description}
                        </div>
                      )}

                      {step.result && (
                        <div style={{ fontSize: "0.775rem", color: "#1e293b", marginBottom: "0.3rem" }}>
                          <strong>Verification Result:</strong> {step.result}{" "}
                          <span style={{ color: "var(--text-muted)" }}>
                            (by {step.verified_by || "developer"} at {formatTime(step.verified_at)})
                          </span>
                        </div>
                      )}

                      {/* Status Update Controls */}
                      <div
                        style={{
                          display: "flex",
                          gap: "0.5rem",
                          alignItems: "center",
                          flexWrap: "wrap",
                          marginTop: "0.35rem",
                          paddingTop: "0.35rem",
                          borderTop: "1px dashed #e2e8f0",
                        }}
                      >
                        <input
                          type="text"
                          placeholder="Evidence / verification result note..."
                          className="input-field"
                          style={{ flex: 1, fontSize: "0.75rem", padding: "0.25rem 0.5rem" }}
                          value={resultVal}
                          onChange={(e) =>
                            setStepResultInputs((prev) => ({
                              ...prev,
                              [step.id]: e.target.value,
                            }))
                          }
                        />

                        <button
                          type="button"
                          className="btn btn-secondary btn-sm"
                          style={{ fontSize: "0.75rem", color: "#15803d", borderColor: "#86efac" }}
                          disabled={updatingStepId === step.id}
                          onClick={() => handleUpdateVerificationStep(step.id, "PASSED")}
                        >
                          ✓ Mark Passed
                        </button>
                        <button
                          type="button"
                          className="btn btn-secondary btn-sm"
                          style={{ fontSize: "0.75rem", color: "#b91c1c", borderColor: "#fca5a5" }}
                          disabled={updatingStepId === step.id}
                          onClick={() => handleUpdateVerificationStep(step.id, "FAILED")}
                        >
                          ✕ Mark Failed
                        </button>
                        <button
                          type="button"
                          className="btn btn-secondary btn-sm"
                          style={{ fontSize: "0.75rem", color: "#475569" }}
                          disabled={updatingStepId === step.id}
                          onClick={() => handleUpdateVerificationStep(step.id, "NOT_APPLICABLE")}
                        >
                          N/A
                        </button>
                      </div>
                    </div>
                  );
                })
              )}
            </div>

            {/* Add Step Form */}
            <form
              onSubmit={handleAddVerificationStep}
              style={{
                display: "flex",
                gap: "0.5rem",
                flexWrap: "wrap",
                alignItems: "flex-end",
                background: "#f8fafc",
                padding: "0.75rem",
                borderRadius: "6px",
              }}
            >
              <div style={{ flex: "2 1 200px" }}>
                <label style={{ display: "block", fontSize: "0.75rem", fontWeight: 600, marginBottom: "0.2rem" }}>
                  Verification Step Title
                </label>
                <input
                  type="text"
                  className="input-field"
                  style={{ width: "100%", fontSize: "0.8rem", padding: "0.35rem 0.5rem" }}
                  placeholder="E.g., Confirm service health endpoint is healthy"
                  value={newStepTitle}
                  onChange={(e) => setNewStepTitle(e.target.value)}
                  required
                />
              </div>

              <div style={{ flex: "1 1 150px" }}>
                <label style={{ display: "block", fontSize: "0.75rem", fontWeight: 600, marginBottom: "0.2rem" }}>
                  Evidence References
                </label>
                <input
                  type="text"
                  className="input-field"
                  style={{ width: "100%", fontSize: "0.8rem", padding: "0.35rem 0.5rem" }}
                  placeholder="EVT-1, EXC-1"
                  value={newStepEvidence}
                  onChange={(e) => setNewStepEvidence(e.target.value)}
                />
              </div>

              <div style={{ display: "flex", alignItems: "center", gap: "0.4rem", height: "32px", padding: "0 0.5rem" }}>
                <input
                  type="checkbox"
                  id="reqCheck"
                  checked={newStepRequired}
                  onChange={(e) => setNewStepRequired(e.target.checked)}
                />
                <label htmlFor="reqCheck" style={{ fontSize: "0.75rem", fontWeight: 600, cursor: "pointer" }}>
                  Required
                </label>
              </div>

              <button
                type="submit"
                className="btn btn-secondary btn-sm"
                disabled={isAddingStep || !newStepTitle.trim()}
                style={{ height: "32px", fontSize: "0.8rem" }}
              >
                {isAddingStep ? "Adding..." : "+ Add Step"}
              </button>
            </form>
          </div>

          {/* =========================================================================
              SECTION 9: Resolution & Reopen Workflow
             ========================================================================= */}
          <div
            className="context-card"
            style={{
              padding: "1rem",
              background: "#ffffff",
              border: "1px solid #e2e8f0",
              borderRadius: "8px",
            }}
          >
            <h4 style={{ margin: "0 0 0.5rem", fontSize: "0.95rem", fontWeight: 700 }}>
              6. Incident Resolution & Reopen Management
            </h4>

            {incident.status === "RESOLVED" ? (
              /* Already Resolved View */
              <div
                style={{
                  background: "#f0fdf4",
                  border: "1px solid #bbf7d0",
                  borderRadius: "6px",
                  padding: "1rem",
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.5rem" }}>
                  <span style={{ fontWeight: 700, color: "#166534", fontSize: "1rem" }}>
                    ✓ Incident Resolved
                  </span>
                  <span style={{ fontSize: "0.775rem", color: "#15803d" }}>
                    Resolved at: {formatTime(incident.resolved_at)} by <strong>{incident.resolved_by}</strong>
                  </span>
                </div>

                <div style={{ fontSize: "0.85rem", color: "#1e293b", marginBottom: "0.5rem" }}>
                  <strong>Resolution Summary:</strong> {incident.resolution_summary}
                </div>

                <div style={{ fontSize: "0.8rem", color: "#475569", marginBottom: "1rem" }}>
                  Root Cause Confirmed:{" "}
                  <strong>{incident.root_cause_confirmed || "UNKNOWN"}</strong>
                </div>

                {/* Reopen form */}
                {reopenError && (
                  <div className="alert alert-error" style={{ marginBottom: "0.75rem" }}>
                    {reopenError}
                  </div>
                )}

                <form
                  onSubmit={handleReopenIncident}
                  style={{
                    display: "flex",
                    gap: "0.75rem",
                    flexWrap: "wrap",
                    alignItems: "flex-end",
                    borderTop: "1px dashed #bbf7d0",
                    paddingTop: "0.75rem",
                  }}
                >
                  <div style={{ flex: "2 1 300px" }}>
                    <label style={{ display: "block", fontSize: "0.75rem", fontWeight: 600, color: "#166534", marginBottom: "0.2rem" }}>
                      Reopen Reason (Required if incident resurfaces)
                    </label>
                    <input
                      type="text"
                      className="input-field"
                      style={{ width: "100%", fontSize: "0.8rem", padding: "0.35rem 0.5rem" }}
                      placeholder="E.g., Connection timeouts resurfaced during peak load"
                      value={reopenReason}
                      onChange={(e) => setReopenReason(e.target.value)}
                      required
                    />
                  </div>

                  <div style={{ flex: "1 1 150px" }}>
                    <label style={{ display: "block", fontSize: "0.75rem", fontWeight: 600, color: "#166534", marginBottom: "0.2rem" }}>
                      Reopened By
                    </label>
                    <input
                      type="text"
                      className="input-field"
                      style={{ width: "100%", fontSize: "0.8rem", padding: "0.35rem 0.5rem" }}
                      placeholder="Sarah Chen"
                      value={reopenedBy}
                      onChange={(e) => setReopenedBy(e.target.value)}
                    />
                  </div>

                  <button
                    type="submit"
                    className="btn btn-secondary btn-sm"
                    style={{ height: "32px", color: "#b91c1c", borderColor: "#fca5a5" }}
                    disabled={isReopening || !reopenReason.trim()}
                  >
                    {isReopening ? "Reopening..." : "↺ Reopen Incident"}
                  </button>
                </form>
              </div>
            ) : (
              /* Resolution Input Form */
              <div>
                <p style={{ margin: "0 0 0.75rem", fontSize: "0.775rem", color: "var(--text-secondary)" }}>
                  Enter developer-verified resolution summary and indicate root cause confirmation.
                </p>

                {resolutionError && (
                  <div className="alert alert-error" style={{ marginBottom: "0.75rem" }}>
                    {resolutionError}
                  </div>
                )}

                <form onSubmit={handleResolveIncident}>
                  <div style={{ marginBottom: "0.5rem" }}>
                    <label style={{ display: "block", fontSize: "0.75rem", fontWeight: 600, marginBottom: "0.2rem" }}>
                      Resolution Summary (Required)
                    </label>
                    <textarea
                      rows={3}
                      className="input-field"
                      style={{ width: "100%", padding: "0.4rem 0.6rem", fontSize: "0.825rem" }}
                      placeholder="E.g., Scaled connection pool from 20 to 100. Latency normalized and downstream error rate dropped to 0%."
                      value={resolutionSummary}
                      onChange={(e) => setResolutionSummary(e.target.value)}
                      required
                    />
                  </div>

                  <div
                    style={{
                      display: "flex",
                      gap: "1.25rem",
                      alignItems: "center",
                      flexWrap: "wrap",
                      marginBottom: "0.75rem",
                    }}
                  >
                    <div>
                      <label style={{ display: "block", fontSize: "0.75rem", fontWeight: 600, marginBottom: "0.2rem" }}>
                        Root Cause Confirmed by Developer?
                      </label>
                      <div style={{ display: "flex", gap: "0.5rem" }}>
                        {(["CONFIRMED", "REFUTED", "UNKNOWN"] as RootCauseConfirmed[]).map((opt) => (
                          <label key={opt} style={{ fontSize: "0.8rem", display: "flex", alignItems: "center", gap: "0.25rem", cursor: "pointer" }}>
                            <input
                              type="radio"
                              name="rcConfirmed"
                              value={opt}
                              checked={rootCauseConfirmed === opt}
                              onChange={() => setRootCauseConfirmed(opt)}
                            />
                            {opt}
                          </label>
                        ))}
                      </div>
                    </div>

                    <div style={{ flex: "1 1 180px" }}>
                      <label style={{ display: "block", fontSize: "0.75rem", fontWeight: 600, marginBottom: "0.2rem" }}>
                        Resolved By
                      </label>
                      <input
                        type="text"
                        className="input-field"
                        style={{ width: "100%", fontSize: "0.8rem", padding: "0.35rem 0.5rem" }}
                        placeholder="Sarah Chen"
                        value={resolvedBy}
                        onChange={(e) => setResolvedBy(e.target.value)}
                        required
                      />
                    </div>
                  </div>

                  <button
                    type="submit"
                    className="btn btn-primary"
                    style={{ width: "100%", padding: "0.6rem", fontWeight: 700 }}
                    disabled={isResolving || !resolutionSummary.trim() || !canResolve}
                    title={
                      !canResolve
                        ? "Cannot resolve: all required verification steps must be marked PASSED"
                        : "Resolve incident"
                    }
                  >
                    {isResolving ? "Resolving Incident..." : "✓ Resolve Incident"}
                  </button>

                  {!canResolve && (
                    <div style={{ marginTop: "0.4rem", fontSize: "0.75rem", color: "#b45309", textAlign: "center" }}>
                      Resolution disabled until all required verification checklist items pass.
                    </div>
                  )}
                </form>
              </div>
            )}
          </div>

          {/* =========================================================================
              SECTION 10: Investigation Audit Timeline
             ========================================================================= */}
          <div
            className="context-card"
            style={{
              padding: "1rem",
              background: "#ffffff",
              border: "1px solid #e2e8f0",
              borderRadius: "8px",
            }}
          >
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                marginBottom: "0.75rem",
              }}
            >
              <h4 style={{ margin: 0, fontSize: "0.95rem", fontWeight: 700 }}>
                7. Investigation Audit Timeline ({timelineEvents.length} events)
              </h4>
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                style={{ fontSize: "0.75rem", padding: "0.2rem 0.5rem" }}
                onClick={loadWorkspaceData}
                disabled={timelineLoading}
              >
                {timelineLoading ? "Refreshing..." : "↻ Refresh"}
              </button>
            </div>

            <div style={{ maxHeight: "300px", overflowY: "auto", display: "flex", flexDirection: "column", gap: "0.5rem" }}>
              {timelineEvents.length === 0 ? (
                <p className="text-muted" style={{ fontSize: "0.8rem", fontStyle: "italic", margin: 0 }}>
                  No timeline events recorded yet.
                </p>
              ) : (
                timelineEvents.map((evt) => (
                  <div
                    key={evt.id}
                    style={{
                      display: "flex",
                      alignItems: "flex-start",
                      gap: "0.75rem",
                      padding: "0.45rem 0.6rem",
                      background: "#f8fafc",
                      borderRadius: "4px",
                      borderLeft: "3px solid #3b82f6",
                      fontSize: "0.775rem",
                    }}
                  >
                    <div style={{ minWidth: "140px", color: "var(--text-muted)", fontSize: "0.725rem" }}>
                      {formatTime(evt.timestamp)}
                    </div>
                    <div style={{ flex: 1 }}>
                      <span
                        style={{
                          fontWeight: 700,
                          fontSize: "0.7rem",
                          color: "#1e40af",
                          background: "#dbeafe",
                          padding: "0.1rem 0.35rem",
                          borderRadius: "3px",
                          marginRight: "0.4rem",
                        }}
                      >
                        {evt.event_type}
                      </span>
                      <strong style={{ color: "#0f172a", marginRight: "0.3rem" }}>{evt.actor}:</strong>
                      <span style={{ color: "#334155" }}>{evt.description}</span>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
