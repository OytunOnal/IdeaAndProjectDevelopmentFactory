export const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
export const WS_URL = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000";

export const PHASES = [
  { id: "discovery", label: "Discovery", step: 1 },
  { id: "specification", label: "Specification", step: 2 },
  { id: "quality", label: "Quality", step: 3 },
  { id: "packaging", label: "Packaging", step: 4 },
] as const;

export const PROJECT_CATEGORIES = [
  { id: "saas", label: "SaaS / Enterprise" },
  { id: "fintech", label: "Trading / FinTech" },
  { id: "ai_ml", label: "AI / Machine Learning" },
  { id: "mobile", label: "Mobile Application" },
  { id: "infrastructure", label: "Infrastructure / DevOps" },
  { id: "multi_platform", label: "Multi-Platform" },
] as const;
