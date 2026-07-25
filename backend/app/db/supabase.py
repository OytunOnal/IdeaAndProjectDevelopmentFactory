from app.config import settings


def get_supabase_client():
    """Get Supabase client. Requires SUPABASE_URL and SUPABASE_SERVICE_KEY."""
    if not settings.supabase_url:
        raise RuntimeError("SUPABASE_URL not configured")
    # TODO: from supabase import create_client
    # return create_client(settings.supabase_url, settings.supabase_service_key)
    return None
