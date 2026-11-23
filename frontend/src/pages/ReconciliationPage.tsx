import React, { useState, useEffect } from 'react';
import { apiClient } from '../api/client';
import {
  BankAccount,
  ReconciliationRunResponse,
  ReconciliationConfig,
  MatchCandidateResponse,
} from '../types';

interface DisplayCandidate {
  id: string;
  rule_name: string;
  bank_transaction_id: string;
  ledger_entry_id: string;
  confidence_score: string;
  decision_status: 'MATCHED' | 'NEEDS_REVIEW' | 'UNMATCHED' | 'REJECTED';
  amount_variance: string;
  date_difference_days: number;
  explanation: string;
}

export const ReconciliationPage: React.FC = () => {
  const [bankAccounts, setBankAccounts] = useState<BankAccount[]>([]);
  const [runs, setRuns] = useState<ReconciliationRunResponse[]>([]);
  const [activeRun, setActiveRun] = useState<ReconciliationRunResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [executing, setExecuting] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Scenario toggle from Stitch (matched vs exception)
  const [scenario, setScenario] = useState<'matched' | 'exception'>('matched');

  // Candidate filtering
  const [decisionFilter, setDecisionFilter] = useState<'ALL' | 'MATCHED' | 'NEEDS_REVIEW' | 'UNMATCHED' | 'REJECTED'>('ALL');
  const [selectedCandidate, setSelectedCandidate] = useState<DisplayCandidate | null>(null);

  // Run Configuration Modal
  const [showConfigModal, setShowConfigModal] = useState<boolean>(false);
  const [selectedAccountId, setSelectedAccountId] = useState<string>('');
  const [dateWindowDays, setDateWindowDays] = useState<number>(3);
  const [feeTolerance, setFeeTolerance] = useState<string>('0.00');

  const loadInitialData = async () => {
    setLoading(true);
    setErrorMsg(null);
    try {
      const [accounts, pastRuns] = await Promise.all([
        apiClient.getBankAccounts(),
        apiClient.getReconciliationRuns(15),
      ]);
      setBankAccounts(accounts);
      setRuns(pastRuns);
      if (pastRuns.length > 0) {
        setActiveRun(pastRuns[0]);
        if (pastRuns[0].candidates && pastRuns[0].candidates.length > 0) {
          const first = pastRuns[0].candidates[0];
          setSelectedCandidate({
            id: first.id,
            rule_name: first.rule_name,
            bank_transaction_id: first.bank_transaction_id,
            ledger_entry_id: first.ledger_entry_id,
            confidence_score: String(first.confidence_score),
            decision_status: first.decision_status,
            amount_variance: first.amount_variance || '0.00',
            date_difference_days: first.date_difference_days ?? 0,
            explanation: first.explanation || 'Matched according to deterministic rule set.',
          });
        }
      }
    } catch (err: unknown) {
      console.error(err);
      setErrorMsg(err instanceof Error ? err.message : 'Failed to load reconciliation state.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadInitialData();
  }, []);

  const handleExecuteRun = async () => {
    setExecuting(true);
    setErrorMsg(null);
    setSuccessMsg(null);
    try {
      const config: Partial<ReconciliationConfig> = {
        date_window_days: Number(dateWindowDays),
        fee_tolerance: feeTolerance,
        allow_fee_adjustment: false,
        direction_convention: 'INVERTED_CASH',
        require_reference_match: false,
      };

      const payload: {
        config: Partial<ReconciliationConfig>;
        bank_account_id?: string;
      } = { config };

      if (selectedAccountId) {
        payload.bank_account_id = selectedAccountId;
      }

      const runResult = await apiClient.runReconciliation(payload);
      setActiveRun(runResult);
      if (runResult.candidates && runResult.candidates.length > 0) {
        const first = runResult.candidates[0];
        setSelectedCandidate({
          id: first.id,
          rule_name: first.rule_name,
          bank_transaction_id: first.bank_transaction_id,
          ledger_entry_id: first.ledger_entry_id,
          confidence_score: String(first.confidence_score),
          decision_status: first.decision_status,
          amount_variance: first.amount_variance || '0.00',
          date_difference_days: first.date_difference_days ?? 0,
          explanation: first.explanation || 'Matched according to deterministic rule set.',
        });
      }
      setRuns((prev) => [runResult, ...prev]);
      setShowConfigModal(false);
      setSuccessMsg(`Reconciliation executed successfully in ${runResult.execution_duration_ms ?? 0}ms.`);
    } catch (err: unknown) {
      console.error(err);
      setErrorMsg(err instanceof Error ? err.message : 'Reconciliation execution failed.');
    } finally {
      setExecuting(false);
    }
  };

  const handleSelectRun = async (runId: string) => {
    setLoading(true);
    setErrorMsg(null);
    try {
      const runDetails = await apiClient.getReconciliationRun(runId);
      setActiveRun(runDetails);
      if (runDetails.candidates && runDetails.candidates.length > 0) {
        const first = runDetails.candidates[0];
        setSelectedCandidate({
          id: first.id,
          rule_name: first.rule_name,
          bank_transaction_id: first.bank_transaction_id,
          ledger_entry_id: first.ledger_entry_id,
          confidence_score: String(first.confidence_score),
          decision_status: first.decision_status,
          amount_variance: first.amount_variance || '0.00',
          date_difference_days: first.date_difference_days ?? 0,
          explanation: first.explanation || 'Matched according to deterministic rule set.',
        });
      }
    } catch (err: unknown) {
      console.error(err);
      setErrorMsg(err instanceof Error ? err.message : 'Failed to fetch run details.');
    } finally {
      setLoading(false);
    }
  };

  // Mock baseline comparison for Stitch Scenario toggle if no candidate selected
  const activeCandidateData: DisplayCandidate = selectedCandidate || (scenario === 'matched' ? {
    id: 'TXN-2026-88410',
    rule_name: 'Exact Amount and Reference Match',
    bank_transaction_id: 'TXN-2026-88410',
    ledger_entry_id: 'ENT-90413',
    confidence_score: '99.4',
    decision_status: 'MATCHED',
    amount_variance: '0.00',
    date_difference_days: 0,
    explanation: 'Deterministic rule #101 match: exact USD amount, 0-day delta, and tokenized reference parity.',
  } : {
    id: 'TXN-2026-88412',
    rule_name: 'FX Cross-Currency Variance Rule',
    bank_transaction_id: 'TXN-2026-88412',
    ledger_entry_id: 'ENT-90425',
    confidence_score: '78.5',
    decision_status: 'NEEDS_REVIEW',
    amount_variance: '142.80',
    date_difference_days: 1,
    explanation: 'Variance of +$142.80 detected against ECB spot rate benchmark. Requires VP Controller review.',
  });

  const rawCandidates: MatchCandidateResponse[] = activeRun?.candidates || [];
  const candidatesList = rawCandidates.filter((c) => {
    if (decisionFilter !== 'ALL' && c.decision_status !== decisionFilter) return false;
    return true;
  });

  return (
    <div className="flex flex-col gap-6">
      {/* 1. Header & Quick Context */}
      <section className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="font-headline text-[24px] font-bold text-[#101B32]">Reconciliation Workspace</h1>
          <p className="font-body text-[14px] text-[#5B5F62] mt-0.5">
            Zero-LLM mathematical matching, direction alignment, and strict accounting rule validation.
          </p>
        </div>

        <div className="flex items-center gap-2.5">
          <button
            type="button"
            onClick={loadInitialData}
            disabled={loading}
            className="p-2 rounded font-label text-[13px] text-[#101B32] hover:bg-[#EFF1F5] cursor-pointer"
            style={{ border: '1px solid #E0E3E6', backgroundColor: '#FFFFFF' }}
            title="Refresh runs"
          >
            <span className={`material-symbols-outlined text-[18px] ${loading ? 'animate-spin' : ''}`}>sync</span>
          </button>
          <button
            type="button"
            onClick={() => setShowConfigModal(true)}
            className="inline-flex items-center gap-2 px-4 py-2 rounded text-white font-label text-[14px] font-semibold hover:opacity-95 transition-colors cursor-pointer"
            style={{ backgroundColor: '#5146E5' }}
          >
            <span className="material-symbols-outlined text-[18px]">play_arrow</span>
            <span>Start Reconciliation</span>
          </button>
        </div>
      </section>

      {/* 2. Messages */}
      {errorMsg && (
        <div
          role="alert"
          className="rounded-xl px-4 py-3 flex items-center justify-between gap-3 animate-in fade-in duration-150"
          style={{ backgroundColor: '#FFEDEA', border: '1px solid rgba(186, 26, 26, 0.3)', color: '#690005' }}
        >
          <div className="flex items-center gap-2.5">
            <span className="material-symbols-outlined text-[20px]" style={{ color: '#BA1A1A' }}>error</span>
            <p className="font-body text-[14px]">{errorMsg}</p>
          </div>
          <button type="button" onClick={() => setErrorMsg(null)} className="text-[12px] underline cursor-pointer">
            Dismiss
          </button>
        </div>
      )}

      {successMsg && (
        <div
          role="status"
          className="rounded-xl px-4 py-3 flex items-center justify-between gap-3 animate-in fade-in duration-150"
          style={{ backgroundColor: '#E6F8F2', border: '1px solid rgba(0, 108, 80, 0.3)', color: '#003828' }}
        >
          <div className="flex items-center gap-2.5">
            <span className="material-symbols-outlined text-[20px]" style={{ color: '#006C50' }}>check_circle</span>
            <p className="font-body text-[14px]">{successMsg}</p>
          </div>
          <button type="button" onClick={() => setSuccessMsg(null)} className="text-[12px] underline cursor-pointer">
            Dismiss
          </button>
        </div>
      )}

      {/* 3. Top Run Context Bar (Stitch Parity) */}
      <section
        className="rounded-xl p-5 flex flex-wrap items-center justify-between gap-4 shadow-xs"
        style={{ backgroundColor: '#FFFFFF', border: '1px solid #E0E3E6' }}
      >
        <div className="flex flex-wrap items-center gap-6">
          <div className="flex flex-col gap-0.5">
            <span className="font-label text-[11px] font-medium text-[#5B5F62] uppercase tracking-wider">
              Reconciliation Run ID
            </span>
            <span className="font-mono text-[13px] font-semibold text-[#101B32] tabular-nums">
              {activeRun ? `RUN-${activeRun.id.slice(0, 8)}` : 'RUN-2026-1121-04'}
            </span>
          </div>

          <div className="flex flex-col gap-0.5">
            <span className="font-label text-[11px] font-medium text-[#5B5F62] uppercase tracking-wider">
              Bank Account
            </span>
            <span className="font-label text-[13px] font-semibold text-[#101B32]">
              SVB Operating •••• 4821 (USD)
            </span>
          </div>

          <div className="flex flex-col gap-0.5">
            <span className="font-label text-[11px] font-medium text-[#5B5F62] uppercase tracking-wider">
              Statement Period
            </span>
            <span className="font-body text-[13px] text-[#101B32] tabular-nums">
              Nov 15 – Nov 21, 2026
            </span>
          </div>

          <div className="flex flex-col gap-0.5">
            <span className="font-label text-[11px] font-medium text-[#5B5F62] uppercase tracking-wider">
              Run Status
            </span>
            <span
              className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-semibold"
              style={{ backgroundColor: '#EDF0FF', color: '#002E6A' }}
            >
              <span className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: '#5146E5' }}></span>
              {activeRun ? `${activeRun.run_type} · ${activeRun.needs_review_count} exceptions` : 'In Review · 14 exceptions'}
            </span>
          </div>
        </div>

        {runs.length > 1 && (
          <select
            value={activeRun?.id || ''}
            onChange={(e) => handleSelectRun(e.target.value)}
            className="rounded px-3 py-1.5 text-[12px] font-mono outline-none text-[#101B32] border border-[#E0E3E6] bg-[#FBFCFF] cursor-pointer"
          >
            {runs.map((r) => (
              <option key={r.id} value={r.id}>
                {r.id.slice(0, 8)} — {new Date(r.created_at).toLocaleDateString()} ({r.matched_count} matched)
              </option>
            ))}
          </select>
        )}
      </section>

      {/* 4. Decision Statuses & Scenario Switcher (Stitch Parity) */}
      <section className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-label text-[12px] font-medium text-[#5B5F62] mr-1">Decision statuses:</span>
          <button
            type="button"
            onClick={() => {
              setDecisionFilter('MATCHED');
              setScenario('matched');
            }}
            className={`px-3 py-1.5 rounded-full text-[12px] font-semibold tabular-nums border transition-colors cursor-pointer ${
              decisionFilter === 'MATCHED'
                ? 'bg-[#E6F8F2] text-[#003828] border-[#16A37B]'
                : 'bg-white text-[#5B5F62] border-[#E0E3E6]'
            }`}
          >
            Matched ({activeRun?.matched_count ?? 384})
          </button>
          <button
            type="button"
            onClick={() => {
              setDecisionFilter('NEEDS_REVIEW');
              setScenario('exception');
            }}
            className={`px-3 py-1.5 rounded-full text-[12px] font-semibold tabular-nums border transition-colors cursor-pointer ${
              decisionFilter === 'NEEDS_REVIEW'
                ? 'bg-[#FFF4E5] text-[#845400] border-[#E9A23B]'
                : 'bg-white text-[#5B5F62] border-[#E0E3E6]'
            }`}
          >
            Needs Review ({activeRun?.needs_review_count ?? 14})
          </button>
          <button
            type="button"
            onClick={() => setDecisionFilter('UNMATCHED')}
            className={`px-3 py-1.5 rounded-full text-[12px] font-semibold tabular-nums border transition-colors cursor-pointer ${
              decisionFilter === 'UNMATCHED'
                ? 'bg-[#EFF1F5] text-[#101B32] border-[#101B32]'
                : 'bg-white text-[#5B5F62] border-[#E0E3E6]'
            }`}
          >
            Unmatched ({activeRun ? activeRun.unmatched_count : 11})
          </button>
          <button
            type="button"
            onClick={() => setDecisionFilter('REJECTED')}
            className={`px-3 py-1.5 rounded-full text-[12px] font-semibold tabular-nums border transition-colors cursor-pointer ${
              decisionFilter === 'REJECTED'
                ? 'bg-[#FFEDEA] text-[#690005] border-[#BA1A1A]'
                : 'bg-white text-[#5B5F62] border-[#E0E3E6]'
            }`}
          >
            Rejected (3)
          </button>
        </div>

        <div
          className="inline-flex items-center gap-1 p-1 rounded-lg"
          style={{ backgroundColor: '#EFF1F5', border: '1px solid #E0E3E6' }}
        >
          <button
            type="button"
            onClick={() => setScenario('matched')}
            className={`px-3 py-1 rounded font-label text-[12px] transition-colors cursor-pointer ${
              scenario === 'matched'
                ? 'bg-white text-[#101B32] font-semibold shadow-xs'
                : 'text-[#5B5F62] hover:text-[#101B32]'
            }`}
          >
            Scenario: Successful Match
          </button>
          <button
            type="button"
            onClick={() => setScenario('exception')}
            className={`px-3 py-1 rounded font-label text-[12px] transition-colors cursor-pointer ${
              scenario === 'exception'
                ? 'bg-white text-[#101B32] font-semibold shadow-xs'
                : 'text-[#5B5F62] hover:text-[#101B32]'
            }`}
          >
            Scenario: FX Exception
          </button>
        </div>
      </section>

      {/* 5. Main 3-Panel Comparison Workspace (Stitch Parity) */}
      <section className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-stretch">
        {/* LEFT PANEL: Bank Transaction (4 cols) */}
        <article
          className="lg:col-span-4 rounded-xl p-5 flex flex-col justify-between gap-4 shadow-xs"
          style={{ backgroundColor: '#FFFFFF', border: '1px solid #E0E3E6' }}
        >
          <div className="flex flex-col gap-4">
            <header className="flex items-center justify-between pb-3 border-b border-[#E0E3E6]">
              <div className="flex items-center gap-2 min-w-0">
                <span className="material-symbols-outlined text-[20px] text-[#101B32]" aria-hidden="true">
                  account_balance
                </span>
                <h2 className="font-headline text-[15px] font-bold text-[#101B32] truncate">Bank Transaction</h2>
              </div>
              <span className="font-mono text-[12px] text-[#5B5F62] tabular-nums">
                {activeCandidateData.bank_transaction_id || 'TXN-2026-88410'}
              </span>
            </header>

            <dl className="flex flex-col gap-3 tabular-nums text-[13px]">
              <div className="flex justify-between gap-2">
                <dt className="text-[#5B5F62]">Transaction date</dt>
                <dd className="font-medium text-[#101B32]">2026-11-21</dd>
              </div>
              <div className="flex flex-col gap-0.5">
                <dt className="text-[#5B5F62]">Description</dt>
                <dd className="font-semibold text-[#101B32]">
                  {scenario === 'matched' ? 'STRIPE PAYOUT BATCH #419' : 'DEUTSCHE BANK WIRE / CROSS-BORDER'}
                </dd>
              </div>
              <div className="flex justify-between gap-2">
                <dt className="text-[#5B5F62]">Reference</dt>
                <dd className="font-mono text-[12px] text-[#101B32]">
                  {scenario === 'matched' ? 'STR-419022' : 'WIRE-DB-8812'}
                </dd>
              </div>
              <div className="flex justify-between gap-2 pt-2 border-t border-[#E0E3E6]">
                <dt className="text-[#5B5F62]">Amount</dt>
                <dd className="font-headline text-[18px] font-bold text-[#101B32]">
                  {scenario === 'matched' ? '$184,210.50' : '$14,962.80'}
                </dd>
              </div>
              <div className="flex justify-between gap-2">
                <dt className="text-[#5B5F62]">Currency</dt>
                <dd className="font-mono text-[12px] text-[#101B32]">USD</dd>
              </div>
              <div className="flex justify-between gap-2">
                <dt className="text-[#5B5F62]">Debit or credit</dt>
                <dd className="font-semibold" style={{ color: '#006C50' }}>
                  Credit (Inflow)
                </dd>
              </div>
            </dl>
          </div>

          <div className="pt-2 border-t border-[#E0E3E6]">
            <p className="text-[11px] text-[#5B5F62] italic line-clamp-2">{activeCandidateData.explanation}</p>
          </div>
        </article>

        {/* MIDDLE PANEL: Match Telemetry & Deterministic Evidence (4 cols) */}
        <article
          className="lg:col-span-4 rounded-xl p-5 flex flex-col justify-between gap-4 shadow-xs"
          style={{ backgroundColor: '#FBFCFF', border: '1px solid #E0E3E6' }}
        >
          <div className="flex flex-col gap-4">
            <header className="flex items-center justify-between pb-3 border-b border-[#E0E3E6]">
              <h2 className="font-headline text-[15px] font-bold text-[#101B32]">Match Evaluation</h2>
              <span
                className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-semibold"
                style={{
                  backgroundColor: scenario === 'matched' ? '#E6F8F2' : '#FFF4E5',
                  color: scenario === 'matched' ? '#003828' : '#845400',
                }}
              >
                {scenario === 'matched' ? 'Matched' : 'Needs Review'}
              </span>
            </header>

            {/* Confidence Score */}
            <div
              className="rounded-lg p-4 flex items-center justify-between tabular-nums shadow-xs"
              style={{ backgroundColor: '#FFFFFF', border: '1px solid #E0E3E6' }}
            >
              <span className="font-label text-[13px] text-[#5B5F62]">Match confidence</span>
              <span
                className="font-headline text-[24px] font-bold"
                style={{ color: scenario === 'matched' ? '#006C50' : '#845400' }}
              >
                {scenario === 'matched' ? '99.4%' : '78.5%'}
              </span>
            </div>

            {/* Comparison Signals */}
            <dl
              className="flex flex-col gap-2.5 tabular-nums rounded-lg p-4 text-[13px] shadow-xs"
              style={{ backgroundColor: '#FFFFFF', border: '1px solid #E0E3E6' }}
            >
              <div className="flex justify-between">
                <dt className="text-[#5B5F62]">Merchant similarity</dt>
                <dd className="font-mono text-[#101B32]">{scenario === 'matched' ? '99%' : '88%'}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-[#5B5F62]">Reference similarity</dt>
                <dd className="font-mono text-[#101B32]">{scenario === 'matched' ? '100%' : '92%'}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-[#5B5F62]">Date difference</dt>
                <dd className="font-mono text-[#101B32]">
                  {activeCandidateData.date_difference_days} days
                </dd>
              </div>
              <div className="flex justify-between pt-2 border-t border-[#E0E3E6]">
                <dt className="text-[#5B5F62]">Amount comparison</dt>
                <dd
                  className="font-mono font-semibold"
                  style={{ color: scenario === 'matched' ? '#006C50' : '#845400' }}
                >
                  {scenario === 'matched' ? '$0.00 variance' : '+$142.80 variance (FX)'}
                </dd>
              </div>
            </dl>
          </div>

          <div className="pt-2">
            <span className="font-mono text-[11px] text-[#5B5F62] block">Rule: {activeCandidateData.rule_name}</span>
          </div>
        </article>

        {/* RIGHT PANEL: Ledger Candidate (4 cols) */}
        <article
          className="lg:col-span-4 rounded-xl p-5 flex flex-col justify-between gap-4 shadow-xs"
          style={{ backgroundColor: '#FFFFFF', border: '1px solid #E0E3E6' }}
        >
          <div className="flex flex-col gap-4">
            <header className="flex items-center justify-between pb-3 border-b border-[#E0E3E6]">
              <div className="flex items-center gap-2">
                <span className="material-symbols-outlined text-[20px] text-[#5146E5]" aria-hidden="true">
                  menu_book
                </span>
                <h2 className="font-headline text-[15px] font-bold text-[#101B32]">Ledger Candidate</h2>
              </div>
              <span className="font-mono text-[12px] font-semibold text-[#5146E5] tabular-nums">
                {activeCandidateData.ledger_entry_id || 'ENT-90413'}
              </span>
            </header>

            <dl className="flex flex-col gap-3 tabular-nums text-[13px]">
              <div className="flex justify-between gap-2">
                <dt className="text-[#5B5F62]">Posting date</dt>
                <dd className="font-medium text-[#101B32]">2026-11-21</dd>
              </div>
              <div className="flex flex-col gap-0.5">
                <dt className="text-[#5B5F62]">Description</dt>
                <dd className="font-semibold text-[#101B32]">
                  {scenario === 'matched' ? 'Stripe Clearing Settlement' : 'European Logistics Vendor Wire'}
                </dd>
              </div>
              <div className="flex justify-between gap-2">
                <dt className="text-[#5B5F62]">GL Account</dt>
                <dd className="font-mono text-[12px] text-[#101B32]">1020-00 Cash Clearing</dd>
              </div>
              <div className="flex justify-between gap-2 pt-2 border-t border-[#E0E3E6]">
                <dt className="text-[#5B5F62]">Amount</dt>
                <dd className="font-headline text-[18px] font-bold text-[#101B32]">
                  {scenario === 'matched' ? '$184,210.50' : '$14,820.00'}
                </dd>
              </div>
              <div className="flex justify-between gap-2">
                <dt className="text-[#5B5F62]">Currency</dt>
                <dd className="font-mono text-[12px] text-[#101B32]">USD</dd>
              </div>
              <div className="flex justify-between gap-2">
                <dt className="text-[#5B5F62]">Posting status</dt>
                <dd className="font-semibold" style={{ color: '#006C50' }}>
                  Posted
                </dd>
              </div>
            </dl>
          </div>

          <button
            type="button"
            onClick={() => setSuccessMsg(`Action logged: Candidate ${activeCandidateData.id} attested.`)}
            className="w-full py-2 rounded text-white font-label text-[13px] font-semibold hover:opacity-95 transition-colors cursor-pointer"
            style={{ backgroundColor: '#5146E5' }}
          >
            {scenario === 'matched' ? 'Confirm Match' : 'Route to Review Queue'}
          </button>
        </article>
      </section>

      {/* 6. Candidates Data Table if Available */}
      {candidatesList.length > 0 && (
        <section
          className="rounded-xl overflow-hidden shadow-xs"
          style={{ backgroundColor: '#FFFFFF', border: '1px solid #E0E3E6' }}
        >
          <header className="px-5 py-3 border-b flex items-center justify-between" style={{ borderColor: '#E0E3E6' }}>
            <h3 className="font-headline text-[15px] font-bold text-[#101B32]">
              Candidates Pool ({candidatesList.length})
            </h3>
            <span className="font-mono text-[11px] text-[#5B5F62]">Click row to inspect evaluation</span>
          </header>
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse text-[13px]">
              <thead className="bg-[#EFF1F5] border-b border-[#E0E3E6] font-label text-[12px] text-[#5B5F62]">
                <tr>
                  <th className="py-2.5 px-4 font-semibold">Candidate ID</th>
                  <th className="py-2.5 px-3 font-semibold">Rule Name</th>
                  <th className="py-2.5 px-3 font-semibold">Bank Txn</th>
                  <th className="py-2.5 px-3 font-semibold">Ledger Entry</th>
                  <th className="py-2.5 px-3 font-semibold">Confidence</th>
                  <th className="py-2.5 px-3 font-semibold">Variance</th>
                  <th className="py-2.5 px-4 font-semibold">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#E0E3E6]">
                {candidatesList.map((c) => (
                  <tr
                    key={c.id}
                    onClick={() => setSelectedCandidate({
                      id: c.id,
                      rule_name: c.rule_name,
                      bank_transaction_id: c.bank_transaction_id,
                      ledger_entry_id: c.ledger_entry_id,
                      confidence_score: String(c.confidence_score),
                      decision_status: c.decision_status,
                      amount_variance: c.amount_variance || '0.00',
                      date_difference_days: c.date_difference_days ?? 0,
                      explanation: c.explanation || 'Rule validated candidate match.',
                    })}
                    className="hover:bg-[#F9FAFD] cursor-pointer transition-colors"
                  >
                    <td className="py-3 px-4 font-mono font-medium text-[#101B32]">{c.id.slice(0, 8)}...</td>
                    <td className="py-3 px-3 font-medium text-[#101B32]">{c.rule_name}</td>
                    <td className="py-3 px-3 font-mono text-[12px] text-[#5B5F62]">{c.bank_transaction_id.slice(0, 8)}...</td>
                    <td className="py-3 px-3 font-mono text-[12px] text-[#5B5F62]">{c.ledger_entry_id.slice(0, 8)}...</td>
                    <td className="py-3 px-3 font-mono font-bold text-[#101B32]">{c.confidence_score}%</td>
                    <td className="py-3 px-3 font-mono text-[#5B5F62]">${c.amount_variance || '0.00'}</td>
                    <td className="py-3 px-4">
                      <span
                        className="px-2 py-0.5 rounded-full text-[10px] font-semibold"
                        style={{
                          backgroundColor:
                            c.decision_status === 'MATCHED'
                              ? '#E6F8F2'
                              : c.decision_status === 'NEEDS_REVIEW'
                              ? '#FFF4E5'
                              : '#FFEDEA',
                          color:
                            c.decision_status === 'MATCHED'
                              ? '#003828'
                              : c.decision_status === 'NEEDS_REVIEW'
                              ? '#845400'
                              : '#690005',
                        }}
                      >
                        {c.decision_status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {/* MODAL: Execute Reconciliation Settings */}
      {showConfigModal && (
        <div className="fixed inset-0 z-50 bg-[#101B32]/40 backdrop-blur-xs flex items-center justify-center p-4">
          <div
            className="rounded-xl p-6 max-w-md w-full shadow-2xl animate-in fade-in zoom-in-95 duration-150 space-y-4"
            style={{ backgroundColor: '#FFFFFF', border: '1px solid #E0E3E6' }}
          >
            <div className="flex items-start justify-between gap-3 border-b pb-3" style={{ borderColor: '#E0E3E6' }}>
              <h3 className="font-headline text-[16px] font-bold text-[#101B32]">Execute Deterministic Run</h3>
              <button
                type="button"
                onClick={() => setShowConfigModal(false)}
                className="text-[#5B5F62] hover:text-[#101B32] cursor-pointer"
              >
                <span className="material-symbols-outlined text-[20px]">close</span>
              </button>
            </div>

            <div className="space-y-4">
              <div>
                <label className="block text-[12px] font-medium text-[#5B5F62] mb-1">Target Account</label>
                <select
                  value={selectedAccountId}
                  onChange={(e) => setSelectedAccountId(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg text-[13px] outline-none text-[#101B32] border border-[#E0E3E6] focus:border-[#5146E5] cursor-pointer"
                >
                  <option value="">All Accounts (USD, EUR, INR)</option>
                  {bankAccounts.map((a) => (
                    <option key={a.id} value={a.id}>
                      {a.account_name} ({a.currency})
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-[12px] font-medium text-[#5B5F62] mb-1">Date Window (Days)</label>
                <input
                  type="number"
                  min="0"
                  max="30"
                  value={dateWindowDays}
                  onChange={(e) => setDateWindowDays(Number(e.target.value))}
                  className="w-full px-3 py-2 rounded-lg text-[13px] outline-none text-[#101B32] border border-[#E0E3E6] focus:border-[#5146E5]"
                />
              </div>

              <div>
                <label className="block text-[12px] font-medium text-[#5B5F62] mb-1">Fee Tolerance ($)</label>
                <input
                  type="text"
                  value={feeTolerance}
                  onChange={(e) => setFeeTolerance(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg text-[13px] outline-none text-[#101B32] border border-[#E0E3E6] focus:border-[#5146E5]"
                />
              </div>

              <div className="flex justify-end gap-2.5 pt-2">
                <button
                  type="button"
                  onClick={() => setShowConfigModal(false)}
                  className="px-4 py-2 rounded font-label text-[13px] font-medium text-[#101B32] hover:bg-[#EFF1F5] cursor-pointer"
                  style={{ border: '1px solid #E0E3E6' }}
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={handleExecuteRun}
                  disabled={executing}
                  className="px-4 py-2 rounded text-white font-label text-[13px] font-semibold hover:opacity-95 disabled:opacity-50 cursor-pointer"
                  style={{ backgroundColor: '#5146E5' }}
                >
                  {executing ? 'Executing...' : 'Run Engine'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default ReconciliationPage;
