"""
FastAPI API Routes — all endpoints for the FinOps orchestration platform.

Endpoints:
- POST /api/upload-billing        → Ingest FOCUS data (mock or S3)
- POST /api/collect                → Run multi-cloud collectors
- POST /api/analysis/trigger       → Trigger agent chain (manual or auto)
- GET  /api/analysis/rca           → Run full agent chain (SSE streaming)
- GET  /api/analysis/tag-intelligence → Get tag suggestions
- GET  /api/analysis/forecast      → Get cost forecast
- POST /api/remediate              → Approve/reject staged remediation
- GET  /api/remediations           → List pending remediation actions
- GET  /api/costs/summary          → Cost summary by dimension
- GET  /api/costs/daily            → Daily time-series for charts
- GET  /api/costs/anomalies        → Detect cost anomalies
- GET  /api/costs/untagged         → List untagged resources
- GET  /api/health                 → Health check
"""
import json
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app import database as db
from app.connectors.opencost import OpenCostConnector
from app.connectors.cloud_custodian import CloudCustodianConnector
from app.services.deployment_service import DeploymentService
from app.agents.graph import finops_graph

router = APIRouter(prefix="/api")

# ── Singletons ──
opencost = OpenCostConnector()
custodian = CloudCustodianConnector()
deploy_service = DeploymentService()


# ── Request/Response models ──
class BillingUploadRequest(BaseModel):
    s3_bucket: str = ""
    s3_key: str = ""


class RemediationRequest(BaseModel):
    action_id: str
    approved: bool
    decided_by: str = "user"


# ──────────────────────────────────────────────────────────────
# Billing Ingestion
# ──────────────────────────────────────────────────────────────


@router.post("/upload-billing")
async def upload_billing(req: BillingUploadRequest):
    """
    Ingest FOCUS billing data.
    In mock mode: loads mock data.
    In real mode: runs cloud collectors.
    """
    try:
        from app.services.spike_detector import run_collectors
        count = await run_collectors()
        return {
            "status": "success",
            "records_loaded": count,
            "source": f"s3://{req.s3_bucket}/{req.s3_key}" if req.s3_bucket else "mock_data/collectors",
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/collect")
async def run_collection():
    """Run multi-cloud collectors to ingest billing data from all enabled providers."""
    try:
        from app.services.spike_detector import run_collectors
        count = await run_collectors()
        return {"status": "success", "records_ingested": count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analysis/trigger")
async def trigger_analysis(body: dict = None):
    """
    Trigger the full agent chain.
    Can be called by the spike detector (with spike context)
    or manually via API.
    """
    try:
        from app.services.spike_detector import check_for_spikes
        spikes = await check_for_spikes()
        return {
            "status": "triggered",
            "spikes_found": len(spikes),
            "spikes": spikes[:5],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ──────────────────────────────────────────────────────────────
# Analysis — Agent Chain (SSE Streaming)
# ──────────────────────────────────────────────────────────────


@router.get("/analysis/rca")
async def run_analysis():
    """
    Run the full agent chain: RCA → Tag → Forecast → Action Planner.
    Streams SSE events as each agent starts/completes.
    """
    async def event_stream():
        try:
            # ── Gather input data from FOCUS database ──
            billing_data = db.get_all_billing_records(limit=200)
            anomalies = db.detect_anomalies(threshold_pct=30)
            untagged = db.get_untagged_resources()

            # Get data from connectors
            opencost_data = await opencost.get_workload_costs()
            deploy_events = deploy_service.get_deployments()
            infracost_data = deploy_service._load_infracost()

            # Combine billing data for agents
            combined_billing = billing_data if billing_data else anomalies + untagged

            # ── Build initial state ──
            initial_state = {
                "billing_data": combined_billing,
                "opencost_data": opencost_data,
                "deployment_events": deploy_events,
                "infracost_estimates": infracost_data,
                "rca_output": None,
                "tag_output": None,
                "forecast_output": None,
                "action_output": None,
                "agent_trace": [],
                "errors": [],
                "stream_events": [],
            }

            # Emit start event
            yield f"data: {json.dumps({'type': 'start', 'message': 'Starting agent pipeline...'})}\n\n"

            # ── Run graph with streaming ──
            prev_events_count = 0
            async for chunk in finops_graph.astream(initial_state):
                for node_name, node_output in chunk.items():
                    # Emit new stream events
                    stream_events = node_output.get("stream_events", [])
                    new_events = stream_events[prev_events_count:]
                    prev_events_count = len(stream_events)

                    for event in new_events:
                        yield f"data: {json.dumps({'type': 'agent_event', **event})}\n\n"

                    # Emit agent output
                    for key in ("rca_output", "tag_output", "forecast_output", "action_output"):
                        if key in node_output and node_output[key]:
                            yield f"data: {json.dumps({'type': key, 'data': node_output[key]})}\n\n"

            # Emit completion
            yield f"data: {json.dumps({'type': 'complete', 'message': 'Analysis complete'})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/analysis/tag-intelligence")
async def get_tag_analysis():
    """Get the latest tag intelligence results (runs chain if needed)."""
    billing_data = db.get_all_billing_records(limit=200)

    initial_state = {
        "billing_data": billing_data,
        "opencost_data": [],
        "deployment_events": [],
        "infracost_estimates": [],
        "agent_trace": [],
        "errors": [],
        "stream_events": [],
    }

    result = await finops_graph.ainvoke(initial_state)
    return result.get("tag_output", {"error": "No tag analysis available"})


@router.get("/analysis/forecast")
async def get_forecast():
    """Get the latest cost forecast results."""
    billing_data = db.get_all_billing_records(limit=200)

    initial_state = {
        "billing_data": billing_data,
        "opencost_data": [],
        "deployment_events": [],
        "infracost_estimates": [],
        "agent_trace": [],
        "errors": [],
        "stream_events": [],
    }

    result = await finops_graph.ainvoke(initial_state)
    return result.get("forecast_output", {"error": "No forecast available"})


# ──────────────────────────────────────────────────────────────
# Remediation (HITL)
# ──────────────────────────────────────────────────────────────


@router.post("/remediate")
async def remediate(req: RemediationRequest):
    """
    Approve or reject a staged remediation action.
    If approved, executes Cloud Custodian policy (dry-run in dev).
    """
    if req.approved:
        result = db.approve_remediation(req.action_id, req.decided_by)
        if not result:
            raise HTTPException(404, f"Action {req.action_id} not found or already decided")

        # Execute the policy
        execution = custodian.execute(req.action_id)
        return {"approval": result, "execution": execution}
    else:
        result = db.reject_remediation(req.action_id, req.decided_by)
        if not result:
            raise HTTPException(404, f"Action {req.action_id} not found or already decided")
        return {"approval": result, "execution": None}


@router.get("/remediations")
async def list_remediations():
    """List all pending remediation actions."""
    return db.get_pending_remediations()


# ──────────────────────────────────────────────────────────────
# Cost Data (direct DB queries)
# ──────────────────────────────────────────────────────────────


@router.get("/costs/summary")
async def cost_summary(group_by: str = "service_name", provider: str | None = None):
    """Get cost summary grouped by service, region, etc. Optional provider filter."""
    return db.get_cost_summary(group_by, provider=provider)


@router.get("/costs/daily")
async def daily_costs(service: str | None = None, provider: str | None = None):
    """Get daily cost time-series for charts. Optional filters."""
    return db.get_daily_costs(service, provider=provider)


@router.get("/costs/anomalies")
async def cost_anomalies(threshold: float = 30):
    """Detect cost anomalies exceeding threshold %."""
    return db.detect_anomalies(threshold)


@router.get("/costs/untagged")
async def untagged_resources():
    """List untagged resources."""
    return db.get_untagged_resources()


# ──────────────────────────────────────────────────────────────
# Health
# ──────────────────────────────────────────────────────────────


@router.get("/health")
async def health():
    from app.config import settings
    return {
        "status": "healthy",
        "service": "finops-ai-platform",
        "version": "0.2.0",
        "providers": settings.provider_list,
        "database": "postgresql" if db._use_postgres() else "sqlite",
        "mock_mode": settings.use_mock_data,
    }
