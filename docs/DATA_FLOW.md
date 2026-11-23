# FinBridge — Data Flow & Lifecycle Specifications

**Version**: 1.0.0 (Phase 1 Baseline)  
**Classification**: Financial Data Lifecycle, State Machines & Pipeline Flows

---

## 1. Raw vs. Normalized Data Lifecycle

A primary tenet of financial compliance is that external statements and internal ledger exports must be preserved in their pristine, unadulterated state. Any transformation into canonical domain models must be traceable back to the exact source row and file offset.

```mermaid
flowchart TD
    subgraph RawCapture ["1. Raw Ingestion & Preservation (Immutable)"]
        F1["Bank Statement (CSV/PDF)"] --> Hash["Compute SHA-256 File Hash"]
        Hash --> DupCheck{"File Hash Exists in Org?"}
        DupCheck -- Yes --> RejectDup["HTTP 409 Conflict (Duplicate Blocked)"]
        DupCheck -- No --> StoreBlob["Save Raw File to Object Storage"]
        StoreBlob --> InsStatement["INSERT INTO bank_statements"]
        InsStatement --> StreamRows["Stream Raw File Lines"]
        StreamRows --> InsRaw["INSERT INTO raw_bank_transactions (raw_payload_json)"]
    end

    subgraph Transformation ["2. Deterministic Normalization Pipeline"]
        InsRaw --> Cleanse["Normalize Syntax, Whitespace, & Dialect"]
        Cleanse --> ParseDate["Normalize Date to ISO-8601 UTC"]
        Cleanse --> ParseAmount["Normalize Amount to Decimal (cents)"]
        Cleanse --> InvertSign["Normalize Sign / Direction (DEBIT vs CREDIT)"]
        Cleanse --> TokenizeRef["Extract Clean Reference Tokens"]
        ParseDate & ParseAmount & InvertSign & TokenizeRef --> InsNorm["INSERT INTO normalized_bank_transactions"]
        InsNorm -. "Foreign Key Linked" .-> InsRaw
    end

    subgraph MatchingPool ["3. Active Reconciliation Pool"]
        InsNorm --> ReadyState["Status: UNMATCHED"]
        ReadyState --> RecPipeline["Reconciliation Engine Pipeline"]
    end
```

---

## 2. Reconciliation Data Flow & Matching Pipeline

The reconciliation process moves transactions through three deterministic gates, transitioning entities through explicit state boundaries.

```mermaid
sequenceDiagram
    autonumber
    participant Pool as Normalized Transaction Pool
    participant Tier1 as Tier 1: Deterministic Matcher
    participant PreFilter as Semantic Pre-Filter (RapidFuzz)
    participant LangGraph as Tier 2: AI LangGraph Workflow
    participant OpenAI as OpenAI API
    participant Tier3 as Tier 3: Python Validation Gate
    participant DB as PostgreSQL Database
    participant Audit as Audit Logger

    Pool->>Tier1: Fetch UNMATCHED Bank Tx & UNRECONCILED Ledger Entries
    
    rect rgb(235, 255, 235)
    Note over Tier1: Exact Invariant Matching
    Tier1->>Tier1: Match: abs(Bank) == abs(Ledger) & Date ±2 Days & Ref Token
    alt Exact 1:1 Match Found
        Tier1->>DB: INSERT INTO matches (status='AUTO_RECONCILED')
        Tier1->>DB: UPDATE bank_transactions SET status='RECONCILED'
        Tier1->>DB: UPDATE ledger_entries SET status='RECONCILED'
        Tier1->>Audit: Log AUTO_MATCH_COMMITTED
    end
    end

    rect rgb(240, 240, 255)
    Note over PreFilter,OpenAI: AI Suggestion Generation (For Residual Unmatched)
    Tier1->>PreFilter: Send remaining unmatched records
    PreFilter->>PreFilter: Compute string similarity over descriptions (Score >= 60)
    PreFilter->>LangGraph: Pass top 5 candidates per bank transaction
    LangGraph->>OpenAI: Request structured candidate evaluation (JSON schema)
    OpenAI-->>LangGraph: Return SuggestedMatch (candidate_ids, confidence, rationale)
    end

    rect rgb(255, 240, 240)
    Note over Tier3: Python Financial Gate (Zero Hallucination Shield)
    LangGraph->>Tier3: Submit AI Proposal for Mathematical Verification
    Tier3->>Tier3: Check 1: Sum(Bank) == Sum(Ledger) ± Approved Fee Tolerance
    Tier3->>Tier3: Check 2: Currency parity (USD == USD)
    Tier3->>Tier3: Check 3: Direction balance (Credit matches Debit)
    Tier3->>Tier3: Check 4: Neither item already committed

    alt Verification Passes
        Tier3->>DB: INSERT INTO match_proposals (status='VALIDATED', confidence, rationale)
        Tier3->>Audit: Log MATCH_PROPOSAL_VALIDATED
    else Verification Fails
        Tier3->>DB: INSERT INTO match_proposals (status='FAILED_GATE', error_details)
        Tier3->>Audit: Log AI_PROPOSAL_REJECTED_BY_GATE
    end
    end
```

---

## 3. Human Review & Maker-Checker State Flow

```mermaid
flowchart TD
    VP["Validated Proposal in Queue"] --> ThresholdCheck{"Amount >= $10,000 OR Variance > $0.00?"}
    
    ThresholdCheck -- "No (Low Value / Exact)" --> StandardAction["Accountant Approves Directly"]
    StandardAction --> CommitDirect["Status: RECONCILED"]
    CommitDirect --> LogDirect["Log MATCH_APPROVED (Single Operator)"]

    ThresholdCheck -- "Yes (High Value / Variance)" --> MakerSubmit["Accountant Submits Proposal (Maker)"]
    MakerSubmit --> LockProp["Status: PENDING_CHECKER<br/>Store maker_id"]
    LockProp --> CheckerInbox["Finance Manager Queue"]
    
    CheckerInbox --> Decision{"Checker Evaluates"}
    Decision -- "Approve" --> AssertSoD{"Assert Checker.id != Maker.id"}
    AssertSoD -- "Passed" --> FinalCommit["Status: RECONCILED<br/>Store checker_id"]
    FinalCommit --> LogChecker["Log CHECKER_APPROVED (Dual Control)"]
    AssertSoD -- "Failed (Same User)" --> BlockSoD["403 Forbidden (Self-Approval Prohibited)"]

    Decision -- "Reject" --> Rejection["Status: REJECTED"]
    Rejection --> UnlockItems["Release Items back to UNMATCHED Pool"]
    UnlockItems --> LogReject["Log MATCH_REJECTED_BY_CHECKER"]
```

---

## 4. Cryptographic Audit Event Flow & Verification

Audit records are generated synchronously within the database transaction committing the business state change, guaranteeing that no state mutation can occur without a corresponding audit imprint.

```mermaid
sequenceDiagram
    autonumber
    actor User as Operator / Background Job
    participant App as Service Layer
    participant AuditService as Audit Logging Service
    participant DB as PostgreSQL (Append-Only)
    participant Verifier as Chain Verification Worker

    User->>App: Trigger Financial Action (e.g., Approve Match)
    App->>DB: Begin Database Transaction
    App->>DB: Execute Mutation (UPDATE matches, UPDATE transactions)
    
    App->>AuditService: record_event(actor_id, event_type, payload)
    AuditService->>DB: SELECT current_hash FROM audit_events WHERE org_id=:org_id ORDER BY sequence_id DESC LIMIT 1 FOR UPDATE
    AuditService->>AuditService: prev_hash = last_row.current_hash (or Genesis Hash if first row)
    AuditService->>AuditService: sequence_id = last_row.sequence_id + 1
    AuditService->>AuditService: canonical_payload = sort_keys_and_serialize_json(payload)
    AuditService->>AuditService: current_hash = SHA256(prev_hash + sequence_id + timestamp + actor_id + event_type + canonical_payload)
    AuditService->>DB: INSERT INTO audit_events (sequence_id, actor_id, event_type, payload, prev_hash, current_hash)
    
    App->>DB: Commit Transaction (Atomic State + Audit)

    Note over Verifier,DB: Periodic / On-Demand Verification Flow
    Verifier->>DB: Stream all audit_events for tenant ordered by sequence_id ASC
    loop For Every Event
        Verifier->>Verifier: Recalculate SHA256(...) using row data and prior row's current_hash
        Verifier->>Verifier: Assert calculated_hash == stored_current_hash
    end
    Verifier-->>User: Verification Success (Chain unbroken)
```

---

## 5. Integration Failure & Chaos Injection Data Flow

```mermaid
sequenceDiagram
    autonumber
    actor Admin as Tester / Architect
    participant ChaosAPI as Chaos Simulation Controller
    participant Interceptor as Network / Client Interceptor
    participant Target as External Adapter (Mock Bank / Mock ERP)
    participant State as System State & Database
    participant Telemetry as Simulation Telemetry Store

    Admin->>ChaosAPI: POST /api/v1/simulations/execute {scenario: "ERP_TIMEOUT", latency_ms: 30000}
    ChaosAPI->>Telemetry: Create simulation_run record (status="RUNNING")
    ChaosAPI->>Interceptor: Arm failure injection flag for sim_context_id
    
    Admin->>ChaosAPI: Trigger ERP Reconciliation Sync
    ChaosAPI->>Interceptor: Dispatch outbound sync request
    Interceptor->>Interceptor: Intercept call: Inject 30,000ms delay & trigger HTTP 504 Timeout
    
    Interceptor-->>ChaosAPI: Raise GatewayTimeoutException
    ChaosAPI->>ChaosAPI: Catch exception; invoke CircuitBreaker & Retry Strategy
    ChaosAPI->>State: Verify Invariant: Zero records marked SYNCED; Transaction rolled back
    
    ChaosAPI->>Telemetry: Log result: {status: "PASSED", invariant_intact: true, retry_scheduled: true}
    ChaosAPI-->>Admin: Return Simulation Execution Report
```
