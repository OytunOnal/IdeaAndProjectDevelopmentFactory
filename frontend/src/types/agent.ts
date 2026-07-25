import type { PipelinePhase } from "./project";

export type AgentId =
  | "orchestrator"
  | "idea_analyst"
  | "market_researcher"
  | "competitor_analyst"
  | "tech_feasibility"
  | "brand_strategist"
  | "legal_advisor"
  | "spec_writer"
  | "architecture_designer"
  | "ux_strategist"
  | "visual_designer"
  | "design_system_architect"
  | "gtm_strategist"
  | "financial_modeler"
  | "quality_reviewer"
  | "devils_advocate"
  | "consistency_checker"
  | "doc_formatter"
  | "planning_agent";

export type AgentStatus = "idle" | "running" | "completed" | "failed" | "waiting";

export interface AgentInfo {
  id: AgentId;
  name: string;
  phase: PipelinePhase;
  status: AgentStatus;
  duration_ms?: number;
  tokens_used?: number;
}

export const AGENT_DISPLAY_NAMES: Record<AgentId, string> = {
  orchestrator: "Orchestrator",
  idea_analyst: "Idea Analyst",
  market_researcher: "Market Researcher",
  competitor_analyst: "Competitor Analyst",
  tech_feasibility: "Tech Feasibility",
  brand_strategist: "Brand Strategist",
  legal_advisor: "Legal Advisor",
  spec_writer: "Spec Writer",
  architecture_designer: "Architecture Designer",
  ux_strategist: "UX Strategist",
  visual_designer: "Visual Designer",
  design_system_architect: "Design System Architect",
  gtm_strategist: "GTM Strategist",
  financial_modeler: "Financial Modeler",
  quality_reviewer: "Quality Reviewer",
  devils_advocate: "Devil's Advocate",
  consistency_checker: "Consistency Checker",
  doc_formatter: "Doc Formatter",
  planning_agent: "Planning Agent",
};

export const AGENT_COLORS: Record<AgentId, string> = {
  orchestrator: "#6366F1",
  idea_analyst: "#8B5CF6",
  market_researcher: "#06B6D4",
  competitor_analyst: "#F59E0B",
  tech_feasibility: "#10B981",
  brand_strategist: "#EC4899",
  legal_advisor: "#78716C",
  spec_writer: "#3B82F6",
  architecture_designer: "#6366F1",
  ux_strategist: "#EC4899",
  visual_designer: "#A855F7",
  design_system_architect: "#14B8A6",
  gtm_strategist: "#F97316",
  financial_modeler: "#22C55E",
  quality_reviewer: "#EF4444",
  devils_advocate: "#F97316",
  consistency_checker: "#14B8A6",
  doc_formatter: "#8B5CF6",
  planning_agent: "#22C55E",
};
