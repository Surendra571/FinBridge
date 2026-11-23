# FinBridge — Entity-Relationship (ER) Architecture

**Version**: 1.0.0 (Phase 2 Baseline)  
**Specification**: Relational Model, Foreign Key Architecture & Multi-Tenant Partitioning

---

## 1. Complete Entity-Relationship (ER) Diagram

```mermaid
erDiagram
    %% AUTHENTICATION & MULTI-TENANCY DOMAIN
    organizations ||--o{ organization_memberships : has
    organizations ||--o{ bank_accounts : owns
    organizations ||--o{ bank_statements : receives
    organizations ||--o{ bank_transactions : contains
    organizations ||--o{ ledger_entries : records
    organizations ||--o{ reconciliation_runs : executes
    organizations ||--o{ reconciliation_matches : binds
    organizations ||--o{ audit_events : logs
    organizations ||--o{ audit_integrity_checks : verifies
    organizations ||--o{ integrations : configures
    organizations ||--o{ idempotency_records : guards

    users ||--o{ organization_memberships : holds
    users ||--o{ sessions : authenticates
    users ||--o{ email_verification_tokens : validates
    users ||--o{ password_reset_tokens : recovers
    users ||--o{ bank_statements : uploads
    users ||--o{ ledger_entries : submits
    users ||--o{ reconciliation_runs : triggers
    users ||--o{ manual_reviews : makes_or_checks
    users ||--o{ audit_events : acts_in

    %% FINANCIAL DATA DOMAIN
    bank_accounts ||--o{ bank_statements : associates
    bank_accounts ||--o{ bank_transactions : holds
    bank_statements ||--o{ bank_transactions : extracts_to

    %% RECONCILIATION DOMAIN
    reconciliation_runs ||--o{ match_candidates : produces
    match_candidates ||--o{ validation_results : evaluates_with
    match_candidates ||--o| reconciliation_matches : materializes_as

    reconciliation_matches ||--o{ match_bank_transactions : binds_bank
    reconciliation_matches ||--o{ match_ledger_entries : binds_ledger
    reconciliation_matches ||--o| manual_reviews : requires_review

    bank_transactions ||--o| match_bank_transactions : links_to_match
    ledger_entries ||--o| match_ledger_entries : links_to_match

    %% INTEGRATION & RELIABILITY DOMAIN
    integrations ||--o{ integration_requests : issues
    integration_requests ||--o{ retry_attempts : retries

    %% ENTITY ATTRIBUTES DEFINITION
    organizations {
        uuid id PK
        varchar name
        varchar slug UK
        char base_currency
        jsonb settings
        boolean is_active
        timestamptz created_at
    }

    users {
        uuid id PK
        varchar email UK
        varchar hashed_password
        varchar full_name
        boolean is_verified
        boolean is_active
        timestamptz created_at
    }

    organization_memberships {
        uuid id PK
        uuid organization_id FK
        uuid user_id FK
        varchar role
        boolean is_active
    }

    bank_statements {
        uuid id PK
        uuid organization_id FK
        uuid bank_account_id FK
        varchar file_name
        varchar file_type
        char file_hash_sha256 UK
        bigint file_size_bytes
        varchar storage_path
        int parsed_record_count
        numeric opening_balance
        numeric closing_balance
        varchar status
        uuid uploaded_by FK
    }

    bank_transactions {
        uuid id PK
        uuid organization_id FK
        uuid bank_statement_id FK
        uuid bank_account_id FK
        int source_row_number
        jsonb raw_data
        text raw_description
        date booking_date
        date value_date
        numeric amount
        varchar direction
        char currency
        text normalized_description
        varchar reference_id
        varchar reconciliation_status
    }

    ledger_entries {
        uuid id PK
        uuid organization_id FK
        varchar batch_identifier
        int source_row_number
        jsonb raw_data
        varchar raw_entry_id
        varchar account_code
        date entry_date
        numeric amount
        varchar direction
        char currency
        text memo
        varchar reference_number
        varchar reconciliation_status
        uuid uploaded_by FK
    }

    reconciliation_runs {
        uuid id PK
        uuid organization_id FK
        uuid triggered_by FK
        varchar run_type
        int total_bank_candidates
        int total_ledger_candidates
        int tier1_auto_reconciled_count
        int tier2_ai_proposals_count
        varchar status
        timestamptz completed_at
    }

    match_candidates {
        uuid id PK
        uuid organization_id FK
        uuid reconciliation_run_id FK
        varchar candidate_source
        numeric confidence_score
        varchar suggested_match_type
        text ai_reasoning
        numeric identified_variance
        varchar status
    }

    reconciliation_matches {
        uuid id PK
        uuid organization_id FK
        uuid match_candidate_id FK
        varchar match_type
        numeric total_bank_amount
        numeric total_ledger_amount
        numeric variance_amount
        varchar status
        timestamptz reconciled_at
    }

    match_bank_transactions {
        uuid id PK
        uuid organization_id FK
        uuid match_id FK
        uuid bank_transaction_id FK,UK
    }

    match_ledger_entries {
        uuid id PK
        uuid organization_id FK
        uuid match_id FK
        uuid ledger_entry_id FK,UK
    }

    validation_results {
        uuid id PK
        uuid organization_id FK
        uuid match_candidate_id FK
        boolean is_valid
        varchar rule_name
        numeric bank_total
        numeric ledger_total
        numeric calculated_variance
        boolean currency_parity_passed
        boolean direction_parity_passed
        boolean unconsumed_check_passed
        text failure_reason
    }

    manual_reviews {
        uuid id PK
        uuid organization_id FK
        uuid reconciliation_match_id FK
        uuid maker_id FK
        uuid checker_id FK
        text maker_notes
        text checker_notes
        varchar review_status
        numeric threshold_amount
        timestamptz submitted_at
        timestamptz resolved_at
    }

    audit_events {
        uuid id PK
        bigint sequence_id UK
        uuid organization_id FK
        uuid actor_id FK
        varchar event_type
        varchar resource_type
        uuid resource_id
        varchar action
        jsonb payload_before
        jsonb payload_after
        char prev_hash
        char current_hash
        timestamptz created_at
    }

    idempotency_records {
        uuid id PK
        uuid organization_id FK
        varchar idempotency_key UK
        varchar endpoint
        char request_hash
        varchar status
        int response_code
        jsonb response_body
        timestamptz expires_at
    }
```

---

## 2. Relational Domain Boundaries

### 2.1 The Multi-Tenant Anchor
Every business table contains a non-nullable `organization_id` referencing `organizations(id)`:
- Guarantees logical partitioning at the database engine level.
- Serves as the partition key for Row-Level Security (RLS) policies.
- Prevents cross-organization data leakage even if an application SQL query misses an explicit filter.

### 2.2 Financial Provenance Junction
The relationship between `bank_statements` and `bank_transactions` reflects strict provenance:
- When a statement is uploaded, `bank_statements` records the file's SHA-256 hash.
- Individual transaction lines are extracted into `bank_transactions`.
- Both raw payload strings (`raw_data`, `raw_description`, `raw_amount_string`) and normalized canonical values (`amount`, `direction`, `booking_date`) reside on the record, preserving source fidelity.

### 2.3 The Reconciliation Binding Junction
To prevent a bank transaction or ledger entry from ever participating in two active reconciliations simultaneously:
- `match_bank_transactions` enforces `UNIQUE (bank_transaction_id)`.
- `match_ledger_entries` enforces `UNIQUE (ledger_entry_id)`.
- Reconciling a transaction locks that entity's foreign key in these junction tables, ensuring mathematical uniqueness across 1:1, 1:Many, and Many:1 matches.
