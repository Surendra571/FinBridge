# FinBridge — Technical Decisions & Risk Management

**Version**: 1.0.0 (Phase 1 Baseline)  
**Classification**: Architecture Decision Records (ADRs) & Comprehensive Risk Matrix

---

## 1. Architecture Decision Records (ADRs)

### ADR-001: Separation of Raw Source Data from Normalized Financial Entities
- **Status**: ACCEPTED
- **Context**: Ingesting bank statements (CSV/PDF) and ERP ledger dumps requires cleansing, date parsing, and column transformations. If transformations are applied directly to original records, any parser bug or misinterpretation permanently corrupts source evidence, violating financial auditability standards.
- **Decision**: Persist untouched source files in object storage and raw line payloads in `raw_bank_transactions` / `raw_ledger_records`. Derived canonical entities are stored in `normalized_bank_transactions` / `normalized_ledger_entries` with explicit foreign keys to their raw origin.
- **Consequences**: Increases database storage requirements by ~40%, but guarantees 100% data provenance, auditability, and the ability to re-run updated normalization algorithms without re-requesting client files.

---

### ADR-002: Hybrid AI-Deterministic Verification Architecture
- **Status**: ACCEPTED
- **Context**: LLMs excel at deciphering noisy narrative strings (e.g. counterparty abbreviations, fee breakdowns), but exhibit non-deterministic behavior and potential hallucinations. Directly allowing an LLM to commit financial matches creates unacceptable fiduciary and legal risk.
- **Decision**: Implement a Three-Tier Verification Topology:
  1. *Tier 1*: High-throughput deterministic exact matcher (Python/SQL).
  2. *Tier 2*: Semantic proposal generator (LangGraph + OpenAI structured JSON).
  3. *Tier 3*: Deterministic mathematical invariant gate (Python `decimal.Decimal`).
- **Consequences**: Eliminates hallucination risk. The LLM acts purely as an advisor; zero financial transactions can be reconciled without passing exact mathematical invariant assertions.

---

### ADR-003: Row-Level Multi-Tenancy with PostgreSQL RLS
- **Status**: ACCEPTED
- **Context**: FinBridge is a multi-tenant platform. We evaluated Database-per-Tenant vs. Shared Database with Tenant ID scoping.
- **Decision**: Adopt a Shared PostgreSQL Database utilizing Defense-in-Depth isolation:
  1. Application-level tenant context injection (`contextvars`).
  2. Base SQLAlchemy repositories enforcing `WHERE organization_id = :tenant_id`.
  3. PostgreSQL Row-Level Security (RLS) enforcing `current_setting('app.current_org_id') = organization_id`.
- **Consequences**: Enables low-overhead scaling, simplified migrations, and cost-effective hosting on Render/Vercel, while PostgreSQL RLS prevents data leakage even in the event of an application-level SQL query omission.

---

### ADR-004: Asynchronous Processing via Celery & Redis
- **Status**: ACCEPTED
- **Context**: PDF table extraction, multi-thousand-row CSV normalization, and LLM batch inference introduce significant latency (3s to 60s), exceeding standard HTTP request timeouts.
- **Decision**: Offload all ingestion, batch reconciliation, LLM inference, and cryptographic chain verification to dedicated Celery worker queues backed by Redis.
- **Consequences**: Ensures FastAPI web workers remain lightweight and responsive (<100ms p95 latency). Requires managing Celery worker pools and Redis persistence.

---

### ADR-005: Cryptographic Hash Chaining for Append-Only Audit Trail
- **Status**: ACCEPTED
- **Context**: Auditors require proof that reconciliation logs and manual approvals have not been altered or deleted retroactively by privileged database administrators.
- **Decision**: Store audit logs in an append-only table where each row contains `prev_hash` and calculates `current_hash = SHA256(prev_hash + sequence_id + timestamp + actor_id + event_type + canonical_payload)`. Revoke `UPDATE` and `DELETE` on the table.
- **Consequences**: Provides tamper-evident verification comparable to private ledger databases without adding complex distributed blockchain dependencies.

---

### ADR-006: Property-Based Testing for Financial Math with Hypothesis
- **Status**: ACCEPTED
- **Context**: Unit tests with static fixtures often miss edge cases in monetary math (rounding boundaries, extreme values, precision loss).
- **Decision**: Incorporate `Hypothesis` into the Pytest suite to generate thousands of random financial permutations, validating mathematical invariants across all inputs.
- **Consequences**: Dramatically increases test coverage and catches subtle bugs (e.g. sign inversion errors, split cents) before deployment.

---

### ADR-007: Frontend State Architecture (TanStack Query + Zustand)
- **Status**: ACCEPTED
- **Context**: The frontend requires responsive state management for complex reconciliation tables, real-time background task polling, and optimistic UI updates.
- **Decision**: Use **TanStack Query (React Query v5)** for server state (caching, polling, mutations, optimistic updates) and **Zustand** for local client UI state (sidebar toggles, active filter presets).
- **Consequences**: Avoids Redux boilerplate, simplifies asynchronous data synchronization, and provides out-of-the-box caching.

---

## 2. Comprehensive Risk Matrix

| Risk ID | Category | Risk Description | Likelihood | Impact | Mitigation Strategy |
|---|---|---|:---:|:---:|---|
| **RSK-01** | Financial / AI | LLM hallucinates an invalid transaction pairing with plausible reasoning. | High | Critical | **Tier 3 Deterministic Python Gate**: Invariant validator evaluates `Sum(Bank) == Sum(Ledger)` in exact Decimal before any proposal reaches a user or ledger. Non-conforming proposals are rejected automatically. |
| **RSK-02** | Security | Cross-tenant data leakage via misconfigured API query. | Low | Critical | **Defense-in-Depth Isolation**: 4-tier enforcement (Context Middleware, Domain Assertions, SQLAlchemy repository filtering, and PostgreSQL Row-Level Security). |
| **RSK-03** | Operational | Re-uploading statement files leads to duplicate transactions and distorted cash balances. | Medium | High | **Two-Tier Deduplication**: File-level SHA-256 hash checks reject identical uploads. Line-level content signatures detect duplicate lines within revised files. |
| **RSK-04** | Performance | Ingesting large PDF statements (100+ pages) blocks web server or exhausts worker memory. | Medium | Medium | **Asynchronous Worker Sandboxing**: Ingestion delegated to Celery workers with 120s timeout and memory limits. Streamed layout extraction via `pdfplumber`. |
| **RSK-05** | Governance | Single user in small organization cannot approve high-value reconciliations due to Maker-Checker rules. | Medium | Medium | **Emergency Solo-User Mode**: If active org member count is exactly 1, system permits emergency override with high-severity security audit logging. |
| **RSK-06** | Financial | Binary floating-point rounding errors lead to off-by-one-cent reconciliation failures. | High | High | **Mandatory Fixed-Point Decimal**: Complete prohibition of `float` in financial code. Use `decimal.Decimal` with `ROUND_HALF_UP` and database `NUMERIC(15,2)`. |
| **RSK-07** | Infrastructure | Upstream OpenAI API rate limits (429) or outages stall reconciliation runs. | Medium | Medium | **Queue Throttling & Fallback**: Celery rate-limiting for AI worker queues. Circuit breaker pauses AI queue and alerts operator. System continues operating on Tier 1 deterministic matching. |

---

## 3. Architecture Sign-Off & Approval Gate

The architecture for FinBridge is now comprehensively defined across:
1. [SYSTEM_ARCHITECTURE.md](file:///d:/Founding-Projects/FinBridge/docs/SYSTEM_ARCHITECTURE.md)
2. [DATA_FLOW.md](file:///d:/Founding-Projects/FinBridge/docs/DATA_FLOW.md)
3. [SECURITY_ARCHITECTURE.md](file:///d:/Founding-Projects/FinBridge/docs/SECURITY_ARCHITECTURE.md)
4. [API_ARCHITECTURE.md](file:///d:/Founding-Projects/FinBridge/docs/API_ARCHITECTURE.md)
5. [TECHNICAL_DECISIONS.md](file:///d:/Founding-Projects/FinBridge/docs/TECHNICAL_DECISIONS.md)

**Awaiting user review and formal approval before writing application code.**
