export interface HealthResponse {
  status: string;
  app_name: string;
  version: string;
  environment: string;
  timestamp: string;
}

export interface LogUploadResponse {
  id: number;
  original_filename: string;
  file_type: string;
  service_name: string | null;
  environment: string | null;
  source_hint: string | null;
  content_hash: string;
  created_at: string;
  is_duplicate: boolean;
  message: string;
}

export interface LogListItem {
  id: number;
  original_filename: string;
  file_type: string;
  service_name: string | null;
  environment: string | null;
  source_hint: string | null;
  content_hash: string;
  created_at: string;
  content_length: number;
}

export interface LogListResponse {
  items: LogListItem[];
  total: number;
  limit: number;
  offset: number;
}

export interface UploadLogPayload {
  file: File;
  service_name?: string;
  environment?: string;
  source_hint?: string;
  onProgress?: (percent: number) => void;
}

export interface ParsedLogEvent {
  id: number;
  log_id: number;
  event_index: number;
  timestamp: string | null;
  level: string | null;
  service_name: string | null;
  message: string;
  exception_type: string | null;
  exception_message: string | null;
  class_name: string | null;
  method_name: string | null;
  source_file: string | null;
  line_number: number | null;
  stack_trace: string | null;
  created_at: string;
}

export interface ParseLogResponse {
  log_id: number;
  status: string;
  event_count: number;
  parser_used: string;
  events: ParsedLogEvent[];
}

export interface ParsedLogListResponse {
  log_id: number;
  total: number;
  events: ParsedLogEvent[];
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

let authToken: string | null = typeof window !== "undefined" ? localStorage.getItem("incident_platform_token") : null;

export function getAuthToken(): string | null {
  return authToken;
}

export function setAuthToken(token: string | null): void {
  authToken = token;
  if (typeof window !== "undefined") {
    if (token) {
      localStorage.setItem("incident_platform_token", token);
    } else {
      localStorage.removeItem("incident_platform_token");
    }
  }
}

// Global fetch interceptor to automatically attach Authorization header
if (typeof window !== "undefined" && window.fetch) {
  const originalFetch = window.fetch.bind(window);
  window.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
    const currentToken = getAuthToken();
    if (currentToken) {
      init = init || {};
      const headers = new Headers(init.headers || {});
      if (!headers.has("Authorization")) {
        headers.set("Authorization", `Bearer ${currentToken}`);
      }
      init.headers = headers;
    }
    return originalFetch(input, init);
  };
}

export async function fetchHealth(): Promise<HealthResponse> {
  const response = await fetch(`${API_BASE_URL}/health`, {
    headers: {
      Accept: "application/json",
    },
  });

  if (!response.ok) {
    throw new Error(`HTTP ${response.status}: ${response.statusText || "Request failed"}`);
  }

  return response.json();
}

/**
 * Fetch paginated list of ingested logs from PostgreSQL.
 */
export async function fetchLogs(limit: number = 50, offset: number = 0): Promise<LogListResponse> {
  const response = await fetch(`${API_BASE_URL}/api/v1/logs?limit=${limit}&offset=${offset}`, {
    headers: {
      Accept: "application/json",
    },
  });

  if (!response.ok) {
    let errorMsg = `HTTP ${response.status}: Failed to fetch logs`;
    try {
      const errData = await response.json();
      if (errData?.error?.message) {
        errorMsg = errData.error.message;
      }
    } catch {
      // fallback
    }
    throw new Error(errorMsg);
  }

  return response.json();
}

/**
 * Upload a raw log file (.log, .txt, .json) with optional metadata.
 * Uses XMLHttpRequest to measure real, genuine network upload progress without faking.
 */
export function uploadLog({
  file,
  service_name,
  environment,
  source_hint,
  onProgress,
}: UploadLogPayload): Promise<LogUploadResponse> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    const formData = new FormData();

    formData.append("file", file, file.name);
    if (service_name && service_name.trim()) {
      formData.append("service_name", service_name.trim());
    }
    if (environment && environment.trim()) {
      formData.append("environment", environment.trim());
    }
    if (source_hint && source_hint.trim()) {
      formData.append("source_hint", source_hint.trim());
    }

    if (xhr.upload && onProgress) {
      xhr.upload.onprogress = (event) => {
        if (event.lengthComputable && event.total > 0) {
          const percent = Math.min(100, Math.round((event.loaded / event.total) * 100));
          onProgress(percent);
        }
      };
    }

    xhr.open("POST", `${API_BASE_URL}/api/v1/logs/upload`, true);
    xhr.setRequestHeader("Accept", "application/json");
    const currentToken = getAuthToken();
    if (currentToken) {
      xhr.setRequestHeader("Authorization", `Bearer ${currentToken}`);
    }

    xhr.onload = () => {
      try {
        const data = JSON.parse(xhr.responseText);
        if (xhr.status >= 200 && xhr.status < 300) {
          resolve(data as LogUploadResponse);
        } else {
          const message = data?.error?.message || data?.detail || `Upload failed with HTTP ${xhr.status}`;
          reject(new Error(message));
        }
      } catch {
        reject(new Error(`Server returned HTTP ${xhr.status}: ${xhr.statusText || "Unexpected response"}`));
      }
    };

    xhr.onerror = () => {
      reject(new Error("Network error occurred. Unable to connect to backend server."));
    };

    xhr.onabort = () => {
      reject(new Error("Upload request was aborted."));
    };

    xhr.send(formData);
  });
}

/**
 * Trigger parsing of an ingested raw log into structured events.
 */
export async function parseLog(logId: number, reparse: boolean = false): Promise<ParseLogResponse> {
  const response = await fetch(`${API_BASE_URL}/api/v1/logs/${logId}/parse?reparse=${reparse}`, {
    method: "POST",
    headers: {
      Accept: "application/json",
    },
  });

  if (!response.ok) {
    let errorMsg = `HTTP ${response.status}: Failed to parse log`;
    try {
      const errData = await response.json();
      if (errData?.error?.message) {
        errorMsg = errData.error.message;
      }
    } catch {
      // fallback
    }
    throw new Error(errorMsg);
  }

  return response.json();
}

/**
 * Fetch previously parsed structured events for a log.
 */
export async function fetchParsedLogs(logId: number): Promise<ParsedLogListResponse> {
  const response = await fetch(`${API_BASE_URL}/api/v1/logs/${logId}/parsed`, {
    headers: {
      Accept: "application/json",
    },
  });

  if (!response.ok) {
    let errorMsg = `HTTP ${response.status}: Failed to fetch parsed logs`;
    try {
      const errData = await response.json();
      if (errData?.error?.message) {
        errorMsg = errData.error.message;
      }
    } catch {
      // fallback
    }
    throw new Error(errorMsg);
  }

  return response.json();
}

// =============================================================================
// Phase 3: Incident Correlation APIs
// =============================================================================

export interface Incident {
  id: number;
  incident_key: string;
  title: string;
  status: string;
  started_at: string | null;
  ended_at: string | null;
  event_count: number;
  service_count: number;
  correlation_reason: string;
  correlation_confidence: number | null;
  resolved_at?: string | null;
  resolution_summary?: string | null;
  resolved_by?: string | null;
  root_cause_confirmed?: string | null;
  created_at: string;
  updated_at: string;
}

export interface IncidentDetail extends Incident {
  events: ParsedLogEvent[];
}

export interface IncidentListResponse {
  items: Incident[];
  total: number;
  limit: number;
  offset: number;
}

export interface CorrelateIncidentsPayload {
  log_id?: number;
  time_window_seconds?: number;
}

export interface CorrelateIncidentsResponse {
  events_considered: number;
  incidents_created: number;
  incidents_existing: number;
  incidents: Incident[];
}

/**
 * Fetch paginated list of correlated incidents.
 */
export async function fetchIncidents(
  statusFilter?: string,
  limit: number = 50,
  offset: number = 0,
): Promise<IncidentListResponse> {
  const params = new URLSearchParams({
    limit: String(limit),
    offset: String(offset),
  });
  if (statusFilter) {
    params.set("status", statusFilter);
  }

  const response = await fetch(`${API_BASE_URL}/api/v1/incidents?${params.toString()}`, {
    headers: {
      Accept: "application/json",
    },
  });

  if (!response.ok) {
    let errorMsg = `HTTP ${response.status}: Failed to fetch incidents`;
    try {
      const errData = await response.json();
      if (errData?.error?.message) {
        errorMsg = errData.error.message;
      }
    } catch {
      // fallback
    }
    throw new Error(errorMsg);
  }

  return response.json();
}

// =============================================================================
// Phase 5: Root Cause Analysis APIs
// =============================================================================

export interface RCAHypothesis {
  hypothesis_id: string;
  title: string;
  description: string;
  confidence: number;
  confidence_level: "LOW" | "MEDIUM" | "HIGH" | string;
  supporting_evidence: string[];
  contradicting_evidence: string[];
  reasoning: string;
  causal_status: "HYPOTHESIS" | "SUPPORTED" | "CONFIRMED" | "UNVERIFIED" | string;
  role: "ROOT_CAUSE_CANDIDATE" | "CONTRIBUTING_FACTOR" | "SYMPTOM" | "UNKNOWN" | string;
}

export interface IncidentRCAAnalysis {
  id: number;
  incident_id: number;
  analysis_id: string;
  analysis_status: "COMPLETED" | "INSUFFICIENT_EVIDENCE" | "PROVIDER_UNAVAILABLE" | "FAILED" | string;
  provider: string;
  model: string;
  summary: string;
  confidence: number | null;
  confidence_level: string | null;
  hypotheses: RCAHypothesis[];
  evidence_snapshot: Record<string, any>;
  limitations: string[];
  created_at: string;
  updated_at: string;
}

export interface IncidentRCAHistoryResponse {
  incident_id: number;
  total: number;
  items: IncidentRCAAnalysis[];
}

/**
 * Trigger AI Root Cause Analysis against the incident evidence.
 */
export async function runIncidentRCA(incidentId: number): Promise<IncidentRCAAnalysis> {
  const response = await fetch(`${API_BASE_URL}/api/v1/incidents/${incidentId}/rca`, {
    method: "POST",
    headers: {
      Accept: "application/json",
    },
  });

  if (!response.ok) {
    let errorMsg = `HTTP ${response.status}: Failed to run root cause analysis`;
    try {
      const errData = await response.json();
      if (errData?.error?.message) {
        errorMsg = errData.error.message;
      }
    } catch {
      // fallback
    }
    throw new Error(errorMsg);
  }

  return response.json();
}

/**
 * Fetch latest RCA analysis for an incident (returns null if none exists yet).
 */
export async function fetchLatestRCA(incidentId: number): Promise<IncidentRCAAnalysis | null> {
  const response = await fetch(`${API_BASE_URL}/api/v1/incidents/${incidentId}/rca`, {
    headers: {
      Accept: "application/json",
    },
  });

  if (response.status === 404) {
    return null;
  }

  if (!response.ok) {
    let errorMsg = `HTTP ${response.status}: Failed to fetch RCA analysis`;
    try {
      const errData = await response.json();
      if (errData?.error?.message) {
        errorMsg = errData.error.message;
      }
    } catch {
      // fallback
    }
    throw new Error(errorMsg);
  }

  return response.json();
}

/**
 * Fetch RCA execution history for an incident.
 */
export async function fetchRCAHistory(incidentId: number): Promise<IncidentRCAHistoryResponse> {
  const response = await fetch(`${API_BASE_URL}/api/v1/incidents/${incidentId}/rca/history`, {
    headers: {
      Accept: "application/json",
    },
  });

  if (!response.ok) {
    let errorMsg = `HTTP ${response.status}: Failed to fetch RCA history`;
    try {
      const errData = await response.json();
      if (errData?.error?.message) {
        errorMsg = errData.error.message;
      }
    } catch {
      // fallback
    }
    throw new Error(errorMsg);
  }

  return response.json();
}

/**
 * Fetch a specific RCA analysis by its unique analysis_id.
 */
export async function fetchRCAById(
  incidentId: number,
  analysisId: string,
): Promise<IncidentRCAAnalysis> {
  const response = await fetch(`${API_BASE_URL}/api/v1/incidents/${incidentId}/rca/${analysisId}`, {
    headers: {
      Accept: "application/json",
    },
  });

  if (!response.ok) {
    let errorMsg = `HTTP ${response.status}: Failed to fetch RCA analysis ${analysisId}`;
    try {
      const errData = await response.json();
      if (errData?.error?.message) {
        errorMsg = errData.error.message;
      }
    } catch {
      // fallback
    }
    throw new Error(errorMsg);
  }

  return response.json();
}

// =============================================================================
// Phase 6: Investigation & Fix Recommendation APIs
// =============================================================================

export type RecommendationType =
  | "INVESTIGATION"
  | "DIAGNOSTIC_VERIFICATION"
  | "FIX"
  | "PREVENTION"
  | "VERIFICATION";

export type RecommendationConfidenceLevel = "LOW" | "MEDIUM" | "HIGH";
export type RiskLevel = "LOW" | "MEDIUM" | "HIGH" | "UNKNOWN";
export type RecommendationStatus = "PROPOSED" | "REVIEW_REQUIRED" | "DISMISSED";

export interface IncidentRecommendation {
  id: number;
  recommendation_id: string;
  incident_id: number;
  rca_analysis_id: number;
  type: RecommendationType | string;
  title: string;
  description: string;
  rationale: string;
  supporting_evidence: string[];
  confidence: number;
  confidence_level: RecommendationConfidenceLevel | string;
  risk_level: RiskLevel | string;
  expected_impact: string;
  prerequisites: string[];
  verification_steps: string[];
  status: RecommendationStatus | string;
  created_at: string;
  updated_at: string;
}

export interface IncidentRecommendationListResponse {
  incident_id: number;
  rca_analysis_id: number;
  status: string;
  total_recommendations: number;
  recommendations: IncidentRecommendation[];
  limitations: string[];
  provider: string;
  model: string;
  generated_at: string;
}

export interface IncidentRecommendationHistoryResponse {
  incident_id: number;
  total_recommendations: number;
  items: IncidentRecommendation[];
}

/**
 * Generate operational investigation and fix recommendations from latest validated RCA.
 */
export async function generateRecommendations(
  incidentId: number,
): Promise<IncidentRecommendationListResponse> {
  const response = await fetch(`${API_BASE_URL}/api/v1/incidents/${incidentId}/recommendations`, {
    method: "POST",
    headers: {
      Accept: "application/json",
    },
  });

  if (!response.ok) {
    let errorMsg = `HTTP ${response.status}: Failed to generate recommendations`;
    try {
      const errData = await response.json();
      if (errData?.error?.message) {
        errorMsg = errData.error.message;
      } else if (errData?.detail) {
        errorMsg = errData.detail;
      }
    } catch {
      // fallback
    }
    throw new Error(errorMsg);
  }

  return response.json();
}

/**
 * Fetch latest recommendations for an incident (returns null if none exist yet).
 */
export async function fetchLatestRecommendations(
  incidentId: number,
): Promise<IncidentRecommendationListResponse | null> {
  const response = await fetch(`${API_BASE_URL}/api/v1/incidents/${incidentId}/recommendations`, {
    headers: {
      Accept: "application/json",
    },
  });

  if (response.status === 404) {
    return null;
  }

  if (!response.ok) {
    let errorMsg = `HTTP ${response.status}: Failed to fetch recommendations`;
    try {
      const errData = await response.json();
      if (errData?.error?.message) {
        errorMsg = errData.error.message;
      } else if (errData?.detail) {
        errorMsg = errData.detail;
      }
    } catch {
      // fallback
    }
    throw new Error(errorMsg);
  }

  return response.json();
}

/**
 * Fetch recommendation run history for an incident.
 */
export async function fetchRecommendationHistory(
  incidentId: number,
): Promise<IncidentRecommendationHistoryResponse> {
  const response = await fetch(`${API_BASE_URL}/api/v1/incidents/${incidentId}/recommendations/history`, {
    headers: {
      Accept: "application/json",
    },
  });

  if (!response.ok) {
    let errorMsg = `HTTP ${response.status}: Failed to fetch recommendation history`;
    try {
      const errData = await response.json();
      if (errData?.error?.message) {
        errorMsg = errData.error.message;
      } else if (errData?.detail) {
        errorMsg = errData.detail;
      }
    } catch {
      // fallback
    }
    throw new Error(errorMsg);
  }

  return response.json();
}

/**
 * Fetch a specific recommendation by its unique string recommendation_id.
 */
export async function fetchRecommendationById(
  incidentId: number,
  recommendationId: string,
): Promise<IncidentRecommendation> {
  const response = await fetch(
    `${API_BASE_URL}/api/v1/incidents/${incidentId}/recommendations/${recommendationId}`,
    {
      headers: {
        Accept: "application/json",
      },
    },
  );

  if (!response.ok) {
    let errorMsg = `HTTP ${response.status}: Failed to fetch recommendation ${recommendationId}`;
    try {
      const errData = await response.json();
      if (errData?.error?.message) {
        errorMsg = errData.error.message;
      } else if (errData?.detail) {
        errorMsg = errData.detail;
      }
    } catch {
      // fallback
    }
    throw new Error(errorMsg);
  }

  return response.json();
}



/**
 * Fetch detailed incident with its constituent correlated parsed events.
 */
export async function fetchIncidentDetail(incidentId: number): Promise<IncidentDetail> {
  const response = await fetch(`${API_BASE_URL}/api/v1/incidents/${incidentId}`, {
    headers: {
      Accept: "application/json",
    },
  });

  if (!response.ok) {
    let errorMsg = `HTTP ${response.status}: Failed to fetch incident details`;
    try {
      const errData = await response.json();
      if (errData?.error?.message) {
        errorMsg = errData.error.message;
      }
    } catch {
      // fallback
    }
    throw new Error(errorMsg);
  }

  return response.json();
}

/**
 * Trigger deterministic correlation across parsed log events.
 */
export async function correlateIncidents(
  payload?: CorrelateIncidentsPayload,
): Promise<CorrelateIncidentsResponse> {
  const response = await fetch(`${API_BASE_URL}/api/v1/incidents/correlate`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: JSON.stringify(payload || {}),
  });

  if (!response.ok) {
    let errorMsg = `HTTP ${response.status}: Failed to run correlation`;
    try {
      const errData = await response.json();
      if (errData?.error?.message) {
        errorMsg = errData.error.message;
      }
    } catch {
      // fallback
    }
    throw new Error(errorMsg);
  }

  return response.json();
}

// =============================================================================
// Phase 4: Context Enrichment APIs
// =============================================================================

export interface IncidentContextItem {
  id: number;
  incident_id: number;
  context_category: string;
  status: "AVAILABLE" | "NOT_CONNECTED" | "UNAVAILABLE" | "INTEGRATION_REQUIRED" | string;
  data: Record<string, any>;
  source: string;
  collected_at: string;
  created_at: string;
  updated_at: string;
}

export interface EnrichedIncidentContext {
  incident_id: number;
  incident_title: string;
  total_categories: number;
  contexts: Record<string, IncidentContextItem>;
  collected_at: string;
}

/**
 * Trigger context enrichment for a correlated incident.
 */
export async function enrichIncident(incidentId: number): Promise<EnrichedIncidentContext> {
  const response = await fetch(`${API_BASE_URL}/api/v1/incidents/${incidentId}/enrich`, {
    method: "POST",
    headers: {
      Accept: "application/json",
    },
  });

  if (!response.ok) {
    let errorMsg = `HTTP ${response.status}: Failed to enrich incident context`;
    try {
      const errData = await response.json();
      if (errData?.error?.message) {
        errorMsg = errData.error.message;
      }
    } catch {
      // fallback
    }
    throw new Error(errorMsg);
  }

  return response.json();
}

/**
 * Fetch all enriched operational contexts for an incident.
 */
export async function fetchIncidentContext(incidentId: number): Promise<EnrichedIncidentContext> {
  const response = await fetch(`${API_BASE_URL}/api/v1/incidents/${incidentId}/context`, {
    headers: {
      Accept: "application/json",
    },
  });

  if (!response.ok) {
    let errorMsg = `HTTP ${response.status}: Failed to fetch incident context`;
    try {
      const errData = await response.json();
      if (errData?.error?.message) {
        errorMsg = errData.error.message;
      }
    } catch {
      // fallback
    }
    throw new Error(errorMsg);
  }

  return response.json();
}

/**
 * Fetch specific context category for an incident.
 */
export async function fetchIncidentContextCategory(
  incidentId: number,
  category: string,
): Promise<IncidentContextItem> {
  const response = await fetch(`${API_BASE_URL}/api/v1/incidents/${incidentId}/context/${category}`, {
    headers: {
      Accept: "application/json",
    },
  });

  if (!response.ok) {
    let errorMsg = `HTTP ${response.status}: Failed to fetch ${category} context`;
    try {
      const errData = await response.json();
      if (errData?.error?.message) {
        errorMsg = errData.error.message;
      }
    } catch {
      // fallback
    }
    throw new Error(errorMsg);
  }

  return response.json();
}

// =============================================================================
// Phase 7: Developer Investigation & Resolution APIs
// =============================================================================

export type InvestigationStatus =
  | "UNASSIGNED"
  | "ASSIGNED"
  | "INVESTIGATING"
  | "READY_FOR_VERIFICATION"
  | "RESOLVED"
  | "CLOSED";

export type ActionType =
  | "OBSERVATION"
  | "DIAGNOSTIC_CHECK"
  | "CONFIG_REVIEW"
  | "LOG_REVIEW"
  | "METRIC_REVIEW"
  | "DEPENDENCY_CHECK"
  | "FIX_APPLIED"
  | "VERIFICATION"
  | "OTHER";

export type RecommendationReviewDecision =
  | "ACCEPTED"
  | "REJECTED"
  | "DEFERRED"
  | "NOT_APPLICABLE";

export type VerificationStatus =
  | "PENDING"
  | "PASSED"
  | "FAILED"
  | "NOT_APPLICABLE";

export type TimelineEventType =
  | "INVESTIGATION_STARTED"
  | "INCIDENT_ASSIGNED"
  | "STATUS_CHANGED"
  | "NOTE_ADDED"
  | "ACTION_RECORDED"
  | "RECOMMENDATION_REVIEWED"
  | "VERIFICATION_CREATED"
  | "VERIFICATION_UPDATED"
  | "INCIDENT_RESOLVED"
  | "INCIDENT_REOPENED";

export type RootCauseConfirmed = "CONFIRMED" | "REFUTED" | "UNKNOWN";

export interface Investigation {
  id: number;
  incident_id: number;
  assigned_to: string | null;
  assigned_to_name: string | null;
  assigned_at: string | null;
  status: InvestigationStatus;
  investigation_summary: string | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface InvestigationNote {
  id: number;
  incident_id: number;
  investigation_id: number | null;
  author: string;
  note: string;
  evidence_references: string[];
  created_at: string;
}

export interface InvestigationAction {
  id: number;
  incident_id: number;
  investigation_id: number | null;
  action_type: ActionType;
  description: string;
  performed_by: string;
  result: string;
  evidence_references: string[];
  created_at: string;
}

export interface RecommendationReview {
  id: number;
  recommendation_id: string;
  incident_id: number;
  investigation_id: number | null;
  reviewed_by: string;
  decision: RecommendationReviewDecision;
  reason: string | null;
  created_at: string;
}

export interface VerificationStep {
  id: number;
  incident_id: number;
  investigation_id: number | null;
  title: string;
  description: string | null;
  is_required: boolean;
  status: VerificationStatus;
  result: string | null;
  verified_by: string | null;
  verified_at: string | null;
  evidence_references: string[];
  created_at: string;
  updated_at: string;
}

export interface VerificationStepListResponse {
  incident_id: number;
  total: number;
  pending_count: number;
  passed_count: number;
  failed_count: number;
  steps: VerificationStep[];
}

export interface TimelineEvent {
  id: number;
  incident_id: number;
  investigation_id: number | null;
  event_type: TimelineEventType;
  actor: string;
  timestamp: string;
  related_entity_type: string | null;
  related_entity_id: string | null;
  description: string;
  created_at: string;
}

export interface TimelineResponse {
  incident_id: number;
  total_events: number;
  events: TimelineEvent[];
}

export interface ResolutionResponse {
  incident_id: number;
  incident_key: string;
  status: string;
  resolved_at: string;
  resolved_by: string;
  resolution_summary: string;
  root_cause_confirmed: RootCauseConfirmed;
  investigation_status: string;
  verified_steps_count: number;
}

export interface ReopenResponse {
  incident_id: number;
  incident_key: string;
  status: string;
  investigation_status: string;
  reopened_by: string;
  reason: string;
  reopened_at: string;
}

/**
 * Start or initialize investigation workspace for an incident.
 */
export async function startInvestigation(
  incidentId: number,
  payload: {
    assigned_to?: string;
    assigned_to_name?: string;
    investigation_summary?: string;
  } = {},
): Promise<Investigation> {
  const response = await fetch(`${API_BASE_URL}/api/v1/incidents/${incidentId}/investigation`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    let errorMsg = `HTTP ${response.status}: Failed to start investigation`;
    try {
      const errData = await response.json();
      if (errData?.error?.message) errorMsg = errData.error.message;
      else if (errData?.detail) errorMsg = errData.detail;
    } catch {
      // fallback
    }
    throw new Error(errorMsg);
  }

  return response.json();
}

/**
 * Fetch the active investigation workspace for an incident.
 */
export async function fetchInvestigation(incidentId: number): Promise<Investigation> {
  const response = await fetch(`${API_BASE_URL}/api/v1/incidents/${incidentId}/investigation`, {
    headers: {
      Accept: "application/json",
    },
  });

  if (!response.ok) {
    let errorMsg = `HTTP ${response.status}: Failed to fetch investigation`;
    try {
      const errData = await response.json();
      if (errData?.error?.message) errorMsg = errData.error.message;
      else if (errData?.detail) errorMsg = errData.detail;
    } catch {
      // fallback
    }
    throw new Error(errorMsg);
  }

  return response.json();
}

/**
 * Update investigation status or assignment.
 */
export async function updateInvestigation(
  incidentId: number,
  payload: {
    assigned_to?: string;
    assigned_to_name?: string;
    status?: InvestigationStatus;
    investigation_summary?: string;
  },
): Promise<Investigation> {
  const response = await fetch(`${API_BASE_URL}/api/v1/incidents/${incidentId}/investigation`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    let errorMsg = `HTTP ${response.status}: Failed to update investigation`;
    try {
      const errData = await response.json();
      if (errData?.error?.message) errorMsg = errData.error.message;
      else if (errData?.detail) errorMsg = errData.detail;
    } catch {
      // fallback
    }
    throw new Error(errorMsg);
  }

  return response.json();
}

/**
 * Add a persistent developer note.
 */
export async function createInvestigationNote(
  incidentId: number,
  payload: {
    author: string;
    note: string;
    evidence_references?: string[];
  },
): Promise<InvestigationNote> {
  const response = await fetch(`${API_BASE_URL}/api/v1/incidents/${incidentId}/investigation/notes`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    let errorMsg = `HTTP ${response.status}: Failed to add investigation note`;
    try {
      const errData = await response.json();
      if (errData?.error?.message) errorMsg = errData.error.message;
      else if (errData?.detail) errorMsg = errData.detail;
    } catch {
      // fallback
    }
    throw new Error(errorMsg);
  }

  return response.json();
}

/**
 * Fetch all notes for an incident.
 */
export async function fetchInvestigationNotes(
  incidentId: number,
): Promise<{ incident_id: number; total: number; notes: InvestigationNote[] }> {
  const response = await fetch(`${API_BASE_URL}/api/v1/incidents/${incidentId}/investigation/notes`, {
    headers: {
      Accept: "application/json",
    },
  });

  if (!response.ok) {
    let errorMsg = `HTTP ${response.status}: Failed to fetch investigation notes`;
    try {
      const errData = await response.json();
      if (errData?.error?.message) errorMsg = errData.error.message;
      else if (errData?.detail) errorMsg = errData.detail;
    } catch {
      // fallback
    }
    throw new Error(errorMsg);
  }

  return response.json();
}

/**
 * Record a developer diagnostic or external action.
 */
export async function createInvestigationAction(
  incidentId: number,
  payload: {
    action_type: ActionType;
    description: string;
    performed_by: string;
    result: string;
    evidence_references?: string[];
  },
): Promise<InvestigationAction> {
  const response = await fetch(`${API_BASE_URL}/api/v1/incidents/${incidentId}/investigation/actions`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    let errorMsg = `HTTP ${response.status}: Failed to record investigation action`;
    try {
      const errData = await response.json();
      if (errData?.error?.message) errorMsg = errData.error.message;
      else if (errData?.detail) errorMsg = errData.detail;
    } catch {
      // fallback
    }
    throw new Error(errorMsg);
  }

  return response.json();
}

/**
 * Fetch all recorded investigation actions.
 */
export async function fetchInvestigationActions(
  incidentId: number,
): Promise<{ incident_id: number; total: number; actions: InvestigationAction[] }> {
  const response = await fetch(`${API_BASE_URL}/api/v1/incidents/${incidentId}/investigation/actions`, {
    headers: {
      Accept: "application/json",
    },
  });

  if (!response.ok) {
    let errorMsg = `HTTP ${response.status}: Failed to fetch investigation actions`;
    try {
      const errData = await response.json();
      if (errData?.error?.message) errorMsg = errData.error.message;
      else if (errData?.detail) errorMsg = errData.detail;
    } catch {
      // fallback
    }
    throw new Error(errorMsg);
  }

  return response.json();
}

/**
 * Review a Phase 6 recommendation (ACCEPT, REJECT, DEFER, NOT_APPLICABLE).
 */
export async function reviewRecommendation(
  incidentId: number,
  recommendationId: string | number,
  payload: {
    reviewed_by: string;
    decision: RecommendationReviewDecision;
    reason?: string;
  },
): Promise<RecommendationReview> {
  const response = await fetch(
    `${API_BASE_URL}/api/v1/incidents/${incidentId}/recommendations/${recommendationId}/review`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify(payload),
    },
  );

  if (!response.ok) {
    let errorMsg = `HTTP ${response.status}: Failed to review recommendation`;
    try {
      const errData = await response.json();
      if (errData?.error?.message) errorMsg = errData.error.message;
      else if (errData?.detail) errorMsg = errData.detail;
    } catch {
      // fallback
    }
    throw new Error(errorMsg);
  }

  return response.json();
}

/**
 * Fetch all recommendation reviews for an incident.
 */
export async function fetchRecommendationReviews(
  incidentId: number,
): Promise<{ incident_id: number; total: number; reviews: RecommendationReview[] }> {
  const response = await fetch(`${API_BASE_URL}/api/v1/incidents/${incidentId}/recommendations/reviews`, {
    headers: {
      Accept: "application/json",
    },
  });

  if (!response.ok) {
    let errorMsg = `HTTP ${response.status}: Failed to fetch recommendation reviews`;
    try {
      const errData = await response.json();
      if (errData?.error?.message) errorMsg = errData.error.message;
      else if (errData?.detail) errorMsg = errData.detail;
    } catch {
      // fallback
    }
    throw new Error(errorMsg);
  }

  return response.json();
}

/**
 * Create a verification checklist step.
 */
export async function createVerificationStep(
  incidentId: number,
  payload: {
    title: string;
    description?: string;
    is_required?: boolean;
    evidence_references?: string[];
  },
): Promise<VerificationStep> {
  const response = await fetch(`${API_BASE_URL}/api/v1/incidents/${incidentId}/verification`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    let errorMsg = `HTTP ${response.status}: Failed to create verification step`;
    try {
      const errData = await response.json();
      if (errData?.error?.message) errorMsg = errData.error.message;
      else if (errData?.detail) errorMsg = errData.detail;
    } catch {
      // fallback
    }
    throw new Error(errorMsg);
  }

  return response.json();
}

/**
 * Fetch all verification steps for an incident.
 */
export async function fetchVerificationSteps(
  incidentId: number,
): Promise<VerificationStepListResponse> {
  const response = await fetch(`${API_BASE_URL}/api/v1/incidents/${incidentId}/verification`, {
    headers: {
      Accept: "application/json",
    },
  });

  if (!response.ok) {
    let errorMsg = `HTTP ${response.status}: Failed to fetch verification steps`;
    try {
      const errData = await response.json();
      if (errData?.error?.message) errorMsg = errData.error.message;
      else if (errData?.detail) errorMsg = errData.detail;
    } catch {
      // fallback
    }
    throw new Error(errorMsg);
  }

  return response.json();
}

/**
 * Update verification step status or result.
 */
export async function updateVerificationStep(
  incidentId: number,
  stepId: number,
  payload: {
    status?: VerificationStatus;
    result?: string;
    verified_by?: string;
    evidence_references?: string[];
  },
): Promise<VerificationStep> {
  const response = await fetch(`${API_BASE_URL}/api/v1/incidents/${incidentId}/verification/${stepId}`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    let errorMsg = `HTTP ${response.status}: Failed to update verification step`;
    try {
      const errData = await response.json();
      if (errData?.error?.message) errorMsg = errData.error.message;
      else if (errData?.detail) errorMsg = errData.detail;
    } catch {
      // fallback
    }
    throw new Error(errorMsg);
  }

  return response.json();
}

/**
 * Resolve an incident after all verification steps pass.
 */
export async function resolveIncident(
  incidentId: number,
  payload: {
    resolved_by: string;
    resolution_summary: string;
    root_cause_confirmed?: RootCauseConfirmed;
  },
): Promise<ResolutionResponse> {
  const response = await fetch(`${API_BASE_URL}/api/v1/incidents/${incidentId}/resolve`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    let errorMsg = `HTTP ${response.status}: Failed to resolve incident`;
    try {
      const errData = await response.json();
      if (errData?.error?.message) errorMsg = errData.error.message;
      else if (errData?.detail) errorMsg = errData.detail;
    } catch {
      // fallback
    }
    throw new Error(errorMsg);
  }

  return response.json();
}

/**
 * Reopen a previously resolved incident.
 */
export async function reopenIncident(
  incidentId: number,
  payload: {
    reopened_by: string;
    reason: string;
  },
): Promise<ReopenResponse> {
  const response = await fetch(`${API_BASE_URL}/api/v1/incidents/${incidentId}/reopen`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    let errorMsg = `HTTP ${response.status}: Failed to reopen incident`;
    try {
      const errData = await response.json();
      if (errData?.error?.message) errorMsg = errData.error.message;
      else if (errData?.detail) errorMsg = errData.detail;
    } catch {
      // fallback
    }
    throw new Error(errorMsg);
  }

  return response.json();
}

/**
 * Fetch complete audit timeline for an incident.
 */
export async function fetchIncidentTimeline(incidentId: number): Promise<TimelineResponse> {
  const response = await fetch(`${API_BASE_URL}/api/v1/incidents/${incidentId}/timeline`, {
    headers: {
      Accept: "application/json",
    },
  });

  if (!response.ok) {
    let errorMsg = `HTTP ${response.status}: Failed to fetch timeline`;
    try {
      const errData = await response.json();
      if (errData?.error?.message) errorMsg = errData.error.message;
      else if (errData?.detail) errorMsg = errData.detail;
    } catch {
      // fallback
    }
    throw new Error(errorMsg);
  }

  return response.json();
}

// ============================================================================
// PHASE 8: PRODUCTION HARDENING, AUTH, INTEGRATIONS, ALERTS & AUDIT
// ============================================================================

export type UserRole = "ADMIN" | "DEVELOPER" | "VIEWER";

export interface User {
  id: number;
  username: string;
  email: string;
  role: UserRole;
  is_active: boolean;
  created_at: string;
  updated_at?: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface LoginPayload {
  username: string;
  password: string;
}

export interface RegisterPayload {
  username: string;
  email: string;
  password: string;
  role?: UserRole;
}

export type IntegrationState = "CONNECTED" | "NOT_CONNECTED" | "UNAVAILABLE" | "ERROR";

export interface IntegrationStatusItem {
  provider: string;
  category: string;
  state: IntegrationState;
  configured: boolean;
  message: string;
  details?: Record<string, unknown>;
}

export interface IntegrationsStatusResponse {
  integrations: Record<string, IntegrationStatusItem>;
  summary: {
    total: number;
    connected: number;
    not_connected: number;
    unavailable: number;
  };
}

export interface AlertRule {
  id: number;
  name: string;
  description?: string;
  condition_type: string;
  severity_filter?: string;
  threshold_minutes?: number;
  is_active: boolean;
  created_at: string;
}

export interface IncidentAlert {
  id: number;
  incident_id: number;
  rule_id: number;
  alert_type: string;
  severity: string;
  status: string;
  dedup_key: string;
  payload: Record<string, unknown>;
  created_at: string;
}

export interface IncidentNotification {
  id: number;
  alert_id: number;
  incident_id: number;
  channel: string;
  recipient: string;
  status: string;
  retry_count: number;
  error_message?: string;
  sent_at?: string;
  created_at: string;
}

export interface AuditLogItem {
  id: number;
  actor: string;
  action: string;
  target_entity: string;
  target_id?: string;
  request_id?: string;
  metadata?: Record<string, unknown>;
  created_at: string;
}

export interface AuditLogResponse {
  items: AuditLogItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface HealthProbeResponse {
  status: string;
  app_name?: string;
  version?: string;
  checks?: Record<string, unknown>;
  timestamp: string;
}

/**
 * Log in with username and password, receiving JWT access & refresh tokens.
 */
export async function loginUser(payload: LoginPayload): Promise<TokenResponse> {
  const response = await fetch(`${API_BASE_URL}/api/v1/auth/login`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    let errorMsg = `HTTP ${response.status}: Login failed`;
    try {
      const errData = await response.json();
      if (errData?.error?.message) errorMsg = errData.error.message;
      else if (errData?.detail) errorMsg = errData.detail;
    } catch {
      // fallback
    }
    throw new Error(errorMsg);
  }

  const data: TokenResponse = await response.json();
  setAuthToken(data.access_token);
  return data;
}

/**
 * Register a new user.
 */
export async function registerUser(payload: RegisterPayload): Promise<User> {
  const response = await fetch(`${API_BASE_URL}/api/v1/auth/register`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    let errorMsg = `HTTP ${response.status}: Registration failed`;
    try {
      const errData = await response.json();
      if (errData?.error?.message) errorMsg = errData.error.message;
      else if (errData?.detail) errorMsg = errData.detail;
    } catch {
      // fallback
    }
    throw new Error(errorMsg);
  }

  return response.json();
}

/**
 * Fetch currently authenticated user identity.
 */
export async function fetchCurrentUser(): Promise<User> {
  const response = await fetch(`${API_BASE_URL}/api/v1/auth/me`, {
    headers: {
      Accept: "application/json",
    },
  });

  if (!response.ok) {
    let errorMsg = `HTTP ${response.status}: Failed to get profile`;
    try {
      const errData = await response.json();
      if (errData?.error?.message) errorMsg = errData.error.message;
      else if (errData?.detail) errorMsg = errData.detail;
    } catch {
      // fallback
    }
    throw new Error(errorMsg);
  }

  const data = await response.json();
  return (data?.user || data) as User;
}

/**
 * Log out and invalidate local session.
 */
export async function logoutUser(): Promise<void> {
  try {
    await fetch(`${API_BASE_URL}/api/v1/auth/logout`, {
      method: "POST",
      headers: {
        Accept: "application/json",
      },
    });
  } catch {
    // Ignore network error on logout
  } finally {
    setAuthToken(null);
  }
}

/**
 * List all users (Admin only).
 */
export async function fetchUsers(): Promise<User[]> {
  const response = await fetch(`${API_BASE_URL}/api/v1/auth/users`, {
    headers: {
      Accept: "application/json",
    },
  });

  if (!response.ok) {
    let errorMsg = `HTTP ${response.status}: Failed to fetch users`;
    try {
      const errData = await response.json();
      if (errData?.error?.message) errorMsg = errData.error.message;
      else if (errData?.detail) errorMsg = errData.detail;
    } catch {
      // fallback
    }
    throw new Error(errorMsg);
  }

  return response.json();
}

/**
 * Health Liveness probe.
 */
export async function fetchHealthLive(): Promise<HealthProbeResponse> {
  const response = await fetch(`${API_BASE_URL}/health/live`, {
    headers: { Accept: "application/json" },
  });
  if (!response.ok) throw new Error(`HTTP ${response.status}: Liveness probe failed`);
  return response.json();
}

/**
 * Health Readiness probe.
 */
export async function fetchHealthReady(): Promise<HealthProbeResponse> {
  const response = await fetch(`${API_BASE_URL}/health/ready`, {
    headers: { Accept: "application/json" },
  });
  if (!response.ok) throw new Error(`HTTP ${response.status}: Readiness probe failed`);
  return response.json();
}

/**
 * Fetch all external integration provider connection statuses.
 */
export async function fetchIntegrationStatus(): Promise<IntegrationsStatusResponse> {
  const response = await fetch(`${API_BASE_URL}/api/v1/integrations/status`, {
    headers: { Accept: "application/json" },
  });

  if (!response.ok) {
    let errorMsg = `HTTP ${response.status}: Failed to fetch integrations status`;
    try {
      const errData = await response.json();
      if (errData?.error?.message) errorMsg = errData.error.message;
      else if (errData?.detail) errorMsg = errData.detail;
    } catch {
      // fallback
    }
    throw new Error(errorMsg);
  }

  return response.json();
}

/**
 * Query recent deployment records from integration provider.
 */
export async function fetchRecentDeployments(limit = 10): Promise<{ provider: string; state: string; deployments: unknown[]; message: string }> {
  const response = await fetch(`${API_BASE_URL}/api/v1/integrations/deployment/recent?limit=${limit}`, {
    headers: { Accept: "application/json" },
  });
  if (!response.ok) throw new Error(`HTTP ${response.status}: Failed to fetch deployments`);
  return response.json();
}

/**
 * Query recent commits from source control integration provider.
 */
export async function fetchRecentCommits(limit = 10): Promise<{ provider: string; state: string; commits: unknown[]; message: string }> {
  const response = await fetch(`${API_BASE_URL}/api/v1/integrations/source-control/commits?limit=${limit}`, {
    headers: { Accept: "application/json" },
  });
  if (!response.ok) throw new Error(`HTTP ${response.status}: Failed to fetch commits`);
  return response.json();
}

/**
 * Query infrastructure pods & status from infrastructure integration provider.
 */
export async function fetchInfrastructureStatus(): Promise<{ provider: string; state: string; pods: unknown[]; services: unknown[]; message: string }> {
  const response = await fetch(`${API_BASE_URL}/api/v1/integrations/infrastructure/status`, {
    headers: { Accept: "application/json" },
  });
  if (!response.ok) throw new Error(`HTTP ${response.status}: Failed to fetch infrastructure status`);
  return response.json();
}

/**
 * Query Prometheus metrics from metrics integration provider.
 */
export async function queryMetrics(query = "up", time?: string): Promise<{ provider: string; state: string; metrics: unknown; message: string }> {
  let url = `${API_BASE_URL}/api/v1/integrations/metrics/query?query=${encodeURIComponent(query)}`;
  if (time) {
    url += `&time=${encodeURIComponent(time)}`;
  }
  const response = await fetch(url, {
    headers: { Accept: "application/json" },
  });
  if (!response.ok) throw new Error(`HTTP ${response.status}: Failed to query metrics`);
  return response.json();
}

/**
 * Fetch alert rules.
 */
export async function fetchAlertRules(): Promise<AlertRule[]> {
  const response = await fetch(`${API_BASE_URL}/api/v1/alerts/rules`, {
    headers: { Accept: "application/json" },
  });
  if (!response.ok) throw new Error(`HTTP ${response.status}: Failed to fetch alert rules`);
  return response.json();
}

/**
 * Fetch triggered alerts.
 */
export async function fetchAlerts(incidentId?: number, status?: string): Promise<IncidentAlert[]> {
  let url = `${API_BASE_URL}/api/v1/alerts/`;
  const params: string[] = [];
  if (incidentId !== undefined) params.push(`incident_id=${incidentId}`);
  if (status) params.push(`status=${encodeURIComponent(status)}`);
  if (params.length > 0) url += `?${params.join("&")}`;

  const response = await fetch(url, {
    headers: { Accept: "application/json" },
  });
  if (!response.ok) throw new Error(`HTTP ${response.status}: Failed to fetch alerts`);
  return response.json();
}

/**
 * Fetch notifications log.
 */
export async function fetchNotifications(incidentId?: number, status?: string): Promise<IncidentNotification[]> {
  let url = `${API_BASE_URL}/api/v1/alerts/notifications`;
  const params: string[] = [];
  if (incidentId !== undefined) params.push(`incident_id=${incidentId}`);
  if (status) params.push(`status=${encodeURIComponent(status)}`);
  if (params.length > 0) url += `?${params.join("&")}`;

  const response = await fetch(url, {
    headers: { Accept: "application/json" },
  });
  if (!response.ok) throw new Error(`HTTP ${response.status}: Failed to fetch notifications`);
  return response.json();
}

/**
 * Trigger alert evaluation for an incident.
 */
export async function triggerAlertEvaluation(incidentId: number): Promise<{ incident_id: number; alerts_triggered: number; notifications_dispatched: number; alerts: unknown[]; notifications: unknown[] }> {
  const response = await fetch(`${API_BASE_URL}/api/v1/alerts/evaluate/${incidentId}`, {
    method: "POST",
    headers: { Accept: "application/json" },
  });
  if (!response.ok) throw new Error(`HTTP ${response.status}: Failed to evaluate alerts`);
  return response.json();
}

/**
 * Fetch security audit logs.
 */
export async function fetchAuditLogs(
  page = 1,
  pageSize = 50,
  action?: string,
  entityType?: string,
): Promise<AuditLogResponse> {
  let url = `${API_BASE_URL}/api/v1/audit/logs?page=${page}&page_size=${pageSize}`;
  if (action) url += `&action=${encodeURIComponent(action)}`;
  if (entityType) url += `&entity_type=${encodeURIComponent(entityType)}`;

  const response = await fetch(url, {
    headers: { Accept: "application/json" },
  });
  if (!response.ok) throw new Error(`HTTP ${response.status}: Failed to fetch audit logs`);
  return response.json();
}



