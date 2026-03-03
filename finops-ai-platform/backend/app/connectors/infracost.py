"""
Infracost Connector — wraps the Infracost CLI for pre-deploy cost estimation.

Production: Runs `infracost breakdown --path <dir> --format json` via subprocess.
Dev fallback: Reads mock_infracost_data.json
"""
import json
import subprocess
from pathlib import Path
from app.config import settings


class InfracostConnector:
    """Wraps the Infracost CLI for Terraform cost estimation."""

    def __init__(self):
        self.api_key = settings.infracost_api_key
        self.mock_data = None

    def _load_mock(self) -> list[dict]:
        if self.mock_data is None:
            path = settings.data_dir / "mock_infracost_data.json"
            with open(path) as f:
                self.mock_data = json.load(f)
        return self.mock_data

    def run_breakdown(self, terraform_path: str) -> dict:
        """
        Run `infracost breakdown` on a Terraform directory.

        Production: subprocess → infracost CLI
        Dev: returns mock data
        """
        if not self.api_key or settings.use_mock_data:
            # ── DEV: return first mock estimate ──
            mock = self._load_mock()
            return mock[0] if mock else {}

        # ── PRODUCTION ──
        # TODO: Uncomment when Infracost CLI is installed
        # env = {**os.environ, "INFRACOST_API_KEY": self.api_key}
        # result = subprocess.run(
        #     ["infracost", "breakdown",
        #      "--path", terraform_path,
        #      "--format", "json",
        #      "--no-color"],
        #     capture_output=True, text=True, env=env
        # )
        # if result.returncode != 0:
        #     raise RuntimeError(f"Infracost error: {result.stderr}")
        # return json.loads(result.stdout)
        return {}

    def run_diff(self, terraform_path: str, baseline_file: str) -> dict:
        """
        Run `infracost diff` comparing current vs baseline.

        Production: subprocess → infracost CLI
        Dev: returns mock delta from mock data
        """
        if not self.api_key or settings.use_mock_data:
            mock = self._load_mock()
            if mock:
                return {
                    "monthly_cost_before": mock[0]["total_monthly_before"],
                    "monthly_cost_after": mock[0]["total_monthly_after"],
                    "monthly_delta": mock[0]["monthly_delta"],
                    "pct_change": mock[0]["pct_change"],
                    "resources_changed": mock[0].get("resources_changed", []),
                }
            return {}

        # TODO: real infracost diff subprocess
        return {}

    def get_pr_estimate(self, pr_number: int) -> dict | None:
        """
        Look up the Infracost cost estimate for a specific PR.
        Used by RCA agent to correlate deployments with predicted cost impact.
        """
        data = self._load_mock()
        for entry in data:
            if entry.get("pr_number") == pr_number:
                return entry
        return None

    def get_all_estimates(self) -> list[dict]:
        """Get all available Infracost estimates."""
        return self._load_mock()
