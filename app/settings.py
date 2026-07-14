from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Multi Brand Video Agent"
    app_env: str = "development"
    app_port: int = 8000

    google_application_credentials: Path = Path(
        "/app/credentials/service_account.json"
    )

    workspace_root: Path = Path("/app/workspace")

    clickup_api_token: str
    clickup_api_base: str = "https://api.clickup.com/api/v2"

    internal_api_key: str

    default_bgm_volume: float = 0.08
    output_existing_policy: str = "skip"

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False
    )


settings = Settings()