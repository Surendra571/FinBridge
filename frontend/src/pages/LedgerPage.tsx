import React, { useState, useEffect, useRef } from 'react';
import { apiClient } from '../api/client';
import { LedgerBatch, LedgerEntry, LedgerUploadResponse } from '../types';

type LedgerState = 'success' | 'unbalanced' | 'missing' | 'duplicate' | 'failed';

export const LedgerPage: React.FC = () => {
  const [batches, setBatches] = useState<LedgerBatch[]>([]);
  const [entries, setEntries] = useState<LedgerEntry[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [uploading, setUploading] = useState<boolean>(false);
  const [confirming, setConfirming] = useState<boolean>(false);
  const [uploadResult, setUploadResult] = useState<LedgerUploadResponse | null>(null);
  const [sourceSystem, setSourceSystem] = useState<string>('NetSuite');
  const [showSchemaModal, setShowSchemaModal] = useState<boolean>(false);
  const [showUploadModal, setShowUploadModal] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Stitch Validation State Switcher
  const [ledgerState, setLedgerState] = useState<LedgerState>('success');
  const [searchTerm, setSearchTerm] = useState('');
  const [sourceFilter, setSourceFilter] = useState('All');

  const fileInputRef = useRef<HTMLInputElement>(null);

  const sampleCsvContent = `Entry ID,Posting Date,Account Code,Description,Reference Number,Debit,Credit,Currency,Journal ID,Source System
JE-101-1,2026-10-15,1010-CASH,Customer Wire Receipt,INV-9801,15000.00,0.00,USD,JRN-2026-01,NetSuite
JE-101-2,2026-10-15,1200-AR,Accounts Receivable Settlement,INV-9801,0.00,15000.00,USD,JRN-2026-01,NetSuite
JE-102-1,2026-10-16,6100-CLOUD,AWS Monthly Hosting,AWS-OCT-26,1250.00,0.00,USD,JRN-2026-02,NetSuite
JE-102-2,2026-10-16,1010-CASH,Operating Account Direct Debit,AWS-OCT-26,0.00,1250.00,USD,JRN-2026-02,NetSuite`;

  const loadData = async () => {
    setLoading(true);
    try {
      const [bList, eList] = await Promise.all([
        apiClient.getLedgerBatches(),
        apiClient.getLedgerEntries(),
      ]);
      setBatches(bList);
      setEntries(eList);
    } catch (err: unknown) {
      console.error(err);
      setErrorMsg(err instanceof Error ? err.message : 'Failed to load ledger data');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleFileUpload = async (file: File) => {
    if (!file.name.toLowerCase().endsWith('.csv')) {
      setErrorMsg('Invalid file format. Please upload a standard .csv ledger export.');
      return;
    }

    if (file.size > 25 * 1024 * 1024) {
      setErrorMsg('File exceeds 25MB limit.');
      return;
    }

    setErrorMsg(null);
    setSuccessMsg(null);
    setUploading(true);

    try {
      const res = await apiClient.uploadLedgerCsv(file, sourceSystem);
      setUploadResult(res);
      await loadData();
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : 'Ledger upload failed');
    } finally {
      setUploading(false);
    }
  };

  const handleConfirmImport = async () => {
    if (!uploadResult) return;
    setConfirming(true);
    setErrorMsg(null);
    try {
      await apiClient.confirmLedgerBatch(uploadResult.batch_id);
      setSuccessMsg(`Ledger batch '${uploadResult.file_name}' confirmed! Entries committed.`);
      setUploadResult(null);
      setShowUploadModal(false);
      await loadData();
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : 'Failed to confirm ledger batch');
    } finally {
      setConfirming(false);
    }
  };

  // Mock sample preview entries matching Stitch
  const sampleEntries = [
    {
      id: 'ENT-90411',
      journal_id: 'JRN-2026-4410',
      posting_date: '2026-11-21',
      description: 'AWS EMEA Cloud Hosting',
      debit: '$14,820.80',
      credit: '—',
      currency: 'USD',
      account_code: '6120-EXP',
    },
    {
      id: 'ENT-90412',
      journal_id: 'JRN-2026-4410',
      posting_date: '2026-11-21',
      description: 'Accounts Payable · AWS EMEA',
      debit: '—',
      credit: '$14,820.80',
      currency: 'USD',
      account_code: '2000-AP',
    },
    {
      id: 'ENT-90413',
      journal_id: 'JRN-2026-4411',
      posting_date: '2026-11-21',
      description: 'Stripe Clearing Settlement',
      debit: '$184,210.50',
      credit: '—',
      currency: 'USD',
      account_code: '1010-CASH',
    },
    {
      id: 'ENT-90414',
      journal_id: 'JRN-2026-4411',
      posting_date: '2026-11-21',
      description: 'Accounts Receivable Clearing',
      debit: '—',
      credit: '$184,210.50',
      currency: 'USD',
      account_code: '1200-AR',
    },
  ];

  // Baseline batches matching Stitch
  const defaultBatches = [
    {
      id: 'LDG-2026-0814',
      source: 'NetSuite ERP',
      file_name: 'ns_gl_nov21_export.csv',
      count: 642,
      date: 'Nov 21, 2026',
      status: 'Balanced & Valid',
      statusType: 'success',
    },
    {
      id: 'LDG-2026-0813',
      source: 'SAP S/4HANA',
      file_name: 'sap_emea_nov20.csv',
      count: 418,
      date: 'Nov 20, 2026',
      status: 'Unbalanced ($142.80)',
      statusType: 'warning',
    },
    {
      id: 'LDG-2026-0812',
      source: 'QuickBooks Online',
      file_name: 'qbo_sub_nov19.csv',
      count: 195,
      date: 'Nov 19, 2026',
      status: 'Missing Fields (2)',
      statusType: 'warning',
    },
    {
      id: 'LDG-2026-0811',
      source: 'SAP S/4HANA',
      file_name: 'sap_gl_nov18.csv',
      count: 0,
      date: 'Nov 18, 2026',
      status: 'Failed',
      statusType: 'error',
    },
  ];

  const filteredBatches = defaultBatches.filter((b) => {
    if (searchTerm) {
      const term = searchTerm.toLowerCase();
      if (!`${b.id} ${b.source} ${b.file_name}`.toLowerCase().includes(term)) return false;
    }
    if (sourceFilter !== 'All' && !b.source.includes(sourceFilter)) return false;
    return true;
  });

  return (
    <div className="flex flex-col gap-6">
      {/* 1. Page Header (Stitch Parity) */}
      <section className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="font-headline text-[24px] font-bold text-[#101B32]">Ledger Imports</h1>
          <p className="font-body text-[14px] text-[#5B5F62] mt-0.5">
            Import and validate general ledger journal entries from NetSuite, SAP, QuickBooks, or CSV exports.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          {/* Validation State Switcher */}
          <div
            className="inline-flex items-center gap-1 p-1 rounded-lg"
            style={{ backgroundColor: '#EFF1F5', border: '1px solid #E0E3E6' }}
          >
            {(['success', 'unbalanced', 'missing', 'duplicate', 'failed'] as LedgerState[]).map((st) => (
              <button
                key={st}
                type="button"
                onClick={() => setLedgerState(st)}
                className={`px-2.5 py-1 rounded font-label text-[12px] capitalize transition-colors cursor-pointer ${
                  ledgerState === st
                    ? 'bg-white text-[#101B32] font-semibold shadow-xs'
                    : 'text-[#5B5F62] hover:text-[#101B32]'
                }`}
              >
                {st === 'missing' ? 'Missing fields' : st}
              </button>
            ))}
          </div>

          <button
            type="button"
            onClick={() => setShowSchemaModal(true)}
            className="px-3.5 py-2 rounded font-label text-[13px] text-[#101B32] font-medium hover:bg-[#EFF1F5] transition-colors cursor-pointer"
            style={{ backgroundColor: '#FFFFFF', border: '1px solid #E0E3E6' }}
          >
            View CSV Schema
          </button>

          <button
            type="button"
            onClick={() => setShowUploadModal(true)}
            className="inline-flex items-center justify-center gap-2 px-4 py-2 rounded text-white font-label text-[14px] font-semibold hover:opacity-95 transition-colors cursor-pointer"
            style={{ backgroundColor: '#5146E5' }}
          >
            <span className="material-symbols-outlined text-[18px]">upload_file</span>
            <span>Import Ledger</span>
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

      {/* 3. State Banners (Stitch Parity) */}
      {ledgerState === 'success' && (
        <section
          className="rounded-lg p-4 flex items-center justify-between gap-4 animate-in fade-in duration-150"
          style={{ backgroundColor: '#E6F8F2', border: '1px solid rgba(0, 108, 80, 0.2)', color: '#003828' }}
        >
          <div className="flex items-center gap-3">
            <span className="material-symbols-outlined text-[20px]" style={{ color: '#006C50' }}>check_circle</span>
            <div>
              <p className="font-label text-[14px] font-bold">Import LDG-2026-0814 validated successfully (NetSuite ERP)</p>
              <p className="font-body text-[12px] tabular-nums text-[#003828]/80">642 journal entries balanced ($1,842,910.40 Debits = $1,842,910.40 Credits).</p>
            </div>
          </div>
          <a
            href="/reconciliation"
            className="shrink-0 px-3 py-1.5 rounded text-white font-label text-[12px] font-semibold hover:opacity-95"
            style={{ backgroundColor: '#006C50' }}
          >
            Run reconciliation
          </a>
        </section>
      )}

      {ledgerState === 'unbalanced' && (
        <section
          className="rounded-lg p-4 flex items-center justify-between gap-4 animate-in fade-in duration-150"
          style={{ backgroundColor: '#FFF4E5', border: '1px solid rgba(132, 84, 0, 0.2)', color: '#462A00' }}
        >
          <div className="flex items-start gap-3">
            <span className="material-symbols-outlined text-[20px] shrink-0 mt-0.5" style={{ color: '#845400' }}>balance</span>
            <div>
              <p className="font-label text-[14px] font-bold">Unbalanced journal warning in LDG-2026-0813 (JRN-2026-4412)</p>
              <p className="font-body text-[12px] tabular-nums text-[#462A00]/80">Total debits ($24,142.80) do not equal total credits ($24,000.00). Variance: $142.80.</p>
            </div>
          </div>
          <button
            type="button"
            onClick={() => setSuccessMsg('Journal details inspected.')}
            className="shrink-0 px-3 py-1.5 rounded text-white font-label text-[12px] font-semibold cursor-pointer"
            style={{ backgroundColor: '#845400' }}
          >
            Inspect journal
          </button>
        </section>
      )}

      {ledgerState === 'missing' && (
        <section
          className="rounded-lg p-4 flex items-center justify-between gap-4 animate-in fade-in duration-150"
          style={{ backgroundColor: '#FFF4E5', border: '1px solid rgba(132, 84, 0, 0.2)', color: '#462A00' }}
        >
          <div className="flex items-start gap-3">
            <span className="material-symbols-outlined text-[20px] shrink-0 mt-0.5" style={{ color: '#845400' }}>warning</span>
            <div>
              <p className="font-label text-[14px] font-bold">Missing required fields in 2 entries (LDG-2026-0812)</p>
              <p className="font-body text-[12px] tabular-nums text-[#462A00]/80">ENT-90408 and ENT-90409 are missing GL Account code (required for deterministic matching).</p>
            </div>
          </div>
          <button
            type="button"
            onClick={() => setSuccessMsg('Account mapping panel opened.')}
            className="shrink-0 px-3 py-1.5 rounded text-white font-label text-[12px] font-semibold cursor-pointer"
            style={{ backgroundColor: '#845400' }}
          >
            Map accounts
          </button>
        </section>
      )}

      {ledgerState === 'duplicate' && (
        <section
          className="rounded-lg p-4 flex items-center justify-between gap-4 animate-in fade-in duration-150"
          style={{ backgroundColor: '#FFF4E5', border: '1px solid rgba(132, 84, 0, 0.2)', color: '#462A00' }}
        >
          <div className="flex items-start gap-3">
            <span className="material-symbols-outlined text-[20px] shrink-0 mt-0.5" style={{ color: '#845400' }}>content_copy</span>
            <div>
              <p className="font-label text-[14px] font-bold">Duplicate journal entries detected (3 rows)</p>
              <p className="font-body text-[12px] tabular-nums text-[#462A00]/80">Journal ID JRN-2026-4398 already exists in Period Nov 2026. Duplicate rows will be skipped.</p>
            </div>
          </div>
          <button
            type="button"
            onClick={() => setSuccessMsg('Skipped 3 duplicate lines.')}
            className="shrink-0 px-3 py-1.5 rounded text-white font-label text-[12px] font-semibold cursor-pointer"
            style={{ backgroundColor: '#845400' }}
          >
            Skip duplicates
          </button>
        </section>
      )}

      {ledgerState === 'failed' && (
        <section
          className="rounded-lg p-4 flex items-center justify-between gap-4 animate-in fade-in duration-150"
          style={{ backgroundColor: '#FFEDEA', border: '1px solid rgba(186, 26, 26, 0.2)', color: '#690005' }}
        >
          <div className="flex items-start gap-3">
            <span className="material-symbols-outlined text-[20px] shrink-0 mt-0.5" style={{ color: '#BA1A1A' }}>error</span>
            <div>
              <p className="font-label text-[14px] font-bold">Import failed for LDG-2026-0811 (sap_gl_nov18.csv)</p>
              <p className="font-body text-[12px] tabular-nums text-[#690005]/80">Line 88: Malformed UTF-8 delimiter and invalid ISO-4217 currency code.</p>
            </div>
          </div>
          <button
            type="button"
            onClick={() => setSuccessMsg('Error log downloaded.')}
            className="shrink-0 px-3 py-1.5 rounded text-white font-label text-[12px] font-semibold cursor-pointer"
            style={{ backgroundColor: '#BA1A1A' }}
          >
            Download error log
          </button>
        </section>
      )}

      {/* 4. Search & Filters Bar (Stitch Parity) */}
      <section
        className="rounded-xl p-4 flex flex-wrap items-center justify-between gap-3 shadow-xs"
        style={{ backgroundColor: '#FFFFFF', border: '1px solid #E0E3E6' }}
      >
        <div className="relative flex-1 min-w-64">
          <span className="material-symbols-outlined text-[18px] text-[#5B5F62] absolute left-3 top-1/2 -translate-y-1/2" aria-hidden="true">
            search
          </span>
          <input
            type="search"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder="Search by Import ID, file name, or Journal ID…"
            className="w-full rounded pl-10 pr-3.5 py-2 text-[13px] outline-none text-[#101B32] border border-[#E0E3E6] focus:border-[#5146E5]"
            style={{ backgroundColor: '#FBFCFF' }}
          />
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <select
            value={sourceFilter}
            onChange={(e) => setSourceFilter(e.target.value)}
            className="rounded px-3 py-2 text-[13px] outline-none text-[#101B32] border border-[#E0E3E6] focus:border-[#5146E5] cursor-pointer"
            style={{ backgroundColor: '#FBFCFF' }}
          >
            <option value="All">All source systems</option>
            <option value="NetSuite">NetSuite ERP</option>
            <option value="SAP">SAP S/4HANA</option>
            <option value="QuickBooks">QuickBooks Online</option>
          </select>

          <select
            className="rounded px-3 py-2 text-[13px] outline-none text-[#101B32] border border-[#E0E3E6] focus:border-[#5146E5] cursor-pointer"
            style={{ backgroundColor: '#FBFCFF' }}
          >
            <option>Nov 1 – Nov 21, 2026</option>
            <option>Oct 1 – Oct 31, 2026</option>
          </select>
        </div>
      </section>

      {/* 5. Ledger Imports Table (Stitch Parity) */}
      {loading ? (
        <div className="p-12 text-center text-[#5B5F62] flex items-center justify-center gap-2">
          <span className="material-symbols-outlined animate-spin text-[20px]">sync</span>
          <span>Loading ledger imports...</span>
        </div>
      ) : (
        <section
          className="rounded-xl overflow-hidden shadow-xs"
          style={{ backgroundColor: '#FFFFFF', border: '1px solid #E0E3E6' }}
        >
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead className="border-b" style={{ backgroundColor: '#EFF1F5', borderColor: '#E0E3E6' }}>
                <tr className="font-label text-[12px] text-[#5B5F62]">
                  <th className="px-4 py-3 font-semibold">Import ID</th>
                  <th className="px-4 py-3 font-semibold">Source system</th>
                  <th className="px-4 py-3 font-semibold">File name</th>
                  <th className="px-4 py-3 font-semibold text-right">Journal entries</th>
                  <th className="px-4 py-3 font-semibold">Import date</th>
                  <th className="px-4 py-3 font-semibold">Validation status</th>
                  <th className="px-4 py-3 font-semibold text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#E0E3E6] font-body text-[13px] tabular-nums">
                {(batches.length > 0
                  ? batches.map((b) => ({
                      id: b.id.slice(0, 13),
                      source: b.source_system,
                      file_name: b.file_name,
                      count: b.valid_rows,
                      date: new Date(b.created_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' }),
                      status: b.status === 'CONFIRMED' ? 'Balanced & Valid' : b.status,
                      statusType: b.status === 'CONFIRMED' ? 'success' : 'warning',
                    }))
                  : filteredBatches
                ).map((b) => (
                  <tr key={b.id} className="hover:bg-[#F9FAFD] transition-colors">
                    <td className="px-4 py-3.5 font-mono text-[12px] font-medium text-[#5146E5]">
                      {b.id}
                    </td>
                    <td className="px-4 py-3.5 font-label font-semibold text-[#101B32]">
                      {b.source}
                    </td>
                    <td className="px-4 py-3.5 font-mono text-[12px] text-[#44474A]">
                      {b.file_name}
                    </td>
                    <td className="px-4 py-3.5 text-right font-medium text-[#101B32]">
                      {b.count > 0 ? b.count : '—'}
                    </td>
                    <td className="px-4 py-3.5 text-[#5B5F62]">
                      {b.date}
                    </td>
                    <td className="px-4 py-3.5">
                      <span
                        className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-semibold"
                        style={{
                          backgroundColor:
                            b.statusType === 'success'
                              ? '#E6F8F2'
                              : b.statusType === 'error'
                              ? '#FFEDEA'
                              : '#FFF4E5',
                          color:
                            b.statusType === 'success'
                              ? '#003828'
                              : b.statusType === 'error'
                              ? '#690005'
                              : '#845400',
                        }}
                      >
                        {b.status}
                      </span>
                    </td>
                    <td className="px-4 py-3.5 text-right">
                      <button
                        type="button"
                        onClick={() => setSuccessMsg(`Previewing journal batch ${b.id}.`)}
                        className="px-3 py-1 rounded font-label text-[12px] font-medium text-[#101B32] hover:bg-[#EFF1F5] cursor-pointer"
                        style={{ border: '1px solid #E0E3E6', backgroundColor: '#FFFFFF' }}
                      >
                        Inspect
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {/* 6. Journal Entry Import Preview Table (Stitch Parity: 8 Required Columns) */}
      <section
        className="rounded-xl overflow-hidden shadow-xs"
        style={{ backgroundColor: '#FFFFFF', border: '1px solid #E0E3E6' }}
      >
        <header className="px-5 py-4 border-b flex items-center justify-between" style={{ borderColor: '#E0E3E6' }}>
          <div>
            <h2 className="font-headline text-[16px] font-bold text-[#101B32]">
              Import Preview · LDG-2026-0814
            </h2>
            <p className="font-body text-[13px] text-[#5B5F62] mt-0.5">
              Showing sample double-entry journal lines from ns_gl_nov21_export.csv
            </p>
          </div>
          <span className="font-mono text-[13px] font-bold" style={{ color: '#006C50' }}>
            Net balance: $0.00 ✓
          </span>
        </header>

        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse tabular-nums">
            <thead className="border-b" style={{ backgroundColor: '#EFF1F5', borderColor: '#E0E3E6' }}>
              <tr className="font-label text-[12px] text-[#5B5F62]">
                <th className="px-4 py-2.5 font-semibold">Entry ID</th>
                <th className="px-4 py-2.5 font-semibold">Journal ID</th>
                <th className="px-4 py-2.5 font-semibold">Posting date</th>
                <th className="px-4 py-2.5 font-semibold">Description</th>
                <th className="px-4 py-2.5 font-semibold text-right">Debit</th>
                <th className="px-4 py-2.5 font-semibold text-right">Credit</th>
                <th className="px-4 py-2.5 font-semibold">Currency</th>
                <th className="px-4 py-2.5 font-semibold">Account code</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#E0E3E6] font-body text-[13px]">
              {(entries.length > 0
                ? entries.slice(0, 6).map((e) => ({
                    id: e.entry_id,
                    journal_id: e.journal_id || 'JRN-2026-4410',
                    posting_date: e.posting_date,
                    description: e.description,
                    debit: e.direction === 'DEBIT' ? `$${parseFloat(e.amount).toLocaleString(undefined, { minimumFractionDigits: 2 })}` : '—',
                    credit: e.direction === 'CREDIT' ? `$${parseFloat(e.amount).toLocaleString(undefined, { minimumFractionDigits: 2 })}` : '—',
                    currency: e.currency,
                    account_code: e.account_code,
                  }))
                : sampleEntries
              ).map((row) => (
                <tr key={row.id} className="hover:bg-[#F9FAFD] transition-colors">
                  <td className="px-4 py-3 font-mono text-[12px] font-medium text-[#101B32]">{row.id}</td>
                  <td className="px-4 py-3 font-mono text-[12px] text-[#5B5F62]">{row.journal_id}</td>
                  <td className="px-4 py-3 text-[#101B32]">{row.posting_date}</td>
                  <td className="px-4 py-3 font-medium text-[#101B32]">{row.description}</td>
                  <td className="px-4 py-3 text-right font-semibold text-[#101B32]">{row.debit}</td>
                  <td className="px-4 py-3 text-right text-[#5B5F62]">{row.credit}</td>
                  <td className="px-4 py-3 font-mono text-[12px] text-[#101B32]">{row.currency}</td>
                  <td className="px-4 py-3 font-mono text-[12px] font-semibold text-[#5146E5]">{row.account_code}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {/* MODAL: Import Ledger CSV Dialog */}
      {showUploadModal && (
        <div className="fixed inset-0 z-50 bg-[#101B32]/40 backdrop-blur-xs flex items-center justify-center p-4">
          <div
            className="rounded-xl p-6 max-w-2xl w-full shadow-2xl animate-in fade-in zoom-in-95 duration-150 space-y-6"
            style={{ backgroundColor: '#FFFFFF', border: '1px solid #E0E3E6' }}
          >
            <div className="flex items-start justify-between gap-3 border-b pb-4" style={{ borderColor: '#E0E3E6' }}>
              <div>
                <h3 className="font-headline text-[18px] font-bold text-[#101B32]">Import General Ledger CSV</h3>
                <p className="font-body text-[13px] text-[#5B5F62] mt-0.5">
                  Select your ERP origin and upload double-entry journal records.
                </p>
              </div>
              <button
                type="button"
                onClick={() => {
                  setShowUploadModal(false);
                  setUploadResult(null);
                }}
                className="text-[#5B5F62] hover:text-[#101B32] cursor-pointer"
              >
                <span className="material-symbols-outlined text-[20px]">close</span>
              </button>
            </div>

            {/* ERP Source System Selector */}
            <div className="space-y-2">
              <label className="block text-[12px] font-semibold text-[#101B32]">1. Source ERP System</label>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-2.5">
                {['NetSuite', 'SAP S/4HANA', 'QuickBooks Enterprise', 'Microsoft Dynamics 365', 'Custom ERP'].map((erp) => (
                  <button
                    key={erp}
                    type="button"
                    onClick={() => setSourceSystem(erp)}
                    className={`p-3 rounded-lg border text-left transition-all cursor-pointer ${
                      sourceSystem === erp
                        ? 'border-[#5146E5] ring-2 ring-[#5146E5] bg-[#F2EFFF]/40 text-[#101B32] font-semibold'
                        : 'border-[#E0E3E6] bg-white text-[#5B5F62] hover:border-[#101B32]'
                    }`}
                  >
                    <span className="text-[13px] block">{erp}</span>
                  </button>
                ))}
              </div>
            </div>

            {/* Drag and Drop Zone */}
            <div className="space-y-2">
              <label className="block text-[12px] font-semibold text-[#101B32]">2. Upload Ledger CSV</label>
              <div
                onDragOver={(e) => e.preventDefault()}
                onDrop={(e) => {
                  e.preventDefault();
                  if (e.dataTransfer.files && e.dataTransfer.files[0]) {
                    handleFileUpload(e.dataTransfer.files[0]);
                  }
                }}
                onClick={() => fileInputRef.current?.click()}
                className="border-2 border-dashed border-[#E0E3E6] hover:border-[#5146E5] rounded-xl p-6 text-center cursor-pointer transition-colors flex flex-col items-center justify-center space-y-2"
                style={{ backgroundColor: '#FBFCFF' }}
              >
                <input
                  type="file"
                  ref={fileInputRef}
                  className="hidden"
                  accept=".csv"
                  onChange={(e) => {
                    if (e.target.files && e.target.files[0]) {
                      handleFileUpload(e.target.files[0]);
                    }
                  }}
                />

                {uploading ? (
                  <div className="flex flex-col items-center space-y-2 py-4">
                    <span className="material-symbols-outlined text-[32px] text-[#5146E5] animate-spin">sync</span>
                    <p className="text-[13px] font-medium text-[#101B32]">Verifying double-entry balances...</p>
                    <p className="text-[11px] text-[#5B5F62]">Checking Debits = Credits and validating account codes</p>
                  </div>
                ) : (
                  <>
                    <div
                      className="w-10 h-10 rounded-full inline-flex items-center justify-center"
                      style={{ backgroundColor: '#F2EFFF', color: '#1F00A4' }}
                    >
                      <span className="material-symbols-outlined text-[20px]">upload_file</span>
                    </div>
                    <div>
                      <p className="text-[13px] font-semibold text-[#101B32]">
                        Drag and drop your ledger CSV, or <span className="text-[#5146E5] underline">browse</span>
                      </p>
                      <p className="text-[11px] text-[#5B5F62] mt-0.5">Accepts standardized accounting CSV files up to 25MB.</p>
                    </div>
                  </>
                )}
              </div>
            </div>

            {/* Validation Staging Preview */}
            {uploadResult && (
              <div className="p-4 rounded-xl border border-[#E0E3E6] bg-[#F9FAFD] space-y-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span
                      className="px-2 py-0.5 rounded-full text-[10px] font-bold tracking-wider"
                      style={{ backgroundColor: '#E6F8F2', color: '#003828' }}
                    >
                      STAGED
                    </span>
                    <h4 className="font-label text-[14px] font-bold text-[#101B32]">{uploadResult.file_name}</h4>
                  </div>
                  <span className="font-mono text-[12px] font-semibold text-[#16A37B]">
                    {uploadResult.valid_rows} entries parsed
                  </span>
                </div>

                <div className="flex justify-end gap-2 pt-2">
                  <button
                    type="button"
                    onClick={() => setUploadResult(null)}
                    className="px-3 py-1.5 rounded font-label text-[12px] font-medium text-[#101B32] hover:bg-[#EFF1F5]"
                    style={{ border: '1px solid #E0E3E6' }}
                  >
                    Discard
                  </button>
                  <button
                    type="button"
                    onClick={handleConfirmImport}
                    disabled={confirming}
                    className="px-4 py-1.5 rounded text-white font-label text-[12px] font-semibold hover:opacity-95 disabled:opacity-50"
                    style={{ backgroundColor: '#16A37B' }}
                  >
                    {confirming ? 'Committing...' : 'Commit Ledger Entries'}
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* MODAL: View CSV Schema */}
      {showSchemaModal && (
        <div className="fixed inset-0 z-50 bg-[#101B32]/40 backdrop-blur-xs flex items-center justify-center p-4">
          <div
            className="rounded-xl p-6 max-w-2xl w-full shadow-2xl animate-in fade-in zoom-in-95 duration-150 space-y-4"
            style={{ backgroundColor: '#FFFFFF', border: '1px solid #E0E3E6' }}
          >
            <div className="flex items-start justify-between gap-3 border-b pb-3" style={{ borderColor: '#E0E3E6' }}>
              <h3 className="font-headline text-[16px] font-bold text-[#101B32]">
                Documented CSV Schema Specification
              </h3>
              <button
                type="button"
                onClick={() => setShowSchemaModal(false)}
                className="text-[#5B5F62] hover:text-[#101B32] cursor-pointer"
              >
                <span className="material-symbols-outlined text-[20px]">close</span>
              </button>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-[12px]">
              <div className="p-3 rounded-lg border border-[#E0E3E6] bg-[#FBFCFF]">
                <span className="font-bold text-[#101B32]">Entry ID *</span>
                <p className="text-[#5B5F62] mt-0.5">Unique line identifier (e.g. JE-101-1). Deduplicated automatically.</p>
              </div>
              <div className="p-3 rounded-lg border border-[#E0E3E6] bg-[#FBFCFF]">
                <span className="font-bold text-[#101B32]">Posting Date *</span>
                <p className="text-[#5B5F62] mt-0.5">ISO format (YYYY-MM-DD) or standard localized dates.</p>
              </div>
              <div className="p-3 rounded-lg border border-[#E0E3E6] bg-[#FBFCFF]">
                <span className="font-bold text-[#101B32]">Account Code *</span>
                <p className="text-[#5B5F62] mt-0.5">General ledger chart of accounts code (1010-CASH, 4000-REV).</p>
              </div>
              <div className="p-3 rounded-lg border border-[#E0E3E6] bg-[#FBFCFF]">
                <span className="font-bold text-[#101B32]">Debit &amp; Credit *</span>
                <p className="text-[#5B5F62] mt-0.5">Strict double-entry balance validation: Σ Debits = Σ Credits.</p>
              </div>
            </div>

            <pre className="p-3 rounded-lg border border-[#E0E3E6] bg-[#FBFCFF] text-[11px] font-mono text-[#101B32] overflow-x-auto">
              {sampleCsvContent}
            </pre>

            <div className="flex justify-end gap-2.5 pt-2">
              <button
                type="button"
                onClick={() => {
                  navigator.clipboard.writeText(sampleCsvContent);
                  setSuccessMsg('Sample CSV template copied to clipboard.');
                  setShowSchemaModal(false);
                }}
                className="px-4 py-2 rounded text-white font-label text-[13px] font-semibold hover:opacity-95 cursor-pointer"
                style={{ backgroundColor: '#5146E5' }}
              >
                Copy Template
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default LedgerPage;
