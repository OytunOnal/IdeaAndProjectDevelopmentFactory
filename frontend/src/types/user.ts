export type AutonomyLevel = "ask" | "suggest" | "delegate";

export interface AutonomySettings {
  strategic: AutonomyLevel;
  technical: AutonomyLevel;
  content: AutonomyLevel;
  quality: AutonomyLevel;
}

export interface User {
  id: string;
  email: string;
  display_name: string | null;
  avatar_url: string | null;
  autonomy_settings: AutonomySettings;
}

export interface ApiKeyStatus {
  provider: "anthropic" | "openai" | "google";
  configured: boolean;
  last_validated: string | null;
}
