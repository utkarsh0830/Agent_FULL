const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export const api = {
  /** Ingest FOCUS billing data from S3 (or mock data) */
  async uploadBilling(s3Bucket: string, s3Key: string) {
    const res = await fetch(`${API_BASE}/api/upload-billing`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ s3_bucket: s3Bucket, s3_key: s3Key }),
    });
    return res.json();
  },

  /** Run full agent chain with SSE streaming */
  runAnalysis(
    onEvent: (event: Record<string, unknown>) => void,
    onComplete: () => void,
    onError: (err: string) => void
  ) {
    const evtSource = new EventSource(`${API_BASE}/api/analysis/rca`);
    evtSource.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data);
        if (data.type === "complete") {
          evtSource.close();
          onComplete();
        } else if (data.type === "error") {
          evtSource.close();
          onError(data.message);
        } else {
          onEvent(data);
        }
      } catch {
        onError("Failed to parse SSE event");
      }
    };
    evtSource.onerror = () => {
      evtSource.close();
      onError("Connection lost");
    };
    return evtSource;
  },

  /** Get cost summary */
  async getCostSummary(groupBy = "service_name") {
    const res = await fetch(`${API_BASE}/api/costs/summary?group_by=${groupBy}`);
    return res.json();
  },

  /** Get daily cost time-series */
  async getDailyCosts(service?: string) {
    const url = service
      ? `${API_BASE}/api/costs/daily?service=${service}`
      : `${API_BASE}/api/costs/daily`;
    const res = await fetch(url);
    return res.json();
  },

  /** Approve/reject a remediation action */
  async remediate(actionId: string, approved: boolean) {
    const res = await fetch(`${API_BASE}/api/remediate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action_id: actionId, approved }),
    });
    return res.json();
  },

  /** List pending remediations */
  async getRemediations() {
    const res = await fetch(`${API_BASE}/api/remediations`);
    return res.json();
  },

  /** Get anomalies */
  async getAnomalies(threshold = 30) {
    const res = await fetch(`${API_BASE}/api/costs/anomalies?threshold=${threshold}`);
    return res.json();
  },
};
