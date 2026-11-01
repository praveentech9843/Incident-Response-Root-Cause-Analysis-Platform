import React, { useState, useEffect, useRef, useCallback } from "react";
import { uploadLog, fetchLogs, parseLog } from "../services/api";
import type { LogListItem, LogUploadResponse, ParseLogResponse } from "../services/api";

const ALLOWED_EXTENSIONS = [".log", ".txt", ".json"];
const MAX_SIZE_BYTES = 10 * 1024 * 1024; // 10MB

export const LiveLogsPage: React.FC = () => {
  // Form input state
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [serviceName, setServiceName] = useState<string>("" );
  const [environment, setEnvironment] = useState<string>("production");
  const [sourceHint, setSourceHint] = useState<string>("");

  // Upload execution state
  const [isUploading, setIsUploading] = useState<boolean>(false);
  const [uploadProgress, setUploadProgress] = useState<number | null>(null);
  const [uploadSuccess, setUploadSuccess] = useState<LogUploadResponse | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);

  // Drag and drop state
  const [isDragging, setIsDragging] = useState<boolean>(false);

  // Logs list state
  const [logs, setLogs] = useState<LogListItem[]>([]);
  const [logsLoading, setLogsLoading] = useState<boolean>(true);
  const [logsError, setLogsError] = useState<string | null>(null);

  // Phase 2: Parsed Events viewer state
  const [activeLogId, setActiveLogId] = useState<number | null>(null);
  const [activeLogFilename, setActiveLogFilename] = useState<string>("");
  const [parsingLogId, setParsingLogId] = useState<number | null>(null);
  const [parseResult, setParseResult] = useState<ParseLogResponse | null>(null);
  const [parseLoading, setParseLoading] = useState<boolean>(false);
  const [parseError, setParseError] = useState<string | null>(null);
  const [expandedTraces, setExpandedTraces] = useState<Record<number, boolean>>({});

  const fileInputRef = useRef<HTMLInputElement | null>(null);

  // Common file validation routine used by both file picker and drag-drop
  const validateAndSetFile = useCallback((file: File) => {
    setUploadSuccess(null);
    setUploadError(null);
    setUploadProgress(null);

    const ext = "." + file.name.split(".").pop()?.toLowerCase();
    if (!ALLOWED_EXTENSIONS.includes(ext)) {
      setUploadError(
        `Unsupported file type "${file.name}". Supported file types: ${ALLOWED_EXTENSIONS.join(", ")}`
      );
      setSelectedFile(null);
      if (fileInputRef.current) fileInputRef.current.value = "";
      return;
    }

    if (file.size === 0) {
      setUploadError(`File "${file.name}" is empty (0 bytes). Please select a non-empty file.`);
      setSelectedFile(null);
      if (fileInputRef.current) fileInputRef.current.value = "";
      return;
    }

    if (file.size > MAX_SIZE_BYTES) {
      setUploadError(
        `File "${file.name}" exceeds the maximum allowed upload limit of 10MB (${(file.size / (1024 * 1024)).toFixed(2)} MB).`
      );
      setSelectedFile(null);
      if (fileInputRef.current) fileInputRef.current.value = "";
      return;
    }

    setSelectedFile(file);
  }, []);

  // Fetch recent uploaded logs from backend
  const loadLogs = useCallback(async () => {
    setLogsLoading(true);
    setLogsError(null);
    try {
      const response = await fetchLogs(50, 0);
      setLogs(response.items);
    } catch (err: unknown) {
      setLogsError(err instanceof Error ? err.message : "Failed to load logs from database.");
    } finally {
      setLogsLoading(false);
    }
  }, []);

  useEffect(() => {
    let isMounted = true;
    fetchLogs(50, 0)
      .then((response) => {
        if (isMounted) {
          setLogs(response.items);
          setLogsLoading(false);
        }
      })
      .catch((err) => {
        if (isMounted) {
          setLogsError(err instanceof Error ? err.message : "Failed to load logs from database.");
          setLogsLoading(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, []);

  // Handle file input change
  const handleFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      validateAndSetFile(e.target.files[0]);
    }
  };

  // Drag and drop event handlers
  const handleDragOver = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);

    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      validateAndSetFile(e.dataTransfer.files[0]);
    }
  };

  // Perform upload
  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedFile) {
      setUploadError("Please select a valid log file before uploading.");
      return;
    }

    setIsUploading(true);
    setUploadProgress(0);
    setUploadError(null);
    setUploadSuccess(null);

    try {
      const result = await uploadLog({
        file: selectedFile,
        service_name: serviceName,
        environment: environment,
        source_hint: sourceHint,
        onProgress: (percent) => {
          setUploadProgress(percent);
        },
      });

      setUploadSuccess(result);
      setSelectedFile(null);
      if (fileInputRef.current) fileInputRef.current.value = "";
      // Refresh the real database records
      await loadLogs();
    } catch (err: unknown) {
      setUploadError(err instanceof Error ? err.message : "Upload encountered an error.");
      setUploadProgress(null);
    } finally {
      setIsUploading(false);
    }
  };

  // Trigger Phase 2 parsing / viewing
  const handleParseLog = async (logItem: LogListItem, reparse: boolean = false) => {
    setActiveLogId(logItem.id);
    setActiveLogFilename(logItem.original_filename);
    setParsingLogId(logItem.id);
    setParseLoading(true);
    setParseError(null);

    try {
      const result = await parseLog(logItem.id, reparse);
      setParseResult(result);
      // Reset expanded trace states
      setExpandedTraces({});
    } catch (err: unknown) {
      setParseError(err instanceof Error ? err.message : "Failed to parse log.");
      setParseResult(null);
    } finally {
      setParseLoading(false);
      setParsingLogId(null);
    }
  };

  const toggleStackTrace = (eventId: number) => {
    setExpandedTraces((prev) => ({
      ...prev,
      [eventId]: !prev[eventId],
    }));
  };

  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
  };

  const formatDate = (isoString: string): string => {
    try {
      const d = new Date(isoString);
      return d.toLocaleString();
    } catch {
      return isoString;
    }
  };

  const getLevelBadgeClass = (level: string | null): string => {
    if (!level) return "badge-level-null";
    const upper = level.toUpperCase();
    switch (upper) {
      case "ERROR":
      case "CRITICAL":
      case "FATAL":
        return "badge-level-error";
      case "WARN":
      case "WARNING":
        return "badge-level-warn";
      case "INFO":
        return "badge-level-info";
      case "DEBUG":
        return "badge-level-debug";
      default:
        return "badge-level-other";
    }
  };

  const getStatusBadgeClass = (status: string): string => {
    switch (status) {
      case "SUCCESS":
        return "badge-status-success";
      case "PARTIAL":
        return "badge-status-partial";
      case "UNSUPPORTED_FORMAT":
        return "badge-status-unsupported";
      default:
        return "badge-status-other";
    }
  };

  return (
    <div className="live-logs-page">
      <div className="page-header">
        <h2>Live Logs & Deterministic Parsing</h2>
        <p className="page-description">
          Upload raw log files into PostgreSQL and parse them deterministically into structured log events.
          Supports standard text logs, multi-line stack traces, and JSON/NDJSON telemetry.
        </p>
      </div>

      <div className="ingestion-grid">
        {/* Upload Form Card */}
        <section className="card upload-card">
          <h3 className="card-title">Upload Log File</h3>

          <form onSubmit={handleUpload} className="upload-form">
            {/* Drag & Drop / File Picker Zone */}
            <div
              className={`dropzone ${isDragging ? "dropzone-active" : ""} ${selectedFile ? "dropzone-selected" : ""}`}
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
              onClick={() => fileInputRef.current?.click()}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept=".log,.txt,.json,text/plain,application/json"
                style={{ display: "none" }}
                onChange={handleFileInputChange}
              />

              <div className="dropzone-icon">
                <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                  <polyline points="17 8 12 3 7 8" />
                  <line x1="12" y1="3" x2="12" y2="15" />
                </svg>
              </div>

              {selectedFile ? (
                <div className="selected-file-info">
                  <span className="file-name">{selectedFile.name}</span>
                  <span className="file-meta">
                    {formatFileSize(selectedFile.size)} • {selectedFile.name.split(".").pop()?.toUpperCase()}
                  </span>
                  <button
                    type="button"
                    className="btn-link change-file-btn"
                    onClick={(e) => {
                      e.stopPropagation();
                      fileInputRef.current?.click();
                    }}
                  >
                    Change file
                  </button>
                </div>
              ) : (
                <div className="dropzone-text">
                  <span className="dropzone-primary">Click to select or drag & drop log file</span>
                  <span className="dropzone-secondary">Supported formats: .log, .txt, .json (Max 10MB)</span>
                </div>
              )}
            </div>

            {/* Metadata Fields */}
            <div className="form-row">
              <div className="form-group">
                <label htmlFor="serviceName">Service Name</label>
                <input
                  id="serviceName"
                  type="text"
                  placeholder="e.g. InventoryService, auth-api"
                  value={serviceName}
                  onChange={(e) => setServiceName(e.target.value)}
                  disabled={isUploading}
                />
              </div>

              <div className="form-group">
                <label htmlFor="environment">Environment</label>
                <select
                  id="environment"
                  value={environment}
                  onChange={(e) => setEnvironment(e.target.value)}
                  disabled={isUploading}
                >
                  <option value="production">production</option>
                  <option value="staging">staging</option>
                  <option value="development">development</option>
                  <option value="test">test</option>
                </select>
              </div>
            </div>

            <div className="form-group">
              <label htmlFor="sourceHint">Source Hint</label>
              <input
                id="sourceHint"
                type="text"
                placeholder="e.g. k8s-stdout, systemd, syslog, lambda"
                value={sourceHint}
                onChange={(e) => setSourceHint(e.target.value)}
                disabled={isUploading}
              />
            </div>

            {/* Real Progress Bar */}
            {isUploading && uploadProgress !== null && (
              <div className="progress-container">
                <div className="progress-header">
                  <span>Uploading to server...</span>
                  <span>{uploadProgress}%</span>
                </div>
                <div className="progress-track">
                  <div className="progress-fill" style={{ width: `${uploadProgress}%` }} />
                </div>
              </div>
            )}

            {/* Error Banner */}
            {uploadError && (
              <div className="alert alert-error" role="alert">
                <div className="alert-header">
                  <strong>Upload Error</strong>
                </div>
                <p className="alert-message">{uploadError}</p>
              </div>
            )}

            {/* Success Banner */}
            {uploadSuccess && (
              <div className="alert alert-success" role="status">
                <div className="alert-header">
                  <strong>Upload Successful</strong>
                </div>
                <p className="alert-message">
                  Log <strong>#{uploadSuccess.id}</strong> ({uploadSuccess.original_filename}) persisted in PostgreSQL.
                </p>
                <div className="alert-details">
                  <span>Hash: <code>{uploadSuccess.content_hash.slice(0, 16)}...</code></span>
                  <span>Type: <code>{uploadSuccess.file_type}</code></span>
                  {uploadSuccess.service_name && <span>Service: <code>{uploadSuccess.service_name}</code></span>}
                  {uploadSuccess.environment && <span>Env: <code>{uploadSuccess.environment}</code></span>}
                </div>
              </div>
            )}

            {/* Submit Button */}
            <div className="form-actions">
              <button
                type="submit"
                className="btn btn-primary"
                disabled={isUploading || !selectedFile}
              >
                {isUploading ? "Uploading..." : "Upload & Ingest Log"}
              </button>
            </div>
          </form>
        </section>

        {/* Database Stored Logs List */}
        <section className="card logs-list-card">
          <div className="card-header-row">
            <div>
              <h3 className="card-title">Recent Ingested Logs</h3>
              <p className="card-subtitle">Real records stored in PostgreSQL</p>
            </div>
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              onClick={loadLogs}
              disabled={logsLoading}
              title="Refresh logs from database"
            >
              {logsLoading ? "Refreshing..." : "Refresh"}
            </button>
          </div>

          {logsLoading && logs.length === 0 && (
            <div className="empty-state">
              <p>Loading log records from PostgreSQL...</p>
            </div>
          )}

          {logsError && (
            <div className="alert alert-error">
              <strong>Database Query Error:</strong>
              <p>{logsError}</p>
            </div>
          )}

          {!logsLoading && !logsError && logs.length === 0 && (
            <div className="empty-state">
              <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                <rect x="3" y="3" width="18" height="18" rx="2" />
                <path d="M7 8h10M7 12h10M7 16h6" />
              </svg>
              <p className="empty-title">No log records yet</p>
              <p className="empty-subtitle">Upload a .log, .txt, or .json file above to persist real telemetry.</p>
            </div>
          )}

          {logs.length > 0 && (
            <div className="table-responsive">
              <table className="logs-table">
                <thead>
                  <tr>
                    <th>ID</th>
                    <th>Filename</th>
                    <th>Type</th>
                    <th>Service</th>
                    <th>Env</th>
                    <th>Characters</th>
                    <th>Uploaded At</th>
                    <th>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {logs.map((item) => {
                    const isSelected = activeLogId === item.id;
                    const isCurrentlyParsing = parsingLogId === item.id;
                    return (
                      <tr key={item.id} className={isSelected ? "row-active" : ""}>
                        <td className="log-id">#{item.id}</td>
                        <td className="log-filename" title={item.original_filename}>
                          {item.original_filename}
                        </td>
                        <td>
                          <span className={`badge badge-${item.file_type}`}>
                            {item.file_type}
                          </span>
                        </td>
                        <td>{item.service_name || <span className="text-muted">—</span>}</td>
                        <td>{item.environment || <span className="text-muted">—</span>}</td>
                        <td className="numeric-cell">{item.content_length.toLocaleString()}</td>
                        <td className="timestamp-cell">{formatDate(item.created_at)}</td>
                        <td>
                          <button
                            type="button"
                            className="btn btn-action-parse"
                            onClick={() => handleParseLog(item, false)}
                            disabled={isCurrentlyParsing || parseLoading}
                            title="Extract structured log events deterministically"
                          >
                            {isCurrentlyParsing ? "Parsing..." : isSelected && parseResult ? "View / Reparse" : "Parse"}
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </div>

      {/* Phase 2: Structured Log Events Section */}
      <section className="card parsed-events-card">
        <div className="card-header-row parsed-header-row">
          <div>
            <h3 className="card-title">
              {activeLogId ? (
                <>
                  Structured Events for Log <span className="highlight-id">#{activeLogId}</span>
                  {activeLogFilename && <span className="filename-sub"> ({activeLogFilename})</span>}
                </>
              ) : (
                "Structured Log Events"
              )}
            </h3>
            <p className="card-subtitle">
              {activeLogId
                ? "Deterministically extracted fields persisted in PostgreSQL parsed_logs table"
                : "Select any log above and click 'Parse' to extract timestamp, level, service, message, and stack trace"}
            </p>
          </div>

          {activeLogId && parseResult && (
            <div className="parsed-header-actions">
              <span className={`badge ${getStatusBadgeClass(parseResult.status)}`}>
                {parseResult.status}
              </span>
              <span className="badge badge-parser-used">
                {parseResult.parser_used}
              </span>
              <span className="badge badge-event-count">
                {parseResult.event_count} {parseResult.event_count === 1 ? "event" : "events"}
              </span>
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                onClick={() => {
                  const logItem = logs.find((l) => l.id === activeLogId);
                  if (logItem) handleParseLog(logItem, true);
                }}
                disabled={parseLoading}
                title="Force re-parsing of raw log content (idempotent replacement)"
              >
                {parseLoading ? "Re-parsing..." : "Re-parse"}
              </button>
              <button
                type="button"
                className="btn-icon-close"
                onClick={() => {
                  setActiveLogId(null);
                  setParseResult(null);
                  setParseError(null);
                }}
                title="Close structured view"
              >
                ✕
              </button>
            </div>
          )}
        </div>

        {parseLoading && (
          <div className="empty-state">
            <p>Parsing raw log content into structured events...</p>
          </div>
        )}

        {parseError && (
          <div className="alert alert-error">
            <strong>Parsing Error:</strong>
            <p className="alert-message">{parseError}</p>
          </div>
        )}

        {!parseLoading && !activeLogId && (
          <div className="empty-state">
            <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
              <polyline points="14 2 14 8 20 8" />
              <line x1="16" y1="13" x2="8" y2="13" />
              <line x1="16" y1="17" x2="8" y2="17" />
              <line x1="10" y1="9" x2="8" y2="9" />
            </svg>
            <p className="empty-title">No log selected for parsing</p>
            <p className="empty-subtitle">
              Click the "Parse" button on any ingested log in the table above to view its structured representation.
            </p>
          </div>
        )}

        {!parseLoading && activeLogId && parseResult && parseResult.events.length === 0 && (
          <div className="empty-state">
            <p className="empty-title">0 structured events found</p>
            <p className="empty-subtitle">The selected log could not be parsed into events.</p>
          </div>
        )}

        {!parseLoading && activeLogId && parseResult && parseResult.events.length > 0 && (
          <div className="table-responsive">
            <table className="parsed-events-table">
              <thead>
                <tr>
                  <th style={{ width: "40px" }}>#</th>
                  <th style={{ width: "170px" }}>Timestamp</th>
                  <th style={{ width: "85px" }}>Level</th>
                  <th style={{ width: "130px" }}>Service</th>
                  <th>Message</th>
                  <th style={{ width: "160px" }}>Exception / Error</th>
                  <th style={{ width: "170px" }}>Source Location</th>
                </tr>
              </thead>
              <tbody>
                {parseResult.events.map((event) => (
                  <React.Fragment key={event.id}>
                    <tr>
                      <td className="event-index-cell">#{event.event_index}</td>
                      <td className="timestamp-cell">
                        {event.timestamp ? (
                          formatDate(event.timestamp)
                        ) : (
                          <span className="field-null">NULL</span>
                        )}
                      </td>
                      <td>
                        {event.level ? (
                          <span className={`badge ${getLevelBadgeClass(event.level)}`}>
                            {event.level}
                          </span>
                        ) : (
                          <span className="field-null">NULL</span>
                        )}
                      </td>
                      <td>
                        {event.service_name ? (
                          <span className="service-name-text">{event.service_name}</span>
                        ) : (
                          <span className="field-null">NULL</span>
                        )}
                      </td>
                      <td className="message-cell">
                        <div className="message-text">{event.message}</div>
                        {event.stack_trace && (
                          <button
                            type="button"
                            className="btn-toggle-trace"
                            onClick={() => toggleStackTrace(event.id)}
                          >
                            {expandedTraces[event.id] ? "Hide Stack Trace ▲" : "View Stack Trace ▼"}
                          </button>
                        )}
                      </td>
                      <td>
                        {event.exception_type ? (
                          <div className="exception-info">
                            <span className="exception-type-badge">{event.exception_type}</span>
                            {event.exception_message && (
                              <div className="exception-msg-text" title={event.exception_message}>
                                {event.exception_message}
                              </div>
                            )}
                          </div>
                        ) : (
                          <span className="field-null">NULL</span>
                        )}
                      </td>
                      <td className="source-location-cell">
                        {event.source_file ? (
                          <div className="source-location-info">
                            <code className="source-file">
                              {event.source_file}
                              {event.line_number !== null ? `:${event.line_number}` : ""}
                            </code>
                            {(event.class_name || event.method_name) && (
                              <div className="method-info">
                                {event.class_name && <span>{event.class_name}.</span>}
                                {event.method_name && <span>{event.method_name}()</span>}
                              </div>
                            )}
                          </div>
                        ) : (
                          <span className="field-null">NULL</span>
                        )}
                      </td>
                    </tr>
                    {event.stack_trace && expandedTraces[event.id] && (
                      <tr className="stack-trace-row">
                        <td colSpan={7}>
                          <div className="stack-trace-container">
                            <div className="stack-trace-header">
                              <span>Full Stack Trace</span>
                              <button
                                type="button"
                                className="btn-link"
                                onClick={() => toggleStackTrace(event.id)}
                              >
                                Close
                              </button>
                            </div>
                            <pre className="stack-trace-pre">{event.stack_trace}</pre>
                          </div>
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
};

export default LiveLogsPage;
