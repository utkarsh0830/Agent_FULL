"""
FOCUS Schema Validator — validates that ingested billing data
conforms to the FOCUS 1.0 specification.
"""


# FOCUS 1.0 required columns
# See: https://focus.finops.org
FOCUS_REQUIRED_COLUMNS = {
    "billing_period_start",  # or BillingPeriodStart
    "billed_cost",           # or BilledCost
    "service_name",          # or ServiceName
}

FOCUS_OPTIONAL_COLUMNS = {
    "billing_period_end",
    "effective_cost",
    "service_category",
    "charge_type",
    "resource_id",
    "resource_name",
    "region",
    "tags",
    "usage_quantity",
    "pricing_unit",
}

ALL_FOCUS_COLUMNS = FOCUS_REQUIRED_COLUMNS | FOCUS_OPTIONAL_COLUMNS


class FocusValidationError(Exception):
    """Raised when FOCUS data fails schema validation."""
    pass


def normalize_column_name(col: str) -> str:
    """Convert CamelCase FOCUS column names to snake_case."""
    import re
    # BillingPeriodStart → billing_period_start
    s1 = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", col)
    return re.sub("([a-z0-9])([A-Z])", r"\1_\2", s1).lower()


def validate_focus_records(records: list[dict]) -> list[dict]:
    """
    Validate and normalize a list of FOCUS billing records.

    - Converts CamelCase keys to snake_case
    - Checks that required columns exist
    - Coerces cost fields to float

    Returns:
        Validated and normalized records.

    Raises:
        FocusValidationError if required columns are missing.
    """
    if not records:
        raise FocusValidationError("Empty billing data — no records to validate.")

    # Normalize column names in all records
    normalized = []
    for record in records:
        norm = {normalize_column_name(k): v for k, v in record.items()}
        normalized.append(norm)

    # Check required columns in first record
    sample_keys = set(normalized[0].keys())
    missing = FOCUS_REQUIRED_COLUMNS - sample_keys
    if missing:
        raise FocusValidationError(
            f"Missing required FOCUS columns: {missing}. "
            f"Available: {sample_keys}"
        )

    # Coerce cost fields to float
    for record in normalized:
        for cost_field in ("billed_cost", "effective_cost"):
            if cost_field in record and record[cost_field] is not None:
                record[cost_field] = float(record[cost_field])
        if "usage_quantity" in record and record["usage_quantity"] is not None:
            record["usage_quantity"] = float(record["usage_quantity"])

    return normalized
