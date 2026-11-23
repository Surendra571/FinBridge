# FinBridge — Acceptance Criteria (Given-When-Then)

**Version**: 1.0.0 (Phase 0 Baseline)  
**Standard**: Behavior-Driven Development (BDD / Gherkin)  
**Coverage**: All Functional & Non-Functional Specifications

---

## 1. Authentication & Multi-Tenancy

### Scenario AC-AUTH-01: User Registration & Email Verification
```gherkin
Feature: User Registration & Email Activation
  As a new financial user
  I want to register with my corporate email
  So that I can access my organization's workspace securely

  Scenario: Successful registration and activation
    Given an unregistered user provides email "jane@acmefinance.com", password "Str0ngP@ssw0rd!2026", and name "Jane Doe"
    When the user submits the registration form
    Then a user account is created in status "PENDING_VERIFICATION"
    And an email containing a cryptographically secure token (valid for 24 hours) is dispatched
    And when the user clicks the activation link with the valid token
    Then the user status is updated to "ACTIVE"
    And the token is invalidated to prevent replay attacks.

  Scenario: Attempt login with unverified email
    Given a user registered with status "PENDING_VERIFICATION"
    When the user attempts to log in with valid credentials
    Then the API returns HTTP 403 Forbidden with code "EMAIL_NOT_VERIFIED"
    And access to organization workspaces is blocked.
```

### Scenario AC-SEC-01: Multi-Tenant Data Leakage Prevention
```gherkin
Feature: Cross-Tenant Data Isolation
  As a compliance officer
  I must ensure Organization A can never read or mutate Organization B's financial records

  Scenario: Attempt to access foreign tenant transaction
    Given User "Alice" authenticated in Organization "Org_Alpha"
    And a bank transaction "tx_999" belonging to Organization "Org_Beta"
    When Alice requests "GET /api/v1/transactions/tx_999"
    Then the API returns HTTP 404 Not Found (or HTTP 403 Forbidden)
    And no transaction details, metadata, or counterparty names are disclosed
    And an audit event "SECURITY_UNAUTHORIZED_CROSS_TENANT_ACCESS" is logged.
```

---

## 2. Bank Statement Ingestion (CSV & PDF)

### Scenario AC-ING-01: Dynamic Bank CSV Parsing & Inverted Signs
```gherkin
Feature: Bank CSV Statement Ingestion
  As an accountant
  I want to upload statements from different banking institutions
  So that transactions are normalized uniformly regardless of column layout

  Scenario: Processing CSV with separate Debit/Credit columns
    Given an active accountant in Organization "Acme"
    And a bank CSV file with columns ["Tx Date", "Description", "Debit", "Credit", "Balance"]
    When the accountant uploads the CSV and confirms column mappings
    Then the system parses all rows into the canonical format:
      | Field          | Normalized Type/Format           |
      | date           | ISO-8601 UTC (YYYY-MM-DD)        |
      | amount         | Decimal minor units (cents)      |
      | direction      | DEBIT (outflow) / CREDIT (inflow)|
      | balance        | Decimal minor units (cents)      |
    And all negative balance representations like "(50.00)" or "-50.00" are normalized correctly
    And transactions are persisted with status "UNMATCHED".

  Scenario: Prevent duplicate statement file upload
    Given an accountant uploads a statement file "statement_oct2026.csv" with SHA-256 hash "abc12345..."
    When another accountant uploads an identical file with matching SHA-256 hash "abc12345..." to the same organization
    Then the ingestion stops before database insertion
    And the API returns HTTP 409 Conflict with message "Duplicate file detected: uploaded by user John on Oct 15"
    And no duplicate transactions are inserted into the database.
```

### Scenario AC-ING-02: Bank Statement PDF Extraction with Math Check
```gherkin
Feature: Bank Statement PDF Extraction
  As an accountant
  I want to upload digital PDF bank statements
  So that tabular rows are extracted and verified against account balances

  Scenario: Successful PDF extraction with opening/closing balance verification
    Given a valid digital PDF statement containing:
      | Metric          | Value        |
      | Opening Balance | $10,000.00   |
      | Total Credits   | +$5,000.00   |
      | Total Debits    | -$3,200.00   |
      | Closing Balance | $11,800.00   |
      | Line Items      | 42 items     |
    When the system processes the PDF via layout table extraction
    Then all 42 line items are extracted
    And the deterministic arithmetic check calculates:
      $10,000.00 + $5,000.00 - $3,200.00 = $11,800.00
    And the balance check passes
    And all 42 transactions are committed with status "UNMATCHED".

  Scenario: Corrupted or mismatched PDF arithmetic
    Given a scanned or corrupted PDF where opening balance + net sum != closing balance (discrepancy of $150.00)
    When the system processes the file
    Then the ingestion is flagged as "EXTRACTION_WARNING_BALANCE_MISMATCH"
    And the statement status is set to "REQUIRES_MANUAL_VERIFICATION"
    And no transactions are auto-reconciled until the user confirms or adjusts the parsed balances.
```

---

## 3. General Ledger CSV Ingestion

### Scenario AC-LED-01: Ledger Import & Schema Enforcement
```gherkin
Feature: Accounting Ledger Import
  As an accountant
  I want to import general ledger journal exports
  So that they can be matched against external bank statements

  Scenario: Ingest valid ledger CSV with strict schema
    Given a ledger CSV containing fields ["entry_id", "booking_date", "account_code", "amount", "currency", "memo"]
    When the user uploads the file
    Then each row is validated:
      | Rule                | Expectation                           |
      | Non-null entry_id   | Must be unique per organization       |
      | ISO Currency        | Must match org supported currencies   |
      | Zero Amount Reject  | Entries with 0.00 are rejected        |
    And all valid rows are inserted with status "UNRECONCILED"
    And an audit event "LEDGER_IMPORT_COMPLETED" is created.
```

---

## 4. Reconciliation Engine: Hybrid Tier Matching

### Scenario AC-REC-01: Tier 1 Deterministic Exact Match (Auto-Reconcile)
```gherkin
Feature: Tier 1 Exact Matching Invariant
  As a finance operations platform
  I must automatically reconcile unambiguous 1:1 matches
  Without invoking expensive or non-deterministic LLM calls

  Scenario: Perfect match on Amount, Currency, and Reference
    Given a bank transaction:
      | ID   | Date       | Amount    | Direction | Description                 |
      | B-01 | 2026-10-12 | $1,250.00 | CREDIT    | WIRE REF: INV-98421 ACME CO |
    And a ledger entry:
      | ID   | Date       | Amount    | Direction | Memo                        |
      | L-01 | 2026-10-11 | $1,250.00 | DEBIT     | INV-98421 ACME CO Settlement|
    When the Tier 1 matching rule runs
    Then the engine identifies an exact 1:1 match
    And the match status is set to "AUTO_RECONCILED"
    And both B-01 and L-01 are marked as reconciled
    And the match confidence is recorded as 1.00
    And the LLM is NOT called for this transaction pair.
```

### Scenario AC-REC-02: Tier 2 AI Match Proposal with Noisy Narrative
```gherkin
Feature: Tier 2 AI Suggestion Generation
  As an accountant
  I want the AI to suggest matches when descriptions are abbreviated or noisy
  So that I do not have to search the ledger manually

  Scenario: AI identifies counterparty semantic alias
    Given a bank transaction with noisy narrative "AMZN MKTP US*8K92 VIS" for -$84.20 on 2026-10-14
    And a ledger entry "Amazon Web Services Office Supplies" for -$84.20 on 2026-10-13
    When Tier 1 exact reference matching fails to pair them
    And Tier 2 AI Matching runs
    Then the LLM identifies the semantic link between "AMZN MKTP" and "Amazon Web Services"
    And produces a structured proposal:
      | Field                 | Value                                              |
      | bank_tx_id            | B-99                                               |
      | suggested_ledger_ids  | ["L-45"]                                           |
      | confidence_score      | 0.92                                               |
      | reasoning             | "Semantic abbreviation of Amazon Marketplace..."   |
    And the proposal status is set to "PROPOSED"
    And the transactions are NOT marked reconciled until validated.
```

### Scenario AC-REC-03: Tier 3 Deterministic Python Validation Gate
```gherkin
Feature: Tier 3 Deterministic Financial Validation Gate
  As a fintech system
  I must prevent any AI hallucination or invalid pairing from reaching financial records

  Scenario: AI proposes match where amounts differ beyond tolerance
    Given a bank transaction for $5,000.00
    And an AI proposal suggesting a ledger entry of $4,800.00 with rationale "Partial invoice match"
    And the organization tolerance rule allows a maximum fee discrepancy of $10.00
    When the proposal enters the Tier 3 Python Validation Gate
    Then the validation rule:
      abs(Bank_Amount - Ledger_Amount) <= Tolerance
      evaluates: abs(5000.00 - 4800.00) = 200.00 > 10.00
    Then the Python Validation Gate REJECTS the proposal
    And sets status to "VALIDATION_FAILED"
    And records failure reason: "Amount variance $200.00 exceeds configured tolerance $10.00"
    And the invalid proposal is prevented from auto-approval.
```

---

## 5. Human Review & Maker-Checker Dual Control

### Scenario AC-REV-01: Maker-Checker High-Value Threshold Approval
```gherkin
Feature: Maker-Checker Dual Control Enforcement
  As a risk manager
  I must ensure high-value reconciliations cannot be approved by a single person

  Scenario: Accountant attempts to self-approve a $50,000 reconciliation
    Given the organization has configured high-value threshold at $10,000.00
    And Accountant "Bob" (Maker) pairs a bank deposit of $50,000.00 with a ledger entry
    When Bob clicks "Submit & Approve"
    Then the system blocks immediate finalization
    And sets match status to "PENDING_CHECKER_APPROVAL"
    And logs audit event "MAKER_SUBMITTED_FOR_REVIEW" with maker_id="Bob".

  Scenario: Finance Manager approves Maker's submission
    Given a match proposal in status "PENDING_CHECKER_APPROVAL" submitted by "Bob"
    And Finance Manager "Sarah" (Checker, where Sarah != Bob) reviews the proposal
    When Sarah clicks "Approve Match"
    Then the match status transitions to "RECONCILED"
    And the record stores both maker_id="Bob" and checker_id="Sarah"
    And an audit event "CHECKER_APPROVED" is recorded.

  Scenario: Finance Manager attempts to approve their own proposal
    Given Finance Manager "Sarah" creates a manual match of $25,000.00 acting as Maker
    When Sarah attempts to approve the same match
    Then the system returns HTTP 403 Forbidden with error "Maker cannot approve their own submission under Dual Control policy".
```

---

## 6. Append-Only Tamper-Evident Audit Trail

### Scenario AC-AUD-01: Cryptographic Hash Chaining & Tamper Detection
```gherkin
Feature: Append-Only Tamper-Evident Audit Trail
  As an independent auditor
  I must verify that no audit records have been deleted, updated, or reordered

  Scenario: Routine cryptographic audit trail verification passes
    Given 1,000 consecutive audit log records for Organization "Acme"
    When the Auditor runs the cryptographic verification tool
    Then the system iteratively computes:
      H_n = SHA256(H_(n-1) + seq_id + timestamp + actor_id + event_type + payload_canonical_json)
    And compares H_n against stored current_hash
    And reports: "Audit chain 100% verified. Zero integrity anomalies detected."

  Scenario: Tamper detection upon unauthorized database row modification
    Given a malicious actor modifies an audit record's payload directly via SQL UPDATE
    When the cryptographic verification runs
    Then the computed hash for that row fails to match stored current_hash
    And all subsequent descendant rows fail hash chain validation
    And the verification tool reports: "CRITICAL ALERT: Audit chain broken at sequence 452"
    And an immutable security alert is dispatched.
```

---

## 7. Integration Failure Simulation (Chaos Engine)

### Scenario AC-SIM-01: Simulating Webhook Network Timeout & Retry
```gherkin
Feature: Chaos Integration Failure Simulator
  As an engineering lead
  I want to simulate external financial API failures
  To prove that FinBridge handles degraded infrastructure without data corruption

  Scenario: Simulate ERP ledger webhook network timeout
    Given the user opens the Integration Failure Simulator console
    And configures scenario "ERP Ledger Sync Timeout" (504 Gateway Timeout)
    When a reconciliation export to the ERP is triggered
    Then the simulation engine intercepts the HTTP call and injects a 35-second delay
    And the client times out gracefully
    And the transaction match status remains "RECONCILED_LOCAL_PENDING_REMOTE_SYNC"
    And the retry worker schedules backoff retry attempts (1m, 5m, 15m)
    And no duplicate ledger adjustment records are created
    And the simulation test report logs: "PASSED: Idempotent retry preserved state integrity".
```

---

## 8. Responsive UI & Accessibility

### Scenario AC-UI-01: Responsive Multi-Device Usability
```gherkin
Feature: Responsive UI Design
  As a finance user on varying devices
  I want a responsive interface that functions cleanly on desktop, tablet, and mobile

  Scenario: Viewing Discrepancy Queue on Mobile Viewport (375px width)
    Given an accountant accessing FinBridge on a mobile browser (375px screen width)
    When viewing the Discrepancy Queue
    Then the layout collapses multi-column comparison tables into vertical transaction cards
    And sticky action buttons ("Approve", "Reject", "Split") remain accessible above the fold
    And touch target sizes meet WCAG 2.1 AA minimum (>= 44x44 CSS pixels)
    And no horizontal viewport scrolling is required to view transaction amounts or status badges.
```
