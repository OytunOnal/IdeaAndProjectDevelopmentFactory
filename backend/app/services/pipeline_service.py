class PipelineService:
    """Manages pipeline execution via LangGraph."""

    async def start(self, project_id: str, initial_message: str) -> dict:
        # TODO: Start LangGraph pipeline
        return {"status": "running"}

    async def pause(self, project_id: str) -> dict:
        # TODO: Pause pipeline
        return {"status": "paused"}

    async def resume(self, project_id: str) -> dict:
        # TODO: Resume pipeline
        return {"status": "running"}

    async def submit_decision(self, project_id: str, decision: dict) -> dict:
        # TODO: Submit decision and resume
        return {"status": "running"}
