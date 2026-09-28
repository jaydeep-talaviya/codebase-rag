from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    max_file_size_mb: int = 1
    openrouter_api_key: str
    llm_model: str
    # A repository is dropped once it has gone this long without being indexed,
    # previewed, or searched. It expires on idleness, not on age, so a
    # repository you are actively working in is never swept out from under you.
    repo_idle_ttl_hours: int = 12
    # How often the background sweeper runs. Also the worst-case delay before a
    # newly-expired repository is reclaimed.
    repo_cleanup_interval_minutes: int = 15
    repo_cleanup_enabled: bool = True
    # Comma-separated origins allowed to call the API. Defaults to the Vite dev
    # server so `npm run dev` works with no extra configuration.
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    class Config:
        env_file = ".env"

settings = Settings()