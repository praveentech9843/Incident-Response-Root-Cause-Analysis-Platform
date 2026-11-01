# AI-Powered Incident Response & Root Cause Analysis Platform

> **Status: Phase 8 — Production Hardening & Integration-Ready Platform Complete**  
> All phases (Phase 0 Foundation through Phase 8 Production Platform) are verified, tested, and complete.

---

## 1. Project Purpose & Phase Scope

The **AI-Powered Incident Response & Root Cause Analysis Platform** is an enterprise-grade developer incident analysis system.

### Phase 1: Real Log Ingestion Scope
Accept real log files from users, validate syntax and formats, perform safe line-ending normalization, prevent duplicate uploads via deterministic hashing, and reliably persist actual uploaded content in PostgreSQL.

### Phase 2: Structured Log Extraction & Parsing Scope
Transform raw ingested logs into queryable, structured event entities. Uses deterministic parsing logic to extract timestamps, normalized log levels, service identifiers, message bodies, exception classifications, and code-location frames (file, line number, class, method, stack traces) without guessing or AI hallucination. Raw logs from Phase 1 remain strictly immutable.

### Phase 3: Incident Correlation Scope
Analyze structured parsed log events from Phase 2 and deterministically group events belonging to the same operational incident. Leverages explicit correlation/request IDs, configurable temporal proximity windows, and multi-service failure evidence. Persists `incidents` and `incident_events` relationships with deterministic deduplication (`incident_key`). **Strict Principle**: Correlation is NOT causation. Raw logs and parsed logs remain 100% immutable.

### Phase 4: Incident Context Enrichment Scope
Enrich correlated incidents with **real, truthful operational context** across 6 evidence categories (Service, Deployment, Infrastructure, Metrics, History, Dependencies). **Strict Principle: NEVER INVENT OPERATIONAL DATA.** Unconnected systems explicitly return `NOT_CONNECTED`, `UNAVAILABLE`, or `INTEGRATION_REQUIRED`. Synthetic metrics, simulated Git commits, and fake Kubernetes pods are strictly forbidden. Phase 4 answers *"What additional evidence/context is available around this incident?"* and **DOES NOT** perform root cause analysis (RCA belongs strictly to Phase 5). Raw logs, parsed logs, and incident event relationships remain 100% immutable. Repeated enrichments are strictly idempotent.

### Phase 5: Evidence-Grounded Root Cause Analysis Scope
Implement an AI-assisted Root Cause Analysis engine that reasons **ONLY over evidence actually observed in the incident**. Formulates plausible root-cause hypotheses with strict anti-hallucination validation, role classification (`ROOT_CAUSE_CANDIDATE`, `CONTRIBUTING_FACTOR`, `SYMPTOM`), deterministic confidence bounding, and auditable evidence snapshots. Unavailable context is never asserted as factual evidence. Fix recommendations, code patches, and automated remediations are strictly out of scope and deferred to Phase 6+. Raw logs, parsed logs, incident events, and operational contexts remain 100% immutable. Repeated analyses preserve full execution history.

### Phase 6: Evidence-Grounded Investigation & Fix Recommendations Scope
Formulate evidence-grounded operational advice layered directly on top of validated Phase 5 RCA findings. Categorizes recommendations into `INVESTIGATION`, `DIAGNOSTIC_VERIFICATION`, `FIX`, `PREVENTION`, and `VERIFICATION`. **Strict Principle: RECOMMENDATION ≠ EXECUTION.** Automatic actions (shell scripts, `kubectl`, restart, rollback, code patching, PR creation) are strictly prohibited. Enforces the Investigation-First principle, sanitizes invented configuration numbers or percentage claims, enforces mandatory verification steps for every `FIX` recommendation, and persists auditable recommendation history. Prior phases remain 100% immutable.

### Phase 7: Developer Investigation & Resolution Workflow Scope
Establish an active developer investigation workspace with incident ownership/assignment, persistent triage notes, developer-recorded external diagnostic actions (strictly no automatic command execution), Phase 6 recommendation review and decision tracking (`ACCEPTED`, `REJECTED`, `DEFERRED`, `NOT_APPLICABLE`), strict evidence reference validation against incident ground truth, mandatory verification checklist execution, gated incident resolution requiring developer verification and summary, reopened incident lifecycle management, and a persistent audit timeline. All historical logs, parsed logs, incident events, contexts, RCA analyses, and recommendation evidence remain 100% immutable.

**Phase 1 Pipeline:**
```text
Real Log File (.log, .txt, .json)
  → File Validation (Extension, Size, UTF-8 Encoding, JSON Syntax)
  → Safe Normalization (Line Endings \r\n → \n, Null Empty Metadata)
  → Duplicate Check (SHA-256 Content Hash)
  → PostgreSQL Storage (Faithful raw_content preservation)
  → Retrieval API & Live UI
```

---

## 2. Supported File Types & Validation Rules

| Extension | Validation Rules | Normalization Applied |
|---|---|---|
| `.log` | Plain text log file. Must be valid UTF-8. Non-empty. | Line endings converted to `\n`. |
| `.txt` | Plain text log or audit file. Must be valid UTF-8. Non-empty. | Line endings converted to `\n`. |
| `.json` | Valid JSON structure required (`json.loads` check). | Line endings converted to `\n`. Original content preserved faithfully without semantic flattening. |

**Rejected with HTTP 400 Bad Request:**
- Unsupported file extensions (e.g., `.pdf`, `.csv`, `.py`, `.exe`).
- Empty files (0 bytes or only whitespace).
- Files with invalid encoding (non-UTF-8 binary data).
- Malformed JSON syntax in `.json` files.
- Missing or empty filenames.

**Rejected with HTTP 413 Content Too Large:**
- Files exceeding `MAX_LOG_UPLOAD_SIZE_MB` (configurable).

**Rejected with HTTP 409 Conflict:**
- Files whose content hash matches an existing log in the database.

---

## 3. Upload Size Limit Configuration

Configurable via `.env` and application settings (`backend/app/core/config.py`):
```bash
# Maximum uploaded file size in megabytes (default: 10)
MAX_LOG_UPLOAD_SIZE_MB=10
```
This configuration is read through `pydantic-settings` and never hardcoded in the service layer.

---

## 4. Metadata

Users may optionally provide:
- `service_name`: Identifier of the originating service (e.g. `auth-service`).
- `environment`: Deployment environment (`production`, `staging`, `development`, `test`).
- `source_hint`: Log origin hint (e.g. `k8s-pod-stdout`, `syslog`, `systemd`).

*Rule:* If metadata is not provided or contains only whitespace, it is stored as `NULL` in the database. No values are invented or guessed.

---

## 5. Duplicate Upload Protection

- Every ingested file's normalized content generates a deterministic **SHA-256** hash (`content_hash`).
- Table `logs` enforces a unique constraint on `content_hash`.
- Uploading duplicate content returns **HTTP 409 Conflict** with details of the existing log ID and upload timestamp.
- Note: This is log-level deduplication. Incident-level correlation deduplication is deferred to Phase 3.

---

## 6. Database Schema & Migration

### Table: `logs`
Managed via Alembic (`alembic/versions/2026_10_06_2010-f2586f9410e7_create_logs_table.py`):

| Column | Type | Constraints / Modifiers |
|---|---|---|
| `id` | `INTEGER` | Primary Key, Auto-increment, Indexed |
| `original_filename` | `VARCHAR(255)` | Not Null |
| `file_type` | `VARCHAR(32)` | Not Null (`log`, `txt`, `json`) |
| `service_name` | `VARCHAR(128)` | Nullable, Indexed |
| `environment` | `VARCHAR(64)` | Nullable, Indexed |
| `source_hint` | `VARCHAR(255)` | Nullable |
| `raw_content` | `TEXT` | Not Null (faithfully preserved) |
| `content_hash` | `VARCHAR(64)` | Not Null, Unique, Indexed |
| `created_at` | `TIMESTAMPTZ` | Not Null, Default `now()` |

---

## 7. API Endpoints

### 1. `POST /api/v1/logs/upload`
Upload a single raw log file via `multipart/form-data`.

**Form Fields:**
- `file`: File upload (`.log`, `.txt`, `.json`)
- `service_name` *(optional)*: string
- `environment` *(optional)*: string
- `source_hint` *(optional)*: string

**Response (`201 Created`):**
```json
{
  "id": 1,
  "original_filename": "auth_service.log",
  "file_type": "log",
  "service_name": "auth-service",
  "environment": "production",
  "source_hint": "k8s-pod-stdout",
  "content_hash": "6c9c7e467f0290e07b540dc43b7fdf287fb261354af88be039b485776ff94bfb",
  "created_at": "2026-10-06T14:59:04.315816+00:00",
  "is_duplicate": false,
  "message": "Log file uploaded and stored successfully."
}
```

### 2. `GET /api/v1/logs`
Retrieve paginated list of actual uploaded logs from PostgreSQL.

**Query Parameters:**
- `limit` (default: 50, max: 100)
- `offset` (default: 0)

**Response (`200 OK`):**
```json
{
  "items": [
    {
      "id": 1,
      "original_filename": "auth_service.log",
      "file_type": "log",
      "service_name": "auth-service",
      "environment": "production",
      "source_hint": "k8s-pod-stdout",
      "content_hash": "6c9c7e46...",
      "created_at": "2026-10-06T14:59:04.315816+00:00",
      "content_length": 348
    }
  ],
  "total": 1,
  "limit": 50,
  "offset": 0
}
```

### 3. `GET /health` & `GET /api/v1/health`
Health check endpoints returning backend status and timestamp.

---

## 8. Phase 2: Structured Log Extraction & Semantic Parsing

### 1. Phase 2 Purpose
Phase 2 transforms stored, raw log text from Phase 1 into structured, queryable log event records persisted in the `parsed_logs` PostgreSQL table. All parsing operates deterministically through regular expressions, string parsing, and JSON decoders without AI, LLM reasoning, or external network calls. Raw logs remain 100% immutable.

### 2. Log Parsing API: `POST /api/v1/logs/{log_id}/parse`
Triggers deterministic parsing of a raw log file by ID.

**Query Parameters:**
- `reparse` (boolean, default: `false`): If `true`, deletes previously extracted events for this log in a single transaction and re-parses from scratch. If `false` and the log has already been parsed, returns the existing structured events without duplication.

**Response (`200 OK`):**
```json
{
  "log_id": 128,
  "status": "SUCCESS",
  "event_count": 2,
  "parser_used": "text_log_parser",
  "events": [
    {
      "id": 1,
      "log_id": 128,
      "event_index": 0,
      "timestamp": "2026-10-06T12:00:01Z",
      "level": "ERROR",
      "service_name": "InventoryService",
      "message": "InventoryService: NullPointerException [run:24e99444]",
      "exception_type": "NullPointerException",
      "exception_message": null,
      "class_name": "InventoryService",
      "method_name": "reserve",
      "source_file": "InventoryService.java",
      "line_number": 65,
      "stack_trace": "    at InventoryService.reserve(InventoryService.java:65)\n    at OrderService.create(OrderService.java:120)",
      "created_at": "2026-10-07T03:44:33.120000Z"
    },
    {
      "id": 2,
      "log_id": 128,
      "event_index": 1,
      "timestamp": "2026-10-06T12:00:05Z",
      "level": "INFO",
      "service_name": "OrderService",
      "message": "OrderService: Order #9821 processed successfully",
      "exception_type": null,
      "exception_message": null,
      "class_name": null,
      "method_name": null,
      "source_file": null,
      "line_number": null,
      "stack_trace": null,
      "created_at": "2026-10-07T03:44:33.125000Z"
    }
  ]
}
```

### 3. Parsed Log Retrieval API: `GET /api/v1/logs/{log_id}/parsed`
Retrieves all structured events previously parsed from the specified log, ordered chronologically by `event_index`.

**Response (`200 OK`):**
```json
{
  "log_id": 128,
  "total": 2,
  "events": [ /* list of ParsedLogEvent */ ]
}
```

### 4. Supported Text Parsing
`TextLogParser` parses plain text formats line-by-line:
- **Timestamp Extraction**: ISO-8601 (`2026-10-06T12:00:01Z`, `2026-10-06 12:00:01,123`), bracketed timestamps (`[2026-10-06 12:00:01]`).
- **Log Level Normalization**: `DEBUG`, `INFO`, `WARN` (from `WARNING` or `WARN`), `ERROR`, `CRITICAL`, `FATAL`, `TRACE`.
- **Service Name Extraction**: Extracted from log header prefixes (e.g. `auth-service:`, `[InventoryService]`), falling back to upload metadata if absent in the log text.
- **Message Body**: Clean extracted message text with timestamp, level, and service prefixes stripped.

### 5. Multi-line Stack Trace Parsing
- **Grouping**: Consecutive stack trace lines (indented with whitespace or starting with `at ` / `File `) are collapsed into the preceding log event rather than generating spurious separate events.
- **Java Traces**: Matches `at package.Class.method(File.java:line)` frames to extract `source_file`, `line_number`, `class_name`, `method_name`, and `exception_type`.
- **Python Tracebacks**: Matches `File "path/file.py", line 42, in method_name` frames to extract code location and trailing exception classes (`KeyError`, `ValueError`, etc.).

### 6. JSON Log Parsing
`JsonLogParser` handles JSON objects, JSON arrays, and Newline-Delimited JSON (NDJSON):
- Supported field aliases:
  - Timestamp: `timestamp`, `time`, `@timestamp`, `ts`, `datetime`, `date`
  - Level: `level`, `severity`, `log_level`, `status`, `lvl`
  - Service: `service`, `service_name`, `app`, `application`, `component`
  - Message: `message`, `msg`, `log`, `text`, `description`, `event`
  - Exception: `exception_type`, `error_type`, `exception`, `error`, `err_type`
  - Code Location: `source_file`, `file`, `filename`, `line_number`, `line`, `lineno`, `class_name`, `method_name`
  - Stack Trace: `stack_trace`, `stack`, `traceback`, `exc_info` (string or array of lines)

### 7. Field Extraction & Unknown Field Handling
- Every extracted field has an explicit type.
- **Strict Rule for Missing/Unknown Fields**: Any field that is absent or unparseable from the log is stored as `NULL` in PostgreSQL and returned as `null` in JSON. No placeholder or synthetic values are ever invented.

### 8. Re-parsing and Idempotency Behavior
- **Default Parse (`reparse=false`)**: If structured events already exist for the log ID, the API returns the existing records with status `"ALREADY_PARSED"`. No duplicate rows are created in `parsed_logs`.
- **Forced Re-parse (`reparse=true`)**: Deletes existing records for that `log_id` and executes fresh extraction within the same database transaction.
- **Foreign Key Cascade**: Deleting a record from `logs` automatically cascades to delete all associated records in `parsed_logs` via `ON DELETE CASCADE`.

### 9. Database Schema: `parsed_logs` Table
Managed via Alembic migration (`2026_10_06_2047-5a2cc3d50bc3_create_parsed_logs_table.py`):

| Column | Type | Constraints / Modifiers |
|---|---|---|
| `id` | `INTEGER` | Primary Key, Auto-increment, Indexed |
| `log_id` | `INTEGER` | Foreign Key (`logs.id` ON DELETE CASCADE), Not Null, Indexed |
| `event_index` | `INTEGER` | Not Null, Indexed (order of event within file) |
| `timestamp` | `TIMESTAMPTZ` | Nullable, Indexed |
| `level` | `VARCHAR(32)` | Nullable, Indexed |
| `service_name` | `VARCHAR(128)` | Nullable, Indexed |
| `message` | `TEXT` | Not Null |
| `exception_type` | `VARCHAR(128)` | Nullable |
| `exception_message` | `TEXT` | Nullable |
| `class_name` | `VARCHAR(255)` | Nullable |
| `method_name` | `VARCHAR(128)` | Nullable |
| `source_file` | `VARCHAR(255)` | Nullable |
| `line_number` | `INTEGER` | Nullable |
| `stack_trace` | `TEXT` | Nullable |
| `created_at` | `TIMESTAMPTZ` | Not Null, Default `now()` |

*Composite Index*: `ix_parsed_logs_log_id_event_index` on `(log_id, event_index)`.

---

## 9. Phase 3: Incident Correlation

### 1. Phase 3 Purpose
Phase 3 takes structured parsed log events from Phase 2 and determines which events belong to the same operational incident.
```text
Real Logs → Phase 1 (Ingestion) → Phase 2 (Parsing) → Structured Log Events → Phase 3 (Correlation) → Incidents + Incident/Event Relationships
```

**Core Question Answered**: *"Which parsed log events belong to the same incident?"*

> [!IMPORTANT]
> **Correlation is NOT Causation.**
> Phase 3 identifies correlated incident event groups based on empirical evidence. It strictly does **NOT** determine root causes, designate any service as "root cause" or "root service", or generate AI recommendations.

### 2. Correlation Signals & Priority
All correlation operations are 100% deterministic, explainable, and rule-based without AI inference:

1. **Signal A — Explicit Correlation / Request / Trace ID (Highest Priority)**:
   - Matches common correlation tokens (`request_id`, `correlation_id`, `trace_id`, `transaction_id`, `[run:...]`, `[req:...]`).
   - Events sharing the same identifier are strongly correlated (confidence: `0.95`).
2. **Signal B — Temporal Proximity**:
   - Events occurring within a configurable sliding window are correlated together.
   - Configured via `INCIDENT_CORRELATION_WINDOW_SECONDS=30` (default: 30 seconds).
3. **Signal C — Multi-Service Failure Evidence**:
   - Multiple distinct services experiencing errors within the active correlation window are grouped into a cross-service incident.
   - Title generation reflects participating services without asserting causality: `"Correlated errors across InventoryService, Redis, PaymentService"`.
4. **Signal D — Isolated Events Rule**:
   - Informational and debug events (`INFO`, `DEBUG`) never independently initiate an incident.
   - An `INFO` event is only included in an incident if it shares an explicit correlation ID with an eligible error event.

### 3. Incident Key & Deduplication Strategy
- Every correlated group computes a deterministic SHA-256 `incident_key` from its sorted constituent event IDs.
- Running correlation multiple times over unchanged events reuses existing incidents without creating duplicates:
  - First run: `incidents_created: 1, incidents_existing: 0`
  - Subsequent runs: `incidents_created: 0, incidents_existing: 1`

### 4. Database Schema: `incidents` & `incident_events`
Managed via Alembic migration (`2026_10_07_0930-516869c13e74_create_incidents_and_incident_events_.py`):

#### Table: `incidents`
| Column | Type | Constraints / Modifiers |
|---|---|---|
| `id` | `INTEGER` | Primary Key, Auto-increment, Indexed |
| `incident_key` | `VARCHAR(64)` | Unique, Not Null, Indexed |
| `title` | `VARCHAR(255)` | Not Null |
| `status` | `VARCHAR(32)` | Not Null, Default `'OPEN'`, Indexed |
| `started_at` | `TIMESTAMPTZ` | Nullable, Indexed |
| `ended_at` | `TIMESTAMPTZ` | Nullable, Indexed |
| `event_count` | `INTEGER` | Not Null, Default `0` |
| `service_count` | `INTEGER` | Not Null, Default `0` |
| `correlation_reason` | `TEXT` | Not Null |
| `correlation_confidence` | `FLOAT` | Nullable |
| `created_at` | `TIMESTAMPTZ` | Not Null, Default `now()` |
| `updated_at` | `TIMESTAMPTZ` | Not Null, Default `now()` |

#### Table: `incident_events` (Many-to-Many Relationship)
| Column | Type | Constraints / Modifiers |
|---|---|---|
| `id` | `INTEGER` | Primary Key, Auto-increment, Indexed |
| `incident_id` | `INTEGER` | Foreign Key (`incidents.id` ON DELETE CASCADE), Not Null, Indexed |
| `parsed_log_id` | `INTEGER` | Foreign Key (`parsed_logs.id` ON DELETE CASCADE), Not Null, Indexed |
| `event_index` | `INTEGER` | Not Null, Indexed (chronological position) |
| `created_at` | `TIMESTAMPTZ` | Not Null, Default `now()` |

*Constraints*: `UNIQUE (incident_id, parsed_log_id)`, compound index on `(incident_id, event_index)`.

### 5. Phase 3 API Endpoints

#### `POST /api/v1/incidents/correlate`
Executes deterministic correlation over candidate parsed events.
- **Optional Request Body**:
  ```json
  {
    "log_id": 128,
    "time_window_seconds": 30
  }
  ```
- **Response (`200 OK`)**:
  ```json
  {
    "events_considered": 4,
    "incidents_created": 1,
    "incidents_existing": 0,
    "incidents": [
      {
        "id": 1,
        "incident_key": "9d7fe6c663442f48fcf8478a69e8de1590d451edee0dbdcd3c470190b6616015",
        "title": "Correlated errors across InventoryService, PaymentService, Redis",
        "status": "OPEN",
        "started_at": "2026-10-06T12:00:01Z",
        "ended_at": "2026-10-06T12:00:08Z",
        "event_count": 3,
        "service_count": 3,
        "correlation_reason": "Events share explicit correlation ID 'e2e-123' across 3 services (InventoryService, PaymentService, Redis).",
        "correlation_confidence": 0.95,
        "created_at": "2026-10-07T04:18:20.120Z",
        "updated_at": "2026-10-07T04:18:20.120Z"
      }
    ]
  }
  ```

#### `GET /api/v1/incidents`
Returns paginated list of real correlated incidents from PostgreSQL.
- Query parameters: `status` (`OPEN` / `RESOLVED`), `limit`, `offset`.

#### `GET /api/v1/incidents/{incident_id}`
Returns incident details with chronologically sorted constituent parsed events.

---

## 10. Phase 4: Operational Context Enrichment

### 1. Architectural Objective
Context Enrichment adds truthful, operational evidence to a correlated incident across 6 categories.
It answers:
> *"What additional operational context surrounds this incident?"*

And strictly does **NOT** answer:
> *"What is the root cause?"* (RCA is strictly Phase 5).

### 2. Core Rule: Never Invent Operational Data
If data is not physically present in the system or provided by a live connected provider, it is **never** fabricated.
Availability is explicitly classified as:
- `AVAILABLE`: Real data derived from constituent parsed logs or active PostgreSQL tables.
- `NOT_CONNECTED`: Integration provider is not connected (e.g. Prometheus, Datadog, Kubernetes).
- `UNAVAILABLE`: Information is not present in the ingested event data.
- `INTEGRATION_REQUIRED`: Requires external platform connection (e.g. CI/CD / Git).

### 3. Context Categories Implemented
1. **Service Context** (`service`):
   - Derived strictly from constituent `parsed_logs` entries.
   - Extracts `service_name`, `services_involved`, `service_count`.
   - Explicitly records `owner`, `team`, `repository`, `runtime` as `NOT_CONNECTED` or `UNAVAILABLE`.
2. **Deployment Context** (`deployment`):
   - Backed by extensible `DeploymentProvider` interface.
   - `NullDeploymentProvider` explicitly reports `INTEGRATION_REQUIRED`.
   - Never fabricates Git commits, authors, or version tags.
3. **Infrastructure Context** (`infrastructure`):
   - Backed by extensible `InfrastructureProvider` interface.
   - `NullInfrastructureProvider` explicitly reports `NOT_CONNECTED`.
   - Never fabricates fake Kubernetes pods, nodes, or clusters.
4. **Metrics Context** (`metrics`):
   - Backed by extensible `MetricsProvider` interface.
   - `NullMetricsProvider` explicitly reports `NOT_CONNECTED`.
   - Never fabricates synthetic CPU%, memory%, or latency values.
5. **Incident History Context** (`history`):
   - Queries real stored incidents in PostgreSQL sharing constituent services.
   - Populates `previous_occurrence_count`, `previous_incident_ids`, `recurring` bool, and temporal bounds.
6. **Dependency Context** (`dependencies`):
   - Derives observed co-occurring services from incident events.
   - Preserves **Correlation is NOT causation**: Causality status is set to `UNVERIFIED` and `causal_graph` is `None`.

### 4. Database Schema: `incident_contexts`
Managed via Alembic migration (`2026_10_07_1049-d0fb7f3d3149_create_incident_contexts_table.py`):

| Column | Type | Constraints / Modifiers |
|---|---|---|
| `id` | `INTEGER` | Primary Key, Auto-increment, Indexed |
| `incident_id` | `INTEGER` | Foreign Key (`incidents.id` ON DELETE CASCADE), Not Null, Indexed |
| `context_category` | `VARCHAR(64)` | Not Null, Indexed (`service`, `deployment`, `infrastructure`, `metrics`, `history`, `dependencies`) |
| `status` | `VARCHAR(32)` | Not Null, Indexed (`AVAILABLE`, `NOT_CONNECTED`, `UNAVAILABLE`, `INTEGRATION_REQUIRED`) |
| `data` | `JSONB` | Not Null, Default `'{}'` |
| `source` | `VARCHAR(128)` | Not Null |
| `collected_at` | `TIMESTAMPTZ` | Not Null, Default `now()` |
| `created_at` | `TIMESTAMPTZ` | Not Null, Default `now()` |
| `updated_at` | `TIMESTAMPTZ` | Not Null, Default `now()` |

*Constraint*: `UNIQUE (incident_id, context_category)` guarantees deterministic upsert and prevents duplicate rows on repeated enrichment requests.

### 5. Phase 4 API Endpoints

#### `POST /api/v1/incidents/{incident_id}/enrich`
Runs context enrichment across all 6 categories and persists the result idempotently.
- **Response (`200 OK`)**:
  ```json
  {
    "incident_id": 228,
    "incident_title": "Correlated errors across CheckoutService, NotificationService, PaymentGateway",
    "total_categories": 6,
    "contexts": {
      "service": { "status": "AVAILABLE", "data": { "services_involved": ["CheckoutService", "PaymentGateway"], ... } },
      "deployment": { "status": "INTEGRATION_REQUIRED", "data": { "git_commit": null, "deployment_version": null, ... } },
      "infrastructure": { "status": "NOT_CONNECTED", "data": { "cluster": null, "pods": [], ... } },
      "metrics": { "status": "NOT_CONNECTED", "data": { "cpu_usage": null, "memory_usage": null, ... } },
      "history": { "status": "AVAILABLE", "data": { "previous_occurrence_count": 2, "recurring": true, ... } },
      "dependencies": { "status": "AVAILABLE", "data": { "causality_status": "UNVERIFIED", "services_involved": [...] } }
    },
    "collected_at": "2026-10-07T06:12:33Z"
  }
  ```

#### `GET /api/v1/incidents/{incident_id}/context`
Returns all enriched operational context categories for the incident.

#### `GET /api/v1/incidents/{incident_id}/context/{category}`
Returns an individual context category (e.g. `service`, `deployment`, `infrastructure`, `metrics`, `history`, `dependencies`). Returns `404 Not Found` if category is invalid or incident does not exist.

---

## 11. Phase 5: Evidence-Grounded Root Cause Analysis

### 1. Architectural Objective
The Phase 5 RCA engine evaluates the controlled evidence package (logs, stack traces, exceptions, operational contexts) to generate evidence-backed hypotheses.
It answers:
> *"What are the most plausible root-cause hypotheses supported by the available evidence?"*

And strictly does **NOT** assert:
> *"What definitely caused this incident?"* without independent, verified causal proof.

### 2. Core Anti-Hallucination & Validation Rules
- **NEVER INVENT EVIDENCE**: Only context marked `AVAILABLE` is eligible as observed evidence.
- **SEPARATE CONCEPTS**:
  - `OBSERVATION`: Verified facts from logs and exceptions.
  - `INFERENCE`: Deductions from event ordering.
  - `HYPOTHESIS`: Proposed causal explanations.
  - `CONFIRMED ROOT CAUSE`: Strictly guarded; requires explicit exception/stack trace corroboration.
- **EVIDENCE CITATION VALIDATION**: Every cited `supporting_evidence` ID (e.g. `EVT-1`, `EXC-1`, `ST-1`, `CTX-*`) must exist in the observed evidence package. Unobserved or fake IDs are stripped.
- **UNAVAILABLE CONTEXT GUARD**: Claims asserting numerical metric values or Git commit details when metrics/deployments are `NOT_CONNECTED` or `INTEGRATION_REQUIRED` are flagged and rejected.
- **CONFIDENCE BOUNDING**: Confidence scores are deterministically bounded based on evidence count, consistency, and causal support.

### 3. Provider Abstraction
- `RCAProvider`: Pluggable interface (`analyze(evidence_package) -> RCAResult`).
- `MockRCAProvider`: Deterministic provider for automated testing and verifiable offline execution.
- `LLMRCAProvider`: Lightweight REST client communicating over `httpx` to any OpenAI-compatible API, Anthropic, or Gemini endpoint without vendor lock-in.
- Graceful degradation: If no provider or API key is configured, returns `analysis_status: "PROVIDER_UNAVAILABLE"` without fabricating analysis.

### 4. Database Schema: `incident_rca_analyses`
Managed via Alembic migration (`2026_10_07_1200-e1a2b3c4d5e6_create_incident_rca_analyses_table.py`):

| Column | Type | Constraints / Modifiers |
|---|---|---|
| `id` | `INTEGER` | Primary Key, Auto-increment, Indexed |
| `incident_id` | `INTEGER` | Foreign Key (`incidents.id` ON DELETE CASCADE), Not Null, Indexed |
| `analysis_id` | `VARCHAR(64)` | Unique, Not Null, Indexed (`rca-<uuid>`) |
| `analysis_status` | `VARCHAR(32)` | Not Null, Indexed (`COMPLETED`, `INSUFFICIENT_EVIDENCE`, `PROVIDER_UNAVAILABLE`, `FAILED`) |
| `provider` | `VARCHAR(64)` | Not Null (`mock`, `llm`, etc.) |
| `model` | `VARCHAR(128)` | Not Null (`mock-rca-v1`, `gpt-4o-mini`, etc.) |
| `summary` | `TEXT` | Not Null |
| `confidence` | `FLOAT` | Nullable |
| `confidence_level` | `VARCHAR(32)` | Nullable (`LOW`, `MEDIUM`, `HIGH`) |
| `hypotheses` | `JSONB` | Not Null, Default `'[]'` |
| `evidence_snapshot` | `JSONB` | Not Null, Default `'{}'` (Complete package for research/audit trail) |
| `limitations` | `JSONB` | Not Null, Default `'[]'` |
| `created_at` | `TIMESTAMPTZ` | Not Null, Default `now()`, Indexed |
| `updated_at` | `TIMESTAMPTZ` | Not Null, Default `now()` |

### 5. Phase 5 API Endpoints

#### `POST /api/v1/incidents/{incident_id}/rca`
Runs evidence-grounded root cause analysis and stores an auditable analysis record.
- **Response (`200 OK`)**:
  ```json
  {
    "id": 1,
    "incident_id": 375,
    "analysis_id": "rca-f825f2fc50f6",
    "analysis_status": "COMPLETED",
    "provider": "mock",
    "model": "mock-rca-v1",
    "summary": "Identified 2 evidence-supported hypothesis(es) across 3 service(s). Primary candidate: AuthService Error State.",
    "confidence": 0.80,
    "confidence_level": "HIGH",
    "hypotheses": [
      {
        "hypothesis_id": "HYP-1",
        "title": "AuthService Error State",
        "description": "Earliest observed failure was recorded in AuthService.",
        "confidence": 0.70,
        "confidence_level": "MEDIUM",
        "supporting_evidence": ["EVT-1213"],
        "contradicting_evidence": [],
        "reasoning": "Log event EVT-1213 shows error message: 'Failed to validate token from session cache'",
        "causal_status": "HYPOTHESIS",
        "role": "ROOT_CAUSE_CANDIDATE"
      }
    ],
    "evidence_snapshot": { ... },
    "limitations": [
      "Metrics telemetry is NOT_CONNECTED; cannot verify runtime metrics state.",
      "Deployment telemetry is INTEGRATION_REQUIRED; cannot verify runtime deployment state."
    ],
    "created_at": "2026-10-07T06:42:50Z",
    "updated_at": "2026-10-07T06:42:50Z"
  }
  ```

#### `GET /api/v1/incidents/{incident_id}/rca`
Returns the latest RCA analysis generated for the incident.

#### `GET /api/v1/incidents/{incident_id}/rca/history`
Returns all previous RCA analyses executed for the incident in descending chronological order.

#### `GET /api/v1/incidents/{incident_id}/rca/{analysis_id}`
Returns a specific historical RCA analysis by its unique `analysis_id`.

#### `POST /api/v1/incidents/{incident_id}/recommendations`
Generates evidence-grounded investigation and fix recommendations strictly grounded on the latest validated RCA analysis.
- **Precondition**: A completed Phase 5 RCA analysis must exist for the incident (returns `409 Conflict` otherwise).
- **Response (`200 OK`)**: List of `IncidentRecommendationResponse` objects:
  ```json
  [
    {
      "id": 1,
      "incident_id": 375,
      "analysis_id": 42,
      "recommendation_id": "REC-f825f2fc50f6-1",
      "type": "INVESTIGATION",
      "status": "PROPOSED",
      "title": "Verify session cache connectivity for AuthService",
      "description": "Investigate session cache availability and latency.",
      "justification": "Root cause candidate indicates session cache failure.",
      "supporting_evidence": ["EVT-1213"],
      "confidence": 0.80,
      "confidence_level": "HIGH",
      "risk_level": "LOW",
      "verification_steps": ["Check session cache ping response"],
      "limitations": ["Metrics telemetry is NOT_CONNECTED"],
      "created_at": "2026-10-07T08:50:00Z"
    }
  ]
  ```

#### `GET /api/v1/incidents/{incident_id}/recommendations`
Returns the latest generated batch of recommendations for the incident.

#### `GET /api/v1/incidents/{incident_id}/recommendations/history`
Returns all historical recommendation runs grouped by batch for the incident.

#### `GET /api/v1/incidents/{incident_id}/recommendations/{recommendation_id}`
Returns a single recommendation by its unique `recommendation_id`.

---

## 12. Technology Stack

| Layer | Technologies |
|---|---|
| **Backend** | Python 3.12+, FastAPI, Pydantic v2, Pydantic Settings, Uvicorn |
| **Database & ORM** | PostgreSQL 16, SQLAlchemy 2.0, Alembic |
| **Frontend** | React 19, TypeScript, Vite, Lucide Icons |
| **Testing** | Pytest, Pytest-Asyncio, HTTPX |
| **Architecture** | Modular Monolith with Provider Abstractions, Safety & Evidence Validation |

---

## 13. Setup & Running Instructions

### 1. Database Migrations
Run Alembic migrations to apply all migrations up to head (`logs`, `parsed_logs`, `incidents`, `incident_events`, `incident_contexts`, `incident_rca_analyses`, `incident_recommendations`):
```bash
cd backend
.venv\Scripts\alembic upgrade head
```

### 2. Running Automated Tests
Run the comprehensive test suite (125 automated test cases covering Phase 0 through Phase 6):
```bash
cd backend
.venv\Scripts\pytest -v
```

### 3. Running Phase 6 E2E Verification
Execute the 27-step end-to-end verification script against running FastAPI and PostgreSQL:
```bash
python verify_phase6_e2e.py
# or from backend:
cd backend
.venv\Scripts\python verify_phase6_e2e.py
```

### 4. Starting the Backend Server
```bash
cd backend
.venv\Scripts\uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
- API Documentation: `http://localhost:8000/api/v1/docs`

### 5. Starting the Frontend Client
```bash
cd frontend
npm run dev
```
- Frontend UI: `http://localhost:5173`

---

---

## 15. Phase 7: Developer Investigation & Resolution Workflow

Phase 7 implements the human-in-the-loop developer investigation and incident resolution lifecycle:

```text
EVIDENCE PACKAGE → AI RCA → RECOMMENDATIONS → DEVELOPER INVESTIGATION → VERIFICATION → RESOLUTION
```

### Core Architecture & Capabilities

1. **Active Investigation Workspace (`incident_investigations`)**:
   - Manages workflow state: `UNASSIGNED`, `ASSIGNED`, `INVESTIGATING`, `READY_FOR_VERIFICATION`, `RESOLVED`, `CLOSED`.
   - Links to incident ownership: `assigned_to`, `assigned_to_name`, `assigned_at`.
   - Automatic incident status transition: `OPEN` → `INVESTIGATING`.

2. **Persistent Investigation Notes (`incident_investigation_notes`)**:
   - Persistent developer notes with optional evidence token citations (`EVT-*`, `EXC-*`, `ST-*`, `CTX-*`).
   - Rejects empty content and non-existent evidence tokens.

3. **External Investigation Actions (`incident_investigation_actions`)**:
   - Records developer observations, diagnostic checks, config/log/metric reviews, and applied fixes.
   - **RECOMMENDATION ≠ EXECUTION**: The system records the action; it NEVER executes shell commands, code modifications, or infrastructure operations.

4. **Recommendation Review Layer (`incident_recommendation_reviews`)**:
   - Developers track decisions: `ACCEPTED`, `REJECTED`, `DEFERRED`, `NOT_APPLICABLE`.
   - Requires explicit justification for rejection/deferral.
   - Original Phase 6 recommendations and RCA evidence remain completely immutable.

5. **Strict Evidence Reference Validator (`EvidenceReferenceValidator`)**:
   - Validates all references against ground-truth incident events, parsed logs, exceptions, stack traces, context categories, RCA analysis IDs, and recommendation IDs.
   - Rejects fabricated/hallucinated evidence tokens with HTTP 400.

6. **Verification Checklist & Gated Resolution (`incident_verification_steps`)**:
   - Developer-defined checklist items: `PENDING`, `PASSED`, `FAILED`, `NOT_APPLICABLE`.
   - Minimum resolution condition: ALL required verification steps must be marked `PASSED` with developer-supplied results.
   - Rejects resolution with HTTP 400 if any required step is pending or failed.
   - Requires developer resolution summary and root-cause confirmation indicator (`CONFIRMED`, `REFUTED`, `UNKNOWN`).

7. **Reopened Incident Lifecycle (`POST /api/v1/incidents/{id}/reopen`)**:
   - Safely reopens resolved incidents with mandatory reason.
   - Clears `resolved_at` and restores status to `INVESTIGATING`.

8. **Audit Timeline (`incident_timeline_events`)**:
   - Chronological audit trail tracking assignments, status transitions, notes, actions, reviews, verification updates, resolution, and reopen events.

### Phase 7 Boundary Confirmation

The following capabilities are **explicitly NOT implemented** in Phase 7:
- Automated remediation / auto-patching / Git commits / Pull Requests
- Automated CLI or Kubernetes execution
- PagerDuty, Slack, email alerting or notification systems (Phase 8)
- Enterprise authentication redesign (Phase 8+)

---

## 13. Phase 8 — Production Hardening & Integration-Ready Platform

### Architectural Overview

Phase 8 elevates the platform from an authenticated prototype into a hardened, integration-ready operational control center. All core non-negotiable principles established across Phases 0–7 remain strictly frozen and immutable:
- **Historical Immutability**: Raw log bytes, SHA-256 content hashes, parsed events, correlated incidents, operational contexts, RCA hypotheses, recommendations, and investigation decisions remain strictly immutable.
- **Real Operational Data Only**: No synthetic or fabricated external integration data. Unconfigured external providers truthfully report `NOT_CONNECTED`, `UNAVAILABLE`, or `INTEGRATION_REQUIRED`.
- **RECOMMENDATION ≠ EXECUTION**: Operational advice is never automatically executed. Developers retain complete human-in-the-loop decision agency.

```text
                                    ┌────────────────────────┐
                                    │      React + Vite      │
                                    │    Role-Aware UI       │
                                    └───────────┬────────────┘
                                                │ Bearer JWT + X-Request-ID
                                                ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                                FastAPI Gateway & Middleware                            │
│  - X-Request-ID Tracking   - Centralized Exception Handler   - Audit Log Interceptor   │
└───────────────────────────────────────┬────────────────────────────────────────────────┘
                                        │
             ┌──────────────────────────┼──────────────────────────┐
             ▼                          ▼                          ▼
┌─────────────────────────┐  ┌─────────────────────┐  ┌────────────────────────┐
│ Authentication & RBAC   │  │ External Integrator │  │ Alerting & Dispatch    │
│ - Argon2 Hashing        │  │ - GitHub Actions    │  │ - Dedup Key Engine     │
│ - JWT Tokens            │  │ - GitHub (Read-Only)│  │ - Slack Provider       │
│ - ADMIN, DEV, VIEWER    │  │ - Kubernetes        │  │ - PagerDuty Provider   │
│ - Identity Derivation   │  │ - Prometheus        │  │ - SMTP Email Provider  │
└─────────────────────────┘  └─────────────────────┘  └────────────────────────┘
             │                          │                          │
             └──────────────────────────┼──────────────────────────┘
                                        │
                                        ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                              PostgreSQL Persistent Storage                             │
│  users | security_audit_logs | incident_alert_rules | incident_alerts                  │
│  incident_notifications | background_jobs | logs | parsed_logs | incidents ...        │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

### Key Capabilities & Security Controls

1. **Authentication & RBAC (Argon2 + JWT)**:
   - Passwords hashed using memory-hard Argon2 (`argon2-cffi`).
   - Stateless JWT tokens (`access_token`, `refresh_token`) with role claims.
   - Enforced roles:
     - `ADMIN`: Full system administration, user management, audit trail inspection, alert rule creation.
     - `DEVELOPER`: Ingestion, correlation, enrichment, RCA generation, investigation actions, resolution.
     - `VIEWER`: Read-only access across incidents, RCA, and telemetry. Strictly forbidden (HTTP 403) from resolving incidents, creating notes, or recording actions.
   - **Identity Derivation**: All acting identities (`author`, `assigned_to`, `resolved_by`, `reopened_by`) are strictly derived from the authenticated token claims on the server. Client-side identity spoofing in request bodies is completely neutralized.

2. **Real External Integration Architecture**:
   - `DeploymentProvider`: Queries GitHub Actions workflow runs. Strictly `NOT_CONNECTED` when credentials are absent.
   - `SourceControlProvider`: Queries GitHub commits, PRs, and diffs strictly read-only. Write/push/merge methods do not exist.
   - `InfrastructureProvider`: Inspects Kubernetes pod health without fabricating fake cluster records.
   - `MetricsProvider`: PromQL queries against Prometheus with truthful `NOT_CONNECTED` fallback.

3. **Alerting & Notification Deduplication Engine**:
   - Deterministic alert deduplication: `dedup_key = sha256(incident_id + alert_rule_id + notification_type)`.
   - Re-evaluations never create duplicate alert entries or duplicate notification dispatches.
   - Bounded retries (maximum 3 attempts) with persistent delivery state tracking (`QUEUED`, `SENT`, `FAILED`, `NOT_CONNECTED`).

4. **Observability, Health & Reliability**:
   - `X-Request-ID` propagation middleware: Accepts client correlation ID or automatically injects a UUID into response headers and audit events.
   - Health probes:
     - `GET /health/live`: Process liveness check.
     - `GET /health/ready`: Database connectivity check without leaking passwords or sensitive environment variables.
   - Append-only `security_audit_logs` capturing authentication events, assignments, resolutions, and reviews.

5. **Frontend Role-Aware Experience**:
   - Automatic JWT bearer injection across API requests.
   - Role-aware badge and navigation (Integrations, Alerts, Security Audit trail).
   - Read-only banner and action disabling for `VIEWER` users.
   - Interactive integration probes testing live provider connectivity without page reloads.

### Verification Status

- **Unit & Integration Tests**: **176 of 176 pytest tests passed (100%)**
- **End-to-End Verification**: **22 of 22 steps in `verify_phase8_e2e.py` passed (100%)**
- **Frontend Code Quality**: **0 oxlint warnings/errors**, clean Vite production build.



