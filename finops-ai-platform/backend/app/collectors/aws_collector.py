"""
AWS Collector — fetches CUR 2.0 FOCUS Parquet from S3
and inserts into the centralized FOCUS database.

AWS CUR 2.0 already uses FOCUS column names, so minimal
transformation is needed (mostly a passthrough).
"""
import json
import io
from app.config import settings
from app.collectors.focus_normalizer import normalize_to_focus
from app.database import insert_focus_records


async def collect_aws_billing() -> int:
    """
    Download CUR FOCUS data from S3 and insert into database.
    Returns number of records inserted.
    """
    if not settings.aws_cur_bucket:
        print("[aws_collector] No AWS_CUR_BUCKET configured, skipping")
        return 0

    import boto3
    import pandas as pd

    s3 = boto3.client(
        "s3",
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
        region_name=settings.aws_region,
    )

    # List recent Parquet files in the CUR bucket
    response = s3.list_objects_v2(
        Bucket=settings.aws_cur_bucket,
        Prefix="focus/",
        MaxKeys=50,
    )

    total = 0
    for obj in response.get("Contents", []):
        key = obj["Key"]
        if not key.endswith(".parquet"):
            continue

        # Download Parquet file
        buf = io.BytesIO()
        s3.download_fileobj(settings.aws_cur_bucket, key, buf)
        buf.seek(0)

        df = pd.read_parquet(buf)
        records = normalize_to_focus(df, provider="AWS")
        inserted = insert_focus_records(records, provider="AWS")
        total += inserted
        print(f"[aws_collector] Loaded {inserted} records from {key}")

    return total


def load_mock_aws_data() -> int:
    """Load mock FOCUS data for development."""
    mock_path = settings.data_dir / "mock_focus_data.json"
    if not mock_path.exists():
        return 0

    with open(mock_path) as f:
        raw = json.load(f)

    # Mock data is already in FOCUS-like format
    records = normalize_to_focus(raw, provider="AWS", column_map={
        "billing_period_start": "billing_period_start",
        "billing_period_end": "billing_period_end",
        "billed_cost": "billed_cost",
        "effective_cost": "effective_cost",
        "service_name": "service_name",
        "service_category": "service_category",
        "resource_id": "resource_id",
        "resource_name": "resource_name",
        "region": "region",
        "tags": "tags",
        "usage_quantity": "usage_quantity",
        "pricing_unit": "pricing_unit",
        "charge_type": "charge_type",
    })
    return insert_focus_records(records, provider="AWS")
