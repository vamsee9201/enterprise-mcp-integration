from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://portal:portal@localhost:5433/portal"
    demo_mode: bool = False
    app_timezone: str = "America/Chicago"
    web_origin: str = "http://localhost:3000"
    web_allowed_origins: list[str] = []
    secure_cookies: bool = False
    mcp_auth_mode: str | None = None
    mcp_public_url: str = "http://localhost:8001/mcp"
    mcp_allowed_hosts: list[str] = ["localhost:8001", "127.0.0.1:8001"]
    mcp_allowed_origins: list[str] = ["http://localhost:3000", "http://localhost:6274"]
    mcp_rate_limit: int = 120
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
