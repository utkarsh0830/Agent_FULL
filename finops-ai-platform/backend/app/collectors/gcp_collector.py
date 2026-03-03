"""
GCP Collector — queries BigQuery billing export
and normalizes to FOCUS format.

GCP billing data lives in BigQuery — we query it,
transform columns, and insert into the FOCUS database.
"""
from app.config import settings
from app.collectors.focus_normalizer import normalize_to_focus, GCP_TO_FOCUS
from app.database import insert_focus_records


async def collect_gcp_billing() -> int:
    """
    Query GCP BigQuery billing export,
    normalize to FOCUS, and insert into database.
    """
    if not settings.gcp_project_id or not settings.gcp_bigquery_dataset:
        print("[gcp_collector] No GCP_PROJECT_ID configured, skipping")
        return 0

    try:
        from google.cloud import bigquery
    except ImportError:
        print("[gcp_collector] google-cloud-bigquery not installed, skipping")
        return 0

    client = bigquery.Client(project=settings.gcp_project_id)

    query = f"""
        SELECT
            service.description AS `service.description`,
            sku.description AS `sku.description`,
            project.id AS `project.id`,
            project.name AS `project.name`,
            billing_account_id,
            cost,
            credits,
            usage.amount AS `usage.amount`,
            usage.unit AS `usage.unit`,
            usage_start_time,
            usage_end_time,
            location.region AS `location.region`,
            location.zone AS `location.zone`,
            currency,
            labels
        FROM `{settings.gcp_project_id}.{settings.gcp_bigquery_dataset}.gcp_billing_export_*`
        WHERE DATE(usage_start_time) >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)
    """

    result = client.query(query)
    rows = [dict(row) for row in result]

    records = normalize_to_focus(rows, provider="GCP", column_map=GCP_TO_FOCUS)
    inserted = insert_focus_records(records, provider="GCP")
    print(f"[gcp_collector] Loaded {inserted} records from BigQuery")
    return inserted
