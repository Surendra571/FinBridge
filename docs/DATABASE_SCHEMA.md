# FinBridge — Normalized PostgreSQL Database Schema

**Version**: 1.0.0 (Phase 2 Baseline)  
**Database Engine**: PostgreSQL 16+  
**Standard**: 3NF Normalized, Multi-Tenant Partitioned, Exact Fixed-Point Financial Precision  

---

## 1. Global Database Standards

1. **Primary Keys**: Universal `UUIDv4` via `gen_random_uuid()` for all business entities. High-velocity audit events pair UUIDs with monotonically increasing `BIGINT` sequence numbers per organization.
2. **Timestamps**: `TIMESTAMPTZ` normalized to UTC. Default `CURRENT_TIMESTAMP`.
3. **Monetary Values**: `NUMERIC(15, 2)` strictly enforced. Zero floating-point representation.
4. **Currency Codes**: `CHAR(3)` conforming to ISO 4217 standard (`USD`, `EUR`, `GBP`, `CAD`, etc.).
5. **Multi-Tenancy**: Every organization-owned entity possesses a non-nullable `organization_id UUID` indexed with foreign key constraint referencing `organizations(id)`.
6. **Data Provenance**: Raw incoming data is preserved verbatim in `JSONB` alongside structured normalized columns.
7. **Deletion Policies**: 
   - Non-financial transient records (tokens, sessions) use `ON DELETE CASCADE`.
   - Core financial records (statements, transactions, ledger entries, matches, audit events) strictly enforce `ON DELETE RESTRICT` to prevent accidental loss of financial accounting evidence.

---

## 2. Authentication Domain Schemas

### 2.1 `organizations`
Stores tenant boundary metadata and base accounting currency.
```sql
CREATE TABLE organizations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(100) NOT NULL UNIQUE,
    base_currency CHAR(3) NOT NULL DEFAULT 'USD',
    settings JSONB NOT NULL DEFAULT '{}'::jsonb,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT chk_org_currency CHECK (base_currency ~ '^[A-Z]{3}$')
);

CREATE INDEX idx_organizations_slug ON organizations(slug);
```

### 2.2 `users`
Global system identity accounts.
```sql
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) NOT NULL UNIQUE,
    hashed_password VARCHAR(255) NOT NULL,
    full_name VARCHAR(255) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    is_verified BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_users_email ON users(email);
```

### 2.3 `organization_memberships`
Role-based access junction binding users to organizations.
```sql
CREATE TABLE organization_memberships (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role VARCHAR(50) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT uq_org_user UNIQUE (organization_id, user_id),
    CONSTRAINT chk_org_role CHECK (role IN ('ADMIN', 'FINANCE_MANAGER', 'ACCOUNTANT', 'AUDITOR'))
);

CREATE INDEX idx_org_memberships_user ON organization_memberships(user_id);
CREATE INDEX idx_org_memberships_org_role ON organization_memberships(organization_id, role);
```

### 2.4 `sessions`
Active refresh token families and device tracking.
```sql
CREATE TABLE sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    organization_id UUID REFERENCES organizations(id) ON DELETE CASCADE,
    refresh_token_hash CHAR(64) NOT NULL UNIQUE,
    family_id UUID NOT NULL,
    user_agent TEXT,
    ip_address INET,
    is_revoked BOOLEAN NOT NULL DEFAULT FALSE,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_sessions_user ON sessions(user_id);
CREATE INDEX idx_sessions_family ON sessions(family_id);
CREATE INDEX idx_sessions_token_hash ON sessions(refresh_token_hash);
```

### 2.5 `email_verification_tokens`
Time-bound activation tokens.
```sql
CREATE TABLE email_verification_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash CHAR(64) NOT NULL UNIQUE,
    expires_at TIMESTAMPTZ NOT NULL,
    used_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_email_verification_token ON email_verification_tokens(token_hash);
```

### 2.6 `password_reset_tokens`
Single-use password recovery tokens.
```sql
CREATE TABLE password_reset_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash CHAR(64) NOT NULL UNIQUE,
    expires_at TIMESTAMPTZ NOT NULL,
    used_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_password_reset_token ON password_reset_tokens(token_hash);
```

---

## 3. Financial Data Domain Schemas

### 3.1 `bank_accounts`
External financial institutional accounts managed by an organization.
```sql
CREATE TABLE bank_accounts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
    account_name VARCHAR(150) NOT NULL,
    institution_name VARCHAR(150) NOT NULL,
    account_number_masked VARCHAR(50) NOT NULL,
    account_type VARCHAR(50) NOT NULL DEFAULT 'CHECKING',
    currency CHAR(3) NOT NULL DEFAULT 'USD',
    current_balance NUMERIC(15, 2) NOT NULL DEFAULT 0.00,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT chk_bank_acc_currency CHECK (currency ~ '^[A-Z]{3}$'),
    CONSTRAINT chk_bank_acc_type CHECK (account_type IN ('CHECKING', 'SAVINGS', 'CREDIT_CARD', 'MONEY_MARKET'))
);

CREATE INDEX idx_bank_accounts_org ON bank_accounts(organization_id);
```

### 3.2 `bank_statements`
Pristine uploaded statement files with cryptographic deduplication.
```sql
CREATE TABLE bank_statements (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
    bank_account_id UUID NOT NULL REFERENCES bank_accounts(id) ON DELETE RESTRICT,
    file_name VARCHAR(255) NOT NULL,
    file_type VARCHAR(10) NOT NULL,
    file_hash_sha256 CHAR(64) NOT NULL,
    file_size_bytes BIGINT NOT NULL,
    storage_path VARCHAR(500) NOT NULL,
    parsed_record_count INT NOT NULL DEFAULT 0,
    opening_balance NUMERIC(15, 2),
    closing_balance NUMERIC(15, 2),
    statement_start_date DATE,
    statement_end_date DATE,
    status VARCHAR(50) NOT NULL DEFAULT 'PENDING_PROCESSING',
    parsing_errors JSONB DEFAULT '[]'::jsonb,
    uploaded_by UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT uq_statement_file_per_org UNIQUE (organization_id, file_hash_sha256),
    CONSTRAINT chk_statement_file_type CHECK (file_type IN ('CSV', 'PDF')),
    CONSTRAINT chk_statement_status CHECK (status IN ('PENDING_PROCESSING', 'PARSED', 'PARSING_FAILED', 'RECONCILED'))
);

CREATE INDEX idx_bank_statements_org ON bank_statements(organization_id);
CREATE INDEX idx_bank_statements_account ON bank_statements(bank_account_id);
```

### 3.3 `bank_transactions`
Contains both pristine raw payload strings and canonical normalized financial attributes.
```sql
CREATE TABLE bank_transactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
    bank_statement_id UUID NOT NULL REFERENCES bank_statements(id) ON DELETE RESTRICT,
    bank_account_id UUID NOT NULL REFERENCES bank_accounts(id) ON DELETE RESTRICT,
    source_row_number INT NOT NULL,
    
    -- RAW IMMUTABLE IMPORT DATA
    raw_data JSONB NOT NULL,
    raw_description TEXT NOT NULL,
    raw_amount_string VARCHAR(100) NOT NULL,
    raw_date_string VARCHAR(100) NOT NULL,

    -- NORMALIZED FINANCIAL DATA
    booking_date DATE NOT NULL,
    value_date DATE,
    amount NUMERIC(15, 2) NOT NULL,
    direction VARCHAR(10) NOT NULL,
    currency CHAR(3) NOT NULL DEFAULT 'USD',
    normalized_description TEXT NOT NULL,
    reference_id VARCHAR(150),
    balance_after NUMERIC(15, 2),
    
    -- RECONCILIATION STATE
    reconciliation_status VARCHAR(30) NOT NULL DEFAULT 'UNMATCHED',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT chk_bank_tx_amount_positive CHECK (amount > 0.00),
    CONSTRAINT chk_bank_tx_direction CHECK (direction IN ('DEBIT', 'CREDIT')),
    CONSTRAINT chk_bank_tx_currency CHECK (currency ~ '^[A-Z]{3}$'),
    CONSTRAINT chk_bank_tx_status CHECK (reconciliation_status IN ('UNMATCHED', 'PROPOSED', 'RECONCILED', 'EXCLUDED')),
    CONSTRAINT uq_bank_tx_source_row UNIQUE (bank_statement_id, source_row_number)
);

CREATE INDEX idx_bank_tx_org_status ON bank_transactions(organization_id, reconciliation_status);
CREATE INDEX idx_bank_tx_amount_date ON bank_transactions(organization_id, amount, booking_date);
CREATE INDEX idx_bank_tx_reference ON bank_transactions(organization_id, reference_id);
```

### 3.4 `ledger_entries`
Internal general ledger journals and receipts imported for reconciliation.
```sql
CREATE TABLE ledger_entries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
    batch_identifier VARCHAR(100) NOT NULL,
    source_row_number INT NOT NULL,
    
    -- RAW IMMUTABLE IMPORT DATA
    raw_data JSONB NOT NULL,
    raw_entry_id VARCHAR(150) NOT NULL,
    
    -- NORMALIZED ACCOUNTING DATA
    account_code VARCHAR(100) NOT NULL,
    account_name VARCHAR(255),
    entry_date DATE NOT NULL,
    amount NUMERIC(15, 2) NOT NULL,
    direction VARCHAR(10) NOT NULL,
    currency CHAR(3) NOT NULL DEFAULT 'USD',
    memo TEXT NOT NULL,
    reference_number VARCHAR(150),
    
    -- RECONCILIATION STATE
    reconciliation_status VARCHAR(30) NOT NULL DEFAULT 'UNRECONCILED',
    uploaded_by UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT chk_ledger_amount_positive CHECK (amount > 0.00),
    CONSTRAINT chk_ledger_direction CHECK (direction IN ('DEBIT', 'CREDIT')),
    CONSTRAINT chk_ledger_currency CHECK (currency ~ '^[A-Z]{3}$'),
    CONSTRAINT chk_ledger_status CHECK (reconciliation_status IN ('UNRECONCILED', 'PROPOSED', 'RECONCILED', 'EXCLUDED')),
    CONSTRAINT uq_ledger_entry_source UNIQUE (organization_id, batch_identifier, raw_entry_id)
);

CREATE INDEX idx_ledger_org_status ON ledger_entries(organization_id, reconciliation_status);
CREATE INDEX idx_ledger_amount_date ON ledger_entries(organization_id, amount, entry_date);
CREATE INDEX idx_ledger_reference ON ledger_entries(organization_id, reference_number);
```

---

## 4. Reconciliation Domain Schemas

### 4.1 `reconciliation_runs`
Tracks automated matching execution cycles.
```sql
CREATE TABLE reconciliation_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
    triggered_by UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    run_type VARCHAR(50) NOT NULL DEFAULT 'FULL_HYBRID',
    total_bank_candidates INT NOT NULL DEFAULT 0,
    total_ledger_candidates INT NOT NULL DEFAULT 0,
    tier1_auto_reconciled_count INT NOT NULL DEFAULT 0,
    tier2_ai_proposals_count INT NOT NULL DEFAULT 0,
    tier3_failed_gate_count INT NOT NULL DEFAULT 0,
    execution_duration_ms BIGINT,
    status VARCHAR(50) NOT NULL DEFAULT 'IN_PROGRESS',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMPTZ,

    CONSTRAINT chk_rec_run_status CHECK (status IN ('IN_PROGRESS', 'COMPLETED', 'FAILED', 'CANCELLED'))
);

CREATE INDEX idx_rec_runs_org ON reconciliation_runs(organization_id);
```

### 4.2 `match_candidates`
Hypothetical pairings produced by deterministic algorithms or LangGraph AI models.
```sql
CREATE TABLE match_candidates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
    reconciliation_run_id UUID NOT NULL REFERENCES reconciliation_runs(id) ON DELETE RESTRICT,
    candidate_source VARCHAR(50) NOT NULL,
    confidence_score NUMERIC(5, 4) NOT NULL,
    suggested_match_type VARCHAR(30) NOT NULL DEFAULT 'ONE_TO_ONE',
    ai_reasoning TEXT,
    identified_variance NUMERIC(15, 2) NOT NULL DEFAULT 0.00,
    variance_category VARCHAR(50),
    status VARCHAR(50) NOT NULL DEFAULT 'PENDING_VALIDATION',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT chk_candidate_confidence CHECK (confidence_score >= 0.0000 AND confidence_score <= 1.0000),
    CONSTRAINT chk_candidate_source CHECK (candidate_source IN ('DETERMINISTIC_TIER1', 'AI_LANGGRAPH_TIER2', 'MANUAL_HEURISTIC')),
    CONSTRAINT chk_candidate_status CHECK (status IN ('PENDING_VALIDATION', 'VALIDATED', 'FAILED_GATE', 'CONSUMED', 'DISCARDED'))
);

CREATE INDEX idx_match_candidates_org ON match_candidates(organization_id, status);
```

### 4.3 `reconciliation_matches`
Permanent, confirmed reconciliation bindings between bank transactions and ledger entries.
```sql
CREATE TABLE reconciliation_matches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
    match_candidate_id UUID REFERENCES match_candidates(id) ON DELETE RESTRICT,
    match_type VARCHAR(30) NOT NULL DEFAULT 'ONE_TO_ONE',
    total_bank_amount NUMERIC(15, 2) NOT NULL,
    total_ledger_amount NUMERIC(15, 2) NOT NULL,
    variance_amount NUMERIC(15, 2) NOT NULL DEFAULT 0.00,
    status VARCHAR(50) NOT NULL,
    reconciled_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT chk_match_type CHECK (match_type IN ('ONE_TO_ONE', 'ONE_TO_MANY', 'MANY_TO_ONE', 'MANY_TO_MANY')),
    CONSTRAINT chk_match_status CHECK (status IN ('AUTO_RECONCILED', 'PENDING_APPROVAL', 'RECONCILED', 'REJECTED'))
);

CREATE INDEX idx_rec_matches_org ON reconciliation_matches(organization_id, status);
```

#### Junction Tables Linking Transactions to Matches:
```sql
CREATE TABLE match_bank_transactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
    match_id UUID NOT NULL REFERENCES reconciliation_matches(id) ON DELETE RESTRICT,
    bank_transaction_id UUID NOT NULL REFERENCES bank_transactions(id) ON DELETE RESTRICT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT uq_bank_tx_single_match UNIQUE (bank_transaction_id)
);

CREATE TABLE match_ledger_entries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
    match_id UUID NOT NULL REFERENCES reconciliation_matches(id) ON DELETE RESTRICT,
    ledger_entry_id UUID NOT NULL REFERENCES ledger_entries(id) ON DELETE RESTRICT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT uq_ledger_single_match UNIQUE (ledger_entry_id)
);

CREATE INDEX idx_match_bank_tx_match ON match_bank_transactions(match_id);
CREATE INDEX idx_match_ledger_entry_match ON match_ledger_entries(match_id);
```

### 4.4 `validation_results`
Deterministic Python validation gate execution results evaluating match candidates.
```sql
CREATE TABLE validation_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
    match_candidate_id UUID NOT NULL REFERENCES match_candidates(id) ON DELETE RESTRICT,
    is_valid BOOLEAN NOT NULL,
    rule_name VARCHAR(100) NOT NULL,
    bank_total NUMERIC(15, 2) NOT NULL,
    ledger_total NUMERIC(15, 2) NOT NULL,
    calculated_variance NUMERIC(15, 2) NOT NULL,
    allowed_tolerance NUMERIC(15, 2) NOT NULL DEFAULT 0.00,
    currency_parity_passed BOOLEAN NOT NULL,
    direction_parity_passed BOOLEAN NOT NULL,
    unconsumed_check_passed BOOLEAN NOT NULL,
    failure_reason TEXT,
    validated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_validation_results_candidate ON validation_results(match_candidate_id);
```

### 4.5 `manual_reviews`
Maker-Checker review and approval workflow records.
```sql
CREATE TABLE manual_reviews (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
    reconciliation_match_id UUID NOT NULL REFERENCES reconciliation_matches(id) ON DELETE RESTRICT,
    maker_id UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    checker_id UUID REFERENCES users(id) ON DELETE RESTRICT,
    maker_notes TEXT,
    checker_notes TEXT,
    review_status VARCHAR(50) NOT NULL DEFAULT 'PENDING_CHECKER',
    threshold_amount NUMERIC(15, 2) NOT NULL DEFAULT 10000.00,
    submitted_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMPTZ,

    CONSTRAINT chk_review_status CHECK (review_status IN ('PENDING_CHECKER', 'APPROVED', 'REJECTED')),
    CONSTRAINT chk_maker_checker_sod CHECK (checker_id IS NULL OR maker_id <> checker_id)
);

CREATE INDEX idx_manual_reviews_org ON manual_reviews(organization_id, review_status);
CREATE INDEX idx_manual_reviews_match ON manual_reviews(reconciliation_match_id);
```

---

## 5. Audit Domain Schemas

### 5.1 `audit_events`
Cryptographically chained, tamper-evident append-only journal.
```sql
CREATE TABLE audit_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sequence_id BIGINT NOT NULL,
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
    actor_id UUID REFERENCES users(id) ON DELETE RESTRICT,
    event_type VARCHAR(100) NOT NULL,
    resource_type VARCHAR(100) NOT NULL,
    resource_id UUID NOT NULL,
    action VARCHAR(50) NOT NULL,
    payload_before JSONB,
    payload_after JSONB,
    ip_address INET,
    user_agent TEXT,
    prev_hash CHAR(64) NOT NULL,
    current_hash CHAR(64) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT uq_audit_seq_per_org UNIQUE (organization_id, sequence_id),
    CONSTRAINT chk_prev_hash_length CHECK (length(prev_hash) = 64),
    CONSTRAINT chk_curr_hash_length CHECK (length(current_hash) = 64)
);

CREATE INDEX idx_audit_events_org_seq ON audit_events(organization_id, sequence_id ASC);
CREATE INDEX idx_audit_events_resource ON audit_events(organization_id, resource_type, resource_id);
```

### 5.2 `audit_integrity_checks`
Tracks periodic verification scans proving the cryptographic continuity of the audit chain.
```sql
CREATE TABLE audit_integrity_checks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
    check_timestamp TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    start_sequence_id BIGINT NOT NULL,
    end_sequence_id BIGINT NOT NULL,
    total_events_checked BIGINT NOT NULL,
    is_valid BOOLEAN NOT NULL,
    broken_at_sequence_id BIGINT,
    verification_duration_ms BIGINT NOT NULL,
    performed_by UUID REFERENCES users(id) ON DELETE RESTRICT
);

CREATE INDEX idx_audit_integrity_org ON audit_integrity_checks(organization_id, check_timestamp DESC);
```

---

## 6. Integrations & Reliability Domain Schemas

### 6.1 `integrations`
Configures external providers (mock banking endpoints, ERP systems).
```sql
CREATE TABLE integrations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
    provider_name VARCHAR(100) NOT NULL,
    provider_type VARCHAR(50) NOT NULL,
    base_url VARCHAR(255) NOT NULL,
    is_simulated BOOLEAN NOT NULL DEFAULT TRUE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    config JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT chk_integration_type CHECK (provider_type IN ('CORE_BANKING', 'ERP_LEDGER', 'WEBHOOK_RECEIVER'))
);

CREATE INDEX idx_integrations_org ON integrations(organization_id);
```

### 6.2 `integration_requests`
Telemetry log of outbound requests dispatched to integration endpoints.
```sql
CREATE TABLE integration_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
    integration_id UUID NOT NULL REFERENCES integrations(id) ON DELETE RESTRICT,
    idempotency_key VARCHAR(255),
    endpoint VARCHAR(255) NOT NULL,
    http_method VARCHAR(10) NOT NULL,
    request_headers JSONB,
    request_payload JSONB,
    response_status INT,
    response_payload JSONB,
    latency_ms INT,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_integration_requests_org ON integration_requests(organization_id, created_at DESC);
```

### 6.3 `idempotency_records`
Prevents double-execution of API mutations and webhooks.
```sql
CREATE TABLE idempotency_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
    idempotency_key VARCHAR(255) NOT NULL,
    endpoint VARCHAR(255) NOT NULL,
    request_hash CHAR(64) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'IN_FLIGHT',
    response_code INT,
    response_body JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMPTZ NOT NULL,

    CONSTRAINT uq_idempotency_per_org UNIQUE (organization_id, idempotency_key),
    CONSTRAINT chk_idempotency_status CHECK (status IN ('IN_FLIGHT', 'COMPLETED', 'FAILED'))
);

CREATE INDEX idx_idempotency_org_key ON idempotency_records(organization_id, idempotency_key);
CREATE INDEX idx_idempotency_expiry ON idempotency_records(expires_at);
```

### 6.4 `retry_attempts`
Manages exponential backoff retries for failed integration tasks.
```sql
CREATE TABLE retry_attempts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
    integration_request_id UUID NOT NULL REFERENCES integration_requests(id) ON DELETE RESTRICT,
    attempt_number INT NOT NULL,
    max_attempts INT NOT NULL DEFAULT 3,
    backoff_delay_seconds INT NOT NULL,
    next_retry_at TIMESTAMPTZ NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'PENDING',
    last_error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT chk_retry_status CHECK (status IN ('PENDING', 'SUCCEEDED', 'EXHAUSTED', 'CANCELLED'))
);

CREATE INDEX idx_retry_attempts_pending ON retry_attempts(next_retry_at) WHERE status = 'PENDING';
```
