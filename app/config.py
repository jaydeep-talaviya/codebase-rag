from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    redis_url: str
    max_file_size_mb: int = 1

    class Config:
        env_file = ".env"

settings = Settings()