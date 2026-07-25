class KeyService:
    """Handles API key encryption and storage."""

    async def save_key(self, user_id: str, provider: str, api_key: str) -> dict:
        # TODO: Encrypt and store in Redis
        return {"provider": provider, "status": "valid"}

    async def get_key(self, user_id: str, provider: str) -> str | None:
        # TODO: Decrypt and return from Redis
        return None

    async def validate_key(self, provider: str, api_key: str) -> bool:
        # TODO: Test call to provider
        return True

    async def list_keys(self, user_id: str) -> list[dict]:
        # TODO: Return configured key statuses
        return []
