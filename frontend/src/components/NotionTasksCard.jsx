import { useState, useEffect, useCallback, useImperativeHandle } from "react";
import {
  fetchNotionTasks,
  fetchNotionStatus,
  createNotionMeetingNotes,
  fetchNotionTaskDetails,
} from "../services/api";

export default function NotionTasksCard({
  ref,
  compact = false,
  onTaskSelect,
  initialRefresh = true,
}) {
  const [tasks, setTasks] = useState([]);
  const [loading, setLoading] = useState(initialRefresh);
  const [error, setError] = useState(null);
  const [statusInfo, setStatusInfo] = useState(null);
  const [statusFilter, setStatusFilter] = useState("ALL");

  // Meeting notes creator state
  const [showNotesModal, setShowNotesModal] = useState(false);
  const [notesTitle, setNotesTitle] = useState("");
  const [notesContent, setNotesContent] = useState("");
  const [creatingNotes, setCreatingNotes] = useState(false);
  const [notesSuccess, setNotesSuccess] = useState(null);
  const [notesError, setNotesError] = useState(null);

  // Task details modal state
  const [selectedTask, setSelectedTask] = useState(null);
  const [taskDetails, setTaskDetails] = useState(null);
  const [loadingDetails, setLoadingDetails] = useState(false);
  const [detailsError, setDetailsError] = useState(null);
  const [showDetailsModal, setShowDetailsModal] = useState(false);

  const handleRefresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [tasksRes, statusRes] = await Promise.all([
        fetchNotionTasks(),
        fetchNotionStatus().catch(() => null),
      ]);
      setTasks(tasksRes?.tasks || []);
      if (statusRes) {
        setStatusInfo(statusRes);
      }
    } catch (err) {
      console.error("Failed to load Notion tasks:", err);
      setError(err.message || "Failed to communicate with Notion MCP server.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let ignore = false;
    if (initialRefresh) {
      Promise.all([
        fetchNotionTasks(),
        fetchNotionStatus().catch(() => null),
      ])
        .then(([tasksRes, statusRes]) => {
          if (!ignore) {
            setTasks(tasksRes?.tasks || []);
            if (statusRes) {
              setStatusInfo(statusRes);
            }
            setLoading(false);
          }
        })
        .catch((err) => {
          if (!ignore) {
            console.error("Failed to load Notion tasks:", err);
            setError(err.message || "Failed to communicate with Notion MCP server.");
            setLoading(false);
          }
        });
    }

    return () => {
      ignore = true;
    };
  }, [initialRefresh]);

  const handleCreateMeetingNotes = async (e) => {
    e.preventDefault();
    if (!notesTitle.trim() || creatingNotes) return;

    setCreatingNotes(true);
    setNotesError(null);
    setNotesSuccess(null);

    try {
      const res = await createNotionMeetingNotes({
        title: notesTitle.trim(),
        content: notesContent.trim(),
        icon: "📝",
      });
      setNotesSuccess({
        message: res.message || "Meeting notes page created successfully in Notion.",
        url: res.page_url,
      });
      setNotesTitle("");
      setNotesContent("");
    } catch (err) {
      setNotesError(err.message || "Failed to create meeting notes in Notion.");
    } finally {
      setCreatingNotes(false);
    }
  };

  const handleTaskClick = async (task) => {
    if (!task) return;
    setSelectedTask(task);
    setShowDetailsModal(true);
    setLoadingDetails(true);
    setDetailsError(null);
    setTaskDetails(null);

    // Call optional callback if provided
    if (onTaskSelect) {
      try {
        onTaskSelect(task);
      } catch (err) {
        console.error("onTaskSelect handler error:", err);
      }
    }

    try {
      const details = await fetchNotionTaskDetails(task.id);
      setTaskDetails(details);
    } catch (err) {
      console.error("Failed to load task details from Notion MCP:", err);
      setDetailsError(err.message || "Failed to retrieve task details from Notion MCP.");
    } finally {
      setLoadingDetails(false);
    }
  };

  useImperativeHandle(ref, () => ({
    openTask: (task) => handleTaskClick(task),
  }));

  const filteredTasks = tasks.filter((t) => {
    if (statusFilter === "ALL") return true;
    return (t.status || "").toLowerCase().replace(/\s+/g, "") === statusFilter.toLowerCase().replace(/\s+/g, "");
  });

  const getPriorityBadgeClass = (priority) => {
    const p = (priority || "").toLowerCase();
    if (p.includes("high")) return "badge-prio-high";
    if (p.includes("med")) return "badge-prio-med";
    if (p.includes("low")) return "badge-prio-low";
    return "badge-prio-default";
  };

  const getStatusBadgeClass = (status) => {
    const s = (status || "").toLowerCase();
    if (s.includes("progress")) return "badge-status-progress";
    if (s.includes("done") || s.includes("complete")) return "badge-status-done";
    if (s.includes("not started")) return "badge-status-todo";
    return "badge-status-default";
  };

  return (
    <div className={`notion-tasks-container ${compact ? "notion-tasks-compact" : ""}`}>
      {/* Header bar */}
      <div className="notion-tasks-header">
        <div className="notion-header-left">
          <div className="notion-logo-badge" aria-hidden="true">
            <svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor">
              <path d="M4 4.5A2.5 2.5 0 0 1 6.5 2h11A2.5 2.5 0 0 1 20 4.5v15a2.5 2.5 0 0 1-2.5 2.5h-11A2.5 2.5 0 0 1 4 19.5v-15zM6.5 3.5A1 1 0 0 0 5.5 4.5v15a1 1 0 0 0 1 1h11a1 1 0 0 0 1-1v-15a1 1 0 0 0-1-1h-11z" />
              <path d="M8 7h8v1.5H8zm0 4h8v1.5H8zm0 4h5v1.5H8z" />
            </svg>
          </div>
          <div>
            <h3 className="notion-tasks-title">Notion Tasks</h3>
            <span className="notion-tasks-subtitle">
              {statusInfo?.authenticated ? "Connected seamlessly to your workspace" : "Daily Tasks Database"}
            </span>
          </div>
        </div>

        <div className="notion-header-actions">
          {!compact && (
            <button
              type="button"
              className="notion-action-btn btn-secondary"
              onClick={() => {
                setShowNotesModal(true);
                setNotesSuccess(null);
                setNotesError(null);
              }}
              title="Create new meeting notes in Notion"
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="14" height="14">
                <path d="M12 5v14M5 12h14" />
              </svg>
              <span>New Meeting Note</span>
            </button>
          )}

          <button
            type="button"
            className={`notion-refresh-btn ${loading ? "refreshing" : ""}`}
            onClick={handleRefresh}
            disabled={loading}
            aria-label="Refresh tasks from Notion"
            title="Refresh tasks from Notion"
          >
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              width="15"
              height="15"
              className={loading ? "spin-animation" : ""}
            >
              <path d="M23 4v6h-6" />
              <path d="M1 20v-6h6" />
              <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15" />
            </svg>
            <span>{loading ? "Refreshing..." : "Refresh"}</span>
          </button>
        </div>
      </div>

      {/* Filter Chips (if not compact) */}
      {!compact && tasks.length > 0 && (
        <div className="notion-filter-bar">
          <div className="filter-chips-group">
            {[
              { id: "ALL", label: `All (${tasks.length})` },
              { id: "In Progress", label: "In Progress" },
              { id: "Not Started", label: "Not Started" },
              { id: "Done", label: "Done" },
            ].map((chip) => (
              <button
                key={chip.id}
                type="button"
                className={`filter-chip ${statusFilter === chip.id ? "active" : ""}`}
                onClick={() => setStatusFilter(chip.id)}
              >
                {chip.label}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Error state */}
      {error && (
        <div className="notion-error-banner" role="alert">
          <div className="notion-error-icon">⚠️</div>
          <div className="notion-error-text">
            <strong>Error connecting to Notion MCP:</strong> {error}
          </div>
          <button type="button" className="notion-retry-btn" onClick={handleRefresh}>
            Retry
          </button>
        </div>
      )}

      {/* Loading Skeleton */}
      {loading && tasks.length === 0 && (
        <div className="notion-loading-list" aria-label="Loading tasks from Notion">
          {[1, 2, 3].map((n) => (
            <div key={n} className="notion-task-skeleton">
              <div className="skeleton-line skeleton-title" />
              <div className="skeleton-badges">
                <div className="skeleton-badge" />
                <div className="skeleton-badge" />
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Tasks List */}
      {!loading && tasks.length === 0 && !error && (
        <div className="notion-empty-tasks">
          <div className="notion-empty-icon">📋</div>
          <p className="notion-empty-title">No tasks found</p>
          <p className="notion-empty-subtitle">Your Notion Daily Tasks database has no pending tasks.</p>
        </div>
      )}

      {tasks.length > 0 && (
        <div className="notion-tasks-list" role="list">
          {filteredTasks.map((task) => (
            <div
              key={task.id || task.name}
              className="notion-task-card"
              role="button"
              tabIndex={0}
              onClick={() => handleTaskClick(task)}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  handleTaskClick(task);
                }
              }}
            >
              <div className="notion-task-main">
                <div className="notion-task-title-row">
                  <h4 className="notion-task-name">{task.name || "Untitled Task"}</h4>
                  {task.url && (
                    <a
                      href={task.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="notion-link-external"
                      title="Open in Notion"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="13" height="13">
                        <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
                        <polyline points="15 3 21 3 21 9" />
                        <line x1="10" y1="14" x2="21" y2="3" />
                      </svg>
                    </a>
                  )}
                </div>

                <div className="notion-task-metadata">
                  {/* Status Badge */}
                  <span className={`task-badge ${getStatusBadgeClass(task.status)}`}>
                    <span className="badge-indicator-dot" />
                    {task.status || "Unknown"}
                  </span>

                  {/* Priority Badge */}
                  {task.priority && (
                    <span className={`task-badge ${getPriorityBadgeClass(task.priority)}`}>
                      Priority: {task.priority}
                    </span>
                  )}

                  {/* Due Date */}
                  <span className="task-due-date">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="13" height="13" aria-hidden="true">
                      <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
                      <line x1="16" y1="2" x2="16" y2="6" />
                      <line x1="8" y1="2" x2="8" y2="6" />
                      <line x1="3" y1="10" x2="21" y2="10" />
                    </svg>
                    <span>{task.due_date ? `Due: ${task.due_date}` : "No due date"}</span>
                  </span>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Meeting Notes Creation Modal / Form */}
      {showNotesModal && (
        <div className="notion-modal-overlay" onClick={() => setShowNotesModal(false)}>
          <div className="notion-modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="notion-modal-header">
              <div className="notion-modal-title-group">
                <span className="notion-modal-icon">📝</span>
                <h4>Create Meeting Notes in Notion</h4>
              </div>
              <button
                type="button"
                className="notion-modal-close"
                onClick={() => setShowNotesModal(false)}
                aria-label="Close modal"
              >
                &times;
              </button>
            </div>

            <form onSubmit={handleCreateMeetingNotes} className="notion-modal-form">
              <div className="form-group">
                <label htmlFor="notes-title">Title *</label>
                <input
                  id="notes-title"
                  type="text"
                  placeholder="e.g. Q4 Strategy & Architecture Review"
                  value={notesTitle}
                  onChange={(e) => setNotesTitle(e.target.value)}
                  required
                  disabled={creatingNotes}
                />
              </div>

              <div className="form-group">
                <label htmlFor="notes-content">Content (Markdown)</label>
                <textarea
                  id="notes-content"
                  rows={5}
                  placeholder="## Discussion Points&#10;- Action items&#10;- Milestones"
                  value={notesContent}
                  onChange={(e) => setNotesContent(e.target.value)}
                  disabled={creatingNotes}
                />
              </div>

              {notesError && (
                <div className="modal-alert alert-error">
                  <span>❌ {notesError}</span>
                </div>
              )}

              {notesSuccess && (
                <div className="modal-alert alert-success">
                  <span>✅ {notesSuccess.message}</span>
                  {notesSuccess.url && (
                    <a
                      href={notesSuccess.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="modal-link-notion"
                    >
                      Open in Notion &rarr;
                    </a>
                  )}
                </div>
              )}

              <div className="notion-modal-actions">
                <button
                  type="button"
                  className="btn-cancel"
                  onClick={() => setShowNotesModal(false)}
                  disabled={creatingNotes}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="btn-primary"
                  disabled={creatingNotes || !notesTitle.trim()}
                >
                  {creatingNotes ? "Creating Page..." : "Create in Notion"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Task Details Modal (Direct from Notion MCP notion-fetch) */}
      {showDetailsModal && (
        <div
          className="notion-modal-overlay"
          onClick={() => setShowDetailsModal(false)}
          role="dialog"
          aria-modal="true"
          aria-labelledby="notion-detail-modal-title"
        >
          <div
            className="notion-modal-content notion-task-detail-modal"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Modal Header */}
            <div className="notion-task-detail-header">
              <div className="notion-detail-title-area">
                <span className="notion-detail-icon" aria-hidden="true">📋</span>
                <div>
                  <h3 id="notion-detail-modal-title">
                    {taskDetails?.title || taskDetails?.name || selectedTask?.name || "Task Details"}
                  </h3>
                  <div className="notion-detail-breadcrumbs">
                    <span>Notion</span>
                    <span>&rsaquo;</span>
                    <span>{taskDetails?.path || "Daily Task"}</span>
                  </div>
                </div>
              </div>
              <button
                type="button"
                className="notion-modal-close"
                onClick={() => setShowDetailsModal(false)}
                aria-label="Close task details"
              >
                &times;
              </button>
            </div>

            {/* Modal Body */}
            <div className="notion-task-detail-body">
              {loadingDetails && (
                <div className="notion-loading-list" style={{ padding: "16px 0" }}>
                  <div className="notion-task-skeleton">
                    <div className="skeleton-line skeleton-title" style={{ width: "70%" }} />
                    <div className="skeleton-line" style={{ width: "45%" }} />
                    <div className="skeleton-badges">
                      <div className="skeleton-badge" />
                      <div className="skeleton-badge" />
                    </div>
                  </div>
                  <p style={{ fontSize: "12.5px", color: "var(--text-muted)", textAlign: "center", margin: "12px 0 0" }}>
                    Retrieving task directly via Notion MCP (notion-fetch)...
                  </p>
                </div>
              )}

              {detailsError && !loadingDetails && (
                <div className="modal-alert alert-error">
                  <span>❌ {detailsError}</span>
                  <button
                    type="button"
                    className="notion-retry-btn"
                    style={{ alignSelf: "flex-start", marginTop: "6px" }}
                    onClick={() => handleTaskClick(selectedTask)}
                  >
                    Retry Fetch
                  </button>
                </div>
              )}

              {!loadingDetails && !detailsError && (
                <>
                  {/* Key attributes grid */}
                  <div className="notion-detail-grid">
                    <div className="notion-detail-field">
                      <span className="notion-field-label">Status</span>
                      <div className="notion-field-value">
                        <span className={`task-badge ${getStatusBadgeClass(taskDetails?.status || selectedTask?.status)}`}>
                          <span className="badge-indicator-dot" />
                          {taskDetails?.status || selectedTask?.status || "Unknown"}
                        </span>
                      </div>
                    </div>

                    <div className="notion-detail-field">
                      <span className="notion-field-label">Priority</span>
                      <div className="notion-field-value">
                        <span className={`task-badge ${getPriorityBadgeClass(taskDetails?.priority || selectedTask?.priority)}`}>
                          {taskDetails?.priority || selectedTask?.priority || "None"}
                        </span>
                      </div>
                    </div>

                    <div className="notion-detail-field">
                      <span className="notion-field-label">Due Date</span>
                      <div className="notion-field-value" style={{ fontSize: "12.5px" }}>
                        📅 {taskDetails?.due_date || selectedTask?.due_date || "None"}
                      </div>
                    </div>

                    {taskDetails?.last_edited_at && (
                      <div className="notion-detail-field">
                        <span className="notion-field-label">Last Edited</span>
                        <div className="notion-field-value" style={{ fontSize: "12px", color: "var(--text-secondary)" }}>
                          {new Date(taskDetails.last_edited_at).toLocaleDateString(undefined, {
                            month: "short",
                            day: "numeric",
                            year: "numeric",
                            hour: "2-digit",
                            minute: "2-digit",
                          })}
                        </div>
                      </div>
                    )}
                  </div>

                  {/* Task Notes / Content */}
                  <div>
                    <h5 className="notion-detail-section-title">Page Notes & Content</h5>
                    {taskDetails?.content ? (
                      <div className="notion-detail-content-box">
                        {taskDetails.content}
                      </div>
                    ) : (
                      <p className="notion-detail-empty-content">
                        No notes written on this Notion page yet.
                      </p>
                    )}
                  </div>

                  {/* Extended Properties (if available) */}
                  {taskDetails?.properties && Object.keys(taskDetails.properties).length > 0 && (
                    <div>
                      <h5 className="notion-detail-section-title">Notion Page Properties</h5>
                      <table className="notion-detail-props-table">
                        <tbody>
                          {Object.entries(taskDetails.properties).map(([key, value]) => {
                            if (key === "url" || key === "Name" || key === "name") return null;
                            const displayValue = typeof value === "object" ? JSON.stringify(value) : String(value);
                            return (
                              <tr key={key}>
                                <td className="prop-key">{key}</td>
                                <td className="prop-val">{displayValue}</td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  )}
                </>
              )}
            </div>

            {/* Modal Footer */}
            <div className="notion-task-detail-footer">
              <div className="notion-mcp-badge-pill">
                <span className="status-dot-pulse" style={{ width: "6px", height: "6px" }} />
                <span>Fetched via Notion MCP tool notion-fetch</span>
              </div>

              <div style={{ display: "flex", gap: "8px" }}>
                <button
                  type="button"
                  className="btn-cancel"
                  onClick={() => setShowDetailsModal(false)}
                >
                  Close
                </button>

                {(taskDetails?.url || selectedTask?.url) && (
                  <a
                    href={taskDetails?.url || selectedTask?.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="notion-link-btn"
                  >
                    <span>Open in Notion</span>
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="13" height="13">
                      <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
                      <polyline points="15 3 21 3 21 9" />
                      <line x1="10" y1="14" x2="21" y2="3" />
                    </svg>
                  </a>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

    </div>
  );
}
