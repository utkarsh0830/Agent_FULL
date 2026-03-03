"""
OpenCost Connector — retrieves namespace and workload-level costs.

Production: Queries OpenCost REST API at http://opencost:9003
Dev fallback: Reads mock_opencost_data.json
"""
import json
from pathlib import Path
from app.config import settings


class OpenCostConnector:
    """Wraps the OpenCost API for K8s cost allocation data."""

    def __init__(self):
        self.base_url = settings.opencost_api_url
        self.mock_data = None

    def _load_mock(self) -> list[dict]:
        """Load mock OpenCost data for dev/testing."""
        if self.mock_data is None:
            path = settings.data_dir / "mock_opencost_data.json"
            with open(path) as f:
                self.mock_data = json.load(f)
        return self.mock_data

    async def get_namespace_costs(self, window: str = "7d") -> list[dict]:
        """
        Get cost allocation grouped by namespace.

        Production: GET {base_url}/allocation/compute?window={window}&aggregate=namespace
        """
        if not self.base_url or settings.use_mock_data:
            # ── DEV: aggregate mock data by namespace ──
            data = self._load_mock()
            ns_costs: dict[str, float] = {}
            for pod in data:
                ns = pod["namespace"]
                ns_costs[ns] = ns_costs.get(ns, 0) + pod["total_cost"]
            return [{"namespace": ns, "total_cost": round(cost, 2)}
                    for ns, cost in sorted(ns_costs.items(),
                                           key=lambda x: x[1], reverse=True)]

        # ── PRODUCTION: query OpenCost API ──
        # TODO: Replace with real httpx call
        # import httpx
        # async with httpx.AsyncClient() as client:
        #     resp = await client.get(
        #         f"{self.base_url}/allocation/compute",
        #         params={"window": window, "aggregate": "namespace"}
        #     )
        #     return resp.json()["data"]
        return []

    async def get_workload_costs(
        self, namespace: str | None = None, window: str = "7d"
    ) -> list[dict]:
        """
        Get pod/container-level costs.

        Production: GET {base_url}/allocation/compute?window={window}&aggregate=pod
        """
        if not self.base_url or settings.use_mock_data:
            data = self._load_mock()
            if namespace:
                data = [p for p in data if p["namespace"] == namespace]
            return data

        # TODO: real OpenCost API call
        return []

    async def detect_cost_deltas(
        self, window_start_a: str, window_start_b: str
    ) -> list[dict]:
        """
        Compare pod costs between two date windows.
        Returns pods with significant cost changes.
        """
        if not self.base_url or settings.use_mock_data:
            data = self._load_mock()
            # Group by window_start to compare periods
            period_a = [p for p in data if p.get("window_start") == window_start_a]
            period_b = [p for p in data if p.get("window_start") == window_start_b]

            cost_a = sum(p["total_cost"] for p in period_a)
            cost_b = sum(p["total_cost"] for p in period_b)
            delta = cost_a - cost_b
            pct = (delta / max(cost_b, 0.01)) * 100

            return [{
                "period_a": window_start_a,
                "period_b": window_start_b,
                "cost_a": round(cost_a, 2),
                "cost_b": round(cost_b, 2),
                "delta": round(delta, 2),
                "pct_change": round(pct, 1),
                "top_pods_a": sorted(period_a, key=lambda x: x["total_cost"],
                                     reverse=True)[:5],
            }]

        # TODO: real OpenCost API call with two windows
        return []

    async def correlate_with_timerange(
        self, start_date: str, end_date: str
    ) -> list[dict]:
        """
        Find K8s workloads active within a time range.
        Used by RCA agent to correlate cost spikes with infrastructure.
        """
        if not self.base_url or settings.use_mock_data:
            data = self._load_mock()
            return [
                p for p in data
                if p.get("window_start", "") >= start_date
                and p.get("window_start", "") <= end_date
            ]

        # TODO: real OpenCost API query with time window
        return []

    async def get_idle_pods(self, efficiency_threshold: float = 0.2) -> list[dict]:
        """
        Find pods with very low CPU + memory efficiency (waste candidates).
        """
        if not self.base_url or settings.use_mock_data:
            data = self._load_mock()
            return [
                p for p in data
                if p.get("cpu_efficiency", 1) < efficiency_threshold
                and p.get("memory_efficiency", 1) < efficiency_threshold
                and p.get("total_cost", 0) > 1.0
            ]

        # TODO: real OpenCost API query
        return []
