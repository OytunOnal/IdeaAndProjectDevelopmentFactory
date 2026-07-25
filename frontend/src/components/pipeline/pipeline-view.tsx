"use client";

import { Card, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { AGENT_DISPLAY_NAMES } from "@/types/agent";

const phases = [
  {
    name: "Discovery",
    agents: ["idea_analyst", "market_researcher", "competitor_analyst", "tech_feasibility", "brand_strategist", "legal_advisor"] as const,
    status: "idle" as const,
  },
  {
    name: "Specification",
    agents: ["spec_writer", "architecture_designer", "ux_strategist", "visual_designer", "design_system_architect", "gtm_strategist", "financial_modeler"] as const,
    status: "idle" as const,
  },
  {
    name: "Quality",
    agents: ["quality_reviewer", "devils_advocate", "consistency_checker"] as const,
    status: "idle" as const,
  },
  {
    name: "Packaging",
    agents: ["doc_formatter", "planning_agent"] as const,
    status: "idle" as const,
  },
];

export function PipelineView() {
  return (
    <div className="space-y-6 p-6">
      <h2 className="text-lg font-semibold">Pipeline</h2>
      <div className="space-y-4">
        {phases.map((phase) => (
          <Card key={phase.name}>
            <CardHeader>
              <CardTitle className="text-base">{phase.name}</CardTitle>
              <CardDescription>
                <div className="mt-2 flex flex-wrap gap-2">
                  {phase.agents.map((agentId) => (
                    <span
                      key={agentId}
                      className="rounded-full bg-muted px-3 py-1 text-xs"
                    >
                      {AGENT_DISPLAY_NAMES[agentId]}
                    </span>
                  ))}
                </div>
              </CardDescription>
            </CardHeader>
          </Card>
        ))}
      </div>
    </div>
  );
}
