"""
Deployment Service — queries CI/CD deployment events and Infracost estimates.

Combines deployment history with Infracost PR estimates to give
the RCA agent "The Action" context (who deployed what, when, at what cost).

Production: Query GitHub/GitLab API + Infracost API
Dev fallback: Reads mock_deployments.json + mock_infracost_data.json
"""
import json
from datetime import datetime, timedelta
from pathlib import Path
from app.config import settings


class DeploymentService:
    """Provides deployment event + Infracost estimate data."""

    def __init__(self):
        self._deploys = None
        self._infracost = None

    def _load_deploys(self) -> list[dict]:
        if self._deploys is None:
            path = settings.data_dir / "mock_deployments.json"
            with open(path) as f:
                self._deploys = json.load(f)
        return self._deploys

    def _load_infracost(self) -> list[dict]:
        if self._infracost is None:
            path = settings.data_dir / "mock_infracost_data.json"
            with open(path) as f:
                self._infracost = json.load(f)
        return self._infracost

    def get_deployments(
        self, start: str | None = None, end: str | None = None,
        service: str | None = None
    ) -> list[dict]:
        """Get deployments, optionally filtered by date range and service."""
        deploys = self._load_deploys()
        result = []
        for d in deploys:
            ts = d["timestamp"][:10]  # Extract date portion
            if start and ts < start:
                continue
            if end and ts > end:
                continue
            if service and d.get("service") != service:
                continue
            result.append(d)
        return result

    def find_deployments_near(
        self, timestamp: str, hours: int = 24
    ) -> list[dict]:
        """
        Find deployments within ±hours of a given timestamp.
        Used by RCA agent to find the deployment that caused a cost spike.
        """
        target = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        deploys = self._load_deploys()
        result = []
        for d in deploys:
            deploy_time = datetime.fromisoformat(
                d["timestamp"].replace("Z", "+00:00")
            )
            delta = abs((target - deploy_time).total_seconds()) / 3600
            if delta <= hours:
                result.append(d)
        return result

    def get_infracost_estimate(self, pr_number: int) -> dict | None:
        """Get the Infracost cost estimate for a specific PR."""
        data = self._load_infracost()
        for entry in data:
            if entry.get("pr_number") == pr_number:
                return entry
        return None

    def get_deployment_cost_impact(self, deployment_id: str) -> dict:
        """
        Join a deployment event with its Infracost estimate.
        Returns combined context for the RCA agent.
        """
        deploys = self._load_deploys()
        for d in deploys:
            if d["deployment_id"] == deployment_id:
                pr_num = d.get("pr_number")
                estimate = self.get_infracost_estimate(pr_num) if pr_num else None
                return {
                    "deployment": d,
                    "infracost_estimate": estimate,
                    "cost_reviewed": (estimate or {}).get("review_status") == "reviewed",
                }
        return {}
