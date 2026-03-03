"""
FinOps AI Orchestration Platform — FastAPI Application.

Cloud-agnostic backend with:
- Multi-cloud billing ingestion (AWS, Azure, GCP → FOCUS)
- PostgreSQL centralized store (with SQLite fallback)
- APScheduler for periodic spike detection
- LangGraph multi-agent chain
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.database import init_db
from app.api.routes import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database, load data, and start spike detector."""
    # 1. Init database schema
    init_db()
    print("[startup] Database initialized")

    # 2. Run collectors (mock or real depending on config)
    from app.services.spike_detector import run_collectors
    loaded = await run_collectors()
    print(f"[startup] Collectors loaded {loaded} records")

    # 3. Start APScheduler for spike detection (non-mock mode only)
    scheduler = None
    if not settings.use_mock_data:
        try:
            from apscheduler.schedulers.asyncio import AsyncIOScheduler
            from app.services.spike_detector import check_for_spikes

            scheduler = AsyncIOScheduler()
            scheduler.add_job(
                check_for_spikes,
                "interval",
                hours=settings.spike_check_interval_hours,
                id="spike_detector",
                name="Cost Spike Detector",
            )
            scheduler.start()
            print(
                f"[startup] Spike detector started "
                f"(every {settings.spike_check_interval_hours}h, "
                f"threshold {settings.spike_threshold_pct}%)"
            )
        except ImportError:
            print("[startup] APScheduler not installed, spike detection disabled")

    yield

    # Shutdown
    if scheduler:
        scheduler.shutdown(wait=False)
        print("[shutdown] Spike detector stopped")


app = FastAPI(
    title="FinOps AI Orchestration Platform",
    description=(
        "Cloud-agnostic AI orchestration layer. Ingests billing from "
        "AWS, Azure, and GCP in FOCUS format. Runs multi-agent analysis "
        "(RCA → Tags → Forecast → Action Planner) with human-in-the-loop "
        "remediation via Cloud Custodian."
    ),
    version="0.2.0",
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
