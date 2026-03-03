"""
FastAPI API Routes — all endpoints for the FinOps orchestration platform.

Endpoints:
- POST /api/upload-billing      → Ingest FOCUS data from S3
- GET  /api/analysis/rca        → Run full agent chain (SSE streaming)
- GET  /api/analysis/tag-intelligence → Get tag suggestions
- GET  /api/analysis/forecast   → Get cost forecast
- POST /api/remediate           → Approve/reject staged remediation
- GET  /api/costs/summary       → Cost summary from SQLite
- GET  /api/costs/daily         → Daily time-series for charts
- GET  /api/remediations        → List pending remediation actions
- GET  /api/health              → Health check
"""
import json
import asyncio
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app import database as db
from app.ingestion.s3_fetcher import fetch_from_s3
from app.ingestion.focus_loader import load_focus_file
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
    Ingest FOCUS billing data from S3 (or mock data in dev mode).
    Validates FOCUS schema and loads into SQLite.
    """
    try:
        file_path = fetch_from_s3(req.s3_bucket, req.s3_key)
        count = load_focus_file(file_path)
        return {
            "status": "success",
            "records_loaded": count,
            "source": f"s3://{req.s3_bucket}/{req.s3_key}" if req.s3_bucket else "mock_data",
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


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
            # ── Gather input data ──
            billing_data = db.get_daily_costs()  # billing time-series
            anomalies = db.detect_anomalies(threshold_pct=30)
            untagged = db.get_untagged_resources()
            all_billing = billing_data  # For agents that need raw records

            # Get data from connectors
            opencost_data = await opencost.get_workload_costs()
            deploy_events = deploy_service.get_deployments()
            infracost_data = deploy_service._load_infracost()

            # Combine billing data for agents
            combined_billing = anomalies + untagged

            # ── Build initial state ──
            initial_state = {
                "billing_data": combined_billing if combined_billing else all_billing,
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
                # Each chunk is a dict with the node name as key
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
    # For direct access, run just the tag portion
    billing_data = db.get_untagged_resources()
    all_records = db.get_daily_costs()

    initial_state = {
        "billing_data": billing_data + all_records,
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
    billing_data = db.get_daily_costs()

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
async def cost_summary(group_by: str = "service_name"):
    """Get cost summary grouped by service, region, etc."""
    return db.get_cost_summary(group_by)


@router.get("/costs/daily")
async def daily_costs(service: str | None = None):
    """Get daily cost time-series for charts."""
    return db.get_daily_costs(service)


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
    return {"status": "healthy", "service": "finops-ai-platform"}
