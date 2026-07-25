"use client";

import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Card, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { AuthGuard } from "@/components/layout/auth-guard";
import { useAuth } from "@/components/layout/auth-provider";

export default function DashboardPage() {
  return (
    <AuthGuard>
      <DashboardContent />
    </AuthGuard>
  );
}

function DashboardContent() {
  const { user, signOut } = useAuth();

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
          <Link href="/project/new">
            <Card className="flex h-48 cursor-pointer items-center justify-center border-dashed hover:border-primary">
              <CardHeader className="text-center">
                <CardTitle className="text-lg text-muted-foreground">+ Start a new project</CardTitle>
                <CardDescription>Describe your idea and let AI agents build your spec</CardDescription>
              </CardHeader>
            </Card>
          </Link>
        </div>
      </main>
    </div>
  );
}
