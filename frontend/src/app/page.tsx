"use client";

import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Card, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useAuth } from "@/components/layout/auth-provider";

const features = [
  {
    title: "18 Specialized Agents",
    description: "From market research to financial modeling, each agent is an expert in its domain.",
  },
  {
    title: "Collaborative by Default",
    description: "Agents ask you at every decision point. Delegate or decide yourself.",
  },
  {
    title: "Bring Your Own Key",
    description: "Use your own Claude, GPT, or Gemini API keys. No vendor lock-in.",
  },
  {
    title: "Complete Specifications",
    description: "PRD, architecture, wireframes, financials, legal - everything you need to start building.",
  },
];

export default function LandingPage() {
  const { user, loading, signOut } = useAuth();

  return (
    <div className="flex min-h-screen flex-col">
      <header className="border-b border-border px-6 py-4">
        <div className="mx-auto flex max-w-6xl items-center justify-between">
          <span className="text-xl font-bold">ProjectFactory</span>
          <div className="flex items-center gap-3">
            {loading ? null : user ? (
              <>
                <span className="text-sm text-muted-foreground">{user.email}</span>
                <Link href="/dashboard">
                  <Button variant="ghost" size="sm">Dashboard</Button>
                </Link>
                <Link href="/settings">
                  <Button variant="ghost" size="sm">Settings</Button>
                </Link>
                <Button variant="ghost" size="sm" onClick={signOut}>
                  Sign Out
                </Button>
              </>
            ) : (
              <Link href="/login">
                <Button>Sign In</Button>
              </Link>
            )}
          </div>
        </div>
      </header>

      <main className="flex-1">
        <section className="mx-auto max-w-4xl px-6 py-24 text-center">
          <h1 className="text-5xl font-bold tracking-tight">
            Transform Ideas into
            <br />
            <span className="text-primary">Project Specifications</span>
          </h1>
          <p className="mx-auto mt-6 max-w-2xl text-lg text-muted-foreground">
            Describe your idea. 18 AI agents collaborate to produce professional,
            development-ready project specifications. Complete with market research,
            architecture, wireframes, and financial projections.
          </p>
          <div className="mt-10 flex justify-center gap-4">
            <Link href={user ? "/dashboard" : "/login"}>
              <Button size="lg">Start Building</Button>
            </Link>
            <Button size="lg" variant="outline">
              Learn More
            </Button>
          </div>
        </section>

        <section className="mx-auto max-w-6xl px-6 pb-24">
          <div className="grid gap-6 sm:grid-cols-2">
            {features.map((feature) => (
              <Card key={feature.title}>
                <CardHeader>
                  <CardTitle>{feature.title}</CardTitle>
                  <CardDescription>{feature.description}</CardDescription>
                </CardHeader>
              </Card>
            ))}
          </div>
        </section>
      </main>

      <footer className="border-t border-border px-6 py-6 text-center text-sm text-muted-foreground">
        ProjectFactory - AI-Powered Project Specification Factory
      </footer>
    </div>
  );
}
