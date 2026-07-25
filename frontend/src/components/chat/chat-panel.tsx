"use client";

import { useState, useRef, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { DecisionCard } from "./decision-card";
import { AGENT_DISPLAY_NAMES, AGENT_COLORS } from "@/types/agent";
import type { AgentId } from "@/types/agent";
import { API_URL } from "@/lib/constants";

interface Message {
  id: string;
  role: string;
  agent_id?: string;
  content: string;
  timestamp: string;
}

interface ChatPanelProps {
  projectId: string;
  apiKey: string;
  messages: Message[];
  pendingDecision: Record<string, unknown> | null;
  pipelineStatus: string | null;
  onUpdate: (data?: Record<string, unknown>) => void;
}

export function ChatPanel({
  projectId,
  apiKey,
  messages,
  pendingDecision,
  pipelineStatus,
  onUpdate,
}: ChatPanelProps) {
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  const sendMessage = async () => {
    if (!input.trim() || loading) return;

    const message = input.trim();
    setInput("");
    setLoading(true);

    // Show the user's message immediately; the server response replaces
    // the list with the canonical history (user + agent messages).
    const isFirstMessage = messages.length === 0;
    onUpdate({
      messages: [...messages, {
        id: `msg-user-local-${Date.now()}`,
        role: "user",
        content: message,
        timestamp: new Date().toISOString(),
      }],
      pipeline_status: "running",
    });

    try {
      const endpoint = isFirstMessage
        ? `${API_URL}/api/projects/${projectId}/start`
        : `${API_URL}/api/projects/${projectId}/chat`;

      const res = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message, api_key: apiKey }),
      });

      const data = await res.json();
      // API response contains all messages (user + agent), replace fully
      onUpdate(data);
    } catch (err) {
      console.error("Failed to send message:", err);
      onUpdate({
        messages: [...messages, {
          id: `msg-user-${Date.now()}`,
          role: "user",
          content: message,
          timestamp: new Date().toISOString(),
        }, {
          id: `msg-error-${Date.now()}`,
          role: "agent",
          agent_id: "idea_analyst",
          content: "Connection error. Please try again.",
          timestamp: new Date().toISOString(),
        }],
        pipeline_status: "waiting_for_user",
      });
    } finally {
      setLoading(false);
    }
  };

  const submitDecision = async (action: string, option?: string, customInput?: string) => {
    if (!pendingDecision) return;
    setLoading(true);

    try {
      const res = await fetch(`${API_URL}/api/projects/${projectId}/decision`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          decision_id: (pendingDecision as Record<string, string>).id,
          action,
          chosen_option: option,
          custom_input: customInput,
          api_key: apiKey,
        }),
      });

      if (!res.ok) throw new Error("API error");

      const data = await res.json();
      onUpdate(data);
    } catch (err) {
      console.error("Failed to submit decision:", err);
    } finally {
      setLoading(false);
    }
  };

  const isWaiting = pipelineStatus === "waiting_for_user";

  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-border px-4 py-3">
        <h3 className="text-sm font-semibold">Chat</h3>
        <p className="text-xs text-muted-foreground">
          {pipelineStatus === "running" && "Agent is thinking..."}
          {isWaiting && !pendingDecision && "Waiting for your message"}
          {isWaiting && pendingDecision && "Decision required"}
          {!pipelineStatus && "Start by describing your idea"}
        </p>
      </div>

      <div ref={scrollRef} className="flex-1 space-y-3 overflow-y-auto p-4">
        {messages.length === 0 && (
          <div className="rounded-lg bg-muted p-3 text-sm">
            <p className="mb-1 font-medium text-primary">Idea Analyst</p>
            <p>Tell me about your project idea. Describe it however feels natural - I&apos;ll ask follow-up questions.</p>
          </div>
        )}

        {messages.map((msg) => {
          if (msg.role === "system") return null;

          const isAgent = msg.role === "agent";
          const agentId = msg.agent_id as AgentId | undefined;
          const agentName = agentId ? AGENT_DISPLAY_NAMES[agentId] : "Agent";
          const agentColor = agentId ? AGENT_COLORS[agentId] : "#6366F1";

          return (
            <div
              key={msg.id}
              className={`rounded-lg p-3 text-sm ${
                isAgent ? "bg-muted" : "ml-8 bg-primary/10"
              }`}
            >
              {isAgent && (
                <p className="mb-1 text-xs font-medium" style={{ color: agentColor }}>
                  {agentName}
                </p>
              )}
              {!isAgent && (
                <p className="mb-1 text-xs font-medium text-muted-foreground">You</p>
              )}
              <div className="whitespace-pre-wrap">{msg.content}</div>
            </div>
          );
        })}

        {pendingDecision && (
          <DecisionCard
            decision={pendingDecision as Parameters<typeof DecisionCard>[0]["decision"]}
            onSubmit={submitDecision}
          />
        )}

        {loading && (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <span className="animate-pulse">Thinking...</span>
          </div>
        )}
      </div>

      <div className="border-t border-border p-4">
        <form
          className="flex gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            sendMessage();
          }}
        >
          <Input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={
              pendingDecision
                ? "Use the decision buttons above, or type here..."
                : "Type a message..."
            }
            disabled={loading}
          />
          <Button type="submit" size="sm" disabled={!input.trim() || loading}>
            Send
          </Button>
        </form>
      </div>
    </div>
  );
}
