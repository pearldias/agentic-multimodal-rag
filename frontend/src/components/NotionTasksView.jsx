import { useState, useEffect, useRef } from "react";
import NotionTasksCard from "./NotionTasksCard";
import NotionAssistantChat from "./NotionAssistantChat";
import { fetchNotionTools, fetchNotionStatus } from "../services/api";

export default function NotionTasksView() {
  const [toolsCount, setToolsCount] = useState(null);
  const [status, setStatus] = useState(null);
  const tasksCardRef = useRef(null);

  useEffect(() => {
    fetchNotionStatus()
      .then((st) => setStatus(st))
      .catch((err) => console.error("Error fetching status:", err));

    fetchNotionTools()
      .then((res) => setToolsCount(res?.count || res?.tools?.length || 0))
      .catch((err) => console.error("Error fetching tools count:", err));
  }, []);

  return (
    <div className="notion-tasks-page" aria-label="Notion MCP Workspace">
      {/* Top Header */}
      <div className="notion-page-header">
        <div className="notion-page-title-block">
          <h2>Notion Workspace & Tasks</h2>
          <p className="notion-page-subtitle">
            Synchronized directly with your Notion workspace for seamless, real-time access to your tasks and workspace data.

          </p>
        </div>

        <div className="notion-stats-strip">
          <div className="notion-stat-pill">
            <span className="stat-label">Connection:</span>
            <span className="stat-value text-success">
              <span className="status-dot-pulse" aria-hidden="true" />
              {status?.authenticated ? "Authenticated" : "Connecting..."}
            </span>
          </div>

          <div className="notion-stat-pill">
            <span className="stat-label">MCP Tools:</span>
            <span className="stat-value">{toolsCount !== null ? `${toolsCount} Active` : "Loading..."}</span>
          </div>

          <div className="notion-stat-pill">
            <span className="stat-label">Protocol:</span>
            <span className="stat-value">Streamable HTTP</span>
          </div>
        </div>
      </div>

      {/* Main Notion Workspace: Live Tasks on left, Dedicated Notion Assistant Chat on right */}
      <div className="notion-workspace-grid">
        <div className="notion-workspace-tasks-col">
          <NotionTasksCard ref={tasksCardRef} />
        </div>
        <div className="notion-workspace-chat-col">
          <NotionAssistantChat onOpenTask={(task) => tasksCardRef.current?.openTask(task)} />
        </div>
      </div>
    </div>
  );
}

