import type { AgentId } from "./agent";

export interface DecisionOption {
  id: string;
  label: string;
  description: string;
  pros: string[];
  cons: string[];
}

export interface DecisionPoint {
  id: string;
  agent: AgentId;
  category: "strategic" | "technical" | "content" | "quality";
  question: string;
  context: string;
  options: DecisionOption[];
  agent_recommendation: string | null;
  agent_reasoning: string | null;
  allow_delegate: boolean;
  allow_freeform: boolean;
}

export interface ChatMessage {
  id: string;
  role: "user" | "agent" | "system";
  agent_id?: AgentId;
  content: string;
  decision?: DecisionPoint;
  timestamp: string;
}

export interface DecisionSubmit {
  decision_id: string;
  action: "choose" | "delegate" | "custom" | "more_info";
  chosen_option?: string;
  custom_input?: string;
}
