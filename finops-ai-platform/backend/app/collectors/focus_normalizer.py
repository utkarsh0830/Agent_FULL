"""
FOCUS Normalizer — maps cloud-specific billing columns to the
FinOps Open Cost & Usage Specification (FOCUS) schema.

This is the single point where all cloud data is standardized.
"""
import json
import pandas as pd
from typing import Any


# ── Column Mappings: Cloud → FOCUS ────────────────────────────

AWS_TO_FOCUS = {
    "bill_billing_period_start_date": "billing_period_start",
    "bill_billing_period_end_date": "billing_period_end",
    "line_item_blended_cost": "billed_cost",
    "line_item_unblended_cost": "effective_cost",
    "product_servicename": "service_name",
    "product_product_family": "service_category",
    "line_item_resource_id": "resource_id",
    "line_item_usage_type": "resource_type",
    "product_region": "region",
    "line_item_availability_zone": "availability_zone",
    "bill_payer_account_id": "billing_account_id",
    "line_item_usage_account_id": "sub_account_id",
    "line_item_usage_amount": "usage_quantity",
    "pricing_unit": "pricing_unit",
    "line_item_line_item_type": "charge_type",
    "bill_billing_currency": "billing_currency",
}

AZURE_TO_FOCUS = {
    "CostInBillingCurrency": "billed_cost",
    "EffectivePrice": "effective_cost",
    "ServiceName": "service_name",
    "MeterCategory": "service_category",
    "ResourceId": "resource_id",
    "ResourceName": "resource_name",
    "ResourceType": "resource_type",
    "ResourceLocation": "region",
    "SubscriptionId": "billing_account_id",
    "SubscriptionName": "billing_account_name",
    "ResourceGroup": "sub_account_name",
    "Date": "billing_period_start",
    "Quantity": "usage_quantity",
    "UnitOfMeasure": "pricing_unit",
    "ChargeType": "charge_type",
    "Currency": "billing_currency",
    "Tags": "tags",
}

GCP_TO_FOCUS = {
    "cost": "billed_cost",
    "credits.amount": "effective_cost",
    "service.description": "service_name",
    "sku.description": "resource_type",
    "resource.name": "resource_name",
    "resource.global_name": "resource_id",
    "project.id": "sub_account_id",
    "project.name": "sub_account_name",
    "billing_account_id": "billing_account_id",
    "usage_start_time": "billing_period_start",
    "usage_end_time": "billing_period_end",
    "usage.amount": "usage_quantity",
    "usage.unit": "pricing_unit",
    "location.region": "region",
    "location.zone": "availability_zone",
    "currency": "billing_currency",
    "labels": "tags",
}


def _parse_tags(tags_raw: Any) -> dict:
    """Parse tags from various formats into a dict."""
    if isinstance(tags_raw, dict):
        return tags_raw
    if isinstance(tags_raw, str):
        if not tags_raw or tags_raw in ("null", "None", "{}"):
            return {}
        try:
            parsed = json.loads(tags_raw)
            return parsed if isinstance(parsed, dict) else {}
        except (json.JSONDecodeError, TypeError):
            # Azure format: "key1: val1, key2: val2"
            result = {}
            for pair in tags_raw.split(","):
                if ":" in pair:
                    k, v = pair.split(":", 1)
                    result[k.strip().strip('"')] = v.strip().strip('"')
            return result
    if isinstance(tags_raw, list):
        # GCP format: [{"key": "k", "value": "v"}, ...]
        return {item["key"]: item["value"] for item in tags_raw if "key" in item}
    return {}


def normalize_to_focus(
    data: list[dict] | pd.DataFrame,
    provider: str,
    column_map: dict | None = None,
) -> list[dict]:
    """
    Normalize billing data from any cloud to FOCUS format.

    Args:
        data: Raw billing records (list of dicts or DataFrame)
        provider: "AWS", "Azure", or "GCP"
        column_map: Optional custom column mapping (auto-detected if None)

    Returns:
        List of FOCUS-compliant dicts ready for database insertion.
    """
    if column_map is None:
        column_map = {
            "AWS": AWS_TO_FOCUS,
            "Azure": AZURE_TO_FOCUS,
            "GCP": GCP_TO_FOCUS,
        }.get(provider, {})

    if isinstance(data, pd.DataFrame):
        df = data.copy()
    else:
        df = pd.DataFrame(data)

    if df.empty:
        return []

    # Rename columns that exist
    rename_map = {k: v for k, v in column_map.items() if k in df.columns}
    df = df.rename(columns=rename_map)

    # Ensure required columns
    df["provider"] = provider
    if "billed_cost" not in df.columns:
        df["billed_cost"] = 0
    if "billing_period_start" not in df.columns:
        df["billing_period_start"] = None
    if "service_name" not in df.columns:
        df["service_name"] = "Unknown"

    # Parse tags
    if "tags" in df.columns:
        df["tags"] = df["tags"].apply(_parse_tags)
    else:
        df["tags"] = [{}] * len(df)

    # Coerce types
    df["billed_cost"] = pd.to_numeric(df["billed_cost"], errors="coerce").fillna(0)
    if "effective_cost" in df.columns:
        df["effective_cost"] = pd.to_numeric(df["effective_cost"], errors="coerce")
    if "usage_quantity" in df.columns:
        df["usage_quantity"] = pd.to_numeric(df["usage_quantity"], errors="coerce")

    # Keep only FOCUS columns
    focus_cols = [
        "provider", "billing_period_start", "billing_period_end",
        "billed_cost", "effective_cost", "billing_currency",
        "service_name", "service_category",
        "resource_id", "resource_name", "resource_type",
        "region", "availability_zone",
        "billing_account_id", "billing_account_name",
        "sub_account_id", "sub_account_name",
        "tags", "usage_quantity", "pricing_unit", "charge_type",
    ]
    existing_cols = [c for c in focus_cols if c in df.columns]
    df = df[existing_cols]

    return df.to_dict(orient="records")
