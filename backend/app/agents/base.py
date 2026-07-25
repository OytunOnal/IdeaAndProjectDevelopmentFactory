from abc import ABC, abstractmethod


class BaseAgent(ABC):
    name: str
    description: str
    model_tier: int  # 1=Opus, 2=Sonnet, 3=Haiku

    @abstractmethod
    async def run(self, state: dict) -> dict:
        """Execute the agent's task and return updated state."""
        ...
