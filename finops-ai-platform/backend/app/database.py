"""
SQLite database layer for FOCUS billing records and remediation queue.

Uses plain sqlite3 for simplicity — no ORM overhead for a prototype.
In production, swap to PostgreSQL + SQLAlchemy/Alembic.
"""
import sqlite3
import json
from pathlib import Path
from datetime import datetime
from app.config import settings


DB_PATH = settings.database_path


def get_connection() -> sqlite3.Connection:
    """Get a SQLite connection with row_factory for dict-like access."""
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    """Create tables if they don't exist."""
    conn = get_connection()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS billing_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            billing_period_start TEXT NOT NULL,
            billing_period_end TEXT,
            billed_cost REAL NOT NULL,
            effective_cost REAL,
            service_name TEXT NOT NULL,
            service_category TEXT,
            charge_type TEXT DEFAULT 'Usage',
            resource_id TEXT,
            resource_name TEXT,
            region TEXT,
            tags TEXT,
            usage_quantity REAL,
            pricing_unit TEXT,
            ingested_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS remediation_queue (
            id TEXT PRIMARY KEY,
            policy_yaml TEXT NOT NULL,
            description TEXT,
            affected_resources TEXT,
            estimated_savings REAL,
            risk_level TEXT DEFAULT 'medium',
            status TEXT DEFAULT 'pending',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            decided_at TEXT,
            decided_by TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_billing_period
            ON billing_records(billing_period_start);
        CREATE INDEX IF NOT EXISTS idx_billing_service
            ON billing_records(service_name);
        CREATE INDEX IF NOT EXISTS idx_remediation_status
            ON remediation_queue(status);
    """)
    conn.commit()
    conn.close()


# ── Query helpers ────────────────────────────────────────────


def get_daily_costs(service: str | None = None) -> list[dict]:
    """Get daily cost aggregates, optionally filtered by service."""
    conn = get_connection()
    query = """
        SELECT billing_period_start as date,
               SUM(billed_cost) as total_cost,
               COUNT(DISTINCT resource_id) as resource_count
        FROM billing_records
    """
    params = []
    if service:
        query += " WHERE service_name = ?"
        params.append(service)
    query += " GROUP BY billing_period_start ORDER BY billing_period_start"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_cost_summary(group_by: str = "service_name") -> list[dict]:
    """Get cost aggregated by a dimension (service_name, region, etc.)."""
    allowed = {"service_name", "service_category", "region", "charge_type"}
    if group_by not in allowed:
        group_by = "service_name"

    conn = get_connection()
    rows = conn.execute(f"""
        SELECT {group_by} as dimension,
               SUM(billed_cost) as total_cost,
               COUNT(*) as record_count,
               COUNT(DISTINCT resource_id) as resource_count
        FROM billing_records
        GROUP BY {group_by}
        ORDER BY total_cost DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def detect_anomalies(threshold_pct: float = 30) -> list[dict]:
    """Detect daily cost anomalies exceeding threshold vs 7-day rolling avg."""
    conn = get_connection()
    rows = conn.execute("""
        WITH daily AS (
            SELECT billing_period_start as date,
                   service_name,
                   SUM(billed_cost) as daily_cost
            FROM billing_records
            GROUP BY billing_period_start, service_name
        ),
        with_avg AS (
            SELECT date, service_name, daily_cost,
                   AVG(daily_cost) OVER (
                       PARTITION BY service_name
                       ORDER BY date
                       ROWS BETWEEN 7 PRECEDING AND 1 PRECEDING
                   ) as avg_cost_7d
            FROM daily
        )
        SELECT date, service_name, daily_cost, avg_cost_7d,
               CASE WHEN avg_cost_7d > 0
                    THEN ((daily_cost - avg_cost_7d) / avg_cost_7d) * 100
                    ELSE 0 END as pct_change
        FROM with_avg
        WHERE avg_cost_7d > 0
          AND ((daily_cost - avg_cost_7d) / avg_cost_7d) * 100 > ?
        ORDER BY date DESC, pct_change DESC
    """, (threshold_pct,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_untagged_resources() -> list[dict]:
    """Find resources with missing or empty tags."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT resource_id, resource_name, service_name, region,
               SUM(billed_cost) as total_cost, tags
        FROM billing_records
        WHERE tags IS NULL OR tags = '{}' OR tags = '' OR tags = 'null'
        GROUP BY resource_id
        ORDER BY total_cost DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_idle_resources() -> list[dict]:
    """Find resources with low usage but significant cost."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT resource_id, resource_name, service_name, region,
               SUM(billed_cost) as total_cost,
               AVG(usage_quantity) as avg_usage,
               tags
        FROM billing_records
        WHERE usage_quantity IS NOT NULL AND usage_quantity < 5
          AND billed_cost > 10
        GROUP BY resource_id
        ORDER BY total_cost DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Remediation queue ────────────────────────────────────────


def create_remediation(action: dict) -> str:
    """Stage a remediation action for human approval."""
    conn = get_connection()
    conn.execute("""
        INSERT INTO remediation_queue (id, policy_yaml, description,
                   affected_resources, estimated_savings, risk_level, status)
        VALUES (?, ?, ?, ?, ?, ?, 'pending')
    """, (
        action["action_id"],
        action.get("custodian_policy", ""),
        action.get("description", ""),
        json.dumps(action.get("affected_resources", [])),
        action.get("estimated_monthly_savings", 0),
        action.get("risk_level", "medium"),
    ))
    conn.commit()
    conn.close()
    return action["action_id"]


def approve_remediation(action_id: str, decided_by: str = "user") -> dict:
    """Approve a staged remediation action."""
    conn = get_connection()
    conn.execute("""
        UPDATE remediation_queue
        SET status = 'approved', decided_at = ?, decided_by = ?
        WHERE id = ? AND status = 'pending'
    """, (datetime.utcnow().isoformat(), decided_by, action_id))
    conn.commit()
    row = conn.execute("SELECT * FROM remediation_queue WHERE id = ?",
                       (action_id,)).fetchone()
    conn.close()
    return dict(row) if row else {}


def reject_remediation(action_id: str, decided_by: str = "user") -> dict:
    """Reject a staged remediation action."""
    conn = get_connection()
    conn.execute("""
        UPDATE remediation_queue
        SET status = 'rejected', decided_at = ?, decided_by = ?
        WHERE id = ? AND status = 'pending'
    """, (datetime.utcnow().isoformat(), decided_by, action_id))
    conn.commit()
    row = conn.execute("SELECT * FROM remediation_queue WHERE id = ?",
                       (action_id,)).fetchone()
    conn.close()
    return dict(row) if row else {}


def get_pending_remediations() -> list[dict]:
    """Get all pending remediation actions."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM remediation_queue WHERE status = 'pending'"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
