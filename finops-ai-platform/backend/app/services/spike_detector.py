"""
Spike Detector — runs periodic cost anomaly detection
using APScheduler (cloud-agnostic, no Lambda dependency).

Runs inside the FastAPI process on an interval.
When a spike is detected, triggers the agent chain automatically.
"""
from app.config import settings
from app.database import detect_anomalies


async def check_for_spikes() -> list[dict]:
    """
    Check for cost spikes across all providers.
    Returns list of detected spikes.

    Called by APScheduler on an interval, or manually via API.
    """
    spikes = detect_anomalies(threshold_pct=settings.spike_threshold_pct)

    if spikes:
        providers = set(s.get("provider", "Unknown") for s in spikes)
        services = set(s.get("service_name", "Unknown") for s in spikes)
        print(
            f"[spike_detector] 🚨 {len(spikes)} spike(s) detected! "
            f"Providers: {providers}, Services: {services}"
        )

        # Auto-trigger agent chain
        try:
            from app.agents.graph import finops_graph
            from app.database import get_all_billing_records
            from app.services.deployment_service import DeploymentService
            from app.connectors.opencost import OpenCostConnector

            deploy_svc = DeploymentService()
            opencost = OpenCostConnector()

            billing = get_all_billing_records(limit=200)
            opencost_data = opencost.get_allocations()
            deploys = deploy_svc.get_deployments()

            state = {
                "billing_data": billing,
                "opencost_data": opencost_data,
                "deployment_events": deploys,
                "infracost_estimates": [],
                "rca_output": {},
                "tag_output": {},
                "forecast_output": {},
                "action_output": {},
                "agent_trace": [],
                "stream_events": [],
                "errors": [],
            }

            result = await finops_graph.ainvoke(state)
            print(f"[spike_detector] ✅ Auto-analysis complete. Trace: {result.get('agent_trace')}")

        except Exception as e:
            print(f"[spike_detector] ❌ Auto-analysis failed: {e}")

    else:
        print("[spike_detector] ✅ No spikes detected")

    return spikes


async def run_collectors():
    """
    Run all enabled cloud collectors to ingest billing data.
    Called by APScheduler or manually via API.
    """
    total = 0

    if settings.use_mock_data:
        from app.collectors.aws_collector import load_mock_aws_data
        from app.database import get_connection
        conn = get_connection()
        try:
            from app.database import _fetchall_dicts
            rows = _fetchall_dicts(conn, "SELECT COUNT(*) as cnt FROM focus_billing")
            count = rows[0]["cnt"] if rows else 0
        finally:
            conn.close()

        if count == 0:
            loaded = load_mock_aws_data()
            print(f"[collectors] Loaded {loaded} mock FOCUS records")
            total += loaded
        return total

    providers = settings.provider_list

    if "AWS" in providers:
        from app.collectors.aws_collector import collect_aws_billing
        total += await collect_aws_billing()

    if "Azure" in providers:
        from app.collectors.azure_collector import collect_azure_billing
        total += await collect_azure_billing()

    if "GCP" in providers:
        from app.collectors.gcp_collector import collect_gcp_billing
        total += await collect_gcp_billing()

    print(f"[collectors] Total ingested: {total} records from {providers}")
    return total
