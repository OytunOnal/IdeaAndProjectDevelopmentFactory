from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Supabase
    supabase_url: str = ""
    supabase_service_key: str = ""
    supabase_anon_key: str = ""
    supabase_publishable_key: str = ""
    supabase_secret_key: str = ""
    supabase_jwt_secret: str = ""

    # Redis
    redis_url: str = "redis://localhost:6379"
    upstash_redis_rest_url: str = ""
    upstash_redis_rest_token: str = ""

    # App
    cors_origins: list[str] = ["http://localhost:3000"]
    log_level: str = "DEBUG"
    # Local persistence (SQLite checkpoints + project index)
    data_dir: str = "data"

    # LLM API keys
    google_api_key: str = ""
    google_api_key_2: str = ""
    cerebras_api_key: str = ""
    groq_api_key: str = ""
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    anthropic_api_key: str = ""
    openai_api_key: str = ""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
