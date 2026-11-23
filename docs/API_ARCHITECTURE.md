# FinBridge — API Architecture & Endpoint Specifications

**Version**: 1.0.0 (Phase 1 Baseline)  
**Standard**: RESTful JSON / OpenAPI 3.1  
**Base Path**: `/api/v1`

---

## 1. Global API Conventions

### 1.1 Headers
| Header | Requirement | Description |
|---|---|---|
| `Authorization` | Required for authenticated endpoints | Bearer JWT token (`Bearer <token>`). |
| `X-Organization-Id` | Required for tenant endpoints | UUID of the active organization context. |
| `X-Idempotency-Key` | Recommended for all mutations (`POST`, `PUT`, `PATCH`) | UUIDv4 to guarantee idempotent execution. |
| `X-Correlation-Id` | Optional (Generated if missing) | UUIDv4 tracing identifier propagated across logs. |

### 1.2 Error Handling Standard (RFC 7807 Problem Details)
All error responses return `application/problem+json`:
```json
{
  "type": "https://api.finbridge.io/errors/validation-failed",
  "title": "Financial Invariant Validation Failed",
  "status": 422,
  "detail": "Absolute sum of bank transactions ($1,250.00) does not equal ledger entries ($1,200.00). Variance ($50.00) exceeds tolerance ($0.00).",
  "instance": "/api/v1/reconciliation/matches/submit",
  "code": "FINANCIAL_INVARIANT_VIOLATION",
  "correlation_id": "8f9a2b1c-4d3e-4f5a-9b8c-7d6e5f4a3b2c",
  "invalid_params": [
    {
      "name": "variance",
      "reason": "Exceeds allowed threshold of 0.00"
    }
  ]
}
```

---

## 2. Comprehensive Endpoint Catalog

### 2.1 Authentication & Session Management (`/auth`)

| Method | Endpoint | Description | Auth Required |
|---|---|---|:---:|
| `POST` | `/auth/register` | Register new user account; dispatches verification email. | No |
| `POST` | `/auth/verify-email` | Verify email token and activate user account. | No |
| `POST` | `/auth/login` | Authenticate with credentials; returns JWT and sets refresh cookie. | No |
| `POST` | `/auth/refresh` | Rotate refresh token; issues fresh 15-minute access token. | No (Cookie) |
| `POST` | `/auth/logout` | Revoke active refresh token family in Redis and clear cookie. | Yes |
| `POST` | `/auth/password-reset/request` | Request password reset email. | No |
| `POST` | `/auth/password-reset/confirm` | Confirm password reset with time-bound token. | No |
| `GET`  | `/auth/me` | Fetch active user profile and organization memberships. | Yes |

---

### 2.2 Organizations & Memberships (`/organizations`)

| Method | Endpoint | Description | Roles |
|---|---|---|:---:|
| `GET`  | `/organizations` | List all organizations current user belongs to. | Any |
| `POST` | `/organizations` | Create new organization (caller becomes `ADMIN`). | Any |
| `GET`  | `/organizations/{id}` | Retrieve organization settings and base currency. | Member |
| `PATCH`| `/organizations/{id}` | Update organization settings and tolerance thresholds. | Admin |
| `GET`  | `/organizations/{id}/members` | List members and their assigned roles. | Member |
| `POST` | `/organizations/{id}/invitations` | Invite a user via email with a specific role. | Admin |
| `PATCH`| `/organizations/{id}/members/{user_id}` | Promote/demote member role. | Admin |
| `DELETE`| `/organizations/{id}/members/{user_id}` | Remove member from organization. | Admin |

---

### 2.3 Bank Statements & Ingestion (`/statements`)

| Method | Endpoint | Description | Roles |
|---|---|---|:---:|
| `POST` | `/statements/upload` | Upload bank statement (CSV or PDF) via multipart form. Returns statement ID and Celery ingestion task ID. | Accountant, Manager, Admin |
| `GET`  | `/statements` | List uploaded statements for the active organization. | Any |
| `GET`  | `/statements/{id}` | Get statement metadata, status, and summary counts. | Any |
| `GET`  | `/statements/{id}/raw` | Download original, pristine uploaded file. | Any |
| `GET`  | `/statements/{id}/transactions` | List normalized transactions with pagination & filters. | Any |
| `DELETE`| `/statements/{id}` | Soft-delete an un-reconciled statement. | Admin, Manager |

---

### 2.4 General Ledger Batches (`/ledger`)

| Method | Endpoint | Description | Roles |
|---|---|---|:---:|
| `POST` | `/ledger/upload` | Upload General Ledger CSV batch. Returns batch ID and processing task ID. | Accountant, Manager, Admin |
| `GET`  | `/ledger/batches` | List ledger upload batches with ingestion timestamps. | Any |
| `GET`  | `/ledger/entries` | List normalized ledger entries with status filters (`UNRECONCILED`, `RECONCILED`). | Any |

---

### 2.5 Reconciliation & Review Workspace (`/reconciliation`)

| Method | Endpoint | Description | Roles |
|---|---|---|:---:|
| `POST` | `/reconciliation/runs` | Trigger automated reconciliation pass (Tier 1 Exact Matcher + Tier 2 AI Matcher). Returns job ID. | Accountant, Manager |
| `GET`  | `/reconciliation/runs/{id}` | Check status and metrics of a reconciliation job. | Any |
| `GET`  | `/reconciliation/queue` | Query Discrepancy Queue (unmatched items, AI proposals, exceptions). | Any |
| `POST` | `/reconciliation/matches/manual` | Create manual match proposal (1:1, 1:Many, Many:1). | Accountant, Manager |
| `POST` | `/reconciliation/matches/{id}/submit` | Submit proposal for Maker-Checker review. | Accountant, Manager |
| `POST` | `/reconciliation/matches/{id}/approve` | Sign off on match proposal (Checker != Maker). | Manager, Admin |
| `POST` | `/reconciliation/matches/{id}/reject` | Reject proposal and return transactions to pool. | Accountant, Manager |
| `GET`  | `/reconciliation/reports/summary` | Aggregate reconciliation metrics and aging breakdown. | Any |
| `GET`  | `/reconciliation/reports/export` | Download audit-ready reconciliation package (CSV/PDF). | Any |

---

### 2.6 Cryptographic Audit Trail (`/audit`)

| Method | Endpoint | Description | Roles |
|---|---|---|:---:|
| `GET`  | `/audit/events` | List append-only audit events with sequence filtering. | Any |
| `GET`  | `/audit/events/{id}` | Inspect specific audit event payload and hash pointers. | Any |
| `POST` | `/audit/verify-chain` | Execute cryptographic verification of the SHA-256 chain. Returns verification result and depth. | Admin, Auditor, Manager |
| `GET`  | `/audit/export` | Export compliance evidence package with signed hash proof. | Auditor, Admin |

---

### 2.7 Integration Failure Simulator (`/simulations`)

| Method | Endpoint | Description | Roles |
|---|---|---|:---:|
| `GET`  | `/simulations/scenarios` | List available chaos fault scenarios (ERP Timeout, Duplicate Replay, Partial Batch Drop). | Admin, Manager |
| `POST` | `/simulations/execute` | Arm and trigger a chaos simulation run. | Admin, Manager |
| `GET`  | `/simulations/runs/{id}` | Retrieve simulation telemetry, invariant checks, and logs. | Any |

---

### 2.8 System Health & Telemetry (`/health`)

| Method | Endpoint | Description | Auth Required |
|---|---|---|:---:|
| `GET`  | `/health/live` | Process liveness probe. | No |
| `GET`  | `/health/ready` | Deep readiness probe (PostgreSQL, Redis, Celery). | No |
| `GET`  | `/metrics` | Prometheus metrics endpoint. | Internal / IP Whitelist |
