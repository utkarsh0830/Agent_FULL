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

    # ── Database (cloud-agnostic) ────────────────────────
    database_url: str = ""  # PostgreSQL: postgresql://user:pass@host:5432/db
    database_path: str = "./data/finops.db"  # SQLite fallback

    # ── AWS ──────────────────────────────────────────────
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_region: str = "us-east-1"
    aws_cur_bucket: str = ""  # S3 bucket with CUR FOCUS Parquet

    # ── Azure ────────────────────────────────────────────
    azure_tenant_id: str = ""
    azure_client_id: str = ""
    azure_client_secret: str = ""
    azure_subscription_id: str = ""
    azure_cost_storage_account: str = ""
    azure_cost_container: str = "billing"

    # ── GCP ──────────────────────────────────────────────
    gcp_project_id: str = ""
    gcp_bigquery_dataset: str = "billing_export"

    # ── Connectors ───────────────────────────────────────
    opencost_api_url: str = ""
    infracost_api_key: str = ""
    custodian_policy_dir: str = "./custodian-policies"

    # ── GitHub (deployment events) ───────────────────────
    github_repo: str = ""
    github_token: str = ""

    # ── Spike detection ──────────────────────────────────
    spike_check_interval_hours: int = 1
    spike_threshold_pct: float = 20.0

    # ── Feature flags ────────────────────────────────────
    use_mock_data: bool = True
    enabled_providers: str = "AWS"  # Comma-separated: "AWS,Azure,GCP"

    # ── Server ───────────────────────────────────────────
    allowed_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    @property
    def data_dir(self) -> Path:
        return Path(__file__).parent / "data"

    @property
    def provider_list(self) -> list[str]:
        return [p.strip() for p in self.enabled_providers.split(",") if p.strip()]

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
