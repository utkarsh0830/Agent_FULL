"""
S3 Fetcher — downloads FOCUS billing files from AWS S3.

In production: uses boto3 to fetch real FOCUS exports.
In dev (USE_MOCK_DATA=true): falls back to local mock data.
"""
import json
import tempfile
from pathlib import Path
from app.config import settings


def fetch_from_s3(bucket: str, key: str) -> Path:
    """
    Download a FOCUS billing file from S3 to a local temp path.

    Args:
        bucket: S3 bucket name (e.g. 'finops-focus-data-123456')
        key: S3 object key (e.g. 'focus-export/2026-02/data.json')

    Returns:
        Path to the downloaded local file.
    """
    if settings.use_mock_data or not settings.aws_access_key_id:
        # ── DEV FALLBACK: return mock data path ──
        mock_path = settings.data_dir / "mock_focus_data.json"
        if mock_path.exists():
            return mock_path
        raise FileNotFoundError(f"Mock data not found at {mock_path}")

    # ── PRODUCTION: download from S3 ──
    # TODO: Replace with real boto3 S3 download when deploying to AWS
    import boto3

    s3_client = boto3.client(
        "s3",
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
        region_name=settings.aws_region,
    )

    # Download to a temp file
    suffix = ".json" if key.endswith(".json") else ".csv"
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    s3_client.download_file(bucket, key, tmp.name)
    return Path(tmp.name)
