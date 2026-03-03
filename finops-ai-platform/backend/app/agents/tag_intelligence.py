"""
Tag Intelligence Agent — identifies untagged resources and
suggests tags based on organizational patterns.
"""
import json
from langchain_core.messages import SystemMessage, HumanMessage
from app.agents.state import FinOpsState
from app.agents.llm_factory import get_llm
from app.agents.json_utils import parse_llm_json
from app.agents.prompts import TAG_SYSTEM_PROMPT
from app.config import settings


async def tag_intelligence_node(state: FinOpsState) -> dict:
    """
    LangGraph node: Tag Intelligence.

    Reads billing data from state, separates tagged vs untagged resources,
    and uses LLM to suggest tags for untagged ones.
    """
    trace = list(state.get("agent_trace", []))
    errors = list(state.get("errors", []))
    events = list(state.get("stream_events", []))

    events.append({"agent": "tag_intelligence", "status": "running"})

    try:
        billing_data = state.get("billing_data", [])

        # Separate tagged vs untagged resources
        tagged = []
        untagged = []
        seen = set()

        for record in billing_data:
            rid = record.get("resource_id", "")
            if rid in seen:
                continue
            seen.add(rid)

            tags = record.get("tags")
            if isinstance(tags, str):
                try:
                    tags_dict = json.loads(tags) if tags else {}
                except json.JSONDecodeError:
                    tags_dict = {}
            elif isinstance(tags, dict):
                tags_dict = tags
            else:
                tags_dict = {}

            record_info = {
                "resource_id": rid,
                "resource_name": record.get("resource_name", ""),
                "service": record.get("service_name", ""),
                "region": record.get("region", ""),
                "billed_cost": record.get("billed_cost", 0),
                "tags": tags_dict,
            }

            if tags_dict and len(tags_dict) >= 2:
                tagged.append(record_info)
            else:
                untagged.append(record_info)

        context = {
            "tagged_examples": tagged[:5],
            "untagged": untagged[:8],
            "total_resources": len(seen),
            "total_untagged": len(untagged),
        }

        llm = get_llm(temperature=0)

        response = await llm.ainvoke([
            SystemMessage(content=TAG_SYSTEM_PROMPT),
            HumanMessage(content=(
                "Suggest tags for untagged resources.\n"
                f"DATA:\n{json.dumps(context, separators=(',', ':'), default=str)}"
            )),
        ])

        tag_output = parse_llm_json(response.content)

        trace.append("tag_intelligence")
        events.append({
            "agent": "tag_intelligence",
            "status": "done",
            "summary": tag_output.get("plain_english", "Tag analysis complete"),
        })

        return {
            "tag_output": tag_output,
            "agent_trace": trace,
            "stream_events": events,
            "errors": errors,
        }

    except Exception as e:
        errors.append(f"Tag agent error: {e}")
        trace.append("tag_intelligence (error)")
        events.append({"agent": "tag_intelligence", "status": "error", "error": str(e)})
        return {
            "tag_output": {"error": str(e), "total_untagged": 0, "suggestions": []},
            "agent_trace": trace,
            "stream_events": events,
            "errors": errors,
        }
