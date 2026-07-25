"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";

interface DecisionOption {
  id: string;
  label: string;
  description: string;
}

interface DecisionCardProps {
  decision: {
    id: string;
    agent: string;
    question: string;
    options: DecisionOption[];
    agent_recommendation: string | null;
    agent_reasoning: string | null;
    allow_delegate: boolean;
    allow_freeform: boolean;
  };
  onSubmit: (action: string, option?: string, customInput?: string) => void;
  resolved?: boolean;
  resolvedChoice?: string;
}

export function DecisionCard({ decision, onSubmit, resolved, resolvedChoice }: DecisionCardProps) {
  const [customInput, setCustomInput] = useState("");

  if (resolved) {
    return (
      <Card className="border-green-800 bg-green-950/30 p-4">
        <p className="text-sm font-medium text-green-400">Decision made: {resolvedChoice}</p>
      </Card>
    );
  }

  return (
    <Card className="border-amber-800 bg-amber-950/20 p-4 space-y-3">
      <p className="text-sm font-medium">{decision.question}</p>

      {decision.agent_reasoning && (
        <p className="text-xs text-muted-foreground">
          Agent recommends: {decision.agent_reasoning}
        </p>
      )}

      <div className="flex flex-wrap gap-2">
        {decision.options.map((opt) => (
          <Button
            key={opt.id}
            variant={opt.id === decision.agent_recommendation ? "default" : "outline"}
            size="sm"
            onClick={() => onSubmit("choose", opt.id)}
          >
            {opt.label}
            {opt.id === decision.agent_recommendation && " *"}
          </Button>
        ))}

        {decision.allow_delegate && (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => onSubmit("delegate")}
          >
            You decide
          </Button>
        )}
      </div>

      {decision.allow_freeform && (
        <div className="flex gap-2">
          <Input
            value={customInput}
            onChange={(e) => setCustomInput(e.target.value)}
            placeholder="Or type your own answer..."
            className="text-sm"
          />
          <Button
            size="sm"
            variant="outline"
            onClick={() => onSubmit("custom", undefined, customInput)}
            disabled={!customInput.trim()}
          >
            Send
          </Button>
        </div>
      )}
    </Card>
  );
}
