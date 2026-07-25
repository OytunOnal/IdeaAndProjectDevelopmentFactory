export type PipelinePhase = "idle" | "discovery" | "specification" | "quality" | "packaging" | "completed";
export type PipelineStatus = "idle" | "running" | "waiting_for_user" | "paused" | "completed" | "failed";
export type ProjectCategory = "saas" | "fintech" | "mobile" | "ai_ml" | "infrastructure" | "multi_platform";

export interface Project {
  id: string;
  name: string;
  slug: string;
  category: ProjectCategory | null;
  description: string | null;
  current_phase: PipelinePhase;
  pipeline_status: PipelineStatus;
  current_agent: string | null;
  quality_score: number | null;
  total_tokens_used: number;
  estimated_cost_usd: number;
  created_at: string;
  updated_at: string;
}

export interface ProjectFile {
  file_path: string;
  file_name: string;
  folder: string;
  content: string;
  generated_by: string | null;
  version: number;
  status: "draft" | "reviewed" | "final";
  updated_at: string;
}

export interface ProjectCreate {
  name: string;
  description?: string;
}
