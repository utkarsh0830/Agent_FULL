"""
Cloud Custodian Connector — runs c7n policies in DRY-RUN mode.

CRITICAL SAFETY: NEVER runs without --dryrun unless explicitly approved
via the remediation_queue table (status == 'approved').

Production: Runs `custodian run --dryrun -s /tmp/output policy.yml`
Dev fallback: Simulates dry-run output
"""
import json
import subprocess
import tempfile
import yaml
from pathlib import Path
from app.config import settings
from app import database as db


class CloudCustodianConnector:
    """Wraps the Cloud Custodian CLI with mandatory safety checks."""

    def __init__(self):
        self.policy_dir = settings.custodian_policy_dir

    def dry_run(self, policy_yaml: str) -> dict:
        """
        Execute a Cloud Custodian policy in DRY-RUN mode.
        Returns the resources that WOULD be affected.

        Production: subprocess → custodian run --dryrun
        Dev: returns simulated output
        """
        if settings.use_mock_data:
            # ── DEV: simulate dry-run result ──
            return {
                "policy_name": "simulated-dry-run",
                "mode": "dry-run",
                "resources_found": 3,
                "resources": [
                    {"ResourceId": "i-0a1b2c3d4e5f6005", "ResourceName": "payments-v2-burst-5", "State": "running"},
                    {"ResourceId": "i-0a1b2c3d4e5f6006", "ResourceName": "payments-v2-burst-6", "State": "running"},
                    {"ResourceId": "i-0a1b2c3d4e5f6007", "ResourceName": "payments-v2-burst-7", "State": "running"},
                ],
                "estimated_monthly_savings": 1368.00,
                "status": "dry_run_complete",
            }

        # ── PRODUCTION ──
        # TODO: Uncomment when Cloud Custodian is installed
        # with tempfile.NamedTemporaryFile(mode='w', suffix='.yml',
        #                                  delete=False) as f:
        #     f.write(policy_yaml)
        #     policy_path = f.name
        #
        # output_dir = tempfile.mkdtemp()
        # result = subprocess.run(
        #     ["custodian", "run", "--dryrun",
        #      "-s", output_dir, policy_path],
        #     capture_output=True, text=True
        # )
        # if result.returncode != 0:
        #     return {"error": result.stderr, "status": "failed"}
        #
        # resources_file = Path(output_dir) / "resources.json"
        # resources = json.loads(resources_file.read_text()) if resources_file.exists() else []
        # return {
        #     "mode": "dry-run",
        #     "resources_found": len(resources),
        #     "resources": resources,
        #     "status": "dry_run_complete",
        # }
        return {"status": "not_configured"}

    def execute(self, action_id: str) -> dict:
        """
        Execute a Cloud Custodian policy FOR REAL.

        SAFETY: Checks remediation_queue.status == 'approved' before proceeding.
        This is the ONLY code path that can run custodian without --dryrun.
        """
        # ── SAFETY CHECK ──
        conn = db.get_connection()
        row = conn.execute(
            "SELECT * FROM remediation_queue WHERE id = ? AND status = 'approved'",
            (action_id,),
        ).fetchone()
        conn.close()

        if not row:
            return {
                "error": f"Action {action_id} is NOT approved. Cannot execute.",
                "status": "blocked",
            }

        if settings.use_mock_data:
            # ── DEV: simulate execution ──
            conn = db.get_connection()
            conn.execute(
                "UPDATE remediation_queue SET status = 'executed' WHERE id = ?",
                (action_id,),
            )
            conn.commit()
            conn.close()
            return {
                "action_id": action_id,
                "status": "executed",
                "message": "Policy executed successfully (simulated)",
                "resources_affected": 3,
            }

        # ── PRODUCTION ──
        # TODO: subprocess → custodian run (WITHOUT --dryrun)
        # policy_yaml = dict(row)["policy_yaml"]
        # ... run subprocess ...
        # Update DB status to 'executed' or 'failed'
        return {"status": "not_configured"}

    def list_builtin_policies(self) -> list[dict]:
        """List available Cloud Custodian policy templates."""
        return [
            {
                "name": "stop-idle-ec2",
                "description": "Stop EC2 instances with <5% CPU for 7 days",
                "resource": "aws.ec2",
                "action": "stop",
                "risk": "medium",
            },
            {
                "name": "delete-unused-ebs",
                "description": "Delete unattached EBS volumes older than 14 days",
                "resource": "aws.ebs",
                "action": "delete",
                "risk": "low",
            },
            {
                "name": "tag-compliance",
                "description": "Notify about resources missing required tags",
                "resource": "aws.ec2",
                "action": "notify",
                "risk": "low",
            },
            {
                "name": "cleanup-old-snapshots",
                "description": "Delete EBS snapshots older than 90 days",
                "resource": "aws.ebs-snapshot",
                "action": "delete",
                "risk": "medium",
            },
        ]
