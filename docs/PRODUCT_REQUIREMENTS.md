# FinBridge — Product Requirements Document (PRD)

**Tagline**: Finance. Connected. Verified.  
**Version**: 1.0.0 (Phase 0 Baseline)  
**Status**: Pending Architecture Review & Approval  
**Target Milestone**: Production-Style Portfolio & Reference Architecture

---

## 1. Executive Summary & Vision

FinBridge is an enterprise-grade financial operations and reconciliation platform designed to bridge the chasm between external banking data (unstructured PDF statements, raw CSV dumps) and internal general ledger accounting records. 

Modern finance operations suffer from error-prone, manual reconciliation processes where human analysts spend hours cross-referencing messy bank narrative strings with ERP entries. While Artificial Intelligence (LLMs) offers unprecedented semantic understanding of noisy narrative texts, financial systems cannot tolerate non-deterministic hallucinations, rounding anomalies, or unvalidated automated execution.

FinBridge solves this via a **Hybrid Verification Architecture**:
- **LLM as Advisor**: Analyzes unstructured narratives, infers counterparty relationships, suggests many-to-one or split matches, and scores contextual similarity.
- **Deterministic Python Core as Gatekeeper**: Enforces strict mathematical invariants (cent-accurate balance parity, zero tolerance for unvetted rounding, directionality rules, and date-window boundaries).
- **Human Review as Arbitrator**: Routes edge cases, low-confidence matches, and policy violations to designated financial reviewers with Maker-Checker dual control.

---

## 2. Core Architectural Principles

1. **LLMs Propose, Never Approve**: The Large Language Model produces match hypotheses with structured explanations and confidence scores. It possesses zero authority to modify account balances, mark ledger entries reconciled, or bypass validation checks.
2. **Deterministic Financial Verification**: All financial assertions must pass rigorous, zero-dependency Python mathematical rules (`decimal.Decimal` fixed-point arithmetic, strict sign checking, idempotency validation).
3. **Fail-Closed on Ambiguity**: Any transaction pairing with ambiguity, confidence below defined thresholds, or multiple conflicting candidates is routed to the Human Review Queue (`MANUAL_REVIEW`).
4. **Append-Only Tamper-Evident Audit Trail**: Every data mutation, matching event, manual override, and system state change produces an immutable audit record containing actor identity, before/after snapshots, client fingerprint, and cryptographic SHA-256 chaining.
5. **Strict Idempotency**: All ingestion pipelines, reconciliation jobs, and state mutations use deterministic idempotency keys derived from content hashes and transaction metadata to prevent duplicate executions.
6. **Zero Cross-Tenant Leakage**: Complete multi-tenant data isolation. Every query, storage path, cache key, and background job is hard-scoped to an `organization_id` using database-level Row-Level Security (RLS) or rigorous query interception.
7. **Zero Silent Failures**: No malformed record, unparseable line, missing tax identifier, or currency mismatch is ever dropped silently. Ingestion processes record line-level errors in structured exception logs.

---

## 3. Real vs. Simulated Integrations

To ensure production integrity without incurring enterprise licensing costs or live bank API risk in a portfolio environment, FinBridge strictly categorizes its integrations:

| Component | Status | Implementation Details |
|---|---|---|
| **Bank Statement Parsing (CSV)** | **REAL** | Native Python streaming parser with schema autodetect, dialect sniffer, and RFC 4180 compliance. |
| **Bank Statement Parsing (PDF)** | **REAL** | Hybrid layout-aware extractor using `pdfplumber` / PyPDF with fallback tabular OCR and bounding-box coordinates. |
| **Internal Ledger CSV Import** | **REAL** | High-throughput streaming CSV processor validating double-entry accounting constraints. |
| **LLM Suggestion Engine** | **REAL** | Anthropic / OpenAI / Local Ollama structured JSON extraction via Instructor/Pydantic validation schemas. |
| **Authentication & RBAC** | **REAL** | JWT / Session cookies with argon2id password hashing, email token generation, and tenant-scoped claims. |
| **Audit Logging Engine** | **REAL** | PostgreSQL append-only write store with SHA-256 hash chaining and read-only database roles. |
| **Core Banking Open Banking / Plaid API** | **SIMULATED** | Built-in Mock Bank Webhook & REST Server capable of simulating live feeds, webhook retries, signature verification, and payload degradation. |
| **ERP Sync (NetSuite / SAP / QuickBooks)** | **SIMULATED** | In-app ERP Connector Harness simulating two-way sync, OAuth token expiration, rate limiting, and partial batch commits. |
| **Email Delivery (Verification & Alerts)** | **HYBRID** | Real local SMTP / MailHog test server in development; production-ready for SendGrid/SES via environment variables. |

---

## 4. User Personas & Responsibilities

- **System Administrator (Admin)**: Manages organization profiles, provisions user accounts, assigns RBAC roles, configures tenant-wide reconciliation rules, and audits security events.
- **Finance Manager**: Oversees reconciliation cycles, configures matching tolerance thresholds, reviews aggregate reconciliation metrics, and provides secondary approval ("Checker") for high-value or high-risk manual overrides.
- **Accountant (Operator / Maker)**: Uploads bank statements and ledger files, triggers reconciliation runs, investigates suggested matches, pairs split transactions, and resolves discrepancy queues.
- **Internal / External Auditor**: Accesses read-only audit trails, inspects reconciliation evidence packages, verifies cryptographic hash chains, and exports regulatory compliance reports.

---

## 5. Functional Requirements

### 5.1 Authentication, Organizations & Security
- **FR-AUTH-01 (Registration & Verification)**: New users register with name, business email, and strong password. System sends a time-bound (24h) cryptographically secure verification token. Unverified accounts cannot create or join organizations.
- **FR-AUTH-02 (Session Security)**: Support secure session handling via HTTP-only, SameSite=Strict cookies or signed JWT access tokens (15-minute expiry) with refresh token rotation.
- **FR-AUTH-03 (Password Recovery)**: Safe self-service password reset workflow with single-use, 15-minute invalidation tokens; terminates all active sessions upon password reset.
- **FR-ORG-01 (Multi-Tenancy & Membership)**: Users can create an Organization (becoming Admin) or accept email invitations to join existing organizations with specific roles.
- **FR-ORG-02 (Tenant Scoping)**: All database entities (`users_organizations`, `bank_statements`, `transactions`, `ledger_entries`, `matches`, `audit_logs`) must contain an immutable `organization_id` foreign key.

### 5.2 Ingestion & Normalization Engine
- **FR-ING-01 (Bank Statement CSV Ingestion)**:
  - Supports variable column headers via mapping templates (Date, Amount, Description/Narrative, Reference ID, Balance, Currency).
  - Handles credit/debit represented as single signed column or dual split columns.
  - Normalizes dates into ISO-8601 UTC.
  - Normalizes amounts to integer minor currency units (cents) or `Decimal` with fixed scale 2.
- **FR-ING-02 (Bank Statement PDF Ingestion)**:
  - Extracts text tables, transaction rows, beginning/ending balances, and metadata from standard digital PDF formats.
  - Generates extraction confidence scores per line item.
  - Flags corrupted pages, non-selectable scanned images (prompting OCR fallback), or arithmetic inconsistencies where beginning balance + net movements != ending balance.
- **FR-ING-03 (General Ledger Ingestion)**:
  - Accepts standard accounting ledger CSV exports containing Entry ID, Account Code, Booking Date, Effective Date, Amount, Currency, Reference/Memo, and Entity Code.
  - Enforces ledger structural checks (e.g. non-null Entry ID, valid ISO currency code).
- **FR-ING-04 (File Storage & Content Hashing)**:
  - Every uploaded file is hashed (SHA-256) upon arrival. Re-uploading an identical file within the same organization is blocked with a descriptive idempotency alert.

### 5.3 Reconciliation Engine: Two-Tier Architecture
- **FR-REC-01 (Deterministic Rule Tier — Tier 1)**:
  - **Exact Match Rule**: Identical absolute amount, matching currency, opposite sign (bank credit = ledger debit or vice versa), matching reference string, and transaction dates within ±2 business days.
  - Automatic reconciliation threshold: If Tier 1 deterministic rules pass with 100% confidence and unique 1:1 candidacy, the system marks the pair as `AUTO_RECONCILED`.
- **FR-REC-02 (AI Proposal Tier — Tier 2)**:
  - For un-matched or noisy records, the LLM receives candidate vectors and transaction metadata.
  - LLM evaluates semantic variations (e.g., "AMZN MKTPLACE US" vs "Amazon Web Services Inc INV-8942"), identifies bank fee splits, and suggests multi-to-one matches.
  - LLM outputs structured schema: `suggested_ledger_ids`, `confidence_score` (0.00 - 1.00), `reasoning_summary`, and `suggested_discrepancy_category` (e.g., Timing Difference, Bank Fee, Currency Fluctuation).
  - LLM proposals are saved in state `PROPOSED` and **never** auto-committed.
- **FR-REC-03 (Deterministic Validation Gate — Tier 3)**:
  - Every AI proposal must run through the Python Validation Engine prior to reaching human review or approval.
  - Verifies: Sum(Bank Amount) == Sum(Ledger Amount) (within designated tolerance, e.g., $0.00 for exact, or up to configured threshold for fee splits), currency parity, directionality check, and unconsumed state (preventing double-matching).
  - If Python validation fails, the AI proposal is rejected and flagged as `INVALID_PROPOSAL` with error breakdown.
- **FR-REC-04 (Matching Topologies)**:
  - 1-to-1 (One bank transaction matches one ledger entry).
  - 1-to-Many (One bulk bank deposit matches multiple invoice ledger entries).
  - Many-to-1 (Multiple batch card disbursements match a consolidated settlement ledger entry).
  - Discrepancy with Adjustment (Match with an acceptable variance, e.g. bank processing fee, requiring auto-drafting of an adjustment journal).

### 5.4 Human Review & Approval Workflow
- **FR-REV-01 (Discrepancy Queue)**: Filterable, sortable operational queue categorizing transactions into:
  - High Confidence Suggestions (Score >= 0.85, passed validation gate).
  - Ambiguous / Low Confidence (Score < 0.85 or multiple candidate matches).
  - Unmatched Exceptions (No candidates found in ledger).
  - Integrity Violations (Mathematical failures, duplicate candidates).
- **FR-REV-02 (Interactive Split & Manual Pair)**:
  - UI allows accountants to manually link bank records with ledger records, view AI explanations, and enter adjustment notes.
- **FR-REV-03 (Maker-Checker Dual Control)**:
  - Configurable monetary threshold (e.g., > $10,000 or any transaction with price discrepancy > $50).
  - Maker (Accountant) submits proposed reconciliation; Checker (Finance Manager) must review and approve before final state commit.
  - The Maker cannot approve their own submission.

### 5.5 Append-Only Audit Trail
- **FR-AUD-01 (Event Completeness)**: Log all events: `USER_LOGIN`, `FILE_UPLOADED`, `INGESTION_PARSED`, `MATCH_PROPOSED`, `VALIDATION_PASSED`, `VALIDATION_FAILED`, `MANUAL_OVERRIDE`, `MAKER_SUBMITTED`, `CHECKER_APPROVED`, `RECONCILIATION_FINALIZED`, `SIMULATION_EXECUTED`.
- **FR-AUD-02 (Cryptographic Integrity)**: Each audit log row computes `current_hash = SHA256(previous_hash + timestamp + org_id + actor_id + event_type + payload_json)`.
- **FR-AUD-03 (Tamper Detection)**: Automated routine validates hash continuity; any altered row or missing sequence breaks the chain and triggers an immediate critical security alert.

### 5.6 Integration Failure Simulator
- **FR-SIM-01 (Chaos Injection Engine)**: Controlled simulation modal enabling engineers/reviewers to test system resiliency against financial infrastructure failures:
  - *Network Timeout / Partition*: Simulates ERP webhook delays (504 Gateway Timeout).
  - *Partial Batch Failure*: Ingests 50 records, simulates network drop at record 26; validates atomic rollback or idempotent resumption.
  - *Duplicate Delivery / Replay Attack*: Re-submits previously processed bank webhooks; verifies idempotent rejection without balance duplication.
  - *Corrupted Payload*: Submits invalid data types, missing balancing lines, or mismatched currency symbols.
- **FR-SIM-02 (Resilience Verification)**: Logs every simulation attempt, system response, retry backoff calculation, and failure isolation result.

### 5.7 Reconciliation Reports & Analytics
- **FR-REP-01 (Dashboard Analytics)**: Real-time operational dashboard displaying:
  - Total Volume & Value Ingested vs Reconciled.
  - Auto-Reconciliation Rate (%) vs Manual Review Rate (%).
  - Aging breakdown of unmatched transactions (0-30 days, 31-60 days, 60+ days).
  - Variance and discrepancy value distribution.
- **FR-REP-02 (Audit & Compliance Export)**: One-click export of comprehensive reconciliation packs (PDF summary + CSV details) including signed audit trail references for external auditors.

---

## 6. Non-Functional Requirements (NFR)

### 6.1 Data Integrity & Precision
- **NFR-DAT-01**: Monetary arithmetic must never use binary floating-point (`float`). All computations must use fixed-point `Decimal` with standard rounding rules (`ROUND_HALF_UP`) or integer minor currency units.
- **NFR-DAT-02**: All state mutations affecting reconciliation status must run within ACID database transactions at `READ COMMITTED` or `SERIALIZABLE` isolation levels to eliminate race conditions.

### 6.2 Security & Compliance
- **NFR-SEC-01**: Passwords hashed using `argon2id` with memory cost >= 64MB and time cost >= 3.
- **NFR-SEC-02**: At-rest encryption for sensitive financial documents stored in object storage (AES-256-GCM). In-transit encryption via TLS 1.3.
- **NFR-SEC-03**: Role-based access validation checked at both API gateway and business domain service layers.
- **NFR-SEC-04**: Sanitization of all file uploads to eliminate CSV formula injection (`=cmd`, `@SUM`, `+`, `-`) and malicious PDF payloads.

### 6.3 Performance & Scalability
- **NFR-PERF-01**: Parse and normalize a 5,000-line bank CSV within <= 3.0 seconds.
- **NFR-PERF-02**: End-to-end reconciliation pass (Tier 1 deterministic matching) for 10,000 transaction pairs within <= 10.0 seconds.
- **NFR-PERF-03**: Sub-100ms API response time for p95 dashboard and queue queries.

### 6.4 Usability & Responsive Design
- **NFR-UI-01**: Fully responsive interface optimized for Desktop (1920x1080, 1440x900), Tablet (iPad landscape/portrait), and Mobile viewports (375px+).
- **NFR-UI-02**: Accessible color contrasts adhering to WCAG 2.1 AA standards; keyboard-navigable reconciliation queues.

---

## 7. Analysis of Missing Requirements & Conflicting Decisions

During initial requirements discovery, several critical ambiguities and conflicting operational patterns were identified and resolved:

### Conflict 1: LLM Non-Determinism vs. Financial Repeatability
- *Conflict*: LLMs may yield slightly different confidence scores or text reasoning for identical inputs across runs, which violates accounting reproducibility requirements.
- *Resolution*: FinBridge decouples **Reasoning Generation** from **Matching State**. The LLM provides proposal suggestions only once, cached deterministically by a prompt-and-payload SHA-256 hash. Once an Accountant/Manager approves or rejects a match, that decision is recorded permanently in the deterministic state engine. Re-running a matching batch will not overwrite human-reviewed or deterministically validated records.

### Conflict 2: Automated Ingestion vs. Idempotent Retry of Corrected Files
- *Conflict*: If an Accountant uploads a bank statement with bad dates, and later re-uploads a corrected version with the same file name or slightly altered lines, standard hash deduplication could block the file, or partial duplication could inflate balances.
- *Resolution*: FinBridge implements a two-level deduplication:
  1. *File-Level Deduplication*: Identical SHA-256 file uploads within an organization are rejected as exact duplicates.
  2. *Line-Level Deduplication*: If a file is uploaded as a "Replacement / Revision", transactions are individually checked against `(organization_id, bank_account_id, date, amount, reference_hash)`. Existing entries are not re-inserted; un-reconciled existing entries can be marked `SUPERSEDED` only through explicit user confirmation.

### Missing Requirement 1: Currency Conversion & Multi-Currency Portfolios
- *Missing*: Statements may be in EUR while the general ledger operates in USD, introducing FX rate spreads and timing differences.
- *Specification*: Phase 0 defines single-currency reconciliations (e.g., USD-to-USD or EUR-to-EUR per account). Multi-currency reconciliation with dynamic FX rate feeds is slated for Phase 2/3 and marked explicitly in the roadmap.

### Missing Requirement 2: Maker-Checker Deadlock in Small Organizations
- *Missing*: If an organization has only 1 user (the Admin/Accountant), strict Maker-Checker enforcement prevents approving reconciliations that exceed the approval threshold.
- *Specification*: Introduce an Organization-Level Policy toggle: `ENFORCE_DUAL_CONTROL` (default: `true` for teams > 1 member; auto-bypassed with high-severity audit logging when single-user mode is active).
