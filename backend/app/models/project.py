from pydantic import BaseModel


class ProjectCreate(BaseModel):
    name: str
    description: str | None = None


class ProjectResponse(BaseModel):
    id: str
    name: str
    slug: str
    current_phase: str = "idle"
    pipeline_status: str = "idle"
    quality_score: int | None = None
    estimated_cost_usd: float = 0
    created_at: str
