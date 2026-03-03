"""
FinOps AI Orchestration Platform — FastAPI Application.

This is the main entry point for the backend server.
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.database import init_db
from app.api.routes import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database on startup."""
    init_db()

    # Auto-load mock data in dev mode if DB is empty
    if settings.use_mock_data:
        from app.database import get_connection
        conn = get_connection()
        count = conn.execute("SELECT COUNT(*) FROM billing_records").fetchone()[0]
        conn.close()
        if count == 0:
            from app.ingestion.focus_loader import load_focus_file
            from app.config import settings as s
            mock_path = s.data_dir / "mock_focus_data.json"
            if mock_path.exists():
                loaded = load_focus_file(mock_path)
                print(f"[startup] Loaded {loaded} mock FOCUS records into SQLite")

    yield


app = FastAPI(
    title="FinOps AI Orchestration Platform",
    description=(
        "AI-powered orchestration layer over OpenCost, Infracost, "
        "and Cloud Custodian. Ingests FOCUS billing data, runs "
        "multi-agent analysis, and provides human-in-the-loop remediation."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

# ── CORS ──
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routes ──
app.include_router(router)
