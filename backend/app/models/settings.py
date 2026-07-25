from pydantic import BaseModel


class ApiKeyRequest(BaseModel):
    provider: str  # anthropic, openai, google
    api_key: str


class ApiKeyStatus(BaseModel):
    provider: str
    configured: bool
    last_validated: str | None = None


class AutonomySettings(BaseModel):
    strategic: str = "ask"
    technical: str = "suggest"
    content: str = "delegate"
    quality: str = "ask"
