"""
LangGraph Orchestration Graph — sequential agent chain.

Flow: RCA → Tag Intelligence → Forecast → Action Planner

All agents run in strict sequence. Each agent's output feeds into the next.
"""
from langgraph.graph import StateGraph, START, END
from app.agents.state import FinOpsState
from app.agents.root_cause import root_cause_node
from app.agents.tag_intelligence import tag_intelligence_node
from app.agents.forecasting import forecasting_node
from app.agents.action_planner import action_planner_node


def build_finops_graph():
    """
    Build and compile the FinOps agent chain.

    Returns a compiled LangGraph that can be invoked with:
        result = await graph.ainvoke(initial_state)
    """
    graph = StateGraph(FinOpsState)

    # ── Add agent nodes ──
    graph.add_node("root_cause_analyzer", root_cause_node)
    graph.add_node("tag_intelligence", tag_intelligence_node)
    graph.add_node("cost_forecaster", forecasting_node)
    graph.add_node("action_planner", action_planner_node)

    # ── Strict sequential chain ──
    graph.add_edge(START, "root_cause_analyzer")
    graph.add_edge("root_cause_analyzer", "tag_intelligence")
    graph.add_edge("tag_intelligence", "cost_forecaster")
    graph.add_edge("cost_forecaster", "action_planner")
    graph.add_edge("action_planner", END)

    return graph.compile()


# ── Singleton graph instance ──
finops_graph = build_finops_graph()
