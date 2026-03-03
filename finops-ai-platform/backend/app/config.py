"""
Application configuration using pydantic-settings.
Reads from .env file or environment variables.
"""
from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    """FinOps AI Platform configuration."""

    # ── LLM ──────────────────────────────────────────────
    openai_api_key: str = ""
    google_api_key: str = ""
    grok_api_key: str = ""
    groq_api_key: str = ""
    llm_provider: str = "groq"  # "groq", "gemini", "openai", or "grok"
    llm_model: str = "llama-3.3-70b-versatile"

    # ── AWS (for S3 FOCUS ingestion) ─────────────────────
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_region: str = "us-east-1"
    focus_s3_bucket: str = ""

    # ── Connectors (optional — uses mock data if blank) ──
    opencost_api_url: str = ""  # e.g. http://opencost:9003
    infracost_api_key: str = ""
    custodian_policy_dir: str = "./policies"

    # ── Database ─────────────────────────────────────────
    database_path: str = "./data/finops.db"

    # ── Feature flags ────────────────────────────────────
    use_mock_data: bool = True  # False when real connectors are configured

    # ── Server ───────────────────────────────────────────
    allowed_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    @property
    def data_dir(self) -> Path:
        return Path(__file__).parent / "data"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
