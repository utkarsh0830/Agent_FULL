"""
Action Planner Agent — converts RCA, Tag, and Forecast outputs
into specific Cloud Custodian policy recommendations.

NEVER executes anything — only PROPOSES actions for human approval.
"""
import json
from langchain_core.messages import SystemMessage, HumanMessage
from app.agents.state import FinOpsState
from app.agents.llm_factory import get_llm
from app.agents.json_utils import parse_llm_json
from app.agents.prompts import ACTION_PLANNER_PROMPT
from app.config import settings
from app import database as db


async def action_planner_node(state: FinOpsState) -> dict:
    """
    LangGraph node: Action Planner.

    Takes all previous agent outputs and generates actionable
    Cloud Custodian policy recommendations with HITL approval.
    """
    trace = list(state.get("agent_trace", []))
    errors = list(state.get("errors", []))
    events = list(state.get("stream_events", []))

    events.append({"agent": "action_planner", "status": "running"})

    try:
        rca_output = state.get("rca_output", {})
        tag_output = state.get("tag_output", {})
        forecast_output = state.get("forecast_output", {})

        # Trim prior outputs to essential summaries to save tokens
        context = {
            "rca": {
                "spike_summary": (rca_output or {}).get("spike_summary", ""),
                "urgency": (rca_output or {}).get("urgency", ""),
                "impacted_services": (rca_output or {}).get("impacted_services", [])[:3],
            },
            "tags": {
                "total_untagged": (tag_output or {}).get("total_untagged", 0),
                "suggestions": (tag_output or {}).get("suggestions", [])[:3],
            },
            "forecast": {
                "projected_30d_cost": (forecast_output or {}).get("projected_30d_cost", 0),
                "trend": (forecast_output or {}).get("trend", ""),
            },
        }

        llm = get_llm(temperature=0)

        response = await llm.ainvoke([
            SystemMessage(content=ACTION_PLANNER_PROMPT),
            HumanMessage(content=(
                "Generate remediation actions from these agent findings.\n"
                f"DATA:\n{json.dumps(context, separators=(',', ':'), default=str)}"
            )),
        ])

        action_output = parse_llm_json(response.content)

        # ── Stage actions in the remediation queue for HITL ──
        for action in action_output.get("recommended_actions", []):
            try:
                db.create_remediation(action)
            except Exception as db_err:
                # Non-fatal: log but don't block the agent
                errors.append(f"Failed to stage action {action.get('action_id')}: {db_err}")

        trace.append("action_planner")
        events.append({
            "agent": "action_planner",
            "status": "done",
            "summary": action_output.get("plain_english", "Action plan complete"),
            "actions_count": len(action_output.get("recommended_actions", [])),
        })

        return {
            "action_output": action_output,
            "agent_trace": trace,
            "stream_events": events,
            "errors": errors,
        }

    except Exception as e:
        errors.append(f"Action planner error: {e}")
        trace.append("action_planner (error)")
        events.append({"agent": "action_planner", "status": "error", "error": str(e)})
        return {
            "action_output": {"error": str(e), "recommended_actions": []},
            "agent_trace": trace,
            "stream_events": events,
            "errors": errors,
        }
