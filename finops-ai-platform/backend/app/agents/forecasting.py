"""
Cost Forecaster Agent — projects 30-day spend using historical data.
"""
import json
from langchain_core.messages import SystemMessage, HumanMessage
from app.agents.state import FinOpsState
from app.agents.llm_factory import get_llm
from app.agents.json_utils import parse_llm_json
from app.agents.prompts import FORECAST_SYSTEM_PROMPT
from app.config import settings


async def forecasting_node(state: FinOpsState) -> dict:
    """
    LangGraph node: Cost Forecaster.

    Reads daily cost time-series from billing data and RCA context,
    projects future spend with confidence intervals.
    """
    trace = list(state.get("agent_trace", []))
    errors = list(state.get("errors", []))
    events = list(state.get("stream_events", []))

    events.append({"agent": "cost_forecaster", "status": "running"})

    try:
        billing_data = state.get("billing_data", [])
        rca_output = state.get("rca_output", {})

        # Build daily cost time series
        daily_costs: dict[str, float] = {}
        for record in billing_data:
            date = record.get("billing_period_start", "")
            cost = record.get("billed_cost", 0)
            daily_costs[date] = daily_costs.get(date, 0) + cost

        time_series = [
            {"date": date, "total_cost": round(cost, 2)}
            for date, cost in sorted(daily_costs.items())
        ]

        context = {
            "daily_cost_history": time_series,
            "rca_context": {
                "spike_detected": rca_output.get("spike_detected", False),
                "spike_period": rca_output.get("spike_period", {}),
                "spike_summary": rca_output.get("spike_summary", ""),
            } if rca_output else None,
            "total_days": len(time_series),
        }

        llm = get_llm(temperature=0)

        response = await llm.ainvoke([
            SystemMessage(content=FORECAST_SYSTEM_PROMPT),
            HumanMessage(content=(
                "Forecast 30-day costs from this daily history.\n"
                f"DATA:\n{json.dumps(context, separators=(',', ':'), default=str)}"
            )),
        ])

        forecast_output = parse_llm_json(response.content)

        trace.append("cost_forecaster")
        events.append({
            "agent": "cost_forecaster",
            "status": "done",
            "summary": forecast_output.get("plain_english", "Forecast complete"),
        })

        return {
            "forecast_output": forecast_output,
            "agent_trace": trace,
            "stream_events": events,
            "errors": errors,
        }

    except Exception as e:
        errors.append(f"Forecast agent error: {e}")
        trace.append("cost_forecaster (error)")
        events.append({"agent": "cost_forecaster", "status": "error", "error": str(e)})
        return {
            "forecast_output": {"error": str(e), "projected_30d_cost": 0},
            "agent_trace": trace,
            "stream_events": events,
            "errors": errors,
        }
