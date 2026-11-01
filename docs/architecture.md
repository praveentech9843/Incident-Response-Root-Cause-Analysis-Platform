# System Architecture — Phase 3: Incident Correlation

## Overview

The **AI-Powered Incident Response & Root Cause Analysis Platform** is designed as a **modular monolith**. It combines developer incident telemetry with context-aware analysis, root cause deduction, and resolution guidance.

### Implemented Phases:
- **Phase 0**: Modular Monolith Foundation (FastAPI, PostgreSQL 16, SQLAlchemy 2.0, Alembic, React 19 / Vite UI shell, Pytest suite).
- **Phase 1**: Real Log Ingestion (Upload validation, line normalization, SHA-256 deduplication, raw log persistence in `logs` table).
- **Phase 2**: Structured Log Extraction & Semantic Parsing (Parser Registry, deterministic text/JSON parsing, multi-line stack trace collapsing, structured event persistence in `parsed_logs` table, idempotency & re-parse controls).
- **Phase 3**: Incident Correlation (Multi-service event clustering, deterministic sliding window, explicit correlation ID extraction, confidence scoring, deterministic `incident_key` deduplication, `incidents` and `incident_events` persistence).

### Strict Boundary
Phase 3 strictly terminates at grouping structured log events into operational incidents with correlated event relationships.
- **Correlation is NOT Causation**: Phase 3 determines *which events are related*, NOT *which event or service caused the failure*. Root cause determination and root service labeling are strictly reserved for Phase 5.
- **No Phase 4+ functionality**: Strictly no AI/LLM, no RAG or vector database, no context enrichment (metrics, traces, deployments, PRs), no external integrations (Kubernetes, GitHub, PagerDuty, Slack), and no automated remediation.

---

## High-Level Pipeline Architecture

```text
┌────────────────────────────────────────────────────────────────────────┐
│                        Phase 1: Ingestion                              │
│                                                                        │
│   Real Log File (.log, .txt, .json)                                    │
│       ↓                                                                │
│   Validation & Normalization (UTF-8, size, line endings \n)            │
│       ↓                                                                │
│   SHA-256 Content Deduplication                                        │
│       ↓                                                                │
│   PostgreSQL: logs (raw_content faithfully preserved)                  │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ log_id
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                        Phase 2: Parsing Engine                         │
│                                                                        │
│   Raw Log                                                              │
│      ↓                                                                 │
│   Parser Registry (Heuristic & file_type inspection)                   │
│      ↓                                                                 │
│   Text Parser / JSON Parser (Deterministic regex & object mapping)     │
│      ↓                                                                 │
│   Structured Events (ParsedEventData with normalized fields)           │
│      ↓                                                                 │
│   PostgreSQL: parsed_logs (event_index ordered, FK -> logs.id)         │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ parsed_logs
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                   Phase 3: Correlation Engine                          │
│                                                                        │
│   Structured Log Events                                                │
│      ↓                                                                 │
│   Correlation Engine (Deterministic Signal Evaluation)                 │
│      ├── Signal A: Correlation / Request / Trace ID (Confidence 0.95)  │
│      ├── Signal B: Temporal Sliding Window (Default: 30 seconds)       │
│      └── Signal C: Multi-Service Error Evidence                        │
│      ↓                                                                 │
│   Deduplication (SHA-256 deterministic incident_key hash)              │
│      ↓                                                                 │
│   PostgreSQL: incidents & incident_events (M:N relation, FK cascades)  │
└────────────────────────────────────────────────────────────────────────┘
```

---

## Detailed System Component Map

```text
┌────────────────────────────────────────────────────────────────────────┐
│                    React + Vite Frontend (TypeScript)                  │
│    • LiveLogsPage: Raw log upload, progress bar, logs list             │
│    • Parse Action: "Parse Log" / "Re-parse" trigger buttons            │
│    • Structured Event Viewer: Chronological events table, frame drawer │
│    • IncidentsPage:                                                    │
│        - Operational Incidents table with status and severity filters  │
│        - "Trigger Correlation" button with instant refresh             │
│        - Incident Detail view with constituent chronological events    │
│        - Stack trace inspection drawer with copy-to-clipboard          │
│        - Signal breakdown and confidence percentage badges             │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ HTTP (REST JSON / multipart)
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                         FastAPI Backend                                │
│                                                                        │
│   ┌────────────────────────────────────────────────────────────────┐   │
│   │                      app/api/v1/endpoints                      │   │
│   │   • health.py: GET /health, GET /api/v1/health                 │   │
│   │   • logs.py:                                                   │   │
│   │       - POST /api/v1/logs/upload (Upload raw log)              │   │
│   │       - GET  /api/v1/logs (Paginated raw logs)                 │   │
│   │       - POST /api/v1/logs/{id}/parse (Parse / Re-parse log)    │   │
│   │       - GET  /api/v1/logs/{id}/parsed (Get parsed events)      │   │
│   │   • incidents.py:                                              │   │
│   │       - POST /api/v1/incidents/correlate (Trigger correlation) │   │
│   │       - GET  /api/v1/incidents (List incidents with filters)   │   │
│   │       - GET  /api/v1/incidents/{id} (Get incident detail)      │   │
│   │       - GET  /api/v1/incidents/{id}/events (Chronological)     │   │
│   └────────────────────────────────────────────────────────────────┘   │
│                                   │                                    │
│   ┌───────────────────────────────┴────────────────────────────────┐   │
│   │                         app/services                           │   │
│   │   • log_service.py: Ingestion, validation, SHA-256 dedupe      │   │
│   │   • parser_service.py: Parsing orchestration, idempotency      │   │
│   │   • correlation_service.py: Fetch candidate events, correlate, │   │
│   │     deduplicate via incident_key, persist records              │   │
│   └───────────────────────────────┬────────────────────────────────┘   │
│                                   │                                    │
│   ┌───────────────────────────────┴────────────────────────────────┐   │
│   │                       app/correlation                          │   │
│   │   • engine.py: CorrelationEngine (orchestrates grouping logic) │   │
│   │   • rules.py: Deterministic rule definitions, ID extraction    │   │
│   │     regex, sliding window clustering, confidence calculation   │   │
│   └───────────────────────────────┬────────────────────────────────┘   │
│                                   │                                    │
│   ┌───────────────────────────────┴────────────────────────────────┐   │
│   │                       app/repositories                         │   │
│   │   • log_repository.py: CRUD on logs table                      │   │
│   │   • parsed_log_repository.py: CRUD on parsed_logs table        │   │
│   │   • incident_repository.py: CRUD on incidents & incident_events│   │
│   └───────────────────────────────┬────────────────────────────────┘   │
│                                   │                                    │
│   ┌───────────────────────────────┴────────────────────────────────┐   │
│   │                       app/models & schemas                     │   │
│   │   • log.py: Log ORM entity & schemas                           │   │
│   │   • parsed_log.py: ParsedLog ORM entity & schemas              │   │
│   │   • incident.py: Incident ORM entity & schemas                 │   │
│   │   • incident_event.py: IncidentEvent join table entity         │   │
│   └────────────────────────────────────────────────────────────────┘   │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ SQLAlchemy 2.0 / Alembic
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                        PostgreSQL Database                             │
│                                                                        │
│   ┌────────────────────────────────────────────────────────────────┐   │
│   │ logs table:                                                    │   │
│   │   id (PK), original_filename, file_type, service_name,        │   │
│   │   environment, source_hint, raw_content, content_hash (UQ),   │   │
│   │   created_at                                                   │   │
│   └───────────────────────────────┬────────────────────────────────┘   │
│                                   │ 1                                  │
│                                   │ N (FK logs.id, ON DELETE CASCADE)  │
│                                   ▼                                    │
│   ┌────────────────────────────────────────────────────────────────┐   │
│   │ parsed_logs table:                                             │   │
│   │   id (PK), log_id (FK), event_index, timestamp, level,         │   │
│   │   service_name, message, exception_type, exception_message,    │   │
│   │   class_name, method_name, source_file, line_number,           │   │
│   │   stack_trace, created_at                                      │   │
│   │   Index: (log_id, event_index)                                 │   │
│   └───────────────┬────────────────────────────────────────────────┘   │
│                   │ 1                                                  │
│                   │ N (FK parsed_logs.id, ON DELETE CASCADE)           │
│                   ▼                                                    │
│   ┌────────────────────────────────────────────────────────────────┐   │
│   │ incident_events table (Join table):                            │   │
│   │   id (PK), incident_id (FK), parsed_log_id (FK),               │   │
│   │   correlation_signal, confidence, created_at                   │   │
│   │   Unique: (incident_id, parsed_log_id)                         │   │
│   └───────────────▲────────────────────────────────────────────────┘   │
│                   │ N (FK incidents.id, ON DELETE CASCADE)             │
│                   │ 1                                                  │
│   ┌───────────────┴────────────────────────────────────────────────┐   │
│   │ incidents table:                                               │   │
│   │   id (PK), incident_key (UQ), title, status, severity,         │   │
│   │   correlation_type, started_at, detected_at, resolved_at,      │   │
│   │   services_involved (JSONB), correlation_score, metadata (JSONB)│   │
│   └────────────────────────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────────────────────────┘
```

---

## Incident Correlation Architecture & Engine Details

### 1. Correlation Signals and Priority
The engine assesses three deterministic signals in strict priority:

| Signal | Name | Description | Confidence Score | Priority |
| :--- | :--- | :--- | :--- | :--- |
| **Signal A** | **Explicit Correlation ID** | Matches `correlation_id`, `request_id`, `trace_id`, `run_id`, or `session_id` in log messages/traces | `0.95` | **1 (Highest)** |
| **Signal B** | **Temporal Proximity** | Events clustered within a configurable sliding window (`INCIDENT_CORRELATION_WINDOW_SECONDS`, default: 30s) | `0.70` (adjusted by count & proximity) | **2** |
| **Signal C** | **Multi-Service Evidence** | Multiple distinct microservices reporting errors within the temporal window | `0.85` | **3** |

### 2. Isolated Events Rule
- Informational or debugging messages (`INFO`, `DEBUG`, `TRACE`) never trigger an incident on their own.
- Non-error events are included in an incident **if and only if** they share an explicit correlation ID (Signal A) with an active error incident.
- Single-event low-severity logs that lack error indications are ignored to prevent operational alert fatigue.

### 3. Configurable Time Window
- Configured via environment variable:
  - `INCIDENT_CORRELATION_WINDOW_SECONDS=30` (default)
- Implemented in `backend/app/core/config.py` via Pydantic `Settings`.
- Sliding Window Behavior:
  - Events are sorted chronologically by `timestamp`.
  - An open incident cluster window extends as long as consecutive events occur within `window_seconds` of the cluster's active range.
  - If a gap between events exceeds `window_seconds`, the active cluster closes and a new candidate cluster starts.

### 4. Deduplication Strategy (`incident_key`)
- To guarantee idempotency across repeated correlation runs, a deterministic SHA-256 hash is generated for each candidate incident:
  ```python
  incident_key = hashlib.sha256(
      f"inc:{','.join(str(i) for i in sorted(constituent_event_ids))}".encode("utf-8")
  ).hexdigest()
  ```
- Uniqueness is enforced at both:
  - **Database Level**: `UNIQUE INDEX ix_incidents_incident_key ON incidents (incident_key)`
  - **Repository / Service Level**: Checks if `incident_key` already exists. If existing, it marks the cluster as existing without inserting duplicate rows.

### 5. Cascade Behaviors
- `incident_events.incident_id REFERENCES incidents(id) ON DELETE CASCADE`
- `incident_events.parsed_log_id REFERENCES parsed_logs(id) ON DELETE CASCADE`
- Deleting an incident cleans up all incident event associations.
- Deleting a log file cascades through `parsed_logs` down into `incident_events` automatically.

---

## Database Schemas: `incidents` & `incident_events`

Managed via Alembic migration `2026_10_07_0930-516869c13e74_create_incidents_and_incident_events_tables.py`:

```sql
CREATE TABLE incidents (
    id SERIAL PRIMARY KEY,
    incident_key VARCHAR(64) NOT NULL UNIQUE,
    title VARCHAR(255) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'OPEN',
    severity VARCHAR(32) NOT NULL DEFAULT 'HIGH',
    correlation_type VARCHAR(64) NOT NULL,
    started_at TIMESTAMPTZ NOT NULL,
    detected_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    resolved_at TIMESTAMPTZ NULL,
    services_involved JSONB NOT NULL DEFAULT '[]',
    correlation_score DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    metadata JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX ix_incidents_id ON incidents (id);
CREATE UNIQUE INDEX ix_incidents_incident_key ON incidents (incident_key);
CREATE INDEX ix_incidents_status ON incidents (status);
CREATE INDEX ix_incidents_severity ON incidents (severity);
CREATE INDEX ix_incidents_started_at ON incidents (started_at);

CREATE TABLE incident_events (
    id SERIAL PRIMARY KEY,
    incident_id INTEGER NOT NULL REFERENCES incidents(id) ON DELETE CASCADE,
    parsed_log_id INTEGER NOT NULL REFERENCES parsed_logs(id) ON DELETE CASCADE,
    correlation_signal VARCHAR(64) NOT NULL,
    confidence DOUBLE PRECISION NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_incident_parsed_log UNIQUE (incident_id, parsed_log_id)
);

CREATE INDEX ix_incident_events_id ON incident_events (id);
CREATE INDEX ix_incident_events_incident_id ON incident_events (incident_id);
CREATE INDEX ix_incident_events_parsed_log_id ON incident_events (parsed_log_id);
```

---

## Phase 4 Architecture: Incident Context Enrichment

### 1. Objective & Scope

Context Enrichment enriches existing correlated incidents with **REAL operational context** across 6 evidence categories.
The architecture answers:
> *"What additional operational evidence/context is available around this incident?"*

And strictly does **NOT** answer:
> *"What is the root cause?"* (RCA belongs strictly to Phase 5).

### 2. Core Architectural Principle: Truthful Operational Evidence
**NEVER INVENT OPERATIONAL DATA.** If information is not available through current data or a connected external integration, it is never fabricated or simulated.
Availability is explicitly categorized as one of:
- `AVAILABLE`: Real data extracted directly from stored event entities or active database queries.
- `NOT_CONNECTED`: The integration provider is not configured or connected (e.g., Prometheus, Datadog, Kubernetes).
- `UNAVAILABLE`: Data point cannot be derived from current system state.
- `INTEGRATION_REQUIRED`: The feature requires external platform connection (e.g., CI/CD, Git repository).

### 3. Pipeline Position

```text
RAW LOG
   ↓
INGESTION (Phase 1)
   ↓
PARSING (Phase 2)
   ↓
CORRELATION (Phase 3)
   ↓
CONTEXT ENRICHMENT (Phase 4)
   ↓
[PHASE 5] AI ROOT CAUSE ANALYSIS (Strictly Deferred)
```

### 4. Context Enrichment Architecture & Layering

```text
API Router (/api/v1/incidents/{id}/enrich, /context, /context/{category})
   ↓
Service Layer (ContextEnrichmentService)
   ↓
Context Engine & Provider Abstractions:
   ├── ServiceContextProvider (derived from parsed_logs)
   ├── DeploymentContextProvider -> DeploymentProvider (NullDeploymentProvider: INTEGRATION_REQUIRED)
   ├── InfrastructureContextProvider -> InfrastructureProvider (NullInfrastructureProvider: NOT_CONNECTED)
   ├── MetricsContextProvider -> MetricsProvider (NullMetricsProvider: NOT_CONNECTED)
   ├── HistoryContextProvider (derived from real PostgreSQL incidents)
   └── DependencyContextProvider (observed co-occurring services; CORRELATION != CAUSATION)
   ↓
Repository Layer (IncidentContextRepository with upsert & idempotency)
   ↓
Database (incident_contexts table in PostgreSQL)
```

### 5. Context Categories Implemented

1. **Service Context** (`service`):
   - Derived strictly from constituent `parsed_logs` records.
   - Populates `service_name`, `services_involved`, and `service_count`.
   - Explicitly records unverified attributes (`owner`, `team`, `repository`, `runtime`) as `NOT_CONNECTED` / `UNAVAILABLE`.
2. **Deployment Context** (`deployment`):
   - Pluggable `DeploymentProvider` interface (integration-ready for GitHub, GitLab, ArgoCD).
   - In default environment, `NullDeploymentProvider` explicitly reports `INTEGRATION_REQUIRED`.
   - All Git commit, author, and version fields remain `None` without fabrication.
3. **Infrastructure Context** (`infrastructure`):
   - Pluggable `InfrastructureProvider` interface (integration-ready for Kubernetes, Docker, Cloud providers).
   - In default environment, `NullInfrastructureProvider` explicitly reports `NOT_CONNECTED`.
   - Never fabricates fake pods, nodes, or clusters.
4. **Metrics Context** (`metrics`):
   - Pluggable `MetricsProvider` interface (integration-ready for Prometheus, Datadog, APM).
   - In default environment, `NullMetricsProvider` explicitly reports `NOT_CONNECTED`.
   - Never generates synthetic CPU%, memory%, or latency metrics.
5. **Incident History Context** (`history`):
   - Queries actual previous incidents in PostgreSQL sharing constituent services.
   - Derives `previous_occurrence_count`, `previous_incident_ids`, `recurring` bool, and temporal bounds.
6. **Dependency Context** (`dependencies`):
   - Derives observed co-occurring services from incident events.
   - **Correlation is NOT causation**: Causality status is set to `UNVERIFIED` and causal graph is `None`.

### 6. Database Schema: `incident_contexts`

Managed via Alembic migration `2026_10_07_1049-d0fb7f3d3149_create_incident_contexts_table.py`:

```sql
CREATE TABLE incident_contexts (
    id SERIAL PRIMARY KEY,
    incident_id INTEGER NOT NULL REFERENCES incidents(id) ON DELETE CASCADE,
    context_category VARCHAR(64) NOT NULL,
    status VARCHAR(32) NOT NULL,
    data JSONB NOT NULL DEFAULT '{}',
    source VARCHAR(128) NOT NULL,
    collected_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_incident_context_category UNIQUE (incident_id, context_category)
);

CREATE INDEX ix_incident_contexts_id ON incident_contexts (id);
CREATE INDEX ix_incident_contexts_incident_id ON incident_contexts (incident_id);
CREATE INDEX ix_incident_contexts_context_category ON incident_contexts (context_category);
CREATE INDEX ix_incident_contexts_status ON incident_contexts (status);
```

### 7. Idempotency Guarantees
- The `(incident_id, context_category)` unique constraint ensures that repeated calls to `POST /api/v1/incidents/{incident_id}/enrich` refresh existing category records deterministically.
- Direct PostgreSQL inspection confirms exactly 6 rows exist per incident regardless of enrichment execution count.

---

## Phase 5 Architecture: Evidence-Grounded Root Cause Analysis

### 1. Objective & Scope

Phase 5 introduces an AI-assisted Root Cause Analysis (RCA) engine that reasons **ONLY over evidence actually observed in the incident**.
It answers:
> *"What are the most plausible root-cause hypotheses supported by the available evidence?"*

And strictly does **NOT** assert definitive causality without evidence backing.

### 2. Core Architectural Principle: No Hallucinated Operational Evidence
**THE AI MUST NEVER INVENT EVIDENCE.**
- Only context marked `AVAILABLE` is eligible as observed evidence.
- Context marked `NOT_CONNECTED`, `UNAVAILABLE`, or `INTEGRATION_REQUIRED` is strictly excluded from factual evidence claims.
- The system explicitly separates:
  - **OBSERVATION**: Direct facts from logs and exceptions.
  - **INFERENCE**: Contextual deductions from event timing and sequence.
  - **HYPOTHESIS**: Proposed causal explanations.
  - **CONFIRMED ROOT CAUSE**: Strictly guarded and only permitted when corroborating code traces/exceptions prove direction.

### 3. Pipeline Architecture

```text
RAW LOG
   ↓
INGESTION (Phase 1)
   ↓
PARSING (Phase 2)
   ↓
CORRELATION (Phase 3)
   ↓
CONTEXT ENRICHMENT (Phase 4)
   ↓
EVIDENCE PACKAGE BUILDER (RCAEvidenceBuilder)
   ├── Normalizes stable evidence IDs: EVT-<id>, EXC-<id>, ST-<id>, CTX-*
   └── Gathers unavailable contexts into limitations snapshot
   ↓
EVIDENCE PACKAGE VALIDATION
   ├── If 0 events -> INSUFFICIENT_EVIDENCE
   ↓
AI RCA PROVIDER (RCAProvider abstraction)
   ├── MockRCAProvider (deterministic testing only)
   └── LLMRCAProvider (REST HTTP client for OpenAI/Gemini/Anthropic)
   ├── If provider/key unconfigured -> PROVIDER_UNAVAILABLE
   ↓
RCA VALIDATOR (RCAValidator)
   ├── CITED EVIDENCE: Validates every supporting_evidence ID
   ├── CITED SERVICES: Enforces membership in observed incident services
   ├── UNAVAILABLE TELEMETRY: Strips unverified metric/deployment claims
   ├── CAUSAL STATUS: Downgrades uncorroborated CONFIRMED to SUPPORTED/HYPOTHESIS
   └── CONFIDENCE BOUNDING: Bounds confidence deterministically by evidence volume
   ↓
AUDITABLE PERSISTENCE (IncidentRCARepository)
   └── Table: incident_rca_analyses (includes complete evidence_snapshot)
   ↓
API & UI (POST/GET /api/v1/incidents/{id}/rca, /history, /{analysis_id})
```

### 4. Database Schema: `incident_rca_analyses`

Managed via Alembic migration `2026_10_07_1200-e1a2b3c4d5e6_create_incident_rca_analyses_table.py`:

```sql
CREATE TABLE incident_rca_analyses (
    id SERIAL PRIMARY KEY,
    incident_id INTEGER NOT NULL REFERENCES incidents(id) ON DELETE CASCADE,
    analysis_id VARCHAR(64) NOT NULL UNIQUE,
    analysis_status VARCHAR(32) NOT NULL,
    provider VARCHAR(64) NOT NULL,
    model VARCHAR(128) NOT NULL,
    summary TEXT NOT NULL,
    confidence FLOAT NULL,
    confidence_level VARCHAR(32) NULL,
    hypotheses JSONB NOT NULL DEFAULT '[]',
    evidence_snapshot JSONB NOT NULL DEFAULT '{}',
    limitations JSONB NOT NULL DEFAULT '[]',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX ix_incident_rca_analyses_id ON incident_rca_analyses (id);
CREATE INDEX ix_incident_rca_analyses_incident_id ON incident_rca_analyses (incident_id);
CREATE UNIQUE INDEX ix_incident_rca_analyses_analysis_id ON incident_rca_analyses (analysis_id);
CREATE INDEX ix_incident_rca_analyses_analysis_status ON incident_rca_analyses (analysis_status);
CREATE INDEX ix_incident_rca_analyses_created_at ON incident_rca_analyses (created_at);
CREATE INDEX ix_incident_rca_analyses_incident_created ON incident_rca_analyses (incident_id, created_at);
```

### 5. Auditability & Research Trail
Every hypothesis links to normalized evidence IDs (`EVT-`, `EXC-`, `ST-`, `CTX-`) which map directly to constituent database primary keys stored inside the `evidence_snapshot`. This establishes a complete, verifiable audit trail:
```text
RCA Conclusion → Evidence IDs → Parsed Log Event / Context ID → Raw Log Content
```

---

## Data Immutability Guarantees

1. **`logs.raw_content` Immutability**:
   - Ingestion logs are never modified, enriched, or truncated by Phase 2 parsing, Phase 3 correlation, Phase 4 enrichment, or Phase 5 RCA.
2. **`parsed_logs` Immutability**:
   - Structured parsed log records remain read-only during RCA reasoning.
3. **`incident_events` Immutability**:
   - Incident event associations and correlation scoring remain untouched during RCA.
4. **`incident_contexts` Immutability**:
   - Operational context records are strictly read-only during RCA.

---

## Strict Phase 5 Boundary

Phase 5 concludes strictly at:
```text
EVIDENCE PACKAGE → VALIDATED AI REASONING → ROOT-CAUSE HYPOTHESES
```

The following features are **strictly out of scope** and deferred to future phases:
- **Phase 6**: Fix Recommendations & Remediation Runbooks (code patches, rollback actions, config fixes).
- **Phase 7**: Developer Resolution Workflow & Incident Lifecycle Tracking.
- **Phase 8**: Production Hardening & Observability.

---

---

## Phase 6: Evidence-Grounded Investigation & Fix Recommendations

Phase 6 implements an evidence-grounded recommendation engine layered directly on top of validated Phase 5 RCA results.

### 1. Core Principle: Recommendation ≠ Execution
Phase 6 produces actionable, structured operational advice for human engineers. It strictly prohibits automatic execution:
- No shell command or CLI execution (`kubectl`, `systemctl`, `docker`, `rm -rf`, etc.).
- No code modification, Git commit, or Pull Request creation.
- No automated deployments, restarts, or rollback execution.
- No automated database alterations or configuration mutations.
- Permitted recommendation statuses: `PROPOSED`, `REVIEW_REQUIRED`, `DISMISSED` (Status `EXECUTED` is strictly forbidden).

### 2. Recommendation Types
1. **`INVESTIGATION`**: Guidance on logs, boundaries, and dependencies to inspect before changing any system state.
2. **`DIAGNOSTIC_VERIFICATION`**: Diagnostic tests to verify whether a root cause hypothesis is factually correct.
3. **`FIX`**: Potential corrective actions proposed ONLY when supported by verified RCA evidence. Mandatory verification steps required.
4. **`PREVENTION`**: Proactive alerting, monitoring, or architectural guardrails to prevent future incident recurrence.
5. **`VERIFICATION`**: Steps to confirm recovery post-change without causing secondary failures.

### 3. Investigation-First Principle & Safety Guardrails
- **Investigation-First**: When RCA confidence is `LOW` or `MEDIUM`, or hypotheses are `HYPOTHESIS` / `UNVERIFIED`, `FIX` actions are automatically downgraded to `DIAGNOSTIC_VERIFICATION` or `INVESTIGATION`.
- **Insufficient Evidence**: When underlying RCA has `INSUFFICIENT_EVIDENCE`, fix recommendations are strictly prohibited. The system proposes only investigation and telemetry collection steps.
- **No Invented Configuration Values**: Specific numerical configurations (e.g., "set timeout to 30s", "increase memory to 4GB") are forbidden and sanitized into conceptual guidance unless explicitly present in observed evidence.
- **No Invented Numerical Impact**: Fabricated percentage reductions (e.g., "reduce errors by 87%") are replaced with qualitative operational impact statements.
- **Mandatory Verification Steps**: Every `FIX` recommendation must supply concrete verification steps to ensure recovery without cascading degradation.

### 4. Recommendation Provider Abstraction
Decoupled provider abstraction via `RecommendationProvider`:
- `MockRecommendationProvider`: Deterministic recommendations citing real evidence IDs for testing and offline environments.
- `LLMRecommendationProvider`: Production provider communicating over HTTP with OpenAI-compatible / Gemini / Anthropic endpoints using strict JSON schema prompting.
- Fallback: Gracefully returns `PROVIDER_UNAVAILABLE` when no provider or API key is configured.

### 5. Database Schema: `incident_recommendations`
Managed via Alembic migration `2026_10_07_1230-a2b3c4d5e6f7_create_incident_recommendations_table.py`:

```sql
CREATE TABLE incident_recommendations (
    id SERIAL PRIMARY KEY,
    recommendation_id VARCHAR(64) NOT NULL UNIQUE,
    incident_id INTEGER NOT NULL REFERENCES incidents(id) ON DELETE CASCADE,
    rca_analysis_id INTEGER NOT NULL REFERENCES incident_rca_analyses(id) ON DELETE CASCADE,
    type VARCHAR(32) NOT NULL,
    title VARCHAR(255) NOT NULL,
    description TEXT NOT NULL,
    rationale TEXT NOT NULL,
    supporting_evidence JSONB NOT NULL DEFAULT '[]',
    confidence DOUBLE PRECISION NOT NULL,
    confidence_level VARCHAR(16) NOT NULL,
    risk_level VARCHAR(16) NOT NULL DEFAULT 'LOW',
    expected_impact TEXT NOT NULL,
    prerequisites JSONB NOT NULL DEFAULT '[]',
    verification_steps JSONB NOT NULL DEFAULT '[]',
    status VARCHAR(32) NOT NULL DEFAULT 'PROPOSED',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX ix_incident_recommendations_id ON incident_recommendations (id);
CREATE UNIQUE INDEX ix_incident_recommendations_recommendation_id ON incident_recommendations (recommendation_id);
CREATE INDEX ix_incident_recommendations_incident_id ON incident_recommendations (incident_id);
CREATE INDEX ix_incident_recommendations_rca_analysis_id ON incident_recommendations (rca_analysis_id);
CREATE INDEX ix_incident_recommendations_type ON incident_recommendations (type);
CREATE INDEX ix_incident_recommendations_status ON incident_recommendations (status);
CREATE INDEX ix_incident_recommendations_created_at ON incident_recommendations (created_at);
CREATE INDEX ix_incident_recommendations_incident_created ON incident_recommendations (incident_id, created_at);
```

### 6. Research Paper & Auditability Trail
Every recommendation forms an unbroken audit chain tracing back to original log telemetry:
```text
Recommendation → Rationale & Risk → Verification Steps → Supporting Evidence IDs → RCA Hypotheses → Parsed Logs → Raw Log Content
```

---

## Data Immutability Guarantees

1. **`logs.raw_content` Immutability**:
   - Ingestion logs are never modified, enriched, or truncated.
2. **`parsed_logs` Immutability**:
   - Structured parsed log records remain read-only.
3. **`incident_events` Immutability**:
   - Incident event associations and correlation scoring remain untouched.
4. **`incident_contexts` Immutability**:
   - Operational context records are strictly read-only.
5. **`incident_rca_analyses` Immutability**:
   - Previous RCA analyses and evidence snapshots remain untouched.

---

## Phase 7: Developer Investigation & Resolution Workflow Architecture

Phase 7 implements the human-in-the-loop developer investigation workspace and resolution lifecycle.

```text
EVIDENCE PACKAGE → AI RCA → RECOMMENDATIONS → DEVELOPER INVESTIGATION → VERIFICATION → RESOLUTION
```

### Core Architecture & Components

1. **Investigation State & Ownership (`incident_investigations`)**:
   - Manages developer assignment (`assigned_to`, `assigned_to_name`, `assigned_at`).
   - Workflow statuses: `UNASSIGNED`, `ASSIGNED`, `INVESTIGATING`, `READY_FOR_VERIFICATION`, `RESOLVED`, `CLOSED`.
   - Transitions incident from `OPEN` to `INVESTIGATING` automatically upon triage.

2. **Persistent Investigation Notes (`incident_investigation_notes`)**:
   - Captures free-form developer triage notes linked to the incident and active investigation.
   - Strictly validates cited evidence tokens against ground-truth incident data.

3. **External Diagnostic & Investigation Actions (`incident_investigation_actions`)**:
   - Records developer observations, diagnostic checks, config/log/metric reviews, dependency checks, and applied fixes.
   - **RECOMMENDATION ≠ EXECUTION**: The system records the developer's external action; it never executes code, scripts, or cloud commands.

4. **Recommendation Review Layer (`incident_recommendation_reviews`)**:
   - Records developer decisions: `ACCEPTED`, `REJECTED`, `DEFERRED`, `NOT_APPLICABLE`.
   - Requires explicit justification for rejection and deferral.
   - Original recommendations and RCA evidence remain completely immutable.

5. **Strict Evidence Reference Validator (`EvidenceReferenceValidator`)**:
   - Validates tokens (`EVT-*`, `EXC-*`, `ST-*`, `CTX-*`, RCA analysis IDs, recommendation IDs) against the incident's ground-truth evidence graph.
   - Rejects hallucinated tokens with HTTP 400.

6. **Verification Checklist & Gated Resolution (`incident_verification_steps`)**:
   - Checklist items with statuses: `PENDING`, `PASSED`, `FAILED`, `NOT_APPLICABLE`.
   - Resolution rule: ALL required verification steps must be explicitly marked `PASSED` with developer verification notes before incident resolution is permitted.
   - Gated `POST /api/v1/incidents/{id}/resolve` rejects resolution if any required step is pending or failed.
   - Requires developer resolution summary and root-cause confirmation indicator (`CONFIRMED`, `REFUTED`, `UNKNOWN`).

7. **Reopened Incident Lifecycle (`POST /api/v1/incidents/{id}/reopen`)**:
   - Reopens resolved incidents when issues resurface.
   - Clears `resolved_at` and restores status to `INVESTIGATING`.

8. **Audit Timeline (`incident_timeline_events`)**:
   - Chronological audit log capturing all developer actions, assignments, reviews, notes, verification transitions, resolutions, and reopenings.

---

## Roadmap & Phase Boundaries

- **Phase 0 (Complete)**: Modular monolith foundation, database engine, health routes, React client shell.
- **Phase 1 (Complete)**: Real Log Ingestion (Validation, Line Normalization, Hash Deduplication, PostgreSQL Storage, Retrieval API, UI).
- **Phase 2 (Complete)**: Structured Log Extraction & Semantic Parsing (Parser Registry, deterministic text/JSON parsing, stack trace grouping, `parsed_logs` persistence, re-parse idempotency).
- **Phase 3 (Complete)**: Multi-Service Incident Correlation & Deduplication (Sliding window, explicit correlation ID extraction, multi-service error evidence, confidence scoring, `incidents` & `incident_events`).
- **Phase 4 (Complete)**: Real Context Enrichment (Service, deployment, infrastructure, metrics, history, dependencies; explicit provider interfaces; truthful availability; idempotent persistence).
- **Phase 5 (Complete)**: Evidence-Grounded Root Cause Analysis (Deterministic evidence packaging, anti-hallucination validation, role classification, bounded confidence, auditable snapshot, history tracking).
- **Phase 6 (Complete)**: Evidence-Grounded Investigation & Fix Recommendations (Categorized actions, Investigation-First principle, risk and confidence validation, verification steps, PostgreSQL persistence, auditable runs).
- **Phase 7 (Complete)**: Developer Investigation & Resolution Workflow (Active investigation workspace, developer assignment, persistent notes, diagnostic actions, recommendation review, evidence reference validation, verification checklist, gated resolution, reopen lifecycle, audit timeline).
- **Phase 8 (Future)**: Production Hardening, Alerting & Paging.



