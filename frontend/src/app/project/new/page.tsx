"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { AuthGuard } from "@/components/layout/auth-guard";
import { API_URL } from "@/lib/constants";
import Link from "next/link";

export default function NewProjectPage() {
  return (
    <AuthGuard>
      <NewProjectContent />
    </AuthGuard>
  );
}

function NewProjectContent() {
  const router = useRouter();
  const [idea, setIdea] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!idea.trim()) return;
    setLoading(true);

    try {
      const res = await fetch(`${API_URL}/api/projects`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: idea.trim().slice(0, 50), description: idea.trim() }),
      });
      const project = await res.json();
      router.push(`/project/${project.id}`);
    } catch {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-background">
      <header className="border-b border-border px-6 py-4">
        <div className="mx-auto flex max-w-6xl items-center justify-between">
          <Link href="/dashboard" className="text-xl font-bold">
            ProjectFactory
          </Link>
        </div>
      </header>

      <main className="mx-auto max-w-2xl px-6 py-16">
        <Card>
          <CardHeader className="text-center">
            <CardTitle className="text-2xl">New Project</CardTitle>
            <CardDescription>
              Describe your project idea. Our AI agents will turn it into a complete specification.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-6">
              <div className="space-y-2">
                <Label htmlFor="idea">Your Idea</Label>
                <textarea
                  id="idea"
                  className="flex min-h-32 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                  placeholder="I want to build a marketplace for boats and marine equipment in Turkey..."
                  value={idea}
                  onChange={(e) => setIdea(e.target.value)}
                />
              </div>
              <Button type="submit" className="w-full" size="lg" disabled={!idea.trim() || loading}>
                {loading ? "Creating project..." : "Start Project"}
              </Button>
            </form>
          </CardContent>
        </Card>
      </main>
    </div>
  );
}
