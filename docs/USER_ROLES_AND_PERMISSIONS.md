# FinBridge — User Roles & Permissions Matrix

**Version**: 1.0.0 (Phase 0 Baseline)  
**Security Standard**: Least Privilege & Maker-Checker Separation of Duties (SoD)  
**Isolation Architecture**: Multi-Tenant Hard Partitioning

---

## 1. Role Definitions

FinBridge implements four primary operational roles. Every user belongs to an Organization with one of these roles. A user may belong to multiple organizations with different roles in each, but within any single active tenant session, their privileges are strictly bound to that organization's active context.

```
                  ┌───────────────────────────────┐
                  │             Admin             │
                  │   (Org & System Governance)   │
                  └───────────────┬───────────────┘
                                  │ Manages
                                  ▼
                  ┌───────────────────────────────┐
                  │        Finance Manager        │
                  │     (Checker & Super-User)    │
                  └───────────────┬───────────────┘
                                  │ Approves / Oversees
                                  ▼
                  ┌───────────────────────────────┐
                  │          Accountant           │
                  │       (Maker / Operator)      │
                  └───────────────────────────────┘
                                  ▲
                                  │ Audits (Read-Only)
                  ┌───────────────┴───────────────┐
                  │            Auditor            │
                  │   (Independent Compliance)    │
                  └───────────────────────────────┘
```

### 1.1 Admin (System & Organization Administrator)
- **Primary Goal**: Manage organization lifecycle, configure global security policies, provision team members, assign roles, and inspect technical system health.
- **Financial Authority**: Admins **cannot** approve financial matches or override reconciliation entries unless explicitly granted dual-role status. This enforces separation between technical governance and financial sign-off.

### 1.2 Finance Manager (Checker / Financial Supervisor)
- **Primary Goal**: Oversee financial operations, define reconciliation matching tolerance rules, review discrepancy queues, and act as the authorized "Checker" for high-value or disputed reconciliations.
- **Financial Authority**: Full authority to approve proposals, authorize fee adjustments, resolve exceptions, and sign off on month-end reconciliation closes.

### 1.3 Accountant (Maker / Financial Operator)
- **Primary Goal**: Day-to-day operations: ingest bank statements, import general ledger files, trigger matching runs, inspect AI-generated candidate proposals, pair split transactions, and draft reconciliation batches.
- **Financial Authority**: Can propose matches, link transactions, and resolve sub-threshold discrepancies. Cannot unilaterally approve matches exceeding the Maker-Checker monetary threshold ($10,000 or custom organization rule).

### 1.4 Auditor (Independent Compliance Officer)
- **Primary Goal**: Conduct internal or external financial audits, verify reconciliation completeness, inspect cryptographic audit trails, verify tamper-evident hash chains, and export evidence packages.
- **Financial Authority**: Strict **READ-ONLY** access across all financial data, audit logs, and reports. Zero write, upload, or approval permissions.

---

## 2. Granular Permissions & Resource Capabilities

Permissions are formatted as `resource:action` tokens:

| Permission Token | Description | Admin | Finance Manager | Accountant | Auditor |
|---|---|:---:|:---:|:---:|:---:|
| **ORGANIZATION & USERS** | | | | | |
| `org:view` | View organization details & settings | Yes | Yes | Yes | Yes |
| `org:update` | Update organization name, base currency, rules | Yes | No | No | No |
| `org:delete` | Archive or delete organization | Yes | No | No | No |
| `user:invite` | Invite new users via email | Yes | No | No | No |
| `user:modify_role`| Promote/demote user roles | Yes | No | No | No |
| `user:remove` | Revoke user membership | Yes | No | No | No |
| **DATA INGESTION** | | | | | |
| `statement:upload` | Upload Bank CSV / PDF files | Yes | Yes | Yes | No |
| `statement:view` | View raw statements & parsed line items | Yes | Yes | Yes | Yes |
| `statement:delete` | Soft-delete un-reconciled statements | Yes | Yes | No | No |
| `ledger:upload` | Upload General Ledger CSV files | Yes | Yes | Yes | No |
| `ledger:view` | View General Ledger entries & accounts | Yes | Yes | Yes | Yes |
| `ledger:delete` | Soft-delete un-reconciled ledger batches | Yes | Yes | No | No |
| **RECONCILIATION & MATCHING** | | | | | |
| `reconciliation:trigger` | Execute matching pipeline (Tier 1 & 2) | No | Yes | Yes | No |
| `match:view` | View match suggestions and discrepancies | Yes | Yes | Yes | Yes |
| `match:propose` | Link transactions & propose match (Maker) | No | Yes | Yes | No |
| `match:approve_standard` | Approve matches within standard threshold | No | Yes | Yes | No |
| `match:approve_threshold`| Approve matches > Maker-Checker threshold | No | Yes | No | No |
| `match:reject` | Reject AI or operator proposal | No | Yes | Yes | No |
| `match:manual_override` | Force match with documented variance | No | Yes | No | No |
| `reconciliation:close` | Formal close of reconciliation period | No | Yes | No | No |
| **AUDIT & COMPLIANCE** | | | | | |
| `audit:view` | View append-only audit trail | Yes | Yes | Yes | Yes |
| `audit:verify_integrity`| Trigger cryptographic SHA-256 chain verification | Yes | Yes | No | Yes |
| `audit:export` | Export compliance evidence package | Yes | Yes | Yes | Yes |
| **INTEGRATION & SIMULATION** | | | | | |
| `simulation:run` | Trigger Chaos / Integration Failure Simulation | Yes | Yes | No | No |
| `simulation:view_logs`| View simulation results & telemetry | Yes | Yes | Yes | Yes |
| `settings:tolerance` | Configure reconciliation matching tolerances | Yes | Yes | No | No |

---

## 3. Separation of Duties (SoD) & Maker-Checker Policies

To conform with fintech governance standards (SOX 404, SOC 1 / SOC 2 Type II), FinBridge enforces strict Separation of Duties at the application domain layer:

### 3.1 Maker-Checker Rule Enforcement
1. **Self-Approval Prohibition**: If User $U_A$ (Accountant or Manager acting as Maker) creates a manual match or modifies a suggested match where absolute value $|V| \ge \$10,000.00$ (configurable per org) or $|Variance| > \$0.00$, User $U_A$ **cannot** approve that match.
2. **Checker Eligibility**: Only a user with role `Finance Manager` distinct from the Maker ($U_B \neq U_A$) can sign off (`match:approve_threshold`).
3. **Audit Imprint**: Both Maker and Checker user IDs, timestamps, and IP addresses are recorded on the final `MatchRecord` entity.

### 3.2 Single-User Org Exception Policy
In development or small business environments where an organization has only 1 active user:
- The system checks: `COUNT(users WHERE org_id = :current_org AND status = 'ACTIVE') == 1`.
- If true and `ENFORCE_DUAL_CONTROL` is enabled, high-value reconciliations raise a warning dialog. The user may override only if an explicit "Emergency Solo Override" flag is checked, producing a `HIGH_SEVERITY` audit log entry flagged for subsequent audit inspection.

---

## 4. Multi-Tenant Data Isolation Rules

1. **Database-Level Row Scoping**:
   - Every financial table (`bank_statements`, `bank_transactions`, `ledger_entries`, `matches`, `audit_events`, `simulation_runs`) contains a non-nullable `organization_id` column.
   - All SQL queries must enforce `WHERE organization_id = :tenant_id`. Where supported by the DB driver (e.g. PostgreSQL), Row Level Security (RLS) policies validate `current_setting('app.current_org_id') = organization_id`.
2. **Object Storage Isolation**:
   - Ingested files (PDFs, CSVs) are stored with keys formatted as:  
     `tenants/{organization_id}/statements/{year}/{month}/{file_hash}.{ext}`
   - Pre-signed URLs for file downloads validate that the requesting user's session organization matches the path's `{organization_id}`.
3. **Audit Log Partitioning**:
   - Hash chains are calculated **per-tenant**. Organization A's audit chain is completely independent of Organization B's audit chain. This prevents cross-tenant timing attacks and allows clean data portability/export.

---

## 5. Session, Authentication & Token Policies

- **Access Token**: JWT containing `sub` (user_id), `org_id` (current tenant context), `role` (current role in this org), and `exp` (15 minutes).
- **Refresh Token**: Stored in HTTP-only, SameSite=Strict secure cookie, valid for 7 days. Implements automatic token rotation and reuse detection.
- **Context Switching**: If a user belongs to multiple organizations, switching organization requires issuing a fresh access token scoped to the target `org_id`. Cross-organization requests in a single API call are strictly rejected with `403 Forbidden`.
- **Session Revocation**: Password reset, role demotion, or admin eviction immediately blacklists active refresh tokens for that user/tenant pair.
