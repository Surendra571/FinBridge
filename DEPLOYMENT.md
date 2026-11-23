# FinBridge — Production Deployment Guide & Architecture Reference

This document provides complete instructions for deploying the **FinBridge** platform to production:
- **Frontend**: React 18, TypeScript, Tailwind CSS, Vite deployed to **Vercel**.
- **Backend**: FastAPI, SQLAlchemy Async, Pydantic v2 deployed to **Render**.
- **Database & Cache**: Managed **PostgreSQL** (Neon / Supabase / Render Postgres) and Managed **Redis** (Upstash / Render Redis).

---

## 1. System Architecture Overview

```
                          ┌──────────────────────────┐
                          │   Vercel Edge Network    │
                          │   FinBridge Web Frontend │
                          │ (https://finbridge.app)  │
                          └─────────────┬────────────┘
                                        │ HTTPS / JSON API
                                        ▼
                          ┌──────────────────────────┐
                          │     Render Web Service   │
                          │      FastAPI Backend     │
                          │ (https://api.finbridge)  │
                          └───────┬────────────┬─────┘
                                  │            │
            ┌─────────────────────┴──┐      ┌──┴────────────────────────┐
            │ Managed PostgreSQL     │      │ Managed Redis Cache       │
            │ (Neon / Render DB)     │      │ (Upstash / Render Redis)  │
            │ AsyncPG Connection Pool│      │ Token revocations & locks │
            └────────────────────────┘      └───────────────────────────┘
```

---

## 2. Live Deployment Endpoints

| Component | Target URL | Documentation / Health Probe |
|---|---|---|
| **Web Frontend** | `https://finbridge-app.vercel.app` (or custom domain) | Route rewrites to `/index.html` via `vercel.json` |
| **API Backend** | `https://finbridge-api.onrender.com` | Live Swagger UI: `https://finbridge-api.onrender.com/docs` |
| **Liveness Probe** | `https://finbridge-api.onrender.com/api/v1/health/live` | `{"status": "ok", "app": "FinBridge"}` |
| **Readiness Probe** | `https://finbridge-api.onrender.com/api/v1/health/ready` | Verifies PostgreSQL DB pool and active tables |

---

## 3. Environment Variable Documentation

### Backend Environment Variables (`backend/.env.production`)

| Key | Example Value | Description |
|---|---|---|
| `ENVIRONMENT` | `production` | Enables production security mode and disables insecure overrides. |
| `DEBUG` | `false` | Disables debug stack traces in JSON responses. |
| `APP_NAME` | `FinBridge` | System identifier in logs and headers. |
| `HOST` | `0.0.0.0` | Bind host for ASGI server. |
| `PORT` | `8000` | Port injected by Render (`$PORT`). |
| `API_V1_PREFIX` | `/api/v1` | Versioned route root. |
| `SECRET_KEY` | `64_char_cryptographic_random_string` | Used to sign HS256 JWT access and refresh tokens. |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `60` | Access token lifetime. |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `7` | Refresh token lifetime. |
| `DATABASE_URL` | `postgresql+asyncpg://user:pass@host/db?ssl=require` | Async connection string for PostgreSQL. |
| `DATABASE_POOL_SIZE` | `20` | Concurrent DB pool connections. |
| `DATABASE_MAX_OVERFLOW` | `10` | Allowed surge DB connections. |
| `REDIS_URL` | `rediss://default:pass@host:6379` | TLS Redis URI for caching and idempotency locks. |
| `STORAGE_BACKEND` | `local` | Storage driver (`local` or `s3`). |
| `LOCAL_STORAGE_PATH` | `/var/data/finbridge/storage` | Path for uploaded bank statements and ledger files. |
| `ALLOWED_ORIGINS` | `https://finbridge-app.vercel.app` | Comma-separated list of trusted CORS origins. |
| `OPENAI_API_KEY` | `sk-proj-...` | *(Optional)* OpenAI key for natural language match explanations. |
| `AI_MOCK_FALLBACK` | `true` | Guarantees deterministic match explanations if OpenAI key is omitted. |

### Frontend Environment Variables (`frontend/.env.production`)

| Key | Example Value | Description |
|---|---|---|
| `VITE_API_BASE_URL` | `https://finbridge-api.onrender.com/api/v1` | Public backend v1 API root. |

---

## 4. Backend Deployment to Render

### Option A: Render Blueprint (`render.yaml`)

FinBridge includes a root `render.yaml` specification that provisions the web service, PostgreSQL database, and Redis instance automatically:

1. Push code to your Git repository (GitHub / GitLab).
2. In the **Render Dashboard**, click **New +** → **Blueprint**.
3. Connect your repository.
4. Render detects `render.yaml` and deploys:
   - `finbridge-api` (Python Web Service)
   - `finbridge-postgres` (Managed PostgreSQL)
   - `finbridge-redis` (Managed Redis)
5. Under `finbridge-api` settings, set `ALLOWED_ORIGINS` to your Vercel frontend URL.

### Option B: Manual Web Service Setup

1. In Render, select **New Web Service**.
2. Set **Root Directory** to `backend`.
3. Set **Runtime** to `Python 3`.
4. Set **Build Command**:
   ```bash
   pip install -r requirements.txt && python -m alembic upgrade head
   ```
5. Set **Start Command**:
   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port $PORT
   ```
6. Set **Health Check Path** to `/api/v1/health/live`.
7. Add the environment variables listed in Section 3.

---

## 5. Frontend Deployment to Vercel

FinBridge is preconfigured with `frontend/vercel.json` for seamless client-side single-page app (SPA) routing:

1. Install Vercel CLI or link through the [Vercel Dashboard](https://vercel.com).
2. Set **Root Directory** to `frontend`.
3. Set **Framework Preset** to `Vite`.
4. Configure Build & Output:
   - **Build Command**: `npm run build`
   - **Output Directory**: `dist`
   - **Install Command**: `npm install`
5. Under **Environment Variables**, add:
   ```
   VITE_API_BASE_URL = https://finbridge-api.onrender.com/api/v1
   ```
6. Click **Deploy**.

---

## 6. Database Migrations & Initial Synthetic Seed

Once the production database is connected, execute the automated migration and synthetic data seed:

```bash
# 1. Apply database migrations
cd backend
python -m alembic upgrade head

# 2. Seed verified demo organization and users
python scripts/seed_demo_data.py
```

### Controlled Demo Credentials

| Role | Email | Password | Organization | Permissions |
|---|---|---|---|---|
| **VP Controller** | `elena.rostova@northstarlogistics.com` | `ElenaPass123!` *(or `Password123!`)* | Northstar Logistics | Full reconciliation, approval, audit review |
| **System Admin** | `admin@finbridge.com` | `AdminPass123!` *(or `Password123!`)* | FinBridge Technologies Inc. | Settings, integrations, membership administration |

> [!NOTE]
> All seed and demo data is strictly **synthetic**. No actual banking credentials or real company records are stored or exposed.

---

## 7. Verification & Post-Deployment Testing Checklist

Run through these validation steps on the live deployed URL:

1. **Health Check Probes**:
   - `GET https://<backend>/api/v1/health/live` returns HTTP 200 `{"status": "ok"}`.
   - `GET https://<backend>/api/v1/health/ready` returns HTTP 200 with active DB check.
2. **User Registration & OTP**:
   - Navigate to `/register`, enter a new corporate email, and complete 6-digit OTP verification.
3. **Elena Controller Login**:
   - Navigate to `/login`, click "Elena" quick demo button, submit, and verify instant redirect to `/`.
4. **Dashboard Telemetry**:
   - Verify KPI cards, Inter typography, 256px Navy sidebar, and interactive state switcher.
5. **Bank Statement Upload**:
   - Navigate to `/statements`, drag & drop sample CSV or PDF, click parse & verify table.
6. **General Ledger Ingestion**:
   - Navigate to `/ledger`, test ERP selector (NetSuite, SAP, QBO) and file upload.
7. **Deterministic & AI Reconciliation**:
   - Navigate to `/reconciliation`, click "Run Reconciliation", and inspect the 3-panel matching table.
8. **Review Queue & Approvals**:
   - Navigate to `/reviews`, open exception TXN-2026-88412, and approve or request adjustment.
9. **Cryptographic Audit Trail**:
   - Navigate to `/audit`, click "Verify Chain Integrity", and confirm SHA-256 block hash validation.
10. **Reports & PDF Export**:
    - Navigate to `/reports`, switch currency tabs (USD, EUR, INR), and click "Export PDF" (triggers print layout).

---

## 8. Security & Zero-Secret Commit Policy

- **No Secrets in Git**: All tokens, database passwords, and private keys are injected via environment variables and managed secret vaults (Render Secrets, Vercel Environment Variables).
- **Strict Multi-Tenant Scoping**: All tenant queries require valid membership proof; tenant boundaries cannot be traversed via parameter tampering.
- **CORS Protection**: CORS strictly allows the registered production Vercel domain; credentials and cookies use `SameSite=Lax` and `Secure=True`.
