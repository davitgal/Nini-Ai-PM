from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # App
    app_env: str = "development"
    log_level: str = "INFO"
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # Database (Supabase)
    database_url: str
    direct_database_url: str = ""  # Direct connection for migrations (port 5432)
    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_key: str = ""

    # ClickUp — primary token (TrueCodeLab + CubicSoft)
    clickup_api_token: str = ""
    clickup_team_id: str = "9014579452"
    # ClickUp — Yerevan Mall token (separate account)
    clickup_ym_api_token: str = ""

    # Webhook
    webhook_base_url: str = ""
    clickup_webhook_secret: str = ""

    # Anthropic (Phase 2)
    anthropic_api_key: str = ""

    # Telegram (Phase 2)
    telegram_bot_token: str = ""

    @property
    def is_dev(self) -> bool:
        return self.app_env == "development"


settings = Settings()  # type: ignore[call-arg]
