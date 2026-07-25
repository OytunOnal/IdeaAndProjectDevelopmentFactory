from fastapi import APIRouter

router = APIRouter()


@router.post("/settings/api-keys")
async def save_api_key():
    return {"provider": "anthropic", "status": "valid", "models_available": []}


@router.get("/settings/api-keys")
async def get_api_keys():
    return {
        "keys": [
            {"provider": "anthropic", "configured": False, "last_validated": None},
            {"provider": "openai", "configured": False, "last_validated": None},
            {"provider": "google", "configured": False, "last_validated": None},
        ]
    }


@router.put("/settings/autonomy")
async def update_autonomy():
    return {"status": "updated"}
