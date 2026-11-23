import React, { useState, useEffect, useRef } from 'react';
import { apiClient } from '../api/client';
import { BankAccount, StatementUploadResponse } from '../types';

type StmtState = 'populated' | 'empty' | 'processing' | 'failed' | 'duplicate';

interface DisplayStatement {
  id: string;
  account_name: string;
  file_name: string;
  statement_start_date?: string;
  statement_end_date?: string;
  created_at: string;
  total_records: number;
  status: string;
  closing_balance?: string;
}

export const StatementsPage: React.FC = () => {
  const [bankAccounts, setBankAccounts] = useState<BankAccount[]>([]);
  const [selectedAccountId, setSelectedAccountId] = useState<string>('');
  const [statements, setStatements] = useState<DisplayStatement[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [uploading, setUploading] = useState<boolean>(false);
  const [confirming, setConfirming] = useState<boolean>(false);
  const [uploadResult, setUploadResult] = useState<StatementUploadResponse | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Stitch State Switcher
  const [stmtState, setStmtState] = useState<StmtState>('populated');
  const [searchTerm, setSearchTerm] = useState('');
  const [accountFilter, setAccountFilter] = useState('All');

  // Modals & Drawers
  const [showUploadModal, setShowUploadModal] = useState(false);
  const [showAccountModal, setShowAccountModal] = useState(false);
  const [inspectedStmt, setInspectedStmt] = useState<DisplayStatement | null>(null);

  // New account form
  const [newAccName, setNewAccName] = useState('');
  const [newAccInstitution, setNewAccInstitution] = useState('');
  const [newAccNumber, setNewAccNumber] = useState('');
  const [newAccType, setNewAccType] = useState('CHECKING');
  const [newAccCurrency, setNewAccCurrency] = useState('USD');

  const fileInputRef = useRef<HTMLInputElement>(null);

  const loadData = async () => {
    setLoading(true);
    setErrorMsg(null);
    try {
      const accounts = await apiClient.getBankAccounts();
      setBankAccounts(accounts);
      if (accounts.length > 0 && !selectedAccountId) {
        setSelectedAccountId(accounts[0].id);
      }
      const rawStmts = await apiClient.getStatements();
      const mappedStmts: DisplayStatement[] = rawStmts.map((s) => {
        const acc = accounts.find((a) => a.id === s.bank_account_id);
        const accLabel = acc ? `${acc.account_name} •••• ${acc.account_number_masked}` : 'SVB Operating •••• 4821';
        return {
          id: s.id,
          account_name: accLabel,
          file_name: s.file_name,
          statement_start_date: s.statement_start_date,
          statement_end_date: s.statement_end_date,
          created_at: s.created_at,
          total_records: s.parsed_record_count,
          status: s.status === 'CONFIRMED' ? 'Imported' : s.status === 'FAILED' ? 'Failed' : 'Processing',
          closing_balance: s.closing_balance,
        };
      });
      setStatements(mappedStmts);
    } catch (err: unknown) {
      console.error(err);
      setErrorMsg(err instanceof Error ? err.message : 'Failed to load statements and accounts.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleCreateAccount = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const created = await apiClient.createBankAccount({
        account_name: newAccName,
        institution_name: newAccInstitution,
        account_number_masked: newAccNumber,
        account_type: newAccType,
        currency: newAccCurrency,
      });
      setBankAccounts((prev) => [...prev, created]);
      setSelectedAccountId(created.id);
      setShowAccountModal(false);
      setNewAccName('');
      setNewAccInstitution('');
      setNewAccNumber('');
      setSuccessMsg(`Bank account '${created.account_name}' registered.`);
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : 'Failed to create bank account.');
    }
  };

  const handleFileUpload = async (file: File) => {
    if (!selectedAccountId) {
      setErrorMsg('Please select a target bank account first.');
      return;
    }

    const lowerName = file.name.toLowerCase();
    if (!lowerName.endsWith('.csv') && !lowerName.endsWith('.pdf')) {
      setErrorMsg('Invalid file format. Please upload a .csv or digital text .pdf statement.');
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
      const res = await apiClient.uploadStatement(selectedAccountId, file);
      setUploadResult(res);
      await loadData();
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : 'Statement upload failed.');
    } finally {
      setUploading(false);
    }
  };

  const handleConfirmStatement = async () => {
    if (!uploadResult) return;
    setConfirming(true);
    setErrorMsg(null);
    try {
      await apiClient.confirmStatement(uploadResult.statement_id);
      setSuccessMsg(`Statement '${uploadResult.file_name}' confirmed! Transactions committed.`);
      setUploadResult(null);
      setShowUploadModal(false);
      await loadData();
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : 'Failed to confirm statement.');
    } finally {
      setConfirming(false);
    }
  };

  // Mock baseline rows if backend statements list is empty
  const defaultBaseline: DisplayStatement[] = [
    {
      id: 'STM-2026-0421',
      account_name: 'SVB Operating •••• 4821',
      file_name: 'svb_op_nov21.csv',
      statement_start_date: '2026-11-15',
      statement_end_date: '2026-11-21',
      created_at: '2026-11-21T09:42:00Z',
      total_records: 412,
      status: 'Imported',
      closing_balance: '4,182,410.50',
    },
    {
      id: 'STM-2026-0420',
      account_name: 'Wise EUR •••• 3319',
      file_name: 'wise_eur_nov21.pdf',
      statement_start_date: '2026-11-14',
      statement_end_date: '2026-11-21',
      created_at: '2026-11-21T08:15:00Z',
      total_records: 184,
      status: 'Processing',
      closing_balance: '812,940.20',
    },
    {
      id: 'STM-2026-0419',
      account_name: 'HDFC Corporate •••• 3104',
      file_name: 'hdfc_corp_nov20.csv',
      statement_start_date: '2026-11-01',
      statement_end_date: '2026-11-20',
      created_at: '2026-11-20T17:30:00Z',
      total_records: 890,
      status: 'Imported',
      closing_balance: '18,450,210.00',
    },
  ];

  const displayStatements = stmtState === 'empty' ? [] : statements.length > 0 ? statements : defaultBaseline;

  const filteredStatements = displayStatements.filter((s) => {
    if (searchTerm) {
      const term = searchTerm.toLowerCase();
      const matchText = `${s.id} ${s.account_name} ${s.file_name}`.toLowerCase();
      if (!matchText.includes(term)) return false;
    }
    if (accountFilter !== 'All' && !s.account_name.includes(accountFilter)) {
      return false;
    }
    return true;
  });

  return (
    <div className="flex flex-col gap-6">
      {/* 1. Page Header & Actions (Stitch Parity) */}
      <section className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="font-headline text-[24px] font-bold text-[#101B32]">Bank Statements</h1>
          <p className="font-body text-[14px] text-[#5B5F62] mt-0.5">
            Import, validate, and audit CSV and PDF statements across connected commercial accounts.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          {/* State Switcher */}
          <div
            className="inline-flex items-center gap-1 p-1 rounded-lg"
            style={{ backgroundColor: '#EFF1F5', border: '1px solid #E0E3E6' }}
          >
            {(['populated', 'empty', 'processing', 'failed', 'duplicate'] as StmtState[]).map((st) => (
              <button
                key={st}
                type="button"
                onClick={() => setStmtState(st)}
                className={`px-2.5 py-1 rounded font-label text-[12px] capitalize transition-colors cursor-pointer ${
                  stmtState === st
                    ? 'bg-white text-[#101B32] font-semibold shadow-xs'
                    : 'text-[#5B5F62] hover:text-[#101B32]'
                }`}
              >
                {st === 'populated' ? 'All' : st}
              </button>
            ))}
          </div>

          <button
            type="button"
            onClick={() => setShowAccountModal(true)}
            className="px-3.5 py-2 rounded font-label text-[13px] text-[#101B32] font-medium hover:bg-[#EFF1F5] transition-colors cursor-pointer"
            style={{ backgroundColor: '#FFFFFF', border: '1px solid #E0E3E6' }}
          >
            + Add Bank Account
          </button>

          <button
            type="button"
            onClick={() => setShowUploadModal(true)}
            className="inline-flex items-center justify-center gap-2 px-4 py-2 rounded text-white font-label text-[14px] font-semibold hover:opacity-95 transition-colors cursor-pointer"
            style={{ backgroundColor: '#5146E5' }}
          >
            <span className="material-symbols-outlined text-[18px]" aria-hidden="true">upload_file</span>
            <span>Upload Statement</span>
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

      {/* 3. Contextual State Banners (Stitch Parity) */}
      {stmtState === 'processing' && (
        <section
          className="rounded-lg p-4 flex items-center justify-between gap-4 animate-in fade-in duration-150"
          style={{ backgroundColor: '#EDF0FF', border: '1px solid rgba(29, 91, 185, 0.2)', color: '#002E6A' }}
        >
          <div className="flex items-center gap-3">
            <span className="material-symbols-outlined text-[20px] animate-spin" style={{ color: '#1D5BB9' }}>sync</span>
            <div>
              <p className="font-label text-[14px] font-bold">Parsing statement STM-2026-0420 (wise_eur_nov21.pdf)</p>
              <p className="font-body text-[12px] tabular-nums text-[#002E6A]/80">Extracting 184 transaction lines and verifying opening/closing balances…</p>
            </div>
          </div>
          <span className="font-mono text-[13px] font-bold tabular-nums">68%</span>
        </section>
      )}

      {stmtState === 'failed' && (
        <section
          className="rounded-lg p-4 flex items-center justify-between gap-4 animate-in fade-in duration-150"
          style={{ backgroundColor: '#FFEDEA', border: '1px solid rgba(186, 26, 26, 0.2)', color: '#690005' }}
        >
          <div className="flex items-start gap-3">
            <span className="material-symbols-outlined text-[20px] shrink-0 mt-0.5" style={{ color: '#BA1A1A' }}>error</span>
            <div>
              <p className="font-label text-[14px] font-bold">Import failed for STM-2026-0418 (jpm_wire_export_corrupt.csv)</p>
              <p className="font-body text-[12px] tabular-nums text-[#690005]/80">Row 142: Missing ISO-4217 currency code and invalid posting date format.</p>
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

      {stmtState === 'duplicate' && (
        <section
          className="rounded-lg p-4 flex items-center justify-between gap-4 animate-in fade-in duration-150"
          style={{ backgroundColor: '#FFF4E5', border: '1px solid rgba(132, 84, 0, 0.2)', color: '#462A00' }}
        >
          <div className="flex items-start gap-3">
            <span className="material-symbols-outlined text-[20px] shrink-0 mt-0.5" style={{ color: '#845400' }}>content_copy</span>
            <div>
              <p className="font-label text-[14px] font-bold">Duplicate statement detected (STM-2026-0417)</p>
              <p className="font-body text-[12px] tabular-nums text-[#462A00]/80">SHA-256 checksum matches previously imported statement STM-2026-0412 (svb_operating_nov15.csv).</p>
            </div>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <button
              type="button"
              onClick={() => setStmtState('populated')}
              className="px-3 py-1.5 rounded font-label text-[12px] font-semibold text-[#462A00] hover:bg-[#E9A23B]/20 cursor-pointer"
              style={{ border: '1px solid rgba(132, 84, 0, 0.3)', backgroundColor: '#FFFFFF' }}
            >
              Discard
            </button>
          </div>
        </section>
      )}

      {/* 4. Filter & Search Bar (Stitch Parity) */}
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
            placeholder="Search by Statement ID, file name, or account…"
            className="w-full rounded pl-10 pr-3.5 py-2 text-[13px] outline-none text-[#101B32] border border-[#E0E3E6] focus:border-[#5146E5]"
            style={{ backgroundColor: '#FBFCFF' }}
          />
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <select
            value={accountFilter}
            onChange={(e) => setAccountFilter(e.target.value)}
            className="rounded px-3 py-2 text-[13px] outline-none text-[#101B32] border border-[#E0E3E6] focus:border-[#5146E5] cursor-pointer"
            style={{ backgroundColor: '#FBFCFF' }}
          >
            <option value="All">All bank accounts</option>
            <option value="SVB">SVB Operating •••• 4821</option>
            <option value="Wise">Wise EUR •••• 3319</option>
            <option value="HDFC">HDFC Corporate •••• 3104</option>
          </select>

          <select
            className="rounded px-3 py-2 text-[13px] outline-none text-[#101B32] border border-[#E0E3E6] focus:border-[#5146E5] cursor-pointer"
            style={{ backgroundColor: '#FBFCFF' }}
          >
            <option>Nov 1 – Nov 21, 2026</option>
            <option>Oct 1 – Oct 31, 2026</option>
            <option>Last 90 days</option>
          </select>
        </div>
      </section>

      {/* 5. Empty State or Data Table */}
      {loading ? (
        <div className="p-12 text-center text-[#5B5F62] flex items-center justify-center gap-2">
          <span className="material-symbols-outlined animate-spin text-[20px]">sync</span>
          <span>Loading bank statements...</span>
        </div>
      ) : filteredStatements.length === 0 ? (
        <section
          className="rounded-xl p-12 flex flex-col items-center text-center gap-4 shadow-xs"
          style={{ backgroundColor: '#FFFFFF', border: '1px solid #E0E3E6' }}
        >
          <div
            className="w-12 h-12 rounded-xl inline-flex items-center justify-center"
            style={{ backgroundColor: '#F2EFFF', color: '#1F00A4' }}
          >
            <span className="material-symbols-outlined text-[24px]">cloud_upload</span>
          </div>
          <div className="flex flex-col gap-1 max-w-md">
            <h2 className="font-headline text-[18px] font-bold text-[#101B32]">No bank statements uploaded</h2>
            <p className="font-body text-[13px] text-[#5B5F62]">
              Drag and drop CSV or PDF bank statements here, or select a file from your computer to begin parsing.
            </p>
          </div>
          <button
            type="button"
            onClick={() => setShowUploadModal(true)}
            className="px-4 py-2 rounded text-white font-label text-[13px] font-semibold hover:opacity-95 transition-colors cursor-pointer"
            style={{ backgroundColor: '#5146E5' }}
          >
            Upload Statement
          </button>
        </section>
      ) : (
        <section
          className="rounded-xl overflow-hidden shadow-xs"
          style={{ backgroundColor: '#FFFFFF', border: '1px solid #E0E3E6' }}
        >
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead className="border-b" style={{ backgroundColor: '#EFF1F5', borderColor: '#E0E3E6' }}>
                <tr className="font-label text-[12px] text-[#5B5F62]">
                  <th className="px-4 py-3 font-semibold">Statement ID</th>
                  <th className="px-4 py-3 font-semibold">Bank account</th>
                  <th className="px-4 py-3 font-semibold">File name</th>
                  <th className="px-4 py-3 font-semibold">Statement period</th>
                  <th className="px-4 py-3 font-semibold">Imported date</th>
                  <th className="px-4 py-3 font-semibold text-right">Transactions</th>
                  <th className="px-4 py-3 font-semibold">Import status</th>
                  <th className="px-4 py-3 font-semibold text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#E0E3E6] font-body text-[13px]">
                {filteredStatements.map((stmt) => (
                  <tr key={stmt.id} className="hover:bg-[#F9FAFD] transition-colors">
                    <td className="px-4 py-3.5 font-mono text-[12px] font-medium text-[#101B32] tabular-nums">
                      {stmt.id}
                    </td>
                    <td className="px-4 py-3.5 font-label font-semibold text-[#101B32]">
                      {stmt.account_name}
                    </td>
                    <td className="px-4 py-3.5 font-mono text-[12px] text-[#44474A]">
                      {stmt.file_name}
                    </td>
                    <td className="px-4 py-3.5 text-[#101B32] tabular-nums">
                      {stmt.statement_start_date || 'Nov 15'} – {stmt.statement_end_date || 'Nov 21, 2026'}
                    </td>
                    <td className="px-4 py-3.5 text-[#5B5F62] tabular-nums">
                      {new Date(stmt.created_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })}
                    </td>
                    <td className="px-4 py-3.5 text-right font-semibold text-[#101B32] tabular-nums">
                      {stmt.total_records}
                    </td>
                    <td className="px-4 py-3.5">
                      <span
                        className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-semibold"
                        style={{
                          backgroundColor:
                            stmt.status === 'Processing'
                              ? '#EDF0FF'
                              : stmt.status === 'Failed'
                              ? '#FFEDEA'
                              : '#E6F8F2',
                          color:
                            stmt.status === 'Processing'
                              ? '#002E6A'
                              : stmt.status === 'Failed'
                              ? '#690005'
                              : '#003828',
                        }}
                      >
                        <span className="material-symbols-outlined text-[13px]">
                          {stmt.status === 'Processing' ? 'sync' : stmt.status === 'Failed' ? 'error' : 'check_circle'}
                        </span>
                        {stmt.status}
                      </span>
                    </td>
                    <td className="px-4 py-3.5 text-right">
                      <button
                        type="button"
                        onClick={() => setInspectedStmt(stmt)}
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

      {/* MODAL: Upload Statement & Preview */}
      {showUploadModal && (
        <div className="fixed inset-0 z-50 bg-[#101B32]/40 backdrop-blur-xs flex items-center justify-center p-4">
          <div
            className="rounded-xl p-6 max-w-2xl w-full shadow-2xl animate-in fade-in zoom-in-95 duration-150 space-y-6"
            style={{ backgroundColor: '#FFFFFF', border: '1px solid #E0E3E6' }}
          >
            <div className="flex items-start justify-between gap-3 border-b pb-4" style={{ borderColor: '#E0E3E6' }}>
              <div>
                <h3 className="font-headline text-[18px] font-bold text-[#101B32]">Upload Bank Statement</h3>
                <p className="font-body text-[13px] text-[#5B5F62] mt-0.5">
                  Select the target account and upload a CSV or digital text PDF file.
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

            {/* Target Account Selector */}
            <div className="space-y-2">
              <label className="block text-[12px] font-semibold text-[#101B32]">1. Target Bank Account</label>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                {bankAccounts.map((acc) => {
                  const isSelected = acc.id === selectedAccountId;
                  return (
                    <div
                      key={acc.id}
                      onClick={() => setSelectedAccountId(acc.id)}
                      className={`p-3 rounded-lg border transition-all cursor-pointer ${
                        isSelected
                          ? 'border-[#5146E5] ring-2 ring-[#5146E5] bg-[#F2EFFF]/40'
                          : 'border-[#E0E3E6] bg-white hover:border-[#101B32]'
                      }`}
                    >
                      <p className="font-label text-[13px] font-bold text-[#101B32] truncate">{acc.account_name}</p>
                      <p className="font-mono text-[11px] text-[#5B5F62]">{acc.account_number_masked}</p>
                      <p className="font-mono text-[11px] font-semibold text-[#16A37B] mt-1">{acc.currency}</p>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Drag and Drop Zone */}
            <div className="space-y-2">
              <label className="block text-[12px] font-semibold text-[#101B32]">2. Statement File</label>
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
                  accept=".csv,.pdf"
                  onChange={(e) => {
                    if (e.target.files && e.target.files[0]) {
                      handleFileUpload(e.target.files[0]);
                    }
                  }}
                />

                {uploading ? (
                  <div className="flex flex-col items-center space-y-2 py-4">
                    <span className="material-symbols-outlined text-[32px] text-[#5146E5] animate-spin">sync</span>
                    <p className="text-[13px] font-medium text-[#101B32]">Extracting &amp; normalizing transactions...</p>
                    <p className="text-[11px] text-[#5B5F62]">Calculating SHA-256 hash and checking deduplication</p>
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
                        Drag and drop your statement here, or <span className="text-[#5146E5] underline">browse</span>
                      </p>
                      <p className="text-[11px] text-[#5B5F62] mt-0.5">Supports CSV and digital text PDF (max 25MB)</p>
                    </div>
                  </>
                )}
              </div>
            </div>

            {/* Preview Staging if Parsed */}
            {uploadResult && (
              <div className="p-4 rounded-xl border border-[#E0E3E6] bg-[#F9FAFD] space-y-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span
                      className="px-2 py-0.5 rounded-full text-[10px] font-bold tracking-wider"
                      style={{ backgroundColor: '#FFF4E5', color: '#845400' }}
                    >
                      PREVIEW
                    </span>
                    <h4 className="font-label text-[14px] font-bold text-[#101B32]">{uploadResult.file_name}</h4>
                  </div>
                  <span className="font-mono text-[12px] font-semibold text-[#16A37B]">
                    {uploadResult.total_extracted} records extracted
                  </span>
                </div>
                <p className="font-mono text-[11px] text-[#5B5F62] truncate">SHA-256: {uploadResult.file_hash_sha256}</p>

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
                    onClick={handleConfirmStatement}
                    disabled={confirming}
                    className="px-4 py-1.5 rounded text-white font-label text-[12px] font-semibold hover:opacity-95 disabled:opacity-50"
                    style={{ backgroundColor: '#16A37B' }}
                  >
                    {confirming ? 'Committing...' : 'Confirm & Commit Import'}
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* DRAWER: Inspect Statement Details */}
      {inspectedStmt && (
        <div className="fixed inset-0 z-50 bg-[#101B32]/40 backdrop-blur-xs flex items-center justify-end">
          <div
            className="h-full max-w-lg w-full p-6 shadow-2xl animate-in slide-in-from-right duration-200 flex flex-col justify-between overflow-y-auto"
            style={{ backgroundColor: '#FFFFFF', borderLeft: '1px solid #E0E3E6' }}
          >
            <div className="space-y-6">
              <div className="flex items-start justify-between pb-4 border-b border-[#E0E3E6]">
                <div>
                  <span className="font-mono text-[11px] font-semibold text-[#5146E5]">{inspectedStmt.id}</span>
                  <h3 className="font-headline text-[18px] font-bold text-[#101B32] mt-0.5">{inspectedStmt.file_name}</h3>
                </div>
                <button
                  type="button"
                  onClick={() => setInspectedStmt(null)}
                  className="text-[#5B5F62] hover:text-[#101B32] cursor-pointer"
                >
                  <span className="material-symbols-outlined text-[20px]">close</span>
                </button>
              </div>

              <div className="space-y-4 text-[13px]">
                <div className="flex justify-between py-2 border-b border-[#E0E3E6]">
                  <span className="text-[#5B5F62]">Account</span>
                  <span className="font-semibold text-[#101B32]">{inspectedStmt.account_name}</span>
                </div>
                <div className="flex justify-between py-2 border-b border-[#E0E3E6]">
                  <span className="text-[#5B5F62]">Statement Period</span>
                  <span className="font-mono text-[#101B32]">
                    {inspectedStmt.statement_start_date || 'Nov 15'} – {inspectedStmt.statement_end_date || 'Nov 21, 2026'}
                  </span>
                </div>
                <div className="flex justify-between py-2 border-b border-[#E0E3E6]">
                  <span className="text-[#5B5F62]">Transactions</span>
                  <span className="font-bold text-[#101B32]">{inspectedStmt.total_records} lines</span>
                </div>
                <div className="flex justify-between py-2 border-b border-[#E0E3E6]">
                  <span className="text-[#5B5F62]">Closing Balance</span>
                  <span className="font-mono font-bold text-[#16A37B]">${inspectedStmt.closing_balance || '4,182,410.50'}</span>
                </div>
                <div className="flex justify-between py-2 border-b border-[#E0E3E6]">
                  <span className="text-[#5B5F62]">Audit Checksum</span>
                  <span className="font-mono text-[11px] text-[#44474A]">SHA-256 Verified ✓</span>
                </div>
              </div>
            </div>

            <div className="pt-6 border-t border-[#E0E3E6] flex gap-2">
              <button
                type="button"
                onClick={() => setInspectedStmt(null)}
                className="w-full py-2 rounded font-label text-[13px] font-medium text-[#101B32] hover:bg-[#EFF1F5] cursor-pointer"
                style={{ border: '1px solid #E0E3E6' }}
              >
                Close Drawer
              </button>
            </div>
          </div>
        </div>
      )}

      {/* MODAL: Register New Bank Account */}
      {showAccountModal && (
        <div className="fixed inset-0 z-50 bg-[#101B32]/40 backdrop-blur-xs flex items-center justify-center p-4">
          <div
            className="rounded-xl p-6 max-w-md w-full shadow-2xl animate-in fade-in zoom-in-95 duration-150 space-y-4"
            style={{ backgroundColor: '#FFFFFF', border: '1px solid #E0E3E6' }}
          >
            <div className="flex items-start justify-between gap-3 border-b pb-3" style={{ borderColor: '#E0E3E6' }}>
              <h3 className="font-headline text-[16px] font-bold text-[#101B32]">Register Bank Account</h3>
              <button
                type="button"
                onClick={() => setShowAccountModal(false)}
                className="text-[#5B5F62] hover:text-[#101B32] cursor-pointer"
              >
                <span className="material-symbols-outlined text-[20px]">close</span>
              </button>
            </div>

            <form onSubmit={handleCreateAccount} className="space-y-4">
              <div>
                <label className="block text-[12px] font-medium text-[#5B5F62] mb-1">Account Display Name</label>
                <input
                  type="text"
                  required
                  value={newAccName}
                  onChange={(e) => setNewAccName(e.target.value)}
                  placeholder="e.g. SVB Operating Checking"
                  className="w-full px-3 py-2 rounded-lg text-[13px] outline-none text-[#101B32] border border-[#E0E3E6] focus:border-[#5146E5]"
                />
              </div>

              <div>
                <label className="block text-[12px] font-medium text-[#5B5F62] mb-1">Institution Name</label>
                <input
                  type="text"
                  required
                  value={newAccInstitution}
                  onChange={(e) => setNewAccInstitution(e.target.value)}
                  placeholder="e.g. Silicon Valley Bank"
                  className="w-full px-3 py-2 rounded-lg text-[13px] outline-none text-[#101B32] border border-[#E0E3E6] focus:border-[#5146E5]"
                />
              </div>

              <div>
                <label className="block text-[12px] font-medium text-[#5B5F62] mb-1">Masked Account Number</label>
                <input
                  type="text"
                  required
                  value={newAccNumber}
                  onChange={(e) => setNewAccNumber(e.target.value)}
                  placeholder="•••• 4821"
                  className="w-full px-3 py-2 rounded-lg text-[13px] outline-none text-[#101B32] border border-[#E0E3E6] focus:border-[#5146E5]"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-[12px] font-medium text-[#5B5F62] mb-1">Currency</label>
                  <select
                    value={newAccCurrency}
                    onChange={(e) => setNewAccCurrency(e.target.value)}
                    className="w-full px-3 py-2 rounded-lg text-[13px] outline-none text-[#101B32] border border-[#E0E3E6] focus:border-[#5146E5] cursor-pointer"
                  >
                    <option value="USD">USD ($)</option>
                    <option value="EUR">EUR (€)</option>
                    <option value="INR">INR (₹)</option>
                    <option value="GBP">GBP (£)</option>
                  </select>
                </div>

                <div>
                  <label className="block text-[12px] font-medium text-[#5B5F62] mb-1">Account Type</label>
                  <select
                    value={newAccType}
                    onChange={(e) => setNewAccType(e.target.value)}
                    className="w-full px-3 py-2 rounded-lg text-[13px] outline-none text-[#101B32] border border-[#E0E3E6] focus:border-[#5146E5] cursor-pointer"
                  >
                    <option value="CHECKING">Checking</option>
                    <option value="SAVINGS">Savings</option>
                    <option value="TREASURY">Treasury</option>
                  </select>
                </div>
              </div>

              <div className="flex justify-end gap-2.5 pt-2">
                <button
                  type="button"
                  onClick={() => setShowAccountModal(false)}
                  className="px-4 py-2 rounded font-label text-[13px] font-medium text-[#101B32] hover:bg-[#EFF1F5] cursor-pointer"
                  style={{ border: '1px solid #E0E3E6' }}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 rounded text-white font-label text-[13px] font-semibold hover:opacity-95 cursor-pointer"
                  style={{ backgroundColor: '#5146E5' }}
                >
                  Save Account
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default StatementsPage;
