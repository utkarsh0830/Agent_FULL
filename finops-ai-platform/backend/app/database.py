"""
PostgreSQL database layer for FOCUS billing records and remediation queue.

Cloud-agnostic: PostgreSQL runs on any cloud (RDS, Azure DB, Cloud SQL)
or locally via Docker.

Uses psycopg2 for synchronous queries (compatible with the existing
codebase pattern). Supports both PostgreSQL and SQLite fallback.
"""
import json
from datetime import datetime
from app.config import settings


# ── Connection ───────────────────────────────────────────────

def _use_postgres() -> bool:
    return bool(settings.database_url and settings.database_url.startswith("postgresql"))


def get_connection():
    """Get a database connection — PostgreSQL or SQLite fallback."""
    if _use_postgres():
        import psycopg2
        import psycopg2.extras
        conn = psycopg2.connect(settings.database_url)
        conn.autocommit = False
        return conn
    else:
        import sqlite3
        from pathlib import Path
        Path(settings.database_path).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(settings.database_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn


def _fetchall_dicts(conn, query: str, params=None) -> list[dict]:
    """Execute query and return list of dicts — works for both PG and SQLite."""
    if _use_postgres():
        import psycopg2.extras
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(query, params or ())
        rows = cur.fetchall()
        cur.close()
        return [dict(r) for r in rows]
    else:
        rows = conn.execute(query, params or ()).fetchall()
        return [dict(r) for r in rows]


def _execute(conn, query: str, params=None):
    """Execute a statement — works for both PG and SQLite."""
    if _use_postgres():
        cur = conn.cursor()
        cur.execute(query, params or ())
        cur.close()
    else:
        conn.execute(query, params or ())


# ── Schema ───────────────────────────────────────────────────

_PG_SCHEMA = """
CREATE TABLE IF NOT EXISTS focus_billing (
    id              BIGSERIAL PRIMARY KEY,
    provider        VARCHAR(20) NOT NULL DEFAULT 'AWS',
    billing_period_start TIMESTAMP NOT NULL,
    billing_period_end   TIMESTAMP,
    billed_cost     DECIMAL(12,4) NOT NULL,
    effective_cost  DECIMAL(12,4),
    billing_currency VARCHAR(3) DEFAULT 'USD',
    service_name    VARCHAR(255),
    service_category VARCHAR(255),
    resource_id     VARCHAR(512),
    resource_name   VARCHAR(255),
    resource_type   VARCHAR(255),
    region          VARCHAR(100),
    availability_zone VARCHAR(100),
    billing_account_id   VARCHAR(255),
    billing_account_name VARCHAR(255),
    sub_account_id       VARCHAR(255),
    sub_account_name     VARCHAR(255),
    tags            JSONB DEFAULT '{}',
    usage_quantity  DECIMAL(18,6),
    usage_unit      VARCHAR(50),
    pricing_quantity DECIMAL(18,6),
    pricing_unit    VARCHAR(50),
    charge_type     VARCHAR(50) DEFAULT 'Usage',
    ingested_at     TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS remediation_queue (
    id TEXT PRIMARY KEY,
    provider VARCHAR(20) DEFAULT 'AWS',
    policy_yaml TEXT NOT NULL,
    description TEXT,
    affected_resources TEXT,
    estimated_savings DECIMAL(12,2),
    risk_level VARCHAR(20) DEFAULT 'medium',
    status VARCHAR(20) DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT NOW(),
    decided_at TIMESTAMP,
    decided_by TEXT
);

CREATE INDEX IF NOT EXISTS idx_focus_period ON focus_billing(billing_period_start);
CREATE INDEX IF NOT EXISTS idx_focus_provider ON focus_billing(provider);
CREATE INDEX IF NOT EXISTS idx_focus_service ON focus_billing(service_name);
CREATE INDEX IF NOT EXISTS idx_focus_resource ON focus_billing(resource_id);
CREATE INDEX IF NOT EXISTS idx_remediation_status ON remediation_queue(status);
"""

_SQLITE_SCHEMA = """
CREATE TABLE IF NOT EXISTS focus_billing (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider TEXT NOT NULL DEFAULT 'AWS',
    billing_period_start TEXT NOT NULL,
    billing_period_end TEXT,
    billed_cost REAL NOT NULL,
    effective_cost REAL,
    billing_currency TEXT DEFAULT 'USD',
    service_name TEXT,
    service_category TEXT,
    resource_id TEXT,
    resource_name TEXT,
    resource_type TEXT,
    region TEXT,
    availability_zone TEXT,
    billing_account_id TEXT,
    billing_account_name TEXT,
    sub_account_id TEXT,
    sub_account_name TEXT,
    tags TEXT DEFAULT '{}',
    usage_quantity REAL,
    usage_unit TEXT,
    pricing_quantity REAL,
    pricing_unit TEXT,
    charge_type TEXT DEFAULT 'Usage',
    ingested_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS remediation_queue (
    id TEXT PRIMARY KEY,
    provider TEXT DEFAULT 'AWS',
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

CREATE INDEX IF NOT EXISTS idx_focus_period ON focus_billing(billing_period_start);
CREATE INDEX IF NOT EXISTS idx_focus_provider ON focus_billing(provider);
CREATE INDEX IF NOT EXISTS idx_focus_service ON focus_billing(service_name);
CREATE INDEX IF NOT EXISTS idx_focus_resource ON focus_billing(resource_id);
CREATE INDEX IF NOT EXISTS idx_remediation_status ON remediation_queue(status);
"""


def init_db():
    """Create tables if they don't exist."""
    conn = get_connection()
    if _use_postgres():
        cur = conn.cursor()
        cur.execute(_PG_SCHEMA)
        cur.close()
        conn.commit()
    else:
        conn.executescript(_SQLITE_SCHEMA)
        conn.commit()
    conn.close()


# ── Billing Ingestion ────────────────────────────────────────

def insert_focus_records(records: list[dict], provider: str = "AWS"):
    """Insert FOCUS-normalized billing records."""
    conn = get_connection()

    for r in records:
        tags = r.get("tags", {})
        if isinstance(tags, dict):
            tags_val = json.dumps(tags) if not _use_postgres() else json.dumps(tags)
        elif isinstance(tags, str):
            tags_val = tags
        else:
            tags_val = "{}"

        if _use_postgres():
            _execute(conn, """
                INSERT INTO focus_billing
                (provider, billing_period_start, billing_period_end, billed_cost,
                 effective_cost, billing_currency, service_name, service_category,
                 resource_id, resource_name, resource_type, region,
                 billing_account_id, sub_account_id, sub_account_name,
                 tags, usage_quantity, pricing_unit, charge_type)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s)
            """, (
                provider, r.get("billing_period_start"), r.get("billing_period_end"),
                r.get("billed_cost", 0), r.get("effective_cost"),
                r.get("billing_currency", "USD"),
                r.get("service_name"), r.get("service_category"),
                r.get("resource_id"), r.get("resource_name"), r.get("resource_type"),
                r.get("region"), r.get("billing_account_id"),
                r.get("sub_account_id"), r.get("sub_account_name"),
                tags_val, r.get("usage_quantity"), r.get("pricing_unit"),
                r.get("charge_type", "Usage"),
            ))
        else:
            _execute(conn, """
                INSERT INTO focus_billing
                (provider, billing_period_start, billing_period_end, billed_cost,
                 effective_cost, billing_currency, service_name, service_category,
                 resource_id, resource_name, resource_type, region,
                 billing_account_id, sub_account_id, sub_account_name,
                 tags, usage_quantity, pricing_unit, charge_type)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                provider, r.get("billing_period_start"), r.get("billing_period_end"),
                r.get("billed_cost", 0), r.get("effective_cost"),
                r.get("billing_currency", "USD"),
                r.get("service_name"), r.get("service_category"),
                r.get("resource_id"), r.get("resource_name"), r.get("resource_type"),
                r.get("region"), r.get("billing_account_id"),
                r.get("sub_account_id"), r.get("sub_account_name"),
                tags_val, r.get("usage_quantity"), r.get("pricing_unit"),
                r.get("charge_type", "Usage"),
            ))

    conn.commit()
    conn.close()
    return len(records)


# ── Query helpers ────────────────────────────────────────────

def _param(idx=None):
    """Return placeholder char for the active DB engine."""
    return "%s" if _use_postgres() else "?"


def get_daily_costs(service: str | None = None, provider: str | None = None) -> list[dict]:
    """Get daily cost aggregates, optionally filtered by service/provider."""
    conn = get_connection()
    p = _param()

    if _use_postgres():
        query = f"""
            SELECT billing_period_start::date as date,
                   provider,
                   SUM(billed_cost) as total_cost,
                   COUNT(DISTINCT resource_id) as resource_count
            FROM focus_billing WHERE 1=1
        """
    else:
        query = """
            SELECT billing_period_start as date,
                   provider,
                   SUM(billed_cost) as total_cost,
                   COUNT(DISTINCT resource_id) as resource_count
            FROM focus_billing WHERE 1=1
        """
    params = []
    if service:
        query += f" AND service_name = {p}"
        params.append(service)
    if provider:
        query += f" AND provider = {p}"
        params.append(provider)
    query += " GROUP BY 1, 2 ORDER BY 1"

    rows = _fetchall_dicts(conn, query, params)
    conn.close()
    return rows


def get_cost_summary(group_by: str = "service_name", provider: str | None = None) -> list[dict]:
    """Get cost aggregated by a dimension."""
    allowed = {"service_name", "service_category", "region", "charge_type", "provider"}
    if group_by not in allowed:
        group_by = "service_name"

    conn = get_connection()
    p = _param()
    where = ""
    params = []
    if provider:
        where = f" WHERE provider = {p}"
        params.append(provider)

    rows = _fetchall_dicts(conn, f"""
        SELECT {group_by} as dimension,
               provider,
               SUM(billed_cost) as total_cost,
               COUNT(*) as record_count,
               COUNT(DISTINCT resource_id) as resource_count
        FROM focus_billing {where}
        GROUP BY {group_by}, provider
        ORDER BY total_cost DESC
    """, params)
    conn.close()
    return rows


def detect_anomalies(threshold_pct: float = 30) -> list[dict]:
    """Detect daily cost anomalies exceeding threshold vs 7-day rolling avg."""
    conn = get_connection()

    if _use_postgres():
        query = """
            WITH daily AS (
                SELECT billing_period_start::date as date,
                       provider, service_name,
                       SUM(billed_cost) as daily_cost
                FROM focus_billing GROUP BY 1, 2, 3
            ),
            with_avg AS (
                SELECT date, provider, service_name, daily_cost,
                       AVG(daily_cost) OVER (
                           PARTITION BY provider, service_name
                           ORDER BY date
                           ROWS BETWEEN 7 PRECEDING AND 1 PRECEDING
                       ) as avg_cost_7d
                FROM daily
            )
            SELECT date, provider, service_name, daily_cost, avg_cost_7d,
                   CASE WHEN avg_cost_7d > 0
                        THEN ((daily_cost - avg_cost_7d) / avg_cost_7d) * 100
                        ELSE 0 END as pct_change
            FROM with_avg
            WHERE avg_cost_7d > 0
              AND ((daily_cost - avg_cost_7d) / avg_cost_7d) * 100 > %s
            ORDER BY date DESC, pct_change DESC
        """
    else:
        query = """
            WITH daily AS (
                SELECT billing_period_start as date,
                       provider, service_name,
                       SUM(billed_cost) as daily_cost
                FROM focus_billing GROUP BY 1, 2, 3
            ),
            with_avg AS (
                SELECT date, provider, service_name, daily_cost,
                       AVG(daily_cost) OVER (
                           PARTITION BY provider, service_name
                           ORDER BY date
                           ROWS BETWEEN 7 PRECEDING AND 1 PRECEDING
                       ) as avg_cost_7d
                FROM daily
            )
            SELECT date, provider, service_name, daily_cost, avg_cost_7d,
                   CASE WHEN avg_cost_7d > 0
                        THEN ((daily_cost - avg_cost_7d) / avg_cost_7d) * 100
                        ELSE 0 END as pct_change
            FROM with_avg
            WHERE avg_cost_7d > 0
              AND ((daily_cost - avg_cost_7d) / avg_cost_7d) * 100 > ?
            ORDER BY date DESC, pct_change DESC
        """

    rows = _fetchall_dicts(conn, query, (threshold_pct,))
    conn.close()
    return rows


def get_untagged_resources() -> list[dict]:
    """Find resources with missing or empty tags."""
    conn = get_connection()
    if _use_postgres():
        query = """
            SELECT resource_id, resource_name, service_name, provider, region,
                   SUM(billed_cost) as total_cost, tags
            FROM focus_billing
            WHERE tags IS NULL OR tags = '{}'::jsonb
            GROUP BY resource_id, resource_name, service_name, provider, region, tags
            ORDER BY total_cost DESC
        """
    else:
        query = """
            SELECT resource_id, resource_name, service_name, provider, region,
                   SUM(billed_cost) as total_cost, tags
            FROM focus_billing
            WHERE tags IS NULL OR tags = '{}' OR tags = '' OR tags = 'null'
            GROUP BY resource_id
            ORDER BY total_cost DESC
        """
    rows = _fetchall_dicts(conn, query)
    conn.close()
    return rows


def get_all_billing_records(limit: int = 500) -> list[dict]:
    """Get billing records for agent consumption."""
    conn = get_connection()
    p = _param()
    rows = _fetchall_dicts(conn, f"""
        SELECT provider, billing_period_start, billed_cost, service_name,
               resource_id, resource_name, region, tags, charge_type
        FROM focus_billing
        ORDER BY billing_period_start DESC
        LIMIT {p}
    """, (limit,))
    conn.close()
    return rows


# ── Remediation queue ────────────────────────────────────────

def create_remediation(action: dict) -> str:
    """Stage a remediation action for human approval."""
    conn = get_connection()
    p = _param()
    _execute(conn, f"""
        INSERT INTO remediation_queue (id, provider, policy_yaml, description,
                   affected_resources, estimated_savings, risk_level, status)
        VALUES ({p},{p},{p},{p},{p},{p},{p},'pending')
    """, (
        action["action_id"],
        action.get("provider", "AWS"),
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
    p = _param()
    _execute(conn, f"""
        UPDATE remediation_queue
        SET status = 'approved', decided_at = {p}, decided_by = {p}
        WHERE id = {p} AND status = 'pending'
    """, (datetime.utcnow().isoformat(), decided_by, action_id))
    conn.commit()
    rows = _fetchall_dicts(conn, f"SELECT * FROM remediation_queue WHERE id = {p}", (action_id,))
    conn.close()
    return rows[0] if rows else {}


def reject_remediation(action_id: str, decided_by: str = "user") -> dict:
    """Reject a staged remediation action."""
    conn = get_connection()
    p = _param()
    _execute(conn, f"""
        UPDATE remediation_queue
        SET status = 'rejected', decided_at = {p}, decided_by = {p}
        WHERE id = {p} AND status = 'pending'
    """, (datetime.utcnow().isoformat(), decided_by, action_id))
    conn.commit()
    rows = _fetchall_dicts(conn, f"SELECT * FROM remediation_queue WHERE id = {p}", (action_id,))
    conn.close()
    return rows[0] if rows else {}


def get_pending_remediations() -> list[dict]:
    """Get all pending remediation actions."""
    conn = get_connection()
    rows = _fetchall_dicts(conn, "SELECT * FROM remediation_queue WHERE status = 'pending'")
    conn.close()
    return rows
