export interface User {
  id: string;
  email: string;
  fullName: string;
  isVerified: boolean;
  isActive: boolean;
}

export interface Organization {
  id: string;
  name: string;
  slug: string;
  baseCurrency: string;
  role: 'ADMIN' | 'FINANCE_MANAGER' | 'ACCOUNTANT' | 'AUDITOR';
}

export interface BankAccount {
  id: string;
  organization_id: string;
  account_name: string;
  institution_name: string;
  account_number_masked: string;
  account_type: string;
  currency: string;
  current_balance: string;
  is_active: boolean;
  created_at: string;
}

export interface ParsingErrorItem {
  line_number: number;
  raw_data?: Record<string, unknown>;
  error: string;
  severity: 'WARNING' | 'ERROR';
}

export interface NormalizedTransactionItem {
  source_row_number: number;
  booking_date: string;
  value_date?: string;
  normalized_description: string;
  reference_id?: string;
  direction: 'DEBIT' | 'CREDIT';
  amount: string;
  debit_amount?: string;
  credit_amount?: string;
  currency: string;
  balance_after?: string;
  raw_data: Record<string, unknown>;
  raw_description: string;
  raw_amount_string: string;
  raw_date_string: string;
}

export interface StatementUploadResponse {
  statement_id: string;
  file_name: string;
  file_type: string;
  file_hash_sha256: string;
  file_size_bytes: number;
  status: string;
  total_extracted: number;
  error_count: number;
  opening_balance?: string;
  closing_balance?: string;
  statement_start_date?: string;
  statement_end_date?: string;
  preview_transactions: NormalizedTransactionItem[];
  errors: ParsingErrorItem[];
}

export interface BankStatement {
  id: string;
  organization_id: string;
  bank_account_id: string;
  file_name: string;
  file_type: string;
  file_hash_sha256: string;
  file_size_bytes: number;
  parsed_record_count: number;
  opening_balance?: string;
  closing_balance?: string;
  statement_start_date?: string;
  statement_end_date?: string;
  status: 'PREVIEW' | 'CONFIRMED' | 'FAILED';
  parsing_errors: ParsingErrorItem[];
  created_at: string;
}

// Phase 7 Ledger Ingestion Types
export interface NormalizedLedgerItem {
  source_row_number: number;
  entry_id: string;
  posting_date: string;
  description: string;
  reference_number?: string;
  direction: 'DEBIT' | 'CREDIT';
  amount: string;
  debit_amount?: string;
  credit_amount?: string;
  currency: string;
  account_code: string;
  journal_id?: string;
  source_system: string;
  raw_data: Record<string, unknown>;
  raw_entry_id: string;
  raw_amount_string: string;
  raw_date_string: string;
  raw_description: string;
}

export interface JournalBalanceSummary {
  journal_id: string;
  total_debits: string;
  total_credits: string;
  variance: string;
  is_balanced: boolean;
  entry_count: number;
}

export interface LedgerUploadResponse {
  batch_id: string;
  file_name: string;
  file_hash_sha256: string;
  file_size_bytes: number;
  source_system: string;
  total_rows: number;
  valid_rows: number;
  error_count: number;
  status: string;
  journals: JournalBalanceSummary[];
  preview_entries: NormalizedLedgerItem[];
  errors: ParsingErrorItem[];
}

export interface LedgerBatch {
  id: string;
  organization_id: string;
  file_name: string;
  file_hash_sha256: string;
  file_size_bytes: number;
  source_system: string;
  total_rows: number;
  valid_rows: number;
  error_count: number;
  status: 'PREVIEW' | 'CONFIRMED' | 'FAILED';
  parsing_errors: ParsingErrorItem[];
  created_at: string;
}

export interface LedgerEntry {
  id: string;
  batch_id: string;
  entry_id: string;
  source_row_number: number;
  posting_date: string;
  description: string;
  reference_number?: string;
  amount: string;
  direction: 'DEBIT' | 'CREDIT';
  debit_amount?: string;
  credit_amount?: string;
  currency: string;
  account_code: string;
  journal_id?: string;
  source_system: string;
  reconciliation_status: string;
  created_at: string;
}

export interface LedgerSchemaDocItem {
  field_name: string;
  required: boolean;
  description: string;
  example: string;
  aliases: string[];
}

// Phase 8 Deterministic Reconciliation Types
export interface ReconciliationConfig {
  date_window_days: number;
  fee_tolerance: string;
  allow_fee_adjustment: boolean;
  require_reference_match: boolean;
  direction_convention: 'INVERTED_CASH' | 'DIRECT_FLOW';
  min_description_similarity: string;
}

export interface ValidationResultResponse {
  id: string;
  is_valid: boolean;
  rule_name: string;
  bank_total: string;
  ledger_total: string;
  calculated_variance: string;
  allowed_tolerance: string;
  currency_parity_passed: boolean;
  direction_parity_passed: boolean;
  amount_parity_passed: boolean;
  date_window_passed: boolean;
  unconsumed_check_passed: boolean;
  reversal_check_passed: boolean;
  failure_reason?: string;
  validated_at: string;
}

export interface MatchCandidateResponse {
  id: string;
  reconciliation_run_id: string;
  bank_transaction_id: string;
  ledger_entry_id: string;
  candidate_source: string;
  confidence_score: string;
  decision_status: 'MATCHED' | 'NEEDS_REVIEW' | 'UNMATCHED' | 'REJECTED';
  rule_name: string;
  explanation: string;
  amount_variance: string;
  date_difference_days: number;
  created_at: string;
  validation?: ValidationResultResponse;
}

export interface ReconciliationRunResponse {
  id: string;
  organization_id: string;
  run_type: string;
  total_bank_candidates: number;
  total_ledger_candidates: number;
  matched_count: number;
  needs_review_count: number;
  unmatched_count: number;
  execution_duration_ms?: number;
  status: string;
  configuration: Record<string, unknown>;
  created_at: string;
  completed_at?: string;
  candidates: MatchCandidateResponse[];
}

export interface HealthStatus {
  status: 'ok' | 'degraded' | 'error';
  app: string;
  version: string;
  environment?: string;
  dependencies?: {
    database?: {
      status: string;
      error?: string;
    };
  };
}

export interface ApiError {
  type?: string;
  title?: string;
  status: number;
  detail: string;
  code?: string;
}

// Phase 10 Human Review & Maker-Checker Types
export type ReviewCategory =
  | 'LOW_CONFIDENCE'
  | 'MULTIPLE_MATCHES'
  | 'AMOUNT_MISMATCH'
  | 'MISSING_LEDGER_ENTRY'
  | 'MISSING_BANK_TRANSACTION'
  | 'DUPLICATE_TRANSACTION'
  | 'CURRENCY_MISMATCH'
  | 'POSSIBLE_REVERSAL'
  | 'POSSIBLE_REFUND';

export type ReviewStatus =
  | 'PENDING'
  | 'IN_REVIEW'
  | 'APPROVED'
  | 'REJECTED'
  | 'UNRESOLVED'
  | 'INVESTIGATION_REQUESTED';

export type ReviewPriority = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';

export interface ReviewQueueItem {
  id: string;
  organization_id: string;
  category: ReviewCategory;
  status: ReviewStatus;
  priority: ReviewPriority;
  requires_maker_checker: boolean;
  bank_transaction_id?: string;
  bank_booking_date?: string;
  bank_amount?: string;
  bank_currency?: string;
  bank_description?: string;
  candidate_ledger_id?: string;
  ledger_amount?: string;
  ledger_description?: string;
  confidence_score?: string;
  created_at: string;
  assigned_to?: string;
}

export interface ReviewNote {
  id: string;
  author_id: string;
  note_type: string;
  content: string;
  created_at: string;
}

export interface AdjustmentProposal {
  id: string;
  maker_id: string;
  checker_id?: string;
  proposed_bank_id: string;
  proposed_ledger_id: string;
  adjustment_amount: string;
  adjustment_reason: string;
  status: 'PENDING_APPROVAL' | 'APPROVED' | 'REJECTED';
  decision_notes?: string;
  created_at: string;
  decided_at?: string;
}

export interface ReviewWorkspaceDetail {
  id: string;
  organization_id: string;
  category: ReviewCategory;
  status: ReviewStatus;
  priority: ReviewPriority;
  requires_maker_checker: boolean;
  maker_id?: string;
  checker_id?: string;
  bank_transaction?: {
    id: string;
    booking_date: string;
    amount: string;
    currency: string;
    direction: string;
    normalized_description: string;
    reference_id?: string;
    raw_amount_string?: string;
    raw_date_string?: string;
    raw_description?: string;
    raw_data?: Record<string, unknown>;
  };
  proposed_candidate?: {
    id: string;
    entry_id: string;
    posting_date: string;
    amount: string;
    currency: string;
    direction: string;
    description: string;
    account_code: string;
    reference_number?: string;
    journal_id?: string;
  };
  alternative_candidates: Array<{
    id: string;
    entry_id: string;
    posting_date: string;
    amount: string;
    currency: string;
    direction: string;
    description: string;
    account_code: string;
  }>;
  ai_explanation?: string;
  ai_confidence_score?: string;
  ai_signals: string[];
  ai_potential_concerns: string[];
  deterministic_validation?: {
    is_valid: boolean;
    rule_name: string;
    currency_parity_passed: boolean;
    direction_parity_passed: boolean;
    amount_parity_passed: boolean;
    date_window_passed: boolean;
    unconsumed_check_passed: boolean;
    reversal_check_passed: boolean;
    calculated_variance?: string;
    failure_reason?: string;
  };
  audit_history: Array<{
    id: string;
    action: string;
    actor_id?: string;
    timestamp: string;
    payload?: Record<string, unknown>;
  }>;
  notes: ReviewNote[];
  adjustment_proposals: AdjustmentProposal[];
}

// Phase 11 Audit Trail & Hash Chaining Types
export type AuditEventType =
  | 'USER_LOGIN'
  | 'USER_LOGOUT'
  | 'STATEMENT_UPLOAD'
  | 'LEDGER_IMPORT'
  | 'TRANSACTION_NORMALIZATION'
  | 'RECONCILIATION_RUN'
  | 'AI_PROPOSAL'
  | 'DETERMINISTIC_VALIDATION'
  | 'HUMAN_REVIEW'
  | 'APPROVAL'
  | 'REJECTION'
  | 'ADJUSTMENT'
  | 'INTEGRATION_REQUEST'
  | 'RETRY'
  | 'FAILURE_AND_RECOVERY';

export interface AuditEventItem {
  id: string;
  sequence_id: number;
  organization_id: string;
  actor_type: string;
  actor_id?: string;
  event_type: string;
  entity_type: string;
  entity_id?: string;
  action: string;
  resource_type: string;
  resource_id?: string;
  payload: Record<string, unknown>;
  before_state?: Record<string, unknown>;
  after_state?: Record<string, unknown>;
  correlation_id?: string;
  model_version?: string;
  prompt_version?: string;
  ip_address?: string;
  user_agent?: string;
  prev_hash: string;
  current_hash: string;
  created_at: string;
}

export interface AuditIntegrityVerificationResult {
  status: 'VERIFIED' | 'TAMPERED' | 'BROKEN_CHAIN' | 'MISSING_EVENTS';
  is_valid: boolean;
  total_events_checked: number;
  start_sequence_id: number;
  end_sequence_id: number;
  broken_at_sequence_id?: number;
  tampered_event_id?: string;
  verification_duration_ms: number;
  details: Record<string, unknown>;
  limitation_disclosure: string;
}

export interface AuditIntegrityCheckItem {
  id: string;
  organization_id: string;
  check_timestamp: string;
  start_sequence_id: number;
  end_sequence_id: number;
  total_events_checked: number;
  is_valid: boolean;
  status: string;
  broken_at_sequence_id?: number;
  tampered_event_id?: string;
  verification_duration_ms: number;
  details: Record<string, unknown>;
  performed_by?: string;
}

export interface AuditEventsList {
  items: AuditEventItem[];
  total_count: number;
  limit: number;
  offset: number;
}

// Phase 12 Reliable Integrations & Failure Simulation Types
export type IntegrationProviderType = 'CORE_BANKING' | 'ERP_LEDGER' | 'WEBHOOK_RECEIVER';

export type IntegrationFailureMode =
  | 'NONE'
  | 'RATE_LIMIT_429'
  | 'SERVER_ERROR_500'
  | 'CONNECTION_TIMEOUT'
  | 'DELAYED_RESPONSE'
  | 'DUPLICATE_WEBHOOK'
  | 'NETWORK_INTERRUPTION'
  | 'ERP_WRITE_TIMEOUT'
  | 'WORKER_CRASH';

export interface IntegrationItem {
  id: string;
  organization_id: string;
  provider_name: string;
  provider_type: IntegrationProviderType;
  base_url: string;
  is_simulated: boolean;
  is_active: boolean;
  health_status: 'HEALTHY' | 'DEGRADED' | 'UNHEALTHY';
  consecutive_failures: number;
  config: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface IntegrationRequestLog {
  id: string;
  organization_id: string;
  integration_id: string;
  idempotency_key?: string;
  correlation_id: string;
  endpoint: string;
  http_method: string;
  response_status?: number;
  latency_ms: number;
  error_category: string;
  error_message?: string;
  status: 'PENDING' | 'COMPLETED' | 'FAILED' | 'DEAD_LETTER' | 'RECOVERED_BY_QUERY';
  retry_count: number;
  recovery_notes?: string;
  created_at: string;
}

export interface RetryScheduleItem {
  attempt: number;
  backoff_delay_seconds: number;
  jitter_seconds: number;
  total_wait_seconds: number;
  status: string;
  error?: string;
}

export interface SimulateIntegrationParams {
  provider_type: IntegrationProviderType;
  failure_mode: IntegrationFailureMode;
  endpoint?: string;
  http_method?: string;
  payload?: Record<string, unknown>;
  idempotency_key?: string;
  max_retries?: number;
  base_backoff_seconds?: number;
  simulated_delay_seconds?: number;
}

export interface SimulateIntegrationResult {
  status: 'COMPLETED' | 'FAILED' | 'DEAD_LETTER' | 'RECOVERED_BY_QUERY';
  response_status?: number;
  latency_ms: number;
  attempts_made: number;
  error_category: string;
  error_message?: string;
  idempotency_key: string;
  correlation_id: string;
  response_payload?: Record<string, unknown>;
  retry_schedule: RetryScheduleItem[];
  query_before_retry_performed: boolean;
  double_write_prevented: boolean;
}

export interface SimulatedWebhookParams {
  event_id: string;
  event_type?: string;
  account_number: string;
  amount: string;
  currency?: string;
  transaction_reference?: string;
}

export interface SimulatedWebhookResult {
  status: 'PROCESSED' | 'DEDUPLICATED';
  is_duplicate: boolean;
  message: string;
  event_id: string;
  execution_time_ms: number;
}

// ============================================================================
// Phase 13: Financial Reports & Analytics Types
// ============================================================================

export interface DashboardMetrics {
  total_bank_transactions: number;
  matched_transactions: number;
  pending_review: number;
  unmatched_transactions: number;
  success_rate_percentage: number;
  reconciled_amount_by_currency: Record<string, number>;
  unreconciled_amount_by_currency: Record<string, number>;
  calculation_basis: string;
}

export interface DashboardOverviewResponse {
  organization: {
    id: string;
    name: string;
    currency: string;
    user_role: string;
  };
  kpis: DashboardMetrics;
  recent_runs: Array<{
    id: string;
    run_type: string;
    status: string;
    matched_count: number;
    created_at: string;
    duration_ms: number;
  }>;
  recent_activity: Array<{
    id: string;
    event: string;
    description: string;
    actor: string;
    timestamp: string;
    severity: string;
  }>;
  integration_health: Record<string, {
    name: string;
    status: string;
    latency_ms?: number;
    is_simulated?: boolean;
    rls_active?: boolean;
    model?: string;
  }>;
}

export interface DailyReconciliationItem {
  date: string;
  currency: string;
  total_transactions: number;
  matched_count: number;
  pending_count: number;
  unmatched_count: number;
  reconciled_amount: string | number;
  unreconciled_amount: string | number;
  reconciliation_rate: string | number;
  calculation_basis: string;
}

export interface DailyReconciliationResponse {
  items: DailyReconciliationItem[];
  total_days: number;
  currencies: string[];
  calculation_basis: string;
}

export interface MonthlyReconciliationItem {
  period: string;
  currency: string;
  total_transactions: number;
  matched_count: number;
  unmatched_count: number;
  reconciled_amount: string | number;
  unreconciled_amount: string | number;
  reconciliation_rate: string | number;
  calculation_basis: string;
}

export interface MonthlyReconciliationResponse {
  items: MonthlyReconciliationItem[];
  total_months: number;
  currencies: string[];
  calculation_basis: string;
}

export interface UnmatchedTransactionItem {
  id: string;
  source_type: 'BANK_TRANSACTION' | 'LEDGER_ENTRY';
  record_date: string;
  description: string;
  reference_id?: string;
  amount: string | number;
  currency: string;
  direction: 'DEBIT' | 'CREDIT';
  days_open: number;
  aging_bucket: '<30_DAYS' | '30-60_DAYS' | '60-90_DAYS' | '90+_DAYS';
}

export interface UnmatchedTransactionsResponse {
  items: UnmatchedTransactionItem[];
  total_unmatched_count: number;
  unmatched_amounts_by_currency: Record<string, string | number>;
  aging_summary: Record<string, number>;
  calculation_basis: string;
}

export interface BankFeeItem {
  item_id: string;
  record_date: string;
  currency: string;
  fee_or_variance_amount: string | number;
  fee_type: string;
  description: string;
  status: string;
  maker_id?: string;
  checker_id?: string;
}

export interface BankFeesReportResponse {
  items: BankFeeItem[];
  total_fee_count: number;
  total_fee_amounts_by_currency: Record<string, string | number>;
  calculation_basis: string;
}

export interface PendingApprovalItem {
  item_id: string;
  item_type: 'MANUAL_REVIEW' | 'MAKER_CHECKER_ADJUSTMENT';
  category: string;
  priority: string;
  currency: string;
  amount: string | number;
  days_pending: number;
  created_at: string;
  assigned_to?: string;
  requires_maker_checker: boolean;
}

export interface PendingApprovalsResponse {
  items: PendingApprovalItem[];
  total_pending_count: number;
  pending_amounts_by_currency: Record<string, string | number>;
  priority_breakdown: Record<string, number>;
  calculation_basis: string;
}

export interface ExceptionCategorySummary {
  category: string;
  total_count: number;
  pending_count: number;
  resolved_count: number;
  unresolved_count: number;
  amounts_by_currency: Record<string, string | number>;
  percentage_of_total: string | number;
}

export interface ExceptionSummaryResponse {
  categories: ExceptionCategorySummary[];
  total_exceptions: number;
  resolved_rate: string | number;
  calculation_basis: string;
}

export interface IntegrationFailureItem {
  provider_name: string;
  provider_type: string;
  endpoint: string;
  total_requests: number;
  success_count: number;
  failure_count: number;
  dead_letter_count: number;
  recovered_count: number;
  failure_breakdown: Record<string, number>;
  avg_latency_ms: number;
  availability_rate: string | number;
}

export interface IntegrationFailureResponse {
  items: IntegrationFailureItem[];
  total_requests: number;
  total_failures: number;
  total_dead_letters: number;
  overall_availability_rate: string | number;
  calculation_basis: string;
}

export interface AuditActivityReportResponse {
  total_events: number;
  events_by_actor_type: Record<string, number>;
  events_by_event_type: Record<string, number>;
  integrity_status: string;
  last_verified_at?: string;
  last_verified_sequence_id?: number;
  earliest_event_at?: string;
  latest_event_at?: string;
  calculation_basis: string;
}




