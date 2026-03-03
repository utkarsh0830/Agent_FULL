"""
FinOps Agent State — defines the TypedDict shared across all LangGraph nodes.

Each agent reads from and writes to specific keys in this state.
The state flows sequentially: RCA → Tag Intelligence → Forecast → Action Planner.
"""
from typing import TypedDict, Any


class FinOpsState(TypedDict, total=False):
    """Shared state for the FinOps LangGraph agent chain."""

    # ── Input data (populated before graph runs) ──────────
    billing_data: list[dict]          # FOCUS billing records from SQLite
    opencost_data: list[dict]         # K8s pod/namespace costs from OpenCost
    deployment_events: list[dict]     # CI/CD deployment events
    infracost_estimates: list[dict]   # Infracost PR cost estimates

    # ── Agent outputs (populated sequentially) ────────────
    rca_output: dict | None           # Root Cause Analyzer result (JSON)
    tag_output: dict | None           # Tag Intelligence result (JSON)
    forecast_output: dict | None      # Cost Forecaster result (JSON)
    action_output: dict | None        # Action Planner result (JSON)

    # ── Orchestration metadata ────────────────────────────
    agent_trace: list[str]            # Track which agents have run
    errors: list[str]                 # Error propagation across agents
    stream_events: list[dict]         # SSE events for frontend streaming
