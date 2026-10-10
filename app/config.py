from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False

    download_dir: Path = Path("./downloads")
    max_concurrent_downloads: int = 3
    job_timeout_seconds: int = 600
    file_ttl_seconds: int = 3600

    cookies_file: str | None = None
    cors_origins: str = "*"

    @property
    def cors_origin_list(self) -> list[str]:
        if self.cors_origins.strip() == "*":
            return ["*"]
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
settings.download_dir.mkdir(parents=True, exist_ok=True)
