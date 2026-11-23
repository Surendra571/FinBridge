# FinBridge — Core Workflows & System Architecture

**Version**: 1.0.0 (Phase 0 Baseline)  
**Status**: Architecture Approved Blueprint  

---

## 1. End-to-End System Overview

FinBridge processes noisy external banking statements, synchronizes internal accounting ledgers, applies an AI-assisted and deterministic verification pipeline, and guarantees an immutable audit trail.

```mermaid
flowchart TD
    subgraph Ingestion ["1. Data Ingestion Layer"]
        A1["Bank CSV Upload"] --> B1["Dialect Sniffer & Normalizer"]
        A2["Bank PDF Upload"] --> B2["pdfplumber / Tabular Parser"]
        A3["General Ledger CSV"] --> B3["Ledger Schema Validator"]
        B1 --> C1[("Bank Transactions Table")]
        B2 --> C1
        B3 --> C2[("Ledger Entries Table")]
    end

    subgraph Processing ["2. Hybrid Reconciliation Engine"]
        C1 & C2 --> D1["Tier 1: Deterministic Exact Matcher"]
        D1 -- "100% Exact Match" --> E1["Auto-Reconciled"]
        D1 -- "Unmatched / Partial" --> D2["Tier 2: AI Proposal Generator (LLM)"]
        D2 --> D3["Structured JSON Candidates"]
        D3 --> D4["Tier 3: Deterministic Financial Gate (Python)"]
        D4 -- "Validation Passed" --> E2["Proposed Match Queue"]
        D4 -- "Validation Failed" --> E3["Invalid Proposal / Exception"]
    end

    subgraph Governance ["3. Human-in-the-Loop & Audit"]
        E2 & E3 --> F1{"Maker-Checker Review"}
        F1 -- "Approved" --> G1["Final Reconciled State"]
        F1 -- "Rejected / Split" --> G2["Manual Adjustment"]
        E1 & G1 & G2 --> H1["Append-Only Audit Engine (SHA-256 Chain)"]
    end
```

---

## 2. Detailed Workflows

### 2.1 Workflow 1: User Onboarding & Organization Setup

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant Web as Web App (Client)
    participant Auth as Auth Service
    participant DB as Database (Multi-Tenant)
    participant Mail as Email Dispatcher

    User->>Web: Submit Name, Email, Password
    Web->>Auth: POST /api/v1/auth/register
    Auth->>Auth: Hash password (argon2id)
    Auth->>DB: INSERT INTO users (status='PENDING_VERIFICATION')
    Auth->>DB: Generate verification token (24h TTL)
    Auth->>Mail: Send verification email
    Auth-->>Web: 201 Created (Prompt user to check inbox)
    
    User->>Web: Click email link (/verify-email?token=...)
    Web->>Auth: POST /api/v1/auth/verify-email
    Auth->>DB: Verify token, set user status='ACTIVE'
    Auth-->>Web: 200 OK (Email verified)

    User->>Web: POST /api/v1/organizations (Create "Acme Corp")
    Web->>Auth: Authenticated session request
    Auth->>DB: INSERT INTO organizations (name, base_currency='USD')
    Auth->>DB: INSERT INTO user_organizations (role='ADMIN')
    Auth-->>Web: Issue JWT with org_id and role='ADMIN'
```

---

### 2.2 Workflow 2: Bank Statement Ingestion & Normalization

The ingestion pipeline handles both structured CSV files and semi-structured digital PDF statements.

```mermaid
sequenceDiagram
    autonumber
    actor Accountant
    participant UI as Responsive UI
    participant API as Ingestion API
    participant Parser as Ingestion Engine (CSV/PDF)
    participant Storage as Object Storage
    participant Audit as Audit Service
    participant DB as Database

    Accountant->>UI: Select Bank Account & Upload Statement (CSV/PDF)
    UI->>API: POST /api/v1/statements/upload (multipart/form-data)
    API->>API: Calculate SHA-256 file hash
    API->>DB: Query existing file_hash WHERE org_id = :org_id
    alt Duplicate File Detected
        API-->>UI: 409 Conflict ("Statement already uploaded on [Date]")
    else File Is Unique
        API->>Storage: Store raw file at tenants/{org_id}/statements/...
        API->>Parser: Dispatch Parse Job (file_path, file_type)
        
        alt File is CSV
            Parser->>Parser: Sniff dialect, detect delimiter, map columns
        else File is PDF
            Parser->>Parser: Extract text coordinates, detect tables, extract transactions
            Parser->>Parser: Validate: Starting Balance + Net Sum == Ending Balance
        end

        Parser->>Parser: Normalize Dates (ISO-8601 UTC)
        Parser->>Parser: Normalize Amounts (Decimal cent representation)
        Parser->>DB: INSERT INTO bank_statements (metadata, total_rows)
        Parser->>DB: BULK INSERT INTO bank_transactions (status='UNMATCHED')
        Parser->>Audit: Record FILE_INGESTED event
        Audit->>DB: Append audit log with SHA-256 chain
        Parser-->>UI: 200 OK (Ingestion summary: 342 parsed, 0 errors)
    end
```

---

### 2.3 Workflow 3: Internal General Ledger CSV Ingestion

```mermaid
sequenceDiagram
    autonumber
    actor Accountant
    participant UI as Responsive UI
    participant API as Ledger API
    participant Validator as Ledger Validator
    participant DB as Database

    Accountant->>UI: Upload Ledger CSV (Journal entries, disbursements, receipts)
    UI->>API: POST /api/v1/ledger/upload
    API->>Validator: Stream and validate rows
    Validator->>Validator: Check required fields: entry_id, date, amount, currency, account_code
    Validator->>Validator: Verify date ranges & decimal syntax
    Validator->>DB: Bulk insert into ledger_entries (status='UNRECONCILED', org_id=:org_id)
    API->>DB: Record Audit Event (LEDGER_UPLOADED)
    API-->>UI: 200 OK (Summary: 512 entries ingested)
```

---

### 2.4 Workflow 4: Hybrid Two-Tier Reconciliation Pipeline

This is the core intellectual property and architectural differentiator of FinBridge:

```mermaid
sequenceDiagram
    autonumber
    actor User as Operator / Automated Trigger
    participant Engine as Reconciliation Engine
    participant Tier1 as Tier 1: Deterministic Exact Matcher
    participant Tier2 as Tier 2: AI Proposal Generator (LLM)
    participant Tier3 as Tier 3: Deterministic Financial Gate
    participant DB as Database
    participant Audit as Audit Service

    User->>Engine: POST /api/v1/reconciliation/run
    Engine->>DB: Fetch UNMATCHED bank_transactions & UNRECONCILED ledger_entries
    
    rect rgb(230, 245, 230)
    Note over Engine,Tier1: Tier 1: Deterministic Invariant Match
    Engine->>Tier1: Execute exact rule matching
    Tier1->>Tier1: Conditions: Amount exact, Sign inverted, Date within ±2 days, Ref ID match
    Tier1->>DB: UPDATE matches SET status='AUTO_RECONCILED'
    Tier1->>Audit: Log AUTO_MATCH_COMMITTED
    end

    rect rgb(240, 240, 255)
    Note over Engine,Tier2: Tier 2: AI Proposal Generation (Unmatched Pool)
    Engine->>Tier2: Batch un-reconciled items (Context, Descriptions, Amounts)
    Tier2->>Tier2: Query LLM with strict JSON schema (Instructor/Pydantic)
    Tier2-->>Engine: Return Candidate Proposals: {bank_id, ledger_ids, confidence, rationale}
    end

    rect rgb(255, 240, 240)
    Note over Engine,Tier3: Tier 3: Deterministic Python Validation Gate
    Engine->>Tier3: Validate every AI proposal hypothesis
    Tier3->>Tier3: Assert Sum(Bank) == Sum(Ledger) ± Approved Fee Tolerance
    Tier3->>Tier3: Assert currency matches & accounts compatible
    Tier3->>Tier3: Assert entries not previously locked or matched
    
    alt Validation Passed
        Tier3->>DB: INSERT INTO match_proposals (status='PENDING_REVIEW', confidence, rationale)
        Tier3->>Audit: Log MATCH_PROPOSED_BY_AI
    else Validation Failed
        Tier3->>DB: INSERT INTO match_exceptions (status='INVALID_PROPOSAL', failure_reason)
        Tier3->>Audit: Log AI_PROPOSAL_REJECTED_BY_GATE
    end
    end

    Engine-->>User: Reconciliation Run Completed (X Auto, Y Proposed, Z Exceptions)
```

---

### 2.5 Workflow 5: Human Review & Maker-Checker Dual Control

```mermaid
sequenceDiagram
    autonumber
    actor Maker as Accountant (Maker)
    actor Checker as Finance Manager (Checker)
    participant UI as Discrepancy Queue UI
    participant API as Review API
    participant Gate as Policy & SoD Gate
    participant DB as Database
    participant Audit as Audit Service

    Maker->>UI: View Pending Review Queue
    UI->>API: GET /api/v1/reconciliation/queue
    API-->>UI: Return proposals with AI reasoning & diff views
    
    Maker->>UI: Select Bank Tx ($12,500.00) & Ledger Entry ($12,500.00)
    Maker->>UI: Click "Submit for Approval"
    UI->>API: POST /api/v1/matches/{id}/submit
    API->>Gate: Check Threshold Policy
    
    alt Value < $10,000 and Zero Variance
        Gate->>DB: UPDATE matches SET status='RECONCILED', approved_by=Maker.id
        Gate->>Audit: Log MATCH_APPROVED (Single-operator)
        API-->>UI: Match finalized directly
    else Value >= $10,000 OR Non-zero Variance
        Gate->>DB: UPDATE match_proposals SET status='PENDING_CHECKER', maker_id=Maker.id
        Gate->>Audit: Log MAKER_SUBMITTED_FOR_REVIEW
        API-->>UI: "Submitted to Finance Manager for secondary approval"
        
        Checker->>UI: View "Requires Manager Approval" Tab
        UI-->>Checker: Display Proposal, Maker Identity, LLM Rationale, Audit Trail
        
        alt Checker Approves
            Checker->>UI: Click "Approve Match"
            UI->>API: POST /api/v1/matches/{id}/approve
            API->>Gate: Assert Checker.id != Maker.id (SoD Enforcement)
            Gate->>DB: UPDATE matches SET status='RECONCILED', checker_id=Checker.id
            Gate->>Audit: Log CHECKER_APPROVED_MATCH
            API-->>UI: Match approved & committed to General Ledger
        else Checker Rejects
            Checker->>UI: Click "Reject / Return to Pool" (with reason note)
            UI->>API: POST /api/v1/matches/{id}/reject
            API->>DB: UPDATE match_proposals SET status='REJECTED'
            API->>DB: Reset transactions to status='UNMATCHED'
            API->>Audit: Log MATCH_REJECTED_BY_CHECKER
            API-->>UI: Proposal discarded
        end
    end
```

---

### 2.6 Workflow 6: Cryptographic Append-Only Audit Trail Verification

```mermaid
sequenceDiagram
    autonumber
    actor Auditor as Auditor / Admin
    participant UI as Audit Dashboard
    participant API as Audit API
    participant Verifier as Cryptographic Verifier Engine
    participant DB as Read-Only Database View

    Auditor->>UI: Click "Verify Audit Chain Integrity"
    UI->>API: POST /api/v1/audit/verify-chain
    API->>Verifier: Stream audit log rows for org_id ordered by sequence_id ASC
    Verifier->>DB: SELECT id, sequence_id, timestamp, actor_id, event_type, payload, prev_hash, current_hash
    
    loop Every Record
        Verifier->>Verifier: expected_hash = SHA256(prev_hash + sequence_id + timestamp + actor_id + event_type + canonical_json(payload))
        Verifier->>Verifier: Assert expected_hash == current_hash
    end

    alt All Hashes Match
        Verifier-->>API: Integrity Verified (Chain depth: 14,208 records, 0 anomalies)
        API-->>UI: Green Badge: "Audit Chain Cryptographically Verified"
    else Any Mismatch Detected
        Verifier-->>API: INTEGRITY_BREACH detected at sequence_id: 8,412
        API->>DB: Log CRITICAL_SECURITY_ALERT
        API-->>UI: Red Alert: "Tamper Detected! Record altered or deleted"
    end
```

---

### 2.7 Workflow 7: Chaos & Integration Failure Simulation

FinBridge incorporates an explicit testing and chaos engine to validate error handling without touching live external banking rails:

```mermaid
sequenceDiagram
    autonumber
    actor Lead as Tech Lead / Tester
    participant UI as Simulation Console
    participant SimEngine as Chaos Simulation Engine
    participant Ingest as Ingestion Service
    participant Audit as Audit Logger

    Lead->>UI: Select Scenario: "ERP Ledger Webhook Network Timeout"
    Lead->>UI: Set Failure Rate = 100%, Target = "Batch Ingest"
    UI->>SimEngine: POST /api/v1/simulations/execute
    SimEngine->>SimEngine: Initialize simulation context (sim_run_id)
    SimEngine->>Ingest: Trigger mock webhook dispatch with artificial latency (35,000ms)
    
    Ingest->>Ingest: Client timeout triggers (HTTP 504 Gateway Timeout)
    Ingest->>Ingest: Circuit Breaker opens; Exponential Backoff retry scheduled (Attempt 1 of 3)
    Ingest->>Audit: Log SIMULATED_FAILURE_CAPTURED (sim_run_id, error="ReadTimeout")
    
    SimEngine->>SimEngine: Evaluate system behavior against resilience invariants:
    Note over SimEngine: Invariant 1: No duplicate records created<br/>Invariant 2: Transactions remain locked in pending state<br/>Invariant 3: Failure logged in structured exception table
    
    SimEngine-->>UI: Simulation Report (Passed: Graceful failure handled, zero data corruption)
```
