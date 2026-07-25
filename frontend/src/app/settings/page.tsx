"use client";

import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { AuthGuard } from "@/components/layout/auth-guard";
import { useAuth } from "@/components/layout/auth-provider";

export default function SettingsPage() {
  return (
    <AuthGuard>
      <SettingsContent />
    </AuthGuard>
  );
}

function SettingsContent() {
  const { user, signOut } = useAuth();

  return (
    <div className="min-h-screen bg-background">
      <header className="border-b border-border px-6 py-4">
        <div className="mx-auto flex max-w-6xl items-center justify-between">
          <Link href="/dashboard" className="text-xl font-bold">
            ProjectFactory
          </Link>
          <div className="flex items-center gap-4">
            <span className="text-sm text-muted-foreground">{user?.email}</span>
            <Link href="/dashboard">
              <Button variant="ghost" size="sm">Dashboard</Button>
            </Link>
            <Button variant="ghost" size="sm" onClick={signOut}>
              Sign Out
            </Button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-2xl space-y-8 px-6 py-8">
        <h1 className="text-2xl font-bold">Settings</h1>

        <Card>
          <CardHeader>
            <CardTitle>API Keys</CardTitle>
            <CardDescription>
              Add your LLM provider API keys. Keys are encrypted and never logged.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label>Anthropic (Claude)</Label>
              <div className="flex gap-2">
                <Input type="password" placeholder="sk-ant-..." />
                <Button variant="outline">Save</Button>
              </div>
            </div>
            <div className="space-y-2">
              <Label>OpenAI</Label>
              <div className="flex gap-2">
                <Input type="password" placeholder="sk-..." />
                <Button variant="outline">Save</Button>
              </div>
            </div>
            <div className="space-y-2">
              <Label>Google (Gemini)</Label>
              <div className="flex gap-2">
                <Input type="password" placeholder="AI..." />
                <Button variant="outline">Save</Button>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Autonomy Levels</CardTitle>
            <CardDescription>
              Control how much agents decide on their own vs asking you.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {["Strategic decisions", "Technical decisions", "Content decisions", "Quality decisions"].map(
              (label) => (
                <div key={label} className="flex items-center justify-between">
                  <Label>{label}</Label>
                  <span className="text-sm text-muted-foreground">Ask me</span>
                </div>
              )
            )}
          </CardContent>
        </Card>
      </main>
    </div>
  );
}
