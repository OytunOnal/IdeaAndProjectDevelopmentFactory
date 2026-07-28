"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Card, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { AuthGuard } from "@/components/layout/auth-guard";
import { useAuth } from "@/components/layout/auth-provider";
import { API_URL } from "@/lib/constants";

interface Project {
  id: string;
  name: string;
  description: string | null;
  current_phase: string | null;
  pipeline_status: string | null;
  created_at: string;
}

const PHASE_LABELS: Record<string, string> = {
  idle: "Not started",
  discovery: "Discovery",
  specification: "Specification",
  quality: "Quality review",
  packaging: "Packaging",
  completed: "Completed ✓",
};

export default function DashboardPage() {
  return (
    <AuthGuard>
      <DashboardContent />
    </AuthGuard>
  );
}

function DashboardContent() {
  const { user, signOut } = useAuth();
  const router = useRouter();
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(`${API_URL}/api/projects`);
        const data = await res.json();
        if (!cancelled) setProjects(data.projects ?? []);
      } catch {
        // backend down — keep whatever we had
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const deleteProject = useCallback(
    async (e: React.MouseEvent, id: string) => {
      e.preventDefault();
      e.stopPropagation();
      if (!confirm("Delete this project? This cannot be undone.")) return;
      try {
        await fetch(`${API_URL}/api/projects/${id}`, { method: "DELETE" });
        setProjects((prev) => prev.filter((p) => p.id !== id));
      } catch {
        // ignore; next reload will reconcile
      }
    },
    []
  );

  return (
    <div className="min-h-screen bg-background">
      <header className="border-b border-border px-6 py-4">
        <div className="mx-auto flex max-w-6xl items-center justify-between">
          <Link href="/" className="text-xl font-bold">
            ProjectFactory
          </Link>
          <div className="flex items-center gap-4">
            <span className="text-sm text-muted-foreground">{user?.email}</span>
            <Link href="/settings">
              <Button variant="ghost" size="sm">Settings</Button>
            </Link>
            <Button variant="ghost" size="sm" onClick={signOut}>
              Sign Out
            </Button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-6 py-8">
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-bold">Your Projects</h1>
          <Link href="/project/new">
            <Button>+ New Project</Button>
          </Link>
        </div>

        <div className="mt-8 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {projects.map((project) => (
            <Card
              key={project.id}
              onClick={() => router.push(`/project/${project.id}`)}
              className="group relative h-48 cursor-pointer overflow-hidden transition-colors hover:ring-primary"
            >
              <CardHeader className="w-full">
                <CardTitle className="line-clamp-2 pr-6 text-base">
                  {project.name}
                </CardTitle>
                <CardDescription className="line-clamp-3">
                  {project.description || "—"}
                </CardDescription>
              </CardHeader>
              <div className="absolute inset-x-4 bottom-3 flex items-center justify-between text-xs text-muted-foreground">
                <span
                  className={
                    project.current_phase === "completed"
                      ? "font-medium text-green-500"
                      : "font-medium"
                  }
                >
                  {PHASE_LABELS[project.current_phase ?? "idle"] ??
                    project.current_phase}
                </span>
                <span>{project.created_at?.slice(0, 10)}</span>
              </div>
              <button
                onClick={(e) => deleteProject(e, project.id)}
                className="absolute right-2 top-2 hidden rounded p-1 text-muted-foreground hover:bg-destructive/10 hover:text-destructive group-hover:block"
                title="Delete project"
              >
                ✕
              </button>
            </Card>
          ))}

          <Link href="/project/new">
            <Card className="flex h-48 cursor-pointer flex-col justify-center border-dashed hover:border-primary">
              {/* w-full: CardHeader is a CSS container (inline-size), which
                  removes its intrinsic width — centered in a flex parent it
                  collapses to zero width and wraps one word per line. */}
              <CardHeader className="w-full text-center">
                <CardTitle className="text-lg text-muted-foreground">+ Start a new project</CardTitle>
                <CardDescription>Describe your idea and let AI agents build your spec</CardDescription>
              </CardHeader>
            </Card>
          </Link>
        </div>

        {!loading && projects.length === 0 && (
          <p className="mt-6 text-sm text-muted-foreground">
            No projects yet — describe an idea and the agents will take it from
            there. Projects and their full pipeline state survive server
            restarts.
          </p>
        )}
      </main>
    </div>
  );
}
