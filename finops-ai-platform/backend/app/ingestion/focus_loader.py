"""
FOCUS Loader — parses validated FOCUS records and inserts into SQLite.
"""
import json
from pathlib import Path
from app.database import get_connection
from app.ingestion.focus_validator import validate_focus_records


def load_focus_file(file_path: Path) -> int:
    """
    Load a FOCUS billing file (JSON) into the billing_records table.

    Returns:
        Number of records inserted.
    """
    with open(file_path) as f:
        raw_records = json.load(f)

    # Validate and normalize
    records = validate_focus_records(raw_records)

    # Insert into SQLite
    conn = get_connection()
    inserted = 0
    for r in records:
        conn.execute("""
            INSERT INTO billing_records (
                billing_period_start, billing_period_end, billed_cost,
                effective_cost, service_name, service_category, charge_type,
                resource_id, resource_name, region, tags,
                usage_quantity, pricing_unit
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            r.get("billing_period_start"),
            r.get("billing_period_end"),
            r.get("billed_cost", 0),
            r.get("effective_cost"),
            r.get("service_name", "Unknown"),
            r.get("service_category"),
            r.get("charge_type", "Usage"),
            r.get("resource_id"),
            r.get("resource_name"),
            r.get("region"),
            r.get("tags") if isinstance(r.get("tags"), str) else json.dumps(r.get("tags")),
            r.get("usage_quantity"),
            r.get("pricing_unit"),
        ))
        inserted += 1

    conn.commit()
    conn.close()
    return inserted
