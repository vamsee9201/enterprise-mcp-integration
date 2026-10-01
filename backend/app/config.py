from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://portal:portal@localhost:5433/portal"
    demo_mode: bool = False
    app_timezone: str = "America/Chicago"
    web_origin: str = "http://localhost:3000"
    secure_cookies: bool = False
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
