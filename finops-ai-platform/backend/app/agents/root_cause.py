"""
Root Cause Analyzer Agent — chains FOCUS + OpenCost + Deployments
to explain WHY costs changed.

Evidence chain: The Cost → The Infrastructure → The Action → LLM Synthesis
"""
import json
from langchain_core.messages import SystemMessage, HumanMessage
from app.agents.state import FinOpsState
from app.agents.llm_factory import get_llm
from app.agents.json_utils import parse_llm_json
from app.agents.prompts import RCA_SYSTEM_PROMPT
from app.config import settings


async def root_cause_node(state: FinOpsState) -> dict:
    """
    LangGraph node: Root Cause Analyzer.

    Reads billing anomalies, K8s data, and deployment events from state,
    feeds them to the LLM, and returns structured RCA output.
    """
    trace = list(state.get("agent_trace", []))
    errors = list(state.get("errors", []))
    events = list(state.get("stream_events", []))

    # Emit "running" event for frontend
    events.append({"agent": "root_cause_analyzer", "status": "running"})

    try:
        # ── Step 1: Gather evidence from state (trimmed for token efficiency) ──
        billing_data = state.get("billing_data", [])
        opencost_data = state.get("opencost_data", [])
        deploy_events = state.get("deployment_events", [])
        infracost_data = state.get("infracost_estimates", [])

        # Trim billing to essential fields only
        slim_billing = [
            {k: r[k] for k in ("billing_period_start", "billed_cost", "service_name",
                                "resource_name", "tags", "region") if k in r}
            for r in billing_data[:10]
        ]
        slim_opencost = [
            {k: p[k] for k in ("namespace", "pod", "total_cost", "cpu_efficiency",
                                "memory_efficiency", "window_start", "labels") if k in p}
            for p in opencost_data[:6]
        ]

        context = {
            "billing": slim_billing,
            "k8s": slim_opencost,
            "deployments": deploy_events[:3],
            "infracost": infracost_data[:2],
        }

        # ── Step 2: Call LLM ──
        llm = get_llm(temperature=0)

        response = await llm.ainvoke([
            SystemMessage(content=RCA_SYSTEM_PROMPT),
            HumanMessage(content=(
                "Analyze this FinOps data and produce a root cause analysis.\n"
                f"DATA:\n{json.dumps(context, separators=(',', ':'), default=str)}"
            )),
        ])

        # ── Step 3: Parse JSON output ──
        rca_output = parse_llm_json(response.content)

        trace.append("root_cause_analyzer")
        events.append({
            "agent": "root_cause_analyzer",
            "status": "done",
            "summary": rca_output.get("plain_english", "Analysis complete"),
        })

        return {
            "rca_output": rca_output,
            "agent_trace": trace,
            "stream_events": events,
            "errors": errors,
        }

    except json.JSONDecodeError as e:
        errors.append(f"RCA agent: LLM returned non-JSON output: {e}")
        trace.append("root_cause_analyzer (error)")
        events.append({"agent": "root_cause_analyzer", "status": "error", "error": str(e)})
        return {
            "rca_output": {"error": str(e), "spike_detected": False},
            "agent_trace": trace,
            "stream_events": events,
            "errors": errors,
        }

    except Exception as e:
        errors.append(f"RCA agent error: {e}")
        trace.append("root_cause_analyzer (error)")
        events.append({"agent": "root_cause_analyzer", "status": "error", "error": str(e)})
        return {
            "rca_output": {"error": str(e), "spike_detected": False},
            "agent_trace": trace,
            "stream_events": events,
            "errors": errors,
        }
