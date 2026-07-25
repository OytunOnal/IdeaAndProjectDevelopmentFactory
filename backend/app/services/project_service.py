class ProjectService:
    """Handles project CRUD operations."""

    async def create(self, name: str, description: str | None = None) -> dict:
        # TODO: Create project in Supabase
        return {}

    async def get(self, project_id: str) -> dict | None:
        # TODO: Fetch from Supabase
        return None

    async def list_for_user(self, user_id: str) -> list[dict]:
        # TODO: Fetch user's projects
        return []

    async def delete(self, project_id: str) -> bool:
        # TODO: Delete from Supabase
        return True
