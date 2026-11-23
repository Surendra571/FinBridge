/**
 * Typed API Client for FinBridge Backend with error handling and tenant scoping.
 */
import {
  HealthStatus,
  User,
  Organization,
  BankAccount,
  BankStatement,
  StatementUploadResponse,
  ReconciliationConfig,
  ReconciliationRunResponse,
  ReviewQueueItem,
  ReviewWorkspaceDetail,
  ReviewNote,
  AdjustmentProposal,
  AuditEventItem,
  AuditEventsList,
  AuditIntegrityVerificationResult,
  AuditIntegrityCheckItem,
  IntegrationItem,
  IntegrationRequestLog,
  SimulateIntegrationParams,
  SimulateIntegrationResult,
  SimulatedWebhookParams,
  SimulatedWebhookResult,
  DashboardOverviewResponse,
  DailyReconciliationResponse,
  MonthlyReconciliationResponse,
  UnmatchedTransactionsResponse,
  BankFeesReportResponse,
  PendingApprovalsResponse,
  ExceptionSummaryResponse,
  IntegrationFailureResponse,
  AuditActivityReportResponse,
} from '../types';

const BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api/v1';

class ApiClient {
  private baseUrl: string;
  private activeOrgId: string | null = null;
  private token: string | null = null;

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl.replace(/\/+$/, '');
    this.token = localStorage.getItem('finbridge_token');
    this.activeOrgId = localStorage.getItem('finbridge_org_id');
  }

  setToken(token: string | null) {
    this.token = token;
    if (token) {
      localStorage.setItem('finbridge_token', token);
    } else {
      localStorage.removeItem('finbridge_token');
    }
  }

  setActiveOrg(orgId: string | null) {
    this.activeOrgId = orgId;
    if (orgId) {
      localStorage.setItem('finbridge_org_id', orgId);
    } else {
      localStorage.removeItem('finbridge_org_id');
    }
  }

  getActiveOrg(): string | null {
    return this.activeOrgId;
  }

  private async request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
    const url = `${this.baseUrl}${endpoint.startsWith('/') ? '' : '/'}${endpoint}`;
    const headers = new Headers(options.headers || {});

    if (!headers.has('Content-Type') && !(options.body instanceof FormData)) {
      headers.set('Content-Type', 'application/json');
    }

    if (this.token && !headers.has('Authorization')) {
      headers.set('Authorization', `Bearer ${this.token}`);
    }

    if (this.activeOrgId && !headers.has('X-Organization-Id')) {
      headers.set('X-Organization-Id', this.activeOrgId);
    }

    const response = await fetch(url, {
      ...options,
      headers,
    });

    if (!response.ok) {
      if (response.status === 401) {
        this.setToken(null);
        this.setActiveOrg(null);
        if (
          typeof window !== 'undefined' &&
          !window.location.pathname.startsWith('/login') &&
          !window.location.pathname.startsWith('/register') &&
          !window.location.pathname.startsWith('/verify-email') &&
          !window.location.pathname.startsWith('/forgot-password')
        ) {
          window.location.href = '/login';
        }
      }
      let errorDetail = `HTTP ${response.status} ${response.statusText}`;
      try {
        const errorJson = await response.json();
        errorDetail = errorJson.detail || errorJson.title || errorDetail;
      } catch {
        // Fallback to text status
      }
      throw new Error(errorDetail);
    }

    return response.json() as Promise<T>;
  }

  // Health
  async getHealthLive(): Promise<HealthStatus> {
    return this.request<HealthStatus>('/health/live');
  }

  async getHealthReady(): Promise<HealthStatus> {
    return this.request<HealthStatus>('/health/ready');
  }

  // Auth
  async login(credentials: { email: string; password: string } | FormData): Promise<{ access_token: string; token_type: string }> {
    let body: string;
    if (credentials instanceof FormData) {
      body = JSON.stringify({
        email: credentials.get('email') || credentials.get('username'),
        password: credentials.get('password'),
      });
    } else {
      body = JSON.stringify(credentials);
    }
    const res = await this.request<{ access_token: string; token_type: string }>('/auth/login', {
      method: 'POST',
      body,
    });
    this.setToken(res.access_token);
    return res;
  }

  async register(data: { email: string; password: string; full_name: string }): Promise<User & { otp?: string }> {
    return this.request<User & { otp?: string }>('/auth/register', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async verifyOtp(email: string, otp: string): Promise<{ access_token: string; token_type: string; user: User }> {
    const res = await this.request<{ access_token: string; token_type: string; user: User }>('/auth/verify-otp', {
      method: 'POST',
      body: JSON.stringify({ email, otp }),
    });
    this.setToken(res.access_token);
    return res;
  }

  async resendOtp(email: string): Promise<{ status: string; message: string }> {
    return this.request<{ status: string; message: string }>('/auth/resend-otp', {
      method: 'POST',
      body: JSON.stringify({ email }),
    });
  }

  async verifyEmail(token: string): Promise<{ message: string }> {
    return this.request<{ message: string }>('/auth/verify-email', {
      method: 'POST',
      body: JSON.stringify({ token }),
    });
  }

  async forgotPassword(email: string): Promise<{ message: string }> {
    return this.request<{ message: string }>('/auth/forgot-password', {
      method: 'POST',
      body: JSON.stringify({ email }),
    });
  }

  async getCurrentUser(): Promise<User> {
    return this.request<User>('/auth/me');
  }

  async logout(): Promise<{ message: string }> {
    try {
      const res = await this.request<{ message: string }>('/auth/logout', { method: 'POST' });
      this.setToken(null);
      this.setActiveOrg(null);
      return res;
    } catch {
      this.setToken(null);
      this.setActiveOrg(null);
      return { message: "Logged out" };
    }
  }

  // Organizations
  async getOrganizations(): Promise<Organization[]> {
    return this.request<Organization[]>('/organizations');
  }

  async createOrganization(data: { name: string; slug: string; base_currency: string }): Promise<Organization> {
    return this.request<Organization>('/organizations', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  // Bank Accounts
  async getBankAccounts(): Promise<BankAccount[]> {
    return this.request<BankAccount[]>('/bank-accounts');
  }

  async createBankAccount(data: {
    account_name: string;
    institution_name: string;
    account_number_masked: string;
    account_type: string;
    currency: string;
    initial_balance?: number;
  }): Promise<BankAccount> {
    return this.request<BankAccount>('/bank-accounts', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  // Bank Statements
  async uploadStatement(bankAccountId: string, file: File): Promise<StatementUploadResponse> {
    const formData = new FormData();
    formData.append('bank_account_id', bankAccountId);
    formData.append('file', file);

    return this.request<StatementUploadResponse>('/statements/upload', {
      method: 'POST',
      body: formData,
    });
  }

  async confirmStatement(statementId: string): Promise<BankStatement> {
    return this.request<BankStatement>(`/statements/${statementId}/confirm`, {
      method: 'POST',
    });
  }

  async getStatements(bankAccountId?: string): Promise<BankStatement[]> {
    const query = bankAccountId ? `?bank_account_id=${bankAccountId}` : '';
    return this.request<BankStatement[]>(`/statements${query}`);
  }

  async getStatement(statementId: string): Promise<BankStatement> {
    return this.request<BankStatement>(`/statements/${statementId}`);
  }

  // General Ledger
  async getLedgerSchema(): Promise<any[]> {
    return this.request<any[]>('/ledger/schema');
  }

  async uploadLedgerCsv(file: File, sourceSystem: string = 'ERP'): Promise<any> {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('source_system', sourceSystem);

    return this.request<any>('/ledger/upload', {
      method: 'POST',
      body: formData,
    });
  }

  async confirmLedgerBatch(batchId: string): Promise<any> {
    return this.request<any>(`/ledger/${batchId}/confirm`, {
      method: 'POST',
    });
  }

  async getLedgerBatches(): Promise<any[]> {
    return this.request<any[]>('/ledger/batches');
  }

  async getLedgerBatch(batchId: string): Promise<any> {
    return this.request<any>(`/ledger/batches/${batchId}`);
  }

  async getLedgerEntries(params?: {
    batch_id?: string;
    account_code?: string;
    journal_id?: string;
  }): Promise<any[]> {
    const query = new URLSearchParams();
    if (params?.batch_id) query.set('batch_id', params.batch_id);
    if (params?.account_code) query.set('account_code', params.account_code);
    if (params?.journal_id) query.set('journal_id', params.journal_id);
    const queryString = query.toString() ? `?${query.toString()}` : '';
    return this.request<any[]>(`/ledger/entries${queryString}`);
  }

  // Reconciliation
  async runReconciliation(data: {
    config?: Partial<ReconciliationConfig>;
    bank_account_id?: string;
    start_date?: string;
    end_date?: string;
  } = {}): Promise<ReconciliationRunResponse> {
    return this.request<ReconciliationRunResponse>('/reconciliation/run', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async getReconciliationRuns(limit: number = 20): Promise<ReconciliationRunResponse[]> {
    return this.request<ReconciliationRunResponse[]>(`/reconciliation/runs?limit=${limit}`);
  }

  async getReconciliationRun(runId: string): Promise<ReconciliationRunResponse> {
    return this.request<ReconciliationRunResponse>(`/reconciliation/runs/${runId}`);
  }

  // Phase 10 Human Review & Maker-Checker Endpoints
  async getReviewQueue(params?: {
    category?: string;
    status?: string;
    priority?: string;
  }): Promise<ReviewQueueItem[]> {
    const query = new URLSearchParams();
    if (params?.category) query.set('category', params.category);
    if (params?.status) query.set('status', params.status);
    if (params?.priority) query.set('priority', params.priority);
    const queryString = query.toString() ? `?${query.toString()}` : '';
    return this.request<ReviewQueueItem[]>(`/reviews/queue${queryString}`);
  }

  async getReviewWorkspace(reviewId: string): Promise<ReviewWorkspaceDetail> {
    return this.request<ReviewWorkspaceDetail>(`/reviews/${reviewId}/workspace`);
  }

  async approveReviewMatch(
    reviewId: string,
    data: { review_notes?: string } = {}
  ): Promise<{ status: string; message: string; review_id: string }> {
    return this.request<{ status: string; message: string; review_id: string }>(
      `/reviews/${reviewId}/approve`,
      {
        method: 'POST',
        body: JSON.stringify(data),
      }
    );
  }

  async rejectReviewMatch(
    reviewId: string,
    data: { reason: string }
  ): Promise<{ status: string; message: string; review_id: string }> {
    return this.request<{ status: string; message: string; review_id: string }>(
      `/reviews/${reviewId}/reject`,
      {
        method: 'POST',
        body: JSON.stringify(data),
      }
    );
  }

  async markReviewUnresolved(
    reviewId: string,
    data: { reason: string }
  ): Promise<{ status: string; message: string; review_id: string }> {
    return this.request<{ status: string; message: string; review_id: string }>(
      `/reviews/${reviewId}/unresolved`,
      {
        method: 'POST',
        body: JSON.stringify(data),
      }
    );
  }

  async remapReviewCandidate(
    reviewId: string,
    data: { ledger_entry_id: string; reason: string }
  ): Promise<{ status: string; message: string; review_id: string; candidate_id: string }> {
    return this.request<{ status: string; message: string; review_id: string; candidate_id: string }>(
      `/reviews/${reviewId}/remap`,
      {
        method: 'POST',
        body: JSON.stringify(data),
      }
    );
  }

  async addReviewNote(
    reviewId: string,
    data: { note_type: string; content: string }
  ): Promise<ReviewNote> {
    return this.request<ReviewNote>(`/reviews/${reviewId}/notes`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async requestInvestigation(
    reviewId: string,
    data: { investigation_notes: string; assign_to?: string }
  ): Promise<{ status: string; message: string; review_id: string }> {
    return this.request<{ status: string; message: string; review_id: string }>(
      `/reviews/${reviewId}/investigate`,
      {
        method: 'POST',
        body: JSON.stringify(data),
      }
    );
  }

  async proposeAdjustment(
    reviewId: string,
    data: { adjustment_amount: string | number; adjustment_reason: string; target_ledger_id: string }
  ): Promise<AdjustmentProposal> {
    return this.request<AdjustmentProposal>(`/reviews/${reviewId}/adjustment/propose`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async decideAdjustment(
    proposalId: string,
    data: { approved: boolean; decision_notes?: string }
  ): Promise<{ status: string; message: string; proposal_id: string }> {
    return this.request<{ status: string; message: string; proposal_id: string }>(
      `/reviews/adjustment/${proposalId}/decide`,
      {
        method: 'POST',
        body: JSON.stringify(data),
      }
    );
  }

  // Phase 11 Audit Trail & Cryptographic Verification Endpoints
  async getAuditEvents(params?: {
    event_type?: string;
    entity_type?: string;
    actor_type?: string;
    correlation_id?: string;
    start_date?: string;
    end_date?: string;
    search?: string;
    limit?: number;
    offset?: number;
  }): Promise<AuditEventsList> {
    const query = new URLSearchParams();
    if (params?.event_type) query.set('event_type', params.event_type);
    if (params?.entity_type) query.set('entity_type', params.entity_type);
    if (params?.actor_type) query.set('actor_type', params.actor_type);
    if (params?.correlation_id) query.set('correlation_id', params.correlation_id);
    if (params?.start_date) query.set('start_date', params.start_date);
    if (params?.end_date) query.set('end_date', params.end_date);
    if (params?.search) query.set('search', params.search);
    if (params?.limit) query.set('limit', String(params.limit));
    if (params?.offset) query.set('offset', String(params.offset));
    const queryString = query.toString() ? `?${query.toString()}` : '';
    return this.request<AuditEventsList>(`/audit/events${queryString}`);
  }

  async getAuditEvent(eventId: string): Promise<AuditEventItem> {
    return this.request<AuditEventItem>(`/audit/events/${eventId}`);
  }

  async getEntityAuditTrail(entityType: string, entityId: string): Promise<AuditEventItem[]> {
    return this.request<AuditEventItem[]>(`/audit/events/entity/${entityType}/${entityId}`);
  }

  async verifyAuditIntegrity(
    startSeq?: number,
    endSeq?: number
  ): Promise<AuditIntegrityVerificationResult> {
    const query = new URLSearchParams();
    if (startSeq !== undefined) query.set('start_seq', String(startSeq));
    if (endSeq !== undefined) query.set('end_seq', String(endSeq));
    const queryString = query.toString() ? `?${query.toString()}` : '';
    return this.request<AuditIntegrityVerificationResult>(`/audit/integrity/verify${queryString}`, {
      method: 'POST',
    });
  }

  async getAuditIntegrityHistory(limit: number = 10): Promise<AuditIntegrityCheckItem[]> {
    return this.request<AuditIntegrityCheckItem[]>(`/audit/integrity/history?limit=${limit}`);
  }

  async getAuditLimitationDisclosure(): Promise<{
    title: string;
    guarantees: string[];
    boundaries_and_limitations: string[];
    recommended_hardening: string[];
  }> {
    return this.request<any>('/audit/limitation-disclosure');
  }

  // Phase 12 Reliable Integrations Endpoints
  async getIntegrations(): Promise<IntegrationItem[]> {
    return this.request<IntegrationItem[]>('/integrations');
  }

  async simulateIntegrationRequest(
    params: SimulateIntegrationParams
  ): Promise<SimulateIntegrationResult> {
    return this.request<SimulateIntegrationResult>('/integrations/simulate', {
      method: 'POST',
      body: JSON.stringify(params),
    });
  }

  async getIntegrationRequests(params?: {
    status?: string;
    error_category?: string;
    limit?: number;
    offset?: number;
  }): Promise<IntegrationRequestLog[]> {
    const query = new URLSearchParams();
    if (params?.status) query.set('status', params.status);
    if (params?.error_category) query.set('error_category', params.error_category);
    if (params?.limit) query.set('limit', String(params.limit));
    if (params?.offset) query.set('offset', String(params.offset));
    const queryString = query.toString() ? `?${query.toString()}` : '';
    return this.request<IntegrationRequestLog[]>(`/integrations/requests${queryString}`);
  }

  async getDeadLetterRequests(limit: number = 25, offset: number = 0): Promise<IntegrationRequestLog[]> {
    return this.request<IntegrationRequestLog[]>(`/integrations/dead-letter?limit=${limit}&offset=${offset}`);
  }

  async recoverDeadLetterRequest(
    requestId: string,
    resolutionNotes?: string
  ): Promise<{ status: string; message: string; request_id: string }> {
    return this.request<{ status: string; message: string; request_id: string }>(
      `/integrations/dead-letter/${requestId}/recover`,
      {
        method: 'POST',
        body: JSON.stringify({ resolution_notes: resolutionNotes }),
      }
    );
  }

  async simulateWebhook(params: SimulatedWebhookParams): Promise<SimulatedWebhookResult> {
    return this.request<SimulatedWebhookResult>('/integrations/webhook/simulate', {
      method: 'POST',
      body: JSON.stringify(params),
    });
  }

  // ========================================================================
  // Phase 13: Financial Reports & Analytics Endpoints
  // ========================================================================

  async getDashboardOverview(): Promise<DashboardOverviewResponse> {
    return this.request<DashboardOverviewResponse>('/dashboard/metrics');
  }

  async getDailyReport(params?: {
    start_date?: string;
    end_date?: string;
    currency?: string;
  }): Promise<DailyReconciliationResponse> {
    const query = new URLSearchParams();
    if (params?.start_date) query.set('start_date', params.start_date);
    if (params?.end_date) query.set('end_date', params.end_date);
    if (params?.currency) query.set('currency', params.currency);
    const qs = query.toString() ? `?${query.toString()}` : '';
    return this.request<DailyReconciliationResponse>(`/reports/daily${qs}`);
  }

  async getMonthlyReport(params?: {
    start_date?: string;
    end_date?: string;
    currency?: string;
  }): Promise<MonthlyReconciliationResponse> {
    const query = new URLSearchParams();
    if (params?.start_date) query.set('start_date', params.start_date);
    if (params?.end_date) query.set('end_date', params.end_date);
    if (params?.currency) query.set('currency', params.currency);
    const qs = query.toString() ? `?${query.toString()}` : '';
    return this.request<MonthlyReconciliationResponse>(`/reports/monthly${qs}`);
  }

  async getUnmatchedReport(params?: {
    start_date?: string;
    end_date?: string;
    currency?: string;
  }): Promise<UnmatchedTransactionsResponse> {
    const query = new URLSearchParams();
    if (params?.start_date) query.set('start_date', params.start_date);
    if (params?.end_date) query.set('end_date', params.end_date);
    if (params?.currency) query.set('currency', params.currency);
    const qs = query.toString() ? `?${query.toString()}` : '';
    return this.request<UnmatchedTransactionsResponse>(`/reports/unmatched${qs}`);
  }

  async getBankFeesReport(params?: {
    start_date?: string;
    end_date?: string;
    currency?: string;
  }): Promise<BankFeesReportResponse> {
    const query = new URLSearchParams();
    if (params?.start_date) query.set('start_date', params.start_date);
    if (params?.end_date) query.set('end_date', params.end_date);
    if (params?.currency) query.set('currency', params.currency);
    const qs = query.toString() ? `?${query.toString()}` : '';
    return this.request<BankFeesReportResponse>(`/reports/bank-fees${qs}`);
  }

  async getPendingApprovalsReport(params?: {
    priority?: string;
  }): Promise<PendingApprovalsResponse> {
    const query = new URLSearchParams();
    if (params?.priority) query.set('priority', params.priority);
    const qs = query.toString() ? `?${query.toString()}` : '';
    return this.request<PendingApprovalsResponse>(`/reports/pending-approvals${qs}`);
  }

  async getExceptionSummaryReport(params?: {
    start_date?: string;
    end_date?: string;
  }): Promise<ExceptionSummaryResponse> {
    const query = new URLSearchParams();
    if (params?.start_date) query.set('start_date', params.start_date);
    if (params?.end_date) query.set('end_date', params.end_date);
    const qs = query.toString() ? `?${query.toString()}` : '';
    return this.request<ExceptionSummaryResponse>(`/reports/exceptions${qs}`);
  }

  async getIntegrationFailureReport(params?: {
    start_date?: string;
    end_date?: string;
  }): Promise<IntegrationFailureResponse> {
    const query = new URLSearchParams();
    if (params?.start_date) query.set('start_date', params.start_date);
    if (params?.end_date) query.set('end_date', params.end_date);
    const qs = query.toString() ? `?${query.toString()}` : '';
    return this.request<IntegrationFailureResponse>(`/reports/integration-failures${qs}`);
  }

  async getAuditActivityReport(params?: {
    start_date?: string;
    end_date?: string;
  }): Promise<AuditActivityReportResponse> {
    const query = new URLSearchParams();
    if (params?.start_date) query.set('start_date', params.start_date);
    if (params?.end_date) query.set('end_date', params.end_date);
    const qs = query.toString() ? `?${query.toString()}` : '';
    return this.request<AuditActivityReportResponse>(`/reports/audit-activity${qs}`);
  }

  async downloadReportCsv(endpointPath: string, queryParams: Record<string, string> = {}): Promise<void> {
    const query = new URLSearchParams({ ...queryParams, format: 'csv' });
    const url = `${this.baseUrl}${endpointPath}?${query.toString()}`;
    const headers: Record<string, string> = {};
    if (this.token) {
      headers['Authorization'] = `Bearer ${this.token}`;
    }
    if (this.activeOrgId) {
      headers['X-Organization-Id'] = this.activeOrgId;
    }

    const response = await fetch(url, { headers });
    if (!response.ok) {
      throw new Error(`Failed to download CSV: ${response.statusText}`);
    }
    const blob = await response.blob();
    const disposition = response.headers.get('content-disposition');
    let filename = 'finbridge_report.csv';
    if (disposition && disposition.indexOf('filename=') !== -1) {
      const match = disposition.match(/filename="?([^"]+)"?/);
      if (match && match[1]) filename = match[1];
    }
    const downloadUrl = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = downloadUrl;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.URL.revokeObjectURL(downloadUrl);
  }
}

export const apiClient = new ApiClient(BASE_URL);
