"""
Cloud Custodian Connector — runs c7n policies in DRY-RUN mode.

SUPPORTS: AWS (c7n), Azure (c7n-azure), GCP (c7n-gcp)

CRITICAL SAFETY: NEVER runs without --dryrun unless explicitly approved
via the remediation_queue table (status == 'approved').
"""
import json
import subprocess
import tempfile
from pathlib import Path
from app.config import settings
from app import database as db


# ── Provider → CLI flag mapping ──
_PROVIDER_FLAGS = {
    "AWS": [],
    "Azure": ["--provider", "azure"],
    "GCP": ["--provider", "gcp"],
}


class CloudCustodianConnector:
    """Wraps the Cloud Custodian CLI with mandatory safety checks."""

    def __init__(self):
        self.policy_dir = Path(settings.custodian_policy_dir)

    def get_policies_for_provider(self, provider: str = "AWS") -> list[dict]:
        """List available policy files for a specific cloud provider."""
        provider_dir = self.policy_dir / provider.lower()
        if not provider_dir.exists():
            return []

        policies = []
        for f in provider_dir.glob("*.yml"):
            try:
                import yaml
                with open(f) as fh:
                    data = yaml.safe_load(fh)
                for pol in data.get("policies", []):
                    policies.append({
                        "name": pol["name"],
                        "resource": pol.get("resource", "unknown"),
                        "file": str(f),
                        "provider": provider,
                    })
            except Exception:
                policies.append({"name": f.stem, "file": str(f), "provider": provider})

        return policies

    def dry_run(self, policy_yaml: str, provider: str = "AWS") -> dict:
        """
        Execute a Cloud Custodian policy in DRY-RUN mode.
        Returns the resources that WOULD be affected.
        """
        if settings.use_mock_data:
            return {
                "policy_name": "simulated-dry-run",
                "provider": provider,
                "mode": "dry-run",
                "resources_found": 3,
                "resources": [
                    {"ResourceId": "i-0a1b2c3d4e5f6005", "ResourceName": "burst-5", "State": "running"},
                    {"ResourceId": "i-0a1b2c3d4e5f6006", "ResourceName": "burst-6", "State": "running"},
                    {"ResourceId": "i-0a1b2c3d4e5f6007", "ResourceName": "burst-7", "State": "running"},
                ],
                "estimated_monthly_savings": 1368.00,
                "status": "dry_run_complete",
            }

        # ── PRODUCTION: Real dry-run ──
        try:
            with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
                f.write(policy_yaml)
                policy_path = f.name

            output_dir = tempfile.mkdtemp()
            cmd = ["custodian", "run", "--dryrun", "-s", output_dir]
            cmd += _PROVIDER_FLAGS.get(provider, [])
            cmd.append(policy_path)

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

            if result.returncode != 0:
                return {"error": result.stderr, "status": "failed", "provider": provider}

            # Parse output
            resources = []
            for res_dir in Path(output_dir).iterdir():
                res_file = res_dir / "resources.json"
                if res_file.exists():
                    resources.extend(json.loads(res_file.read_text()))

            return {
                "provider": provider,
                "mode": "dry-run",
                "resources_found": len(resources),
                "resources": resources[:20],
                "status": "dry_run_complete",
            }
        except FileNotFoundError:
            return {"error": "Cloud Custodian (c7n) is not installed", "status": "not_configured"}
        except Exception as e:
            return {"error": str(e), "status": "failed"}

    def execute(self, action_id: str) -> dict:
        """
        Execute a Cloud Custodian policy FOR REAL.
        SAFETY: Checks remediation_queue.status == 'approved' before proceeding.
        """
        conn = db.get_connection()
        p = db._param()
        rows = db._fetchall_dicts(
            conn,
            f"SELECT * FROM remediation_queue WHERE id = {p} AND status = 'approved'",
            (action_id,),
        )
        conn.close()

        if not rows:
            return {
                "error": f"Action {action_id} is NOT approved. Cannot execute.",
                "status": "blocked",
            }

        row = rows[0]
        provider = row.get("provider", "AWS")

        if settings.use_mock_data:
            conn = db.get_connection()
            db._execute(
                conn,
                f"UPDATE remediation_queue SET status = 'executed' WHERE id = {p}",
                (action_id,),
            )
            conn.commit()
            conn.close()
            return {
                "action_id": action_id,
                "provider": provider,
                "status": "executed",
                "message": "Policy executed successfully (simulated)",
                "resources_affected": 3,
            }

        # ── PRODUCTION: Run without --dryrun ──
        policy_yaml = row.get("policy_yaml", "")
        result = self._real_execute(policy_yaml, provider, action_id)
        return result

    def _real_execute(self, policy_yaml: str, provider: str, action_id: str) -> dict:
        """Run custodian without --dryrun (PRODUCTION ONLY)."""
        try:
            with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
                f.write(policy_yaml)
                policy_path = f.name

            output_dir = tempfile.mkdtemp()
            cmd = ["custodian", "run", "-s", output_dir]
            cmd += _PROVIDER_FLAGS.get(provider, [])
            cmd.append(policy_path)

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

            p = db._param()
            conn = db.get_connection()
            if result.returncode == 0:
                db._execute(conn, f"UPDATE remediation_queue SET status = 'executed' WHERE id = {p}", (action_id,))
                conn.commit()
                conn.close()
                return {"action_id": action_id, "provider": provider, "status": "executed"}
            else:
                db._execute(conn, f"UPDATE remediation_queue SET status = 'failed' WHERE id = {p}", (action_id,))
                conn.commit()
                conn.close()
                return {"action_id": action_id, "error": result.stderr, "status": "failed"}

        except Exception as e:
            return {"error": str(e), "status": "failed"}

    def list_builtin_policies(self) -> list[dict]:
        """List available Cloud Custodian policy templates for ALL clouds."""
        return [
            # AWS
            {"name": "stop-idle-ec2", "description": "Stop EC2 instances with <5% CPU for 7 days",
             "resource": "aws.ec2", "provider": "AWS", "risk": "medium"},
            {"name": "delete-unused-ebs", "description": "Delete unattached EBS volumes older than 14 days",
             "resource": "aws.ebs", "provider": "AWS", "risk": "low"},
            {"name": "tag-compliance-aws", "description": "Notify about AWS resources missing required tags",
             "resource": "aws.ec2", "provider": "AWS", "risk": "low"},
            # Azure
            {"name": "stop-idle-vms", "description": "Stop Azure VMs with <5% CPU for 7 days",
             "resource": "azure.vm", "provider": "Azure", "risk": "medium"},
            {"name": "delete-unused-disks", "description": "Delete unattached Azure managed disks",
             "resource": "azure.disk", "provider": "Azure", "risk": "low"},
            {"name": "tag-compliance-azure", "description": "Notify about Azure resources missing tags",
             "resource": "azure.vm", "provider": "Azure", "risk": "low"},
            # GCP
            {"name": "stop-idle-instances", "description": "Stop GCE instances with <5% CPU for 7 days",
             "resource": "gcp.instance", "provider": "GCP", "risk": "medium"},
            {"name": "delete-unused-disks-gcp", "description": "Delete unattached GCP persistent disks",
             "resource": "gcp.disk", "provider": "GCP", "risk": "low"},
        ]
