# FinBridge — Assumptions & Architectural Trade-offs

**Version**: 1.0.0 (Phase 0 Baseline)  
**Status**: Architecture Approved Blueprint  

---

## 1. Domain & Technical Assumptions

### 1.1 Financial Precision & Representation
- **Assumption**: All monetary amounts must be stored and computed using exact decimal representations. Binary floating-point types (`float`, `double`) are strictly prohibited in the core domain to prevent rounding inaccuracies (e.g. `0.1 + 0.2 = 0.30000000000000004`).
- **Implementation Decision**: 
  - In Python backend: `decimal.Decimal` with explicit rounding context (`ROUND_HALF_UP`).
  - In PostgreSQL database: `NUMERIC(15, 2)` for major currency amounts, or `BIGINT` representing minor currency units (cents). For Phase 0/1 baseline, standard 2-decimal currencies (USD, EUR, GBP) are modeled as `NUMERIC(15, 2)`.
  - In API JSON payloads: Formatted as strict strings (e.g. `"1250.50"`) or integer cents to avoid client-side JavaScript floating-point truncation.

### 1.2 Timezone & Date Boundaries
- **Assumption**: Bank statements report local transaction dates without explicit timezones, whereas internal ledgers may log microsecond UTC timestamps.
- **Implementation Decision**: 
  - All stored timestamps are normalized to ISO-8601 UTC.
  - When matching bank transaction dates (often effective date or value date) with ledger booking dates, the system applies an organization-configurable business day tolerance window (default: ±2 business days) to account for weekend settlement lags and clearing house batching.

### 1.3 Scope of Phase 0 Banking Formats
- **Assumption**: Real-world bank statements vary widely across thousands of institutions.
- **Implementation Decision**:
  - Phase 0 implements an adaptive CSV parser supporting arbitrary column headers via an interactive mapping configuration, plus standard pre-set templates (Chase, Bank of America, Silicon Valley Bank, Wells Fargo).
  - Digital PDF extraction targets standard machine-generated PDF statements with tabular layouts. Scanned image PDFs requiring heavy optical character recognition (OCR) will provide a fallback warning instructing the user to upload a digital export or CSV.

---

## 2. Key Architectural Trade-offs

### 2.1 Deterministic Verification vs. Autonomous AI Agents

```
Option A: Fully Autonomous AI Agent
  [LLM Reads Data] ──► [LLM Decides Match] ──► [LLM Directly Updates DB]
  Trade-off: Fast implementation, highly flexible, BUT zero financial guarantees,
  unpredictable hallucination risk, impossible to audit, violates accounting standards.

Option B: Hybrid Verification Architecture (FinBridge Choice)
  [LLM Reads Noise] ──► [Proposes Candidate] ──► [Python Deterministic Gate] ──► [Human Sign-off]
  Trade-off: Requires building two matching engines (heuristic + deterministic), but
  guarantees 100% mathematical invariant safety and full compliance.
```

- **Decision**: Adopt Option B. The LLM acts solely as an intelligent narrative decoder and fuzzy similarity engine. Financial approval authority is completely withheld from the LLM.

---

### 2.2 Multi-Tenancy Architecture: Row-Level Security vs. Database-per-Tenant

| Dimension | Option 1: Shared DB + Row-Level Security (RLS) | Option 2: Database-per-Tenant |
|---|---|---|
| **Resource Cost** | Low; single database cluster, shared connection pool | High; connection sprawl, idle database overhead |
| **Operational Simplicity** | High; single schema migration, centralized backup | Low; requires orchestrating hundreds of schema migrations |
| **Data Isolation** | Relies on application query filtering and Postgres RLS | Physical separation at storage and process boundary |
| **FinBridge Choice** | **SELECTED FOR PHASE 0-2** | Deferred to Enterprise on-premise tier |

- **Trade-off Evaluation**: For a portfolio and modern SaaS tier, Shared DB with PostgreSQL Row-Level Security (RLS) and strict tenant query interceptors provides enterprise-grade logical isolation with minimal infrastructure footprint and operational overhead.

---

### 2.3 LLM Integration: Direct Cloud API vs. Local Ollama vs. Embeddings

| Metric | Cloud LLMs (Claude 3.5 Sonnet / GPT-4o) | Local Models (Ollama / Llama 3) | Vector Embeddings (Cosine Similarity) |
|---|---|---|---|
| **Semantic Reasoning** | Superior; extracts complex split fees, tax codes | Moderate; struggles with subtle financial edge cases | Limited; matches text similarity, not accounting intent |
| **Data Privacy** | Requires zero-data-retention agreements | 100% local; zero external transmission | 100% local capable |
| **Inference Cost** | Token-based API fee per matching run | Free compute, requires local GPU/RAM | Negligible CPU cost |
| **Latency** | 800ms - 2,500ms per batch | 2,000ms - 8,000ms per batch | 10ms - 50ms |
| **FinBridge Strategy** | **Primary Cloud Provider** with Pydantic structured output | **Supported Local Fallback** via configurable provider switch | **Pre-filter Step** to narrow candidates before LLM invocation |

- **Decision**: FinBridge uses a layered strategy:
  1. *Candidate Retrieval*: Fast indexed query & vector/fuzzy similarity reduces candidate pairs from 10,000 to top 5.
  2. *LLM Inference*: High-capability LLM evaluates top 5 candidates with structured output schema.
  3. *Zero-Vendor Lock-in*: Abstract LLM client interface allowing hot-swapping between Anthropic, OpenAI, and local Ollama endpoints.

---

### 2.4 Audit Log Storage: Hash-Chained Relational Table vs. Blockchain / QLDB

- **Consideration**: Ledger integrity requires proof that records have not been retroactively altered or deleted by rogue administrators.
- **Alternative 1**: Public/Private Blockchain (Ethereum, Hyperledger) — High complexity, extreme latency, unnecessary token economics.
- **Alternative 2**: Cloud-proprietary ledger (Amazon QLDB) — Vendor lock-in, service retirement risk.
- **Alternative 3 (FinBridge Choice)**: Cryptographically Hash-Chained Relational Store. Each row stores `prev_hash` and `current_hash = SHA256(...)`. Combined with PostgreSQL `REVOKE UPDATE, DELETE ON audit_logs FROM app_user`, this guarantees immutability and verifiable tamper detection with zero external infrastructure dependencies.

---

### 2.5 Real vs. Simulated Integrations

- **Decision**: FinBridge strictly delineates between real capabilities and simulated infrastructure:
  - **Real**: Bank statement parsing (CSV/PDF), ledger ingestion, deterministic math engine, LLM inference API, RBAC, and hash-chained audit logging.
  - **Simulated**: Live Open Banking feeds (Plaid/Teller) and ERP bidirectional sync (NetSuite/QuickBooks).
- **Rationale**: Live banking APIs require commercial agreements, production bank licenses, and KYC verification that are inappropriate for a demonstration/portfolio architecture. The built-in **Integration Failure Simulator** provides higher testing value by intentionally injecting chaos scenarios (timeouts, schema corruption, duplicate deliveries) that cannot be reliably tested on live bank APIs.

---

## 3. Summary of Identified Dilemmas & Resolutions

| # | Conflict / Dilemma | Resolution in FinBridge |
|---|---|---|
| 1 | How to prevent duplicate matching when re-running reconciliation? | Matches acquire exclusive row locks during matching pass; once `AUTO_RECONCILED` or `RECONCILED`, entities cannot be selected as candidates in subsequent runs. |
| 2 | What happens if bank charges a $15 wire fee, causing bank line ($985) != invoice ($1,000)? | The system introduces **Discrepancy Categorization**. The accountant can approve the pair with an auto-drafted $15 "Bank Fee" adjustment journal. |
| 3 | What if an organization has only 1 user, blocking Maker-Checker? | The system permits self-approval only when `active_org_members == 1` and logs an emergency solo override alert in the tamper-evident audit log. |
| 4 | How to handle multi-page PDF statements with repeated headers/footers? | The parser uses bounding-box heuristics to strip running headers/footers above and below configurable vertical thresholds. |
