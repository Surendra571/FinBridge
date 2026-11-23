import React, { useState, useEffect } from 'react';
import { apiClient } from '../api/client';
import {
  IntegrationItem,
  IntegrationRequestLog,
  SimulateIntegrationResult,
  IntegrationFailureMode,
  IntegrationProviderType,
} from '../types';
import {
  Cpu,
  RefreshCw,
  Send,
  Zap,
  RotateCcw,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Clock,
  Layers,
  ShieldCheck,
  Server,
  Activity,
  Terminal,
} from 'lucide-react';

const FAILURE_MODE_OPTIONS: { value: IntegrationFailureMode; label: string; desc: string; critical?: boolean }[] = [
  {
    value: 'ERP_WRITE_TIMEOUT',
    label: 'Critical: ERP Write Timeout (Query-Before-Retry)',
    desc: 'Simulates write committing on ERP host while return HTTP response times out. Client queries ERP before retrying to prevent duplicate posting.',
    critical: true,
  },
  {
    value: 'RATE_LIMIT_429',
    label: 'HTTP 429 Rate Limit',
    desc: 'Downstream Core Banking/ERP API returns 429 Too Many Requests with Retry-After header.',
  },
  {
    value: 'SERVER_ERROR_500',
    label: 'HTTP 500 Server Error',
    desc: 'Downstream provider experiences transient internal database lock or 500 error.',
  },
  {
    value: 'CONNECTION_TIMEOUT',
    label: 'Connection Timeout',
    desc: 'TCP handshake fails to establish within connection threshold.',
  },
  {
    value: 'NETWORK_INTERRUPTION',
    label: 'Network Interruption',
    desc: 'Remote host abruptly resets TLS socket connection mid-flight.',
  },
  {
    value: 'WORKER_CRASH',
    label: 'Worker Process Crash',
    desc: 'Background task crashes, exhausting retries and routing request to Dead-Letter Queue (DLQ).',
  },
  {
    value: 'DELAYED_RESPONSE',
    label: 'Delayed Server Latency',
    desc: 'Host responds successfully but with high artificial server latency.',
  },
  {
    value: 'NONE',
    label: 'Normal Successful Execution',
    desc: 'Baseline pristine API communication with 200 OK.',
  },
];

export const FailureSimulatorPage: React.FC = () => {
  const [integrations, setIntegrations] = useState<IntegrationItem[]>([]);
  const [recentRequests, setRecentRequests] = useState<IntegrationRequestLog[]>([]);
  const [deadLetterRequests, setDeadLetterRequests] = useState<IntegrationRequestLog[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Simulation Form State
  const [selectedProvider, setSelectedProvider] = useState<IntegrationProviderType>('ERP_LEDGER');
  const [selectedFailureMode, setSelectedFailureMode] = useState<IntegrationFailureMode>('ERP_WRITE_TIMEOUT');
  const [maxRetries, setMaxRetries] = useState<number>(3);
  const [simulatedAmount, setSimulatedAmount] = useState<string>('15000.00');
  const [customEndpoint, setCustomEndpoint] = useState<string>('/api/v1/erp/journals');
  const [executing, setExecuting] = useState<boolean>(false);
  const [lastSimulationResult, setLastSimulationResult] = useState<SimulateIntegrationResult | null>(null);

  // DLQ Recovery Modal
  const [selectedDlqId, setSelectedDlqId] = useState<string | null>(null);
  const [recoveryNotes, setRecoveryNotes] = useState<string>('');
  const [recovering, setRecovering] = useState<boolean>(false);

  // Webhook Simulator State
  const [webhookEventId, setWebhookEventId] = useState<string>('EVT-BANK-9021');
  const [webhookAmount, setWebhookAmount] = useState<string>('450.00');
  const [webhookStatusMessage, setWebhookStatusMessage] = useState<string | null>(null);
  const [webhookSending, setWebhookSending] = useState<boolean>(false);

  const loadData = async () => {
    setLoading(true);
    try {
      const [integs, reqs, dlq] = await Promise.all([
        apiClient.getIntegrations(),
        apiClient.getIntegrationRequests({ limit: 15 }),
        apiClient.getDeadLetterRequests(10),
      ]);
      setIntegrations(integs);
      setRecentRequests(reqs);
      setDeadLetterRequests(dlq);
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : 'Failed to load integrations data');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleRunSimulation = async (e: React.FormEvent) => {
    e.preventDefault();
    setExecuting(true);
    setErrorMsg(null);
    setSuccessMsg(null);
    setLastSimulationResult(null);

    try {
      const result = await apiClient.simulateIntegrationRequest({
        provider_type: selectedProvider,
        failure_mode: selectedFailureMode,
        endpoint: customEndpoint,
        payload: {
          journal_reference: `JRN-SIM-${Math.floor(1000 + Math.random() * 9000)}`,
          amount: simulatedAmount,
          currency: 'USD',
          memo: 'Simulated FinBridge integration write',
        },
        max_retries: maxRetries,
        base_backoff_seconds: 0.1,
      });

      setLastSimulationResult(result);

      if (result.status === 'RECOVERED_BY_QUERY') {
        setSuccessMsg(
          'Critical Scenario Verified: ERP write timed out, but client queried remote host before retry, confirmed write, and avoided duplicate posting!'
        );
      } else if (result.status === 'COMPLETED') {
        setSuccessMsg(`Simulated request completed in ${result.latency_ms}ms with ${result.attempts_made} attempts.`);
      } else if (result.status === 'DEAD_LETTER') {
        setErrorMsg('Max retries exhausted. Request has been transitioned to the Dead-Letter Queue (DLQ).');
      }

      // Refresh logs
      const [reqs, dlq, integs] = await Promise.all([
        apiClient.getIntegrationRequests({ limit: 15 }),
        apiClient.getDeadLetterRequests(10),
        apiClient.getIntegrations(),
      ]);
      setRecentRequests(reqs);
      setDeadLetterRequests(dlq);
      setIntegrations(integs);
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : 'Simulation failed');
    } finally {
      setExecuting(false);
    }
  };

  const handleRecoverDlq = async () => {
    if (!selectedDlqId) return;
    setRecovering(true);
    try {
      await apiClient.recoverDeadLetterRequest(selectedDlqId, recoveryNotes);
      setSuccessMsg('Dead letter job safely recovered and verified against remote provider.');
      setSelectedDlqId(null);
      setRecoveryNotes('');
      // Reload
      loadData();
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : 'Failed to recover DLQ request');
    } finally {
      setRecovering(false);
    }
  };

  const handleSendWebhook = async () => {
    setWebhookSending(true);
    setWebhookStatusMessage(null);
    try {
      const res = await apiClient.simulateWebhook({
        event_id: webhookEventId,
        event_type: 'TRANSACTION_SETTLED',
        account_number: '****8921',
        amount: webhookAmount,
        currency: 'USD',
      });

      if (res.is_duplicate) {
        setWebhookStatusMessage(`Duplicate webhook detected and rejected (DEDUPLICATED) in ${res.execution_time_ms}ms. Double financial posting was prevented.`);
      } else {
        setWebhookStatusMessage(`Webhook ${res.event_id} verified and processed as fresh transaction.`);
      }
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : 'Webhook dispatch failed');
    } finally {
      setWebhookSending(false);
    }
  };

  const getHealthBadge = (health: string) => {
    switch (health) {
      case 'HEALTHY':
        return <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-semibold bg-emerald-100 text-emerald-800"><CheckCircle2 className="w-3.5 h-3.5" /> Healthy</span>;
      case 'DEGRADED':
        return <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-semibold bg-amber-100 text-amber-800"><AlertTriangle className="w-3.5 h-3.5" /> Degraded</span>;
      default:
        return <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-semibold bg-rose-100 text-rose-800"><XCircle className="w-3.5 h-3.5" /> Unhealthy</span>;
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'COMPLETED':
        return <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-emerald-100 text-emerald-800">Completed</span>;
      case 'RECOVERED_BY_QUERY':
        return <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-purple-100 text-purple-800">Recovered (Query)</span>;
      case 'DEAD_LETTER':
        return <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-rose-100 text-rose-800">Dead Letter (DLQ)</span>;
      default:
        return <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-amber-100 text-amber-800">{status}</span>;
    }
  };

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-indigo-50 border border-indigo-200 flex items-center justify-center text-indigo-600">
              <Activity className="w-6 h-6" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-2xl font-bold text-slate-900 tracking-tight">
                  Distributed Integrations & Failure Simulator
                </h1>
                <span className="px-2 py-0.5 rounded text-[11px] font-bold bg-amber-100 text-amber-800 uppercase tracking-wider">
                  Simulated Environment
                </span>
              </div>
              <p className="text-sm text-slate-500">
                Stress-test Core Banking & NetSuite/SAP ERP reliability, rate limits, timeouts, and query-before-retry idempotency.
              </p>
            </div>
          </div>
        </div>

        <button
          onClick={loadData}
          disabled={loading}
          className="inline-flex items-center gap-2 px-3.5 py-2 border border-slate-300 rounded-lg text-xs font-semibold text-slate-700 bg-white hover:bg-slate-50 shadow-sm transition-colors"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          Refresh Telemetry
        </button>
      </div>

      {/* Notifications */}
      {errorMsg && (
        <div className="p-4 rounded-lg bg-rose-50 border border-rose-200 text-rose-700 text-sm flex items-center justify-between">
          <span className="flex items-center gap-2"><AlertTriangle className="w-4 h-4" /> {errorMsg}</span>
          <button onClick={() => setErrorMsg(null)} className="text-rose-500 hover:text-rose-700 font-bold ml-4">✕</button>
        </div>
      )}
      {successMsg && (
        <div className="p-4 rounded-lg bg-emerald-50 border border-emerald-200 text-emerald-700 text-sm flex items-center justify-between">
          <span className="flex items-center gap-2"><CheckCircle2 className="w-4 h-4" /> {successMsg}</span>
          <button onClick={() => setSuccessMsg(null)} className="text-emerald-500 hover:text-emerald-700 font-bold ml-4">✕</button>
        </div>
      )}

      {/* Integration Providers Health Status Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {integrations.map((integ) => (
          <div key={integ.id} className="p-4 rounded-xl bg-white border border-slate-200 shadow-sm space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Server className="w-4 h-4 text-indigo-600" />
                <span className="font-bold text-sm text-slate-800">{integ.provider_name}</span>
              </div>
              {getHealthBadge(integ.health_status)}
            </div>
            <div className="grid grid-cols-3 gap-2 text-xs text-slate-600 bg-slate-50 p-2.5 rounded-lg border border-slate-100">
              <div>
                <span className="text-slate-400">Type:</span>
                <div className="font-semibold text-slate-800">{integ.provider_type}</div>
              </div>
              <div>
                <span className="text-slate-400">Failures:</span>
                <div className="font-mono font-bold text-slate-800">{integ.consecutive_failures}</div>
              </div>
              <div>
                <span className="text-slate-400">Environment:</span>
                <div className="font-semibold text-amber-700">Simulated</div>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Main Grid: Failure Simulator Form + Execution Telemetry */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: Failure Dispatcher Form (6 cols) */}
        <div className="lg:col-span-6 bg-white rounded-xl border border-slate-200 shadow-sm p-6 space-y-4">
          <div className="flex items-center gap-2 pb-3 border-b border-slate-200">
            <Zap className="w-5 h-5 text-indigo-600" />
            <h2 className="text-base font-bold text-slate-900">Induce Distributed Failure Mode</h2>
          </div>

          <form onSubmit={handleRunSimulation} className="space-y-4 text-xs">
            {/* Target Provider */}
            <div>
              <label className="text-slate-600 font-semibold block mb-1">Target Integration</label>
              <div className="grid grid-cols-2 gap-2">
                <button
                  type="button"
                  onClick={() => {
                    setSelectedProvider('ERP_LEDGER');
                    setCustomEndpoint('/api/v1/erp/journals');
                  }}
                  className={`p-2.5 rounded-lg border font-semibold transition-all ${
                    selectedProvider === 'ERP_LEDGER'
                      ? 'border-indigo-600 bg-indigo-50/50 text-indigo-700 ring-1 ring-indigo-200'
                      : 'border-slate-200 hover:bg-slate-50 text-slate-700'
                  }`}
                >
                  NetSuite / SAP ERP
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setSelectedProvider('CORE_BANKING');
                    setCustomEndpoint('/api/v1/banking/transfers');
                  }}
                  className={`p-2.5 rounded-lg border font-semibold transition-all ${
                    selectedProvider === 'CORE_BANKING'
                      ? 'border-indigo-600 bg-indigo-50/50 text-indigo-700 ring-1 ring-indigo-200'
                      : 'border-slate-200 hover:bg-slate-50 text-slate-700'
                  }`}
                >
                  Core Banking API
                </button>
              </div>
            </div>

            {/* Failure Scenario Selection */}
            <div>
              <label className="text-slate-600 font-semibold block mb-1">Failure Scenario</label>
              <select
                value={selectedFailureMode}
                onChange={(e) => setSelectedFailureMode(e.target.value as IntegrationFailureMode)}
                className="w-full p-2.5 border border-slate-300 rounded-lg text-xs bg-white font-medium text-slate-800"
              >
                {FAILURE_MODE_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
              <p className="text-[11px] text-slate-500 mt-1 italic">
                {FAILURE_MODE_OPTIONS.find((o) => o.value === selectedFailureMode)?.desc}
              </p>
            </div>

            {/* Parameter Inputs */}
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-slate-600 font-semibold block mb-1">Financial Amount ($)</label>
                <input
                  type="number"
                  step="0.01"
                  value={simulatedAmount}
                  onChange={(e) => setSimulatedAmount(e.target.value)}
                  className="w-full p-2 border border-slate-300 rounded-lg font-mono text-xs"
                />
              </div>
              <div>
                <label className="text-slate-600 font-semibold block mb-1">Max Retries Allowed</label>
                <input
                  type="number"
                  min="0"
                  max="5"
                  value={maxRetries}
                  onChange={(e) => setMaxRetries(parseInt(e.target.value) || 0)}
                  className="w-full p-2 border border-slate-300 rounded-lg font-mono text-xs"
                />
              </div>
            </div>

            {/* Dispatch Button */}
            <button
              type="submit"
              disabled={executing}
              className="w-full py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white font-bold rounded-lg shadow-sm transition-colors flex items-center justify-center gap-2 disabled:opacity-50"
            >
              <Send className={`w-4 h-4 ${executing ? 'animate-spin' : ''}`} />
              {executing ? 'Executing Distributed Dispatch...' : 'Dispatch Integration Request'}
            </button>
          </form>

          {/* Webhook Deduplication Simulator Mini-Panel */}
          <div className="pt-4 border-t border-slate-200 space-y-2.5">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-slate-800 uppercase tracking-wider flex items-center gap-1.5">
                <RotateCcw className="w-3.5 h-3.5 text-indigo-600" />
                Webhook Deduplication Simulator
              </span>
            </div>
            <div className="flex gap-2 text-xs">
              <input
                type="text"
                value={webhookEventId}
                onChange={(e) => setWebhookEventId(e.target.value)}
                placeholder="Webhook Event ID"
                className="flex-1 p-2 border border-slate-300 rounded-lg font-mono text-xs"
              />
              <input
                type="number"
                step="0.01"
                value={webhookAmount}
                onChange={(e) => setWebhookAmount(e.target.value)}
                placeholder="Amount"
                className="w-24 p-2 border border-slate-300 rounded-lg font-mono text-xs"
              />
              <button
                type="button"
                onClick={handleSendWebhook}
                disabled={webhookSending}
                className="px-3.5 py-2 bg-slate-900 hover:bg-slate-800 text-white rounded-lg text-xs font-semibold whitespace-nowrap"
              >
                Send Webhook
              </button>
            </div>
            {webhookStatusMessage && (
              <div className="p-2.5 bg-indigo-50 border border-indigo-200 rounded-lg text-xs text-indigo-900 font-medium">
                {webhookStatusMessage}
              </div>
            )}
          </div>
        </div>

        {/* Right Column: Execution Telemetry & Retry Trace (6 cols) */}
        <div className="lg:col-span-6 bg-white rounded-xl border border-slate-200 shadow-sm p-6 space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-slate-200">
            <div className="flex items-center gap-2">
              <Terminal className="w-5 h-5 text-indigo-600" />
              <h2 className="text-base font-bold text-slate-900">Execution Telemetry & Trace</h2>
            </div>
            {lastSimulationResult && getStatusBadge(lastSimulationResult.status)}
          </div>

          {!lastSimulationResult ? (
            <div className="p-12 text-center text-slate-400 space-y-2">
              <Cpu className="w-10 h-10 mx-auto text-slate-300" />
              <div className="font-semibold text-slate-700">No simulation triggered yet</div>
              <p className="text-xs text-slate-400">
                Select a failure mode on the left and dispatch a request to see exponential backoff and query-before-retry telemetry.
              </p>
            </div>
          ) : (
            <div className="space-y-4 text-xs">
              {/* Critical Highlights Banner */}
              {lastSimulationResult.query_before_retry_performed && (
                <div className="p-3.5 bg-gradient-to-r from-purple-50 to-indigo-50 border border-purple-200 rounded-lg space-y-1">
                  <div className="font-bold text-purple-900 flex items-center gap-1.5 text-xs">
                    <ShieldCheck className="w-4 h-4 text-purple-600" />
                    Query-Before-Retry Verification Active
                  </div>
                  <p className="text-[11px] text-purple-950">
                    The client queried the remote host prior to attempting a retry.
                    {lastSimulationResult.double_write_prevented && (
                      <span className="font-bold text-emerald-800 block mt-0.5">
                        ✓ Double financial posting was prevented. Operation recovered with existing remote reference.
                      </span>
                    )}
                  </p>
                </div>
              )}

              {/* Status & Latency Metric Pills */}
              <div className="grid grid-cols-3 gap-2 bg-slate-50 p-3 rounded-lg border border-slate-200 font-mono">
                <div>
                  <span className="text-[10px] text-slate-400 uppercase font-sans">Attempts</span>
                  <div className="text-sm font-bold text-slate-900">{lastSimulationResult.attempts_made}</div>
                </div>
                <div>
                  <span className="text-[10px] text-slate-400 uppercase font-sans">Total Latency</span>
                  <div className="text-sm font-bold text-slate-900">{lastSimulationResult.latency_ms} ms</div>
                </div>
                <div>
                  <span className="text-[10px] text-slate-400 uppercase font-sans">HTTP Status</span>
                  <div className="text-sm font-bold text-slate-900">{lastSimulationResult.response_status || 'N/A'}</div>
                </div>
              </div>

              {/* Retry Backoff & Jitter Schedule Trace */}
              {lastSimulationResult.retry_schedule && lastSimulationResult.retry_schedule.length > 0 && (
                <div className="space-y-1.5">
                  <div className="font-semibold text-slate-700 text-xs uppercase tracking-wider flex items-center gap-1">
                    <Clock className="w-3.5 h-3.5 text-slate-400" />
                    Exponential Backoff & Random Jitter Schedule
                  </div>
                  <div className="space-y-1 max-h-36 overflow-y-auto">
                    {lastSimulationResult.retry_schedule.map((sc, i) => (
                      <div key={i} className="p-2 rounded bg-slate-50 border border-slate-200 flex items-center justify-between font-mono text-[11px]">
                        <div>
                          <span className="font-bold text-indigo-700">Attempt #{sc.attempt}:</span>{' '}
                          Backoff: {sc.backoff_delay_seconds}s + Jitter: {sc.jitter_seconds}s ={' '}
                          <span className="font-bold text-slate-800">{sc.total_wait_seconds}s</span>
                        </div>
                        <span className="text-slate-500 font-sans font-semibold text-[10px]">{sc.status}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Response Payload */}
              <div className="space-y-1">
                <span className="font-semibold text-slate-700 text-xs">Response Payload</span>
                <pre className="p-3 bg-slate-900 text-slate-200 rounded-lg text-[11px] font-mono overflow-x-auto max-h-36">
                  {JSON.stringify(lastSimulationResult.response_payload || { message: lastSimulationResult.error_message }, null, 2)}
                </pre>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Dead-Letter Queue (DLQ) Management Panel */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="p-4 border-b border-slate-200 flex items-center justify-between bg-rose-50/40">
          <div className="flex items-center gap-2">
            <XCircle className="w-4 h-4 text-rose-600" />
            <span className="font-bold text-xs text-rose-900 uppercase tracking-wider">
              Dead-Letter Queue (DLQ) Exhausted Tasks ({deadLetterRequests.length})
            </span>
          </div>
          <span className="text-[11px] text-slate-500">
            Unrecovered tasks requiring operator intervention
          </span>
        </div>

        {deadLetterRequests.length === 0 ? (
          <div className="p-6 text-center text-slate-400 text-xs flex items-center justify-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-500" />
            <span>Dead-letter queue is clear. No unhandled failed tasks.</span>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="bg-slate-50 border-b border-slate-200 text-slate-500 font-semibold text-[11px]">
                  <th className="py-2.5 px-4">Request ID</th>
                  <th className="py-2.5 px-4">Endpoint</th>
                  <th className="py-2.5 px-4">Error Category</th>
                  <th className="py-2.5 px-4">Retries</th>
                  <th className="py-2.5 px-4">Error Message</th>
                  <th className="py-2.5 px-4 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {deadLetterRequests.map((dlq) => (
                  <tr key={dlq.id} className="hover:bg-slate-50">
                    <td className="py-2.5 px-4 font-mono font-bold text-slate-800">{dlq.id.slice(0, 8)}...</td>
                    <td className="py-2.5 px-4 font-mono text-slate-600">{dlq.endpoint}</td>
                    <td className="py-2.5 px-4"><span className="text-rose-700 font-semibold">{dlq.error_category}</span></td>
                    <td className="py-2.5 px-4 font-mono">{dlq.retry_count}</td>
                    <td className="py-2.5 px-4 text-slate-500 truncate max-w-xs">{dlq.error_message || 'N/A'}</td>
                    <td className="py-2.5 px-4 text-right">
                      <button
                        onClick={() => setSelectedDlqId(dlq.id)}
                        className="px-3 py-1 bg-indigo-600 hover:bg-indigo-700 text-white rounded text-xs font-semibold"
                      >
                        Replay / Recover
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Recent Integration Requests Table */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="px-5 py-3.5 border-b border-slate-200">
          <div className="text-xs font-bold text-slate-800 uppercase tracking-wider flex items-center gap-1.5">
            <Layers className="w-4 h-4 text-indigo-600" />
            Recent Outbound Request Telemetry ({recentRequests.length})
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs border-collapse">
            <thead>
              <tr className="bg-slate-50 border-b border-slate-200 text-slate-500 font-semibold text-[11px]">
                <th className="py-2.5 px-4">Correlation ID</th>
                <th className="py-2.5 px-4">Endpoint</th>
                <th className="py-2.5 px-4">Status</th>
                <th className="py-2.5 px-4">HTTP</th>
                <th className="py-2.5 px-4">Latency</th>
                <th className="py-2.5 px-4">Error Category</th>
                <th className="py-2.5 px-4">Timestamp</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {recentRequests.map((req) => (
                <tr key={req.id} className="hover:bg-slate-50">
                  <td className="py-2.5 px-4 font-mono text-slate-700">{req.correlation_id.slice(0, 8)}...</td>
                  <td className="py-2.5 px-4 font-mono text-slate-600">{req.endpoint}</td>
                  <td className="py-2.5 px-4">{getStatusBadge(req.status)}</td>
                  <td className="py-2.5 px-4 font-mono font-bold text-slate-800">{req.response_status || '-'}</td>
                  <td className="py-2.5 px-4 font-mono">{req.latency_ms}ms</td>
                  <td className="py-2.5 px-4 text-slate-500">{req.error_category}</td>
                  <td className="py-2.5 px-4 text-slate-400 whitespace-nowrap">{new Date(req.created_at).toLocaleTimeString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* DLQ Recovery Modal */}
      {selectedDlqId && (
        <div className="fixed inset-0 bg-slate-900/50 flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-xl max-w-md w-full p-6 space-y-4 shadow-xl">
            <h3 className="text-base font-bold text-slate-900 flex items-center gap-2">
              <RotateCcw className="w-5 h-5 text-indigo-600" />
              Recover Dead-Letter Job
            </h3>
            <p className="text-xs text-slate-600">
              The client will query the remote host by idempotency key to verify if the operation already committed before attempting replay.
            </p>
            <div>
              <label className="text-xs text-slate-600 font-medium">Resolution Notes (Optional)</label>
              <textarea
                value={recoveryNotes}
                onChange={(e) => setRecoveryNotes(e.target.value)}
                placeholder="e.g. Downstream NetSuite maintenance window completed; manually cleared."
                className="w-full text-xs p-2.5 border border-slate-300 rounded-lg mt-1 h-20"
              />
            </div>
            <div className="flex justify-end gap-2">
              <button
                onClick={() => setSelectedDlqId(null)}
                className="px-3.5 py-1.5 border border-slate-300 rounded-lg text-xs font-semibold text-slate-700 hover:bg-slate-50"
              >
                Cancel
              </button>
              <button
                onClick={handleRecoverDlq}
                disabled={recovering}
                className="px-4 py-1.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-xs font-semibold shadow-sm"
              >
                {recovering ? 'Recovering...' : 'Confirm Safe Recovery'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
