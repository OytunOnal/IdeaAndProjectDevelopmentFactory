"use client";

import { Markdown } from "@/components/markdown";

interface DocumentViewerProps {
  filePath?: string;
  content?: string;
}

export function DocumentViewer({ filePath, content }: DocumentViewerProps) {
  if (!filePath) {
    return (
      <div className="flex h-full items-center justify-center text-muted-foreground">
        Select a file to view
      </div>
    );
  }

  return (
    <div className="h-full overflow-y-auto p-6">
      <div className="mb-4 flex items-center gap-2 text-sm text-muted-foreground">
        <span>{filePath}</span>
      </div>
      <div className="mx-auto max-w-3xl text-sm">
        <Markdown>{content || "File content will appear here..."}</Markdown>
      </div>
    </div>
  );
}
