"""
Azure Collector — fetches billing data from Azure Cost Management
exports and normalizes to FOCUS format.

Azure exports to Blob Storage as CSV or JSON —
we download, transform columns, and insert into the FOCUS database.
"""
from app.config import settings
from app.collectors.focus_normalizer import normalize_to_focus, AZURE_TO_FOCUS
from app.database import insert_focus_records


async def collect_azure_billing() -> int:
    """
    Fetch Azure Cost Management export from Blob Storage,
    normalize to FOCUS, and insert into database.
    """
    if not settings.azure_cost_storage_account:
        print("[azure_collector] No AZURE_COST_STORAGE_ACCOUNT configured, skipping")
        return 0

    try:
        from azure.storage.blob import BlobServiceClient
        from azure.identity import ClientSecretCredential
        import pandas as pd
        import io
    except ImportError:
        print("[azure_collector] azure-storage-blob not installed, skipping")
        return 0

    credential = ClientSecretCredential(
        tenant_id=settings.azure_tenant_id,
        client_id=settings.azure_client_id,
        client_secret=settings.azure_client_secret,
    )

    blob_service = BlobServiceClient(
        account_url=f"https://{settings.azure_cost_storage_account}.blob.core.windows.net",
        credential=credential,
    )

    container = blob_service.get_container_client(settings.azure_cost_container)

    total = 0
    for blob in container.list_blobs():
        if not blob.name.endswith(".csv"):
            continue

        data = container.download_blob(blob.name).readall()
        df = pd.read_csv(io.BytesIO(data))
        records = normalize_to_focus(df, provider="Azure", column_map=AZURE_TO_FOCUS)
        inserted = insert_focus_records(records, provider="Azure")
        total += inserted
        print(f"[azure_collector] Loaded {inserted} records from {blob.name}")

    return total
