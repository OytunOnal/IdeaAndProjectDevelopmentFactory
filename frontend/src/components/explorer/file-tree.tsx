"use client";

interface FileTreeProps {
  files: string[];
  selected: string | null;
  qualityScore: number | null;
  onSelect: (path: string) => void;
  exportUrl: string | null;
}

export function FileTree({ files, selected, qualityScore, onSelect, exportUrl }: FileTreeProps) {
  // Group files by their top-level folder ("" for root files)
  const groups = new Map<string, string[]>();
  for (const path of files) {
    const slash = path.indexOf("/");
    const folder = slash === -1 ? "" : path.slice(0, slash);
    if (!groups.has(folder)) groups.set(folder, []);
    groups.get(folder)!.push(path);
  }

  return (
    <div className="p-3">
      <h3 className="mb-3 text-xs font-semibold uppercase text-muted-foreground">
        Files
      </h3>

      {files.length === 0 && (
        <p className="px-2 text-xs text-muted-foreground">
          Documents will appear here as the pipeline completes.
        </p>
      )}

      <div className="space-y-2">
        {[...groups.entries()].map(([folder, paths]) => (
          <div key={folder || "root"}>
            {folder && (
              <div className="flex items-center gap-2 px-2 py-1 text-xs font-medium text-muted-foreground">
                <span>{"\u{1F4C1}"}</span>
                <span>{folder}</span>
              </div>
            )}
            {paths.map((path) => {
              const name = path.slice(folder ? folder.length + 1 : 0);
              return (
                <button
                  key={path}
                  onClick={() => onSelect(path)}
                  className={`flex w-full items-center gap-2 rounded px-2 py-1 text-left text-sm hover:bg-muted ${
                    selected === path ? "bg-muted" : ""
                  } ${folder ? "pl-6" : ""}`}
                >
                  <span className="text-xs">{"\u{1F4C4}"}</span>
                  <span className="truncate">{name}</span>
                </button>
              );
            })}
          </div>
        ))}
      </div>

      <div className="mt-6 space-y-2 border-t border-border pt-4 text-xs text-muted-foreground">
        <div>Quality: {qualityScore !== null ? `${qualityScore}/100` : "--/100"}</div>
        <div>Files: {files.length}</div>
        {exportUrl && files.length > 0 && (
          <a
            href={exportUrl}
            className="mt-1 inline-block rounded border border-border px-2 py-1 font-medium hover:bg-muted"
            download
          >
            {"⬇"} Export ZIP
          </a>
        )}
      </div>
    </div>
  );
}
