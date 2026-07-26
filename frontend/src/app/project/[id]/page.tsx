"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { useParams } from "next/navigation";
import { API_URL } from "@/lib/constants";
import { ChatPanel } from "@/components/chat/chat-panel";
import { PipelineView } from "@/components/pipeline/pipeline-view";
import { FileTree } from "@/components/explorer/file-tree";
import { DocumentViewer } from "@/components/editor/document-viewer";
import { StatusBar } from "@/components/layout/status-bar";
import { AuthGuard } from "@/components/layout/auth-guard";
import { useSocket } from "@/hooks/use-socket";
import Link from "next/link";
import { Button } from "@/components/ui/button";

interface PipelineState {
  messages: Array<{
    id: string;
    role: string;
    agent_id?: string;
    content: string;
    timestamp: string;
  }>;
  current_phase: string | null;
  pipeline_status: string | null;
  current_agent: string | null;
  pending_decision: Record<string, unknown> | null;
  idea_brief: Record<string, unknown> | null;
  files: string[];
  quality_score: number | null;
}

export default function ProjectWorkspace() {
  return (
    <AuthGuard>
      <WorkspaceContent />
    </AuthGuard>
  );
}

function WorkspaceContent() {
  const params = useParams();
  const projectId = params?.id as string;

  const [state, setState] = useState<PipelineState>({
    messages: [],
    current_phase: null,
    pipeline_status: null,
    current_agent: null,
    pending_decision: null,
    idea_brief: null,
    files: [],
    quality_score: null,
  });
  const [selectedFile, setSelectedFile] = useState<string | null>(null);
  const [fileContent, setFileContent] = useState<string>("");

  const handleApiResponse = useCallback((data?: Record<string, unknown>) => {
    if (!data) return;
    // REST responses use "status", WebSocket updates use "pipeline_status"
    const status = data.status ?? data.pipeline_status;
    setState((prev) => ({
      messages: data.messages ? (data.messages as PipelineState["messages"]) : prev.messages,
      current_phase: data.current_phase !== undefined ? (data.current_phase as string) : prev.current_phase,
      pipeline_status: status !== undefined ? (status as string) : prev.pipeline_status,
      current_agent: data.current_agent !== undefined ? (data.current_agent as string) : prev.current_agent,
      pending_decision: data.pending_decision !== undefined ? (data.pending_decision as Record<string, unknown>) : prev.pending_decision,
      idea_brief: data.idea_brief !== undefined ? (data.idea_brief as Record<string, unknown>) : prev.idea_brief,
      files: data.files !== undefined ? (data.files as string[]) : prev.files,
      quality_score: data.quality_score !== undefined ? (data.quality_score as number | null) : prev.quality_score,
    }));
  }, []);

  // Live pipeline updates over WebSocket (merged into state, not replaced)
  useSocket(projectId, handleApiResponse);

  const handleSelectFile = useCallback(async (path: string) => {
    setSelectedFile(path);
    setFileContent("Loading...");
    try {
      const res = await fetch(
        `${API_URL}/api/projects/${projectId}/files/${path}`
      );
      const data = await res.json();
      setFileContent(data.content ?? data.error ?? "");
    } catch {
      setFileContent("Failed to load file.");
    }
  }, [projectId]);

  // Auto-open documents as agents produce them; when the pipeline pauses,
  // refresh the open document (revisions keep the path, change the content).
  const knownFilesRef = useRef<Set<string>>(new Set());
  useEffect(() => {
    const known = knownFilesRef.current;
    const fresh = state.files.filter((f) => !known.has(f));
    state.files.forEach((f) => known.add(f));
    if (fresh.length > 0) {
      handleSelectFile(fresh[fresh.length - 1]);
    } else if (
      selectedFile &&
      state.pipeline_status === "waiting_for_user" &&
      state.files.includes(selectedFile)
    ) {
      handleSelectFile(selectedFile);
    }
    // Refetch only on file-list growth or pipeline pauses — not on selection
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state.files, state.pipeline_status, handleSelectFile]);

  // On mount: restore existing pipeline state, or auto-start the pipeline
  // with the idea the user entered on the New Project page.
  const initRef = useRef(false);
  useEffect(() => {
    if (!projectId || initRef.current) return;
    initRef.current = true;

    (async () => {
      try {
        const res = await fetch(`${API_URL}/api/projects/${projectId}/state`);
        const st = await res.json();

        if (st.exists) {
          handleApiResponse(st);
          return;
        }

        const description = st.project?.description;
        if (!description) return;

        // Show the idea immediately, then kick off the pipeline with it
        setState((prev) => ({
          ...prev,
          pipeline_status: "running",
          messages: [{ id: "msg-user-0", role: "user", content: description, timestamp: "" }],
        }));

        const startRes = await fetch(`${API_URL}/api/projects/${projectId}/start`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ message: description, api_key: "" }),
        });
        handleApiResponse(await startRes.json());
      } catch (err) {
        console.error("Failed to initialize project workspace:", err);
      }
    })();
  }, [projectId, handleApiResponse]);

  return (
    <div className="flex h-screen flex-col">
      <header className="flex h-12 items-center justify-between border-b border-border px-4">
        <div className="flex items-center gap-4">
          <Link href="/dashboard" className="font-bold">
            ProjectFactory
          </Link>
          <span className="text-sm text-muted-foreground">/ Project</span>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="ghost" size="sm">Pipeline</Button>
          <Button variant="ghost" size="sm">Editor</Button>
          <Button variant="ghost" size="sm">Quality</Button>
        </div>
      </header>

      <div className="flex flex-1 overflow-hidden">
        <aside className="w-60 shrink-0 overflow-y-auto border-r border-border">
          <FileTree
            files={state.files}
            selected={selectedFile}
            qualityScore={state.quality_score}
            onSelect={handleSelectFile}
            exportUrl={`${API_URL}/api/projects/${projectId}/export`}
          />
        </aside>

        <main className="flex-1 overflow-y-auto">
          {selectedFile ? (
            <DocumentViewer filePath={selectedFile} content={fileContent} />
          ) : (
            <PipelineView />
          )}
        </main>

        <aside className="w-96 shrink-0 overflow-hidden border-l border-border">
          <ChatPanel
            projectId={projectId}
            apiKey=""
            messages={state.messages}
            pendingDecision={state.pending_decision}
            pipelineStatus={state.pipeline_status}
            onUpdate={handleApiResponse}
          />
        </aside>
      </div>

      <StatusBar />
    </div>
  );
}
