"use client";

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
      <div className="prose prose-invert max-w-none whitespace-pre-wrap text-sm">
        {content || "File content will appear here..."}
      </div>
    </div>
  );
}
