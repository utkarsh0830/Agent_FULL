# FinOps AI Orchestration Platform

AI-powered orchestration layer over **OpenCost**, **Infracost**, and **Cloud Custodian**.

## Quick Start (Local Development)

### 1. Backend

```bash
cd backend
cp .env.example .env
# Edit .env with your OPENAI_API_KEY

python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

uvicorn app.main:app --reload --port 8000
```

The backend auto-loads mock FOCUS billing data on first startup.

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000)

### 3. Docker Compose

```bash
docker-compose up --build
```

## How to Use

1. **Load Data** — Click "Load Data" (uses mock data by default, or enter S3 bucket/key)
2. **Run Analysis** — Click "Run Analysis" to trigger the 4-agent pipeline
3. **Review Results** — View RCA explanation, tag suggestions, cost forecast
4. **Approve/Reject** — Review Cloud Custodian policies and approve or reject remediation actions

## Agent Pipeline

```
Root Cause Analyzer → Tag Intelligence → Cost Forecaster → Action Planner
```

Each agent:
- Queries mock data (FOCUS + OpenCost + CI/CD deployments + Infracost)
- Calls the LLM with a structured prompt
- Returns JSON output that feeds the next agent

## Architecture

```
frontend/       → Next.js 14 + Tailwind + Recharts
backend/
  app/
    ingestion/  → S3 fetch + FOCUS validation + SQLite loader
    connectors/ → OpenCost, Infracost, Cloud Custodian wrappers
    agents/     → LangGraph sequential chain (4 agents)
    api/        → FastAPI endpoints with SSE streaming
    data/       → Mock FOCUS, OpenCost, deployment, Infracost data
```

## API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/api/upload-billing` | POST | Ingest FOCUS data from S3 |
| `/api/analysis/rca` | GET | Run full agent chain (SSE) |
| `/api/costs/summary` | GET | Cost summary by service |
| `/api/costs/daily` | GET | Daily time-series |
| `/api/remediate` | POST | Approve/reject remediation |
| `/api/remediations` | GET | List pending actions |
| `/api/health` | GET | Health check |

## Production Notes

- Replace mock data with real S3 + Athena queries
- Configure OpenCost API URL for K8s cost data
- Install Infracost CLI for pre-deploy estimates
- Install Cloud Custodian for policy execution
- Set `USE_MOCK_DATA=false` in environment
