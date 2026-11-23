import React, { useState, useEffect } from 'react';
import { apiClient } from '../api/client';
import {
  ReviewQueueItem,
  ReviewWorkspaceDetail,
  ReviewCategory,
  ReviewStatus,
  ReviewPriority,
} from '../types';
import {
  CheckCircle2,
  XCircle,
  HelpCircle,
  FileQuestion,
  RefreshCw,
  SlidersHorizontal,
  ChevronRight,
  Sparkles,
  Scale,
  ArrowRightLeft,
  Clock,
  UserCheck,
  AlertTriangle,
  MessageSquare,
  Lock,
  Layers,
} from 'lucide-react';

const CATEGORY_LABELS: Record<ReviewCategory, { label: string; desc: string }> = {
  LOW_CONFIDENCE: { label: 'Low Confidence', desc: 'AI confidence score is below automated matching threshold' },
  MULTIPLE_MATCHES: { label: 'Multiple Matches', desc: 'Multiple candidate ledger entries found with similar attributes' },
  AMOUNT_MISMATCH: { label: 'Amount Mismatch', desc: 'Potential variance, discounts, or fee deductions detected' },
  MISSING_LEDGER_ENTRY: { label: 'Missing Ledger', desc: 'No internal GL entry corresponds to recorded bank transaction' },
  MISSING_BANK_TRANSACTION: { label: 'Missing Bank Tx', desc: 'Ledger entry posted without matching bank settlement' },
  DUPLICATE_TRANSACTION: { label: 'Duplicate Tx', desc: 'Potential duplicate posting or duplicate statement import' },
  CURRENCY_MISMATCH: { label: 'Currency Mismatch', desc: 'Cross-currency transaction requiring exchange rate verification' },
  POSSIBLE_REVERSAL: { label: 'Possible Reversal', desc: 'Matching debit/credit pair suspected as bank charge reversal' },
  POSSIBLE_REFUND: { label: 'Possible Refund', desc: 'Customer or vendor return transaction requiring link' },
};

export const ReviewQueuePage: React.FC = () => {
  const [queueItems, setQueueItems] = useState<ReviewQueueItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [activeCategory, setActiveCategory] = useState<string>('ALL');
  const [activeStatus, setActiveStatus] = useState<string>('PENDING');
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Selected item workspace detail
  const [selectedReviewId, setSelectedReviewId] = useState<string | null>(null);
  const [workspace, setWorkspace] = useState<ReviewWorkspaceDetail | null>(null);
  const [workspaceLoading, setWorkspaceLoading] = useState<boolean>(false);

  // Modal / Action states
  const [approvalNotes, setApprovalNotes] = useState<string>('');
  const [rejectReason, setRejectReason] = useState<string>('');
  const [unresolvedReason, setUnresolvedReason] = useState<string>('');
  const [investigationNotes, setInvestigationNotes] = useState<string>('');
  const [newNoteContent, setNewNoteContent] = useState<string>('');
  const [noteType, setNoteType] = useState<string>('GENERAL');
  
  // Maker-checker adjustment proposal state
  const [showAdjustmentForm, setShowAdjustmentForm] = useState<boolean>(false);
  const [adjAmount, setAdjAmount] = useState<string>('');
  const [adjReason, setAdjReason] = useState<string>('');
  const [adjLedgerId, setAdjLedgerId] = useState<string>('');

  // Active action modal
  const [activeModal, setActiveModal] = useState<
    'NONE' | 'APPROVE' | 'REJECT' | 'UNRESOLVED' | 'INVESTIGATE' | 'NOTE' | 'REMAP'
  >('NONE');
  const [remapLedgerId, setRemapLedgerId] = useState<string>('');
  const [remapReason, setRemapReason] = useState<string>('');

  const loadQueue = async () => {
    setLoading(true);
    setErrorMsg(null);
    try {
      const params: { category?: string; status?: string } = {};
      if (activeCategory !== 'ALL') params.category = activeCategory;
      if (activeStatus !== 'ALL') params.status = activeStatus;
      const items = await apiClient.getReviewQueue(params);
      setQueueItems(items);
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : 'Failed to load review queue');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadQueue();
  }, [activeCategory, activeStatus]);

  const openWorkspace = async (reviewId: string) => {
    setSelectedReviewId(reviewId);
    setWorkspaceLoading(true);
    setErrorMsg(null);
    try {
      const details = await apiClient.getReviewWorkspace(reviewId);
      setWorkspace(details);
      if (details.proposed_candidate) {
        setAdjLedgerId(details.proposed_candidate.id);
      }
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : 'Failed to load review workspace');
    } finally {
      setWorkspaceLoading(false);
    }
  };

  const handleApprove = async () => {
    if (!selectedReviewId) return;
    try {
      await apiClient.approveReviewMatch(selectedReviewId, { review_notes: approvalNotes });
      setSuccessMsg('Match successfully approved and reconciled.');
      setActiveModal('NONE');
      setApprovalNotes('');
      openWorkspace(selectedReviewId);
      loadQueue();
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : 'Failed to approve match');
    }
  };

  const handleReject = async () => {
    if (!selectedReviewId || !rejectReason.trim()) return;
    try {
      await apiClient.rejectReviewMatch(selectedReviewId, { reason: rejectReason });
      setSuccessMsg('Match candidate rejected. Bank transaction reset to UNMATCHED.');
      setActiveModal('NONE');
      setRejectReason('');
      openWorkspace(selectedReviewId);
      loadQueue();
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : 'Failed to reject match');
    }
  };

  const handleMarkUnresolved = async () => {
    if (!selectedReviewId || !unresolvedReason.trim()) return;
    try {
      await apiClient.markReviewUnresolved(selectedReviewId, { reason: unresolvedReason });
      setSuccessMsg('Marked as unresolved exception.');
      setActiveModal('NONE');
      setUnresolvedReason('');
      openWorkspace(selectedReviewId);
      loadQueue();
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : 'Failed to mark unresolved');
    }
  };

  const handleInvestigation = async () => {
    if (!selectedReviewId || !investigationNotes.trim()) return;
    try {
      await apiClient.requestInvestigation(selectedReviewId, {
        investigation_notes: investigationNotes,
      });
      setSuccessMsg('Investigation requested. Priority raised to HIGH.');
      setActiveModal('NONE');
      setInvestigationNotes('');
      openWorkspace(selectedReviewId);
      loadQueue();
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : 'Failed to request investigation');
    }
  };

  const handleAddNote = async () => {
    if (!selectedReviewId || !newNoteContent.trim()) return;
    try {
      await apiClient.addReviewNote(selectedReviewId, {
        note_type: noteType,
        content: newNoteContent,
      });
      setSuccessMsg('Review note logged successfully.');
      setActiveModal('NONE');
      setNewNoteContent('');
      openWorkspace(selectedReviewId);
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : 'Failed to add note');
    }
  };

  const handleRemap = async () => {
    if (!selectedReviewId || !remapLedgerId || !remapReason.trim()) return;
    try {
      await apiClient.remapReviewCandidate(selectedReviewId, {
        ledger_entry_id: remapLedgerId,
        reason: remapReason,
      });
      setSuccessMsg('Candidate remapped and evaluated against deterministic rules.');
      setActiveModal('NONE');
      setRemapReason('');
      openWorkspace(selectedReviewId);
      loadQueue();
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : 'Failed to remap candidate');
    }
  };

  const handleProposeAdjustment = async () => {
    if (!selectedReviewId || !adjAmount || !adjReason.trim() || !adjLedgerId) return;
    try {
      await apiClient.proposeAdjustment(selectedReviewId, {
        adjustment_amount: adjAmount,
        adjustment_reason: adjReason,
        target_ledger_id: adjLedgerId,
      });
      setSuccessMsg('Adjustment proposal created. Awaiting second checker approval.');
      setShowAdjustmentForm(false);
      setAdjAmount('');
      setAdjReason('');
      openWorkspace(selectedReviewId);
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : 'Failed to submit adjustment proposal');
    }
  };

  const handleDecideAdjustment = async (proposalId: string, approved: boolean) => {
    try {
      await apiClient.decideAdjustment(proposalId, {
        approved,
        decision_notes: approved ? 'Approved by checker' : 'Rejected by checker',
      });
      setSuccessMsg(approved ? 'Adjustment proposal approved by checker.' : 'Adjustment proposal rejected.');
      if (selectedReviewId) openWorkspace(selectedReviewId);
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : 'Failed to decide adjustment');
    }
  };

  const getPriorityBadge = (priority: ReviewPriority) => {
    switch (priority) {
      case 'CRITICAL':
        return <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-red-100 text-red-800">Critical</span>;
      case 'HIGH':
        return <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-amber-100 text-amber-800">High</span>;
      case 'MEDIUM':
        return <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-blue-100 text-blue-800">Medium</span>;
      default:
        return <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-slate-100 text-slate-700">Low</span>;
    }
  };

  const getStatusBadge = (status: ReviewStatus) => {
    switch (status) {
      case 'APPROVED':
        return <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-100 text-emerald-800"><CheckCircle2 className="w-3.5 h-3.5" /> Approved</span>;
      case 'REJECTED':
        return <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-rose-100 text-rose-800"><XCircle className="w-3.5 h-3.5" /> Rejected</span>;
      case 'INVESTIGATION_REQUESTED':
        return <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-purple-100 text-purple-800"><AlertTriangle className="w-3.5 h-3.5" /> Investigating</span>;
      case 'UNRESOLVED':
        return <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-amber-100 text-amber-800"><HelpCircle className="w-3.5 h-3.5" /> Unresolved</span>;
      case 'IN_REVIEW':
        return <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800"><Clock className="w-3.5 h-3.5" /> In Review</span>;
      default:
        return <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-slate-100 text-slate-800"><FileQuestion className="w-3.5 h-3.5" /> Pending</span>;
    }
  };

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-6">
      {/* Page Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-indigo-50 border border-indigo-200 flex items-center justify-center text-indigo-600">
              <UserCheck className="w-6 h-6" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Human Review & Approval Workspace</h1>
              <p className="text-sm text-slate-500">
                Exception triage, candidate remapping, and maker-checker dual authorization.
              </p>
            </div>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => loadQueue()}
            disabled={loading}
            className="inline-flex items-center gap-2 px-3.5 py-2 border border-slate-300 rounded-lg text-sm font-medium text-slate-700 bg-white hover:bg-slate-50 shadow-sm transition-colors"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            Refresh Queue
          </button>
        </div>
      </div>

      {/* Notifications */}
      {errorMsg && (
        <div className="p-4 rounded-lg bg-rose-50 border border-rose-200 text-rose-700 text-sm flex items-center justify-between">
          <span>{errorMsg}</span>
          <button onClick={() => setErrorMsg(null)} className="text-rose-500 hover:text-rose-700 font-bold ml-4">✕</button>
        </div>
      )}
      {successMsg && (
        <div className="p-4 rounded-lg bg-emerald-50 border border-emerald-200 text-emerald-700 text-sm flex items-center justify-between">
          <span>{successMsg}</span>
          <button onClick={() => setSuccessMsg(null)} className="text-emerald-500 hover:text-emerald-700 font-bold ml-4">✕</button>
        </div>
      )}

      {/* Category Pills Filter */}
      <div className="space-y-2">
        <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider flex items-center gap-1.5">
          <SlidersHorizontal className="w-3.5 h-3.5" />
          Review Queue Categories
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            onClick={() => setActiveCategory('ALL')}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
              activeCategory === 'ALL'
                ? 'bg-slate-900 text-white shadow-sm'
                : 'bg-white text-slate-600 border border-slate-200 hover:bg-slate-50'
            }`}
          >
            All Exceptions
          </button>
          {Object.entries(CATEGORY_LABELS).map(([catKey, val]) => (
            <button
              key={catKey}
              onClick={() => setActiveCategory(catKey)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors flex items-center gap-1.5 ${
                activeCategory === catKey
                  ? 'bg-indigo-600 text-white shadow-sm'
                  : 'bg-white text-slate-600 border border-slate-200 hover:bg-slate-50'
              }`}
            >
              <span>{val.label}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Status Bar Filter */}
      <div className="flex items-center justify-between border-b border-slate-200 pb-3">
        <div className="flex items-center gap-2">
          {(['ALL', 'PENDING', 'IN_REVIEW', 'APPROVED', 'REJECTED', 'UNRESOLVED', 'INVESTIGATION_REQUESTED'] as const).map(
            (st) => (
              <button
                key={st}
                onClick={() => setActiveStatus(st)}
                className={`px-3 py-1 text-xs font-medium rounded-md transition-colors ${
                  activeStatus === st
                    ? 'bg-indigo-50 text-indigo-700 font-semibold'
                    : 'text-slate-500 hover:text-slate-800'
                }`}
              >
                {st.replace('_', ' ')}
              </button>
            )
          )}
        </div>
        <div className="text-xs text-slate-500">
          Showing <span className="font-semibold text-slate-800">{queueItems.length}</span> exceptions
        </div>
      </div>

      {/* Main Review Workspace Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Side: Queue List (4 columns) */}
        <div className="lg:col-span-5 space-y-3">
          {loading ? (
            <div className="bg-white rounded-xl border border-slate-200 p-8 text-center text-slate-500">
              <RefreshCw className="w-6 h-6 animate-spin mx-auto mb-2 text-indigo-600" />
              Loading review items...
            </div>
          ) : queueItems.length === 0 ? (
            <div className="bg-white rounded-xl border border-slate-200 p-8 text-center text-slate-500">
              <CheckCircle2 className="w-8 h-8 mx-auto mb-2 text-emerald-500" />
              <div className="font-medium text-slate-800">Review Queue Clear</div>
              <p className="text-xs text-slate-400 mt-1">No items match the selected category and status filters.</p>
            </div>
          ) : (
            queueItems.map((item) => (
              <div
                key={item.id}
                onClick={() => openWorkspace(item.id)}
                className={`p-4 rounded-xl border transition-all cursor-pointer bg-white ${
                  selectedReviewId === item.id
                    ? 'border-indigo-600 shadow-md ring-2 ring-indigo-100'
                    : 'border-slate-200 hover:border-slate-300 hover:shadow-sm'
                }`}
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="flex items-center gap-2">
                    {getPriorityBadge(item.priority)}
                    <span className="text-xs font-medium px-2 py-0.5 rounded bg-slate-100 text-slate-700">
                      {CATEGORY_LABELS[item.category]?.label || item.category}
                    </span>
                  </div>
                  {item.requires_maker_checker && (
                    <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-amber-700 bg-amber-50 px-2 py-0.5 rounded border border-amber-200">
                      <Lock className="w-3 h-3" /> Maker-Checker
                    </span>
                  )}
                </div>

                <div className="mt-3 flex items-center justify-between">
                  <div className="space-y-0.5">
                    <div className="text-sm font-bold text-slate-900 font-mono">
                      {item.bank_currency || 'USD'} {item.bank_amount || '0.00'}
                    </div>
                    <div className="text-xs text-slate-500 truncate max-w-[220px]">
                      {item.bank_description || 'Unspecified Transaction'}
                    </div>
                  </div>
                  {item.confidence_score && (
                    <div className="text-right">
                      <div className="text-xs font-semibold text-indigo-600 flex items-center gap-1">
                        <Sparkles className="w-3 h-3" />
                        {(parseFloat(item.confidence_score) * 100).toFixed(0)}% AI Match
                      </div>
                      <div className="text-[11px] text-slate-400">
                        {item.bank_booking_date || 'No Date'}
                      </div>
                    </div>
                  )}
                </div>

                <div className="mt-3 pt-2.5 border-t border-slate-100 flex items-center justify-between text-xs">
                  <div>{getStatusBadge(item.status)}</div>
                  <span className="text-indigo-600 font-medium inline-flex items-center gap-0.5">
                    Inspect <ChevronRight className="w-3.5 h-3.5" />
                  </span>
                </div>
              </div>
            ))
          )}
        </div>

        {/* Right Side: Detailed Workspace Panel (7 columns) */}
        <div className="lg:col-span-7">
          {workspaceLoading ? (
            <div className="bg-white rounded-xl border border-slate-200 p-12 text-center text-slate-500">
              <RefreshCw className="w-8 h-8 animate-spin mx-auto mb-3 text-indigo-600" />
              Loading inspection workspace...
            </div>
          ) : !workspace ? (
            <div className="bg-slate-50 rounded-xl border border-dashed border-slate-300 p-12 text-center text-slate-500">
              <Layers className="w-10 h-10 mx-auto mb-3 text-slate-400" />
              <div className="font-semibold text-slate-700">Select an item from the queue</div>
              <p className="text-xs text-slate-400 mt-1">
                View original bank statements, AI explanation, deterministic rule evaluations, and maker-checker adjustments.
              </p>
            </div>
          ) : (
            <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden space-y-6 p-6">
              {/* Workspace Header */}
              <div className="flex items-start justify-between pb-4 border-b border-slate-200">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-bold px-2 py-0.5 rounded bg-indigo-50 text-indigo-700 border border-indigo-200">
                      {CATEGORY_LABELS[workspace.category]?.label || workspace.category}
                    </span>
                    {getPriorityBadge(workspace.priority)}
                    {getStatusBadge(workspace.status)}
                  </div>
                  <h2 className="text-lg font-bold text-slate-900 mt-1">
                    Transaction Reconciliation Review
                  </h2>
                  <p className="text-xs text-slate-500">
                    ID: <span className="font-mono">{workspace.id}</span>
                  </p>
                </div>

                {workspace.requires_maker_checker && (
                  <div className="bg-amber-50 border border-amber-200 rounded-lg p-2.5 text-right">
                    <div className="flex items-center justify-end gap-1 text-xs font-bold text-amber-800">
                      <Lock className="w-3.5 h-3.5" /> Maker-Checker Dual Control
                    </div>
                    <div className="text-[11px] text-amber-700">
                      Requires two distinct authorized approvals
                    </div>
                  </div>
                )}
              </div>

              {/* Side-by-Side: Bank Transaction vs Proposed Ledger Entry */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* Bank Transaction Card */}
                <div className="p-4 rounded-lg bg-slate-50 border border-slate-200 space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-slate-600 uppercase tracking-wide">
                      Bank Transaction (Statement)
                    </span>
                    <span className="text-xs font-semibold px-1.5 py-0.5 rounded bg-slate-200 text-slate-700">
                      {workspace.bank_transaction?.direction || 'DEBIT'}
                    </span>
                  </div>

                  {workspace.bank_transaction ? (
                    <div className="space-y-2">
                      <div>
                        <div className="text-xs text-slate-400">Amount & Currency</div>
                        <div className="text-xl font-bold font-mono text-slate-900">
                          {workspace.bank_transaction.currency} {workspace.bank_transaction.amount}
                        </div>
                      </div>
                      <div>
                        <div className="text-xs text-slate-400">Normalized Description</div>
                        <div className="text-xs font-medium text-slate-800">
                          {workspace.bank_transaction.normalized_description}
                        </div>
                      </div>
                      <div>
                        <div className="text-xs text-slate-400">Raw Source Description</div>
                        <div className="text-[11px] font-mono text-slate-600 bg-white p-1.5 rounded border border-slate-200">
                          {workspace.bank_transaction.raw_description || 'N/A'}
                        </div>
                      </div>
                      <div className="grid grid-cols-2 gap-2 text-xs pt-1">
                        <div>
                          <span className="text-slate-400">Booking Date:</span>{' '}
                          <span className="font-medium text-slate-800">{workspace.bank_transaction.booking_date}</span>
                        </div>
                        <div>
                          <span className="text-slate-400">Ref ID:</span>{' '}
                          <span className="font-mono text-slate-800">{workspace.bank_transaction.reference_id || 'None'}</span>
                        </div>
                      </div>
                    </div>
                  ) : (
                    <div className="text-xs text-slate-400">No bank transaction associated.</div>
                  )}
                </div>

                {/* Proposed Ledger Entry Card */}
                <div className="p-4 rounded-lg bg-indigo-50/50 border border-indigo-200 space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-indigo-900 uppercase tracking-wide">
                      Proposed Ledger Entry (GL)
                    </span>
                    <span className="text-xs font-semibold px-1.5 py-0.5 rounded bg-indigo-100 text-indigo-800">
                      {workspace.proposed_candidate?.direction || 'CREDIT'}
                    </span>
                  </div>

                  {workspace.proposed_candidate ? (
                    <div className="space-y-2">
                      <div>
                        <div className="text-xs text-indigo-500">GL Amount & Currency</div>
                        <div className="text-xl font-bold font-mono text-slate-900">
                          {workspace.proposed_candidate.currency} {workspace.proposed_candidate.amount}
                        </div>
                      </div>
                      <div>
                        <div className="text-xs text-indigo-500">Description</div>
                        <div className="text-xs font-medium text-slate-800">
                          {workspace.proposed_candidate.description}
                        </div>
                      </div>
                      <div className="grid grid-cols-2 gap-2 text-xs pt-1">
                        <div>
                          <span className="text-indigo-400">Posting Date:</span>{' '}
                          <span className="font-medium text-slate-800">{workspace.proposed_candidate.posting_date}</span>
                        </div>
                        <div>
                          <span className="text-indigo-400">Account Code:</span>{' '}
                          <span className="font-mono text-slate-800">{workspace.proposed_candidate.account_code}</span>
                        </div>
                        <div>
                          <span className="text-indigo-400">Entry ID:</span>{' '}
                          <span className="font-mono text-slate-800">{workspace.proposed_candidate.entry_id}</span>
                        </div>
                        <div>
                          <span className="text-indigo-400">Journal ID:</span>{' '}
                          <span className="font-mono text-slate-800">{workspace.proposed_candidate.journal_id || 'None'}</span>
                        </div>
                      </div>
                    </div>
                  ) : (
                    <div className="text-xs text-indigo-400">No proposed ledger candidate available.</div>
                  )}
                </div>
              </div>

              {/* AI Reasoning & Signals */}
              {workspace.ai_explanation && (
                <div className="p-4 rounded-lg bg-gradient-to-r from-purple-50 to-indigo-50 border border-purple-200 space-y-2">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-1.5 text-xs font-bold text-purple-900">
                      <Sparkles className="w-4 h-4 text-purple-600" />
                      AI Match Recommendation Engine
                    </div>
                    {workspace.ai_confidence_score && (
                      <span className="text-xs font-semibold px-2 py-0.5 rounded bg-purple-100 text-purple-800">
                        Confidence: {(parseFloat(workspace.ai_confidence_score) * 100).toFixed(0)}%
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-purple-950 leading-relaxed font-sans">
                    {workspace.ai_explanation}
                  </p>
                  {workspace.ai_signals && workspace.ai_signals.length > 0 && (
                    <div className="flex flex-wrap gap-1.5 pt-1">
                      {workspace.ai_signals.map((sig, idx) => (
                        <span key={idx} className="text-[11px] bg-white/80 border border-purple-200 px-2 py-0.5 rounded text-purple-900">
                          ✓ {sig}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {/* Deterministic Validation Rules Checklist */}
              {workspace.deterministic_validation && (
                <div className="p-4 rounded-lg bg-slate-50 border border-slate-200 space-y-3">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-1.5 text-xs font-bold text-slate-700">
                      <Scale className="w-4 h-4 text-indigo-600" />
                      Deterministic Financial Rule Validations
                    </div>
                    <span
                      className={`text-xs font-semibold px-2 py-0.5 rounded ${
                        workspace.deterministic_validation.is_valid
                          ? 'bg-emerald-100 text-emerald-800'
                          : 'bg-rose-100 text-rose-800'
                      }`}
                    >
                      {workspace.deterministic_validation.is_valid ? 'Validation Passed' : 'Rule Violation Detected'}
                    </span>
                  </div>

                  <div className="grid grid-cols-2 md:grid-cols-3 gap-2 text-xs">
                    <div className="flex items-center gap-1.5">
                      {workspace.deterministic_validation.currency_parity_passed ? (
                        <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                      ) : (
                        <XCircle className="w-3.5 h-3.5 text-rose-600" />
                      )}
                      <span>Currency Parity</span>
                    </div>
                    <div className="flex items-center gap-1.5">
                      {workspace.deterministic_validation.direction_parity_passed ? (
                        <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                      ) : (
                        <XCircle className="w-3.5 h-3.5 text-rose-600" />
                      )}
                      <span>Debit/Credit Direction</span>
                    </div>
                    <div className="flex items-center gap-1.5">
                      {workspace.deterministic_validation.amount_parity_passed ? (
                        <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                      ) : (
                        <XCircle className="w-3.5 h-3.5 text-rose-600" />
                      )}
                      <span>Amount Equality</span>
                    </div>
                    <div className="flex items-center gap-1.5">
                      {workspace.deterministic_validation.date_window_passed ? (
                        <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                      ) : (
                        <XCircle className="w-3.5 h-3.5 text-rose-600" />
                      )}
                      <span>Date In-Window</span>
                    </div>
                    <div className="flex items-center gap-1.5">
                      {workspace.deterministic_validation.unconsumed_check_passed ? (
                        <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                      ) : (
                        <XCircle className="w-3.5 h-3.5 text-rose-600" />
                      )}
                      <span>Unconsumed Status</span>
                    </div>
                    <div className="flex items-center gap-1.5">
                      {workspace.deterministic_validation.reversal_check_passed ? (
                        <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                      ) : (
                        <XCircle className="w-3.5 h-3.5 text-rose-600" />
                      )}
                      <span>Non-Reversal Safety</span>
                    </div>
                  </div>

                  {workspace.deterministic_validation.failure_reason && (
                    <div className="text-xs text-rose-700 bg-rose-50 p-2 rounded border border-rose-200">
                      Reason: {workspace.deterministic_validation.failure_reason}
                    </div>
                  )}
                </div>
              )}

              {/* Maker-Checker Adjustment Section */}
              {workspace.requires_maker_checker && (
                <div className="p-4 rounded-lg bg-amber-50/60 border border-amber-200 space-y-3">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-1.5 text-xs font-bold text-amber-900">
                      <Lock className="w-4 h-4 text-amber-600" />
                      Financial Adjustment Dual Authorization
                    </div>
                    <button
                      onClick={() => setShowAdjustmentForm(!showAdjustmentForm)}
                      className="text-xs font-medium text-amber-800 hover:text-amber-900 underline"
                    >
                      {showAdjustmentForm ? 'Cancel Proposal' : '+ Propose Adjustment'}
                    </button>
                  </div>

                  {showAdjustmentForm && (
                    <div className="space-y-3 p-3 bg-white rounded border border-amber-200">
                      <div className="text-xs font-semibold text-slate-800">
                        Propose Amount Variance / Fee Adjustment
                      </div>
                      <div className="grid grid-cols-2 gap-3">
                        <div>
                          <label className="text-[11px] text-slate-500 font-medium">Adjustment Amount ($)</label>
                          <input
                            type="number"
                            step="0.01"
                            value={adjAmount}
                            onChange={(e) => setAdjAmount(e.target.value)}
                            placeholder="e.g. 25.00"
                            className="w-full text-xs p-2 border border-slate-300 rounded focus:ring-1 focus:ring-amber-500"
                          />
                        </div>
                        <div>
                          <label className="text-[11px] text-slate-500 font-medium">Target Ledger ID</label>
                          <input
                            type="text"
                            value={adjLedgerId}
                            onChange={(e) => setAdjLedgerId(e.target.value)}
                            placeholder="Ledger entry UUID"
                            className="w-full text-xs p-2 border border-slate-300 rounded font-mono"
                          />
                        </div>
                      </div>
                      <div>
                        <label className="text-[11px] text-slate-500 font-medium">Business Justification / Reason</label>
                        <input
                          type="text"
                          value={adjReason}
                          onChange={(e) => setAdjReason(e.target.value)}
                          placeholder="e.g. International wire processing fee deducted at source"
                          className="w-full text-xs p-2 border border-slate-300 rounded"
                        />
                      </div>
                      <button
                        onClick={handleProposeAdjustment}
                        className="w-full py-1.5 bg-amber-600 hover:bg-amber-700 text-white text-xs font-semibold rounded shadow-sm"
                      >
                        Submit Adjustment Proposal
                      </button>
                    </div>
                  )}

                  {/* Existing Adjustment Proposals List */}
                  {workspace.adjustment_proposals && workspace.adjustment_proposals.length > 0 ? (
                    <div className="space-y-2">
                      {workspace.adjustment_proposals.map((prop) => (
                        <div key={prop.id} className="p-2.5 rounded bg-white border border-amber-200 text-xs flex items-center justify-between">
                          <div>
                            <div className="font-semibold text-slate-800">
                              Variance: ${prop.adjustment_amount} — {prop.adjustment_reason}
                            </div>
                            <div className="text-[11px] text-slate-400">
                              Status: <span className="font-semibold text-amber-700">{prop.status}</span> | Maker ID: {prop.maker_id.slice(0, 8)}...
                            </div>
                          </div>
                          {prop.status === 'PENDING_APPROVAL' && (
                            <div className="flex items-center gap-1.5">
                              <button
                                onClick={() => handleDecideAdjustment(prop.id, true)}
                                className="px-2.5 py-1 bg-emerald-600 hover:bg-emerald-700 text-white font-medium rounded text-xs"
                                title="Approve as Checker (Maker cannot self-approve)"
                              >
                                Approve (Checker)
                              </button>
                              <button
                                onClick={() => handleDecideAdjustment(prop.id, false)}
                                className="px-2 py-1 bg-rose-50 hover:bg-rose-100 text-rose-700 border border-rose-200 rounded text-xs"
                              >
                                Reject
                              </button>
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="text-xs text-amber-800/80">
                      No adjustments proposed. Maker-checker signoff is required before final match approval.
                    </div>
                  )}
                </div>
              )}

              {/* Alternative Candidates for Remapping */}
              {workspace.alternative_candidates && workspace.alternative_candidates.length > 0 && (
                <div className="p-4 rounded-lg bg-slate-50 border border-slate-200 space-y-2">
                  <div className="text-xs font-bold text-slate-700 flex items-center gap-1.5">
                    <ArrowRightLeft className="w-3.5 h-3.5 text-indigo-600" />
                    Alternative Ledger Candidates
                  </div>
                  <div className="space-y-1.5">
                    {workspace.alternative_candidates.map((alt) => (
                      <div
                        key={alt.id}
                        className="p-2 bg-white rounded border border-slate-200 text-xs flex items-center justify-between hover:bg-slate-50"
                      >
                        <div>
                          <span className="font-mono font-bold text-slate-800">{alt.currency} {alt.amount}</span>
                          <span className="text-slate-400 mx-1.5">|</span>
                          <span className="text-slate-600">{alt.description}</span>
                          <span className="text-slate-400 ml-2 font-mono">({alt.entry_id})</span>
                        </div>
                        <button
                          onClick={() => {
                            setRemapLedgerId(alt.id);
                            setActiveModal('REMAP');
                          }}
                          className="text-xs text-indigo-600 hover:text-indigo-800 font-medium"
                        >
                          Remap to this →
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Reviewer Action Buttons */}
              <div className="p-4 bg-slate-50 border border-slate-200 rounded-lg space-y-3">
                <div className="text-xs font-bold text-slate-700 uppercase tracking-wide">
                  Reviewer Decision Actions
                </div>
                <div className="flex flex-wrap gap-2">
                  <button
                    onClick={() => setActiveModal('APPROVE')}
                    className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-xs font-semibold shadow-sm transition-colors flex items-center gap-1.5"
                  >
                    <CheckCircle2 className="w-4 h-4" /> Approve Match
                  </button>
                  <button
                    onClick={() => setActiveModal('REJECT')}
                    className="px-3.5 py-2 bg-rose-600 hover:bg-rose-700 text-white rounded-lg text-xs font-semibold shadow-sm transition-colors flex items-center gap-1.5"
                  >
                    <XCircle className="w-4 h-4" /> Reject Candidate
                  </button>
                  <button
                    onClick={() => setActiveModal('UNRESOLVED')}
                    className="px-3.5 py-2 bg-white border border-slate-300 text-slate-700 hover:bg-slate-50 rounded-lg text-xs font-semibold shadow-sm transition-colors flex items-center gap-1.5"
                  >
                    <HelpCircle className="w-4 h-4 text-amber-500" /> Mark Unresolved
                  </button>
                  <button
                    onClick={() => setActiveModal('INVESTIGATE')}
                    className="px-3.5 py-2 bg-white border border-purple-300 text-purple-700 hover:bg-purple-50 rounded-lg text-xs font-semibold shadow-sm transition-colors flex items-center gap-1.5"
                  >
                    <AlertTriangle className="w-4 h-4 text-purple-600" /> Request Investigation
                  </button>
                  <button
                    onClick={() => setActiveModal('NOTE')}
                    className="px-3.5 py-2 bg-white border border-slate-300 text-slate-700 hover:bg-slate-50 rounded-lg text-xs font-semibold shadow-sm transition-colors flex items-center gap-1.5"
                  >
                    <MessageSquare className="w-4 h-4 text-indigo-500" /> Add Observation Note
                  </button>
                </div>
              </div>

              {/* Notes & Audit History Logs */}
              <div className="space-y-4 pt-2">
                <div className="flex items-center justify-between border-b border-slate-200 pb-2">
                  <div className="text-xs font-bold text-slate-700 flex items-center gap-1.5">
                    <Clock className="w-3.5 h-3.5 text-slate-500" />
                    Audit Trail & Reviewer Notes
                  </div>
                </div>

                <div className="space-y-2 max-h-56 overflow-y-auto pr-1">
                  {workspace.notes && workspace.notes.length > 0 ? (
                    workspace.notes.map((n) => (
                      <div key={n.id} className="p-2.5 rounded bg-slate-50 border border-slate-200 text-xs">
                        <div className="flex items-center justify-between text-[11px] text-slate-400 mb-1">
                          <span className="font-semibold text-slate-600">{n.note_type}</span>
                          <span>{new Date(n.created_at).toLocaleString()}</span>
                        </div>
                        <p className="text-slate-800">{n.content}</p>
                      </div>
                    ))
                  ) : (
                    <div className="text-xs text-slate-400 py-2">No reviewer notes logged yet.</div>
                  )}

                  {workspace.audit_history && workspace.audit_history.length > 0 && (
                    <div className="pt-2 border-t border-slate-100">
                      <div className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider mb-1.5">
                        Historical Audit Events
                      </div>
                      {workspace.audit_history.map((ev) => (
                        <div key={ev.id} className="text-[11px] py-1 text-slate-500 flex items-center justify-between">
                          <span className="font-mono text-slate-700">{ev.action}</span>
                          <span>{new Date(ev.timestamp).toLocaleTimeString()}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Modal Actions */}
      {activeModal === 'APPROVE' && (
        <div className="fixed inset-0 bg-slate-900/50 flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-xl max-w-md w-full p-6 space-y-4 shadow-xl">
            <h3 className="text-base font-bold text-slate-900 flex items-center gap-2">
              <CheckCircle2 className="w-5 h-5 text-emerald-600" />
              Confirm Match Approval
            </h3>
            <p className="text-xs text-slate-600">
              This will update both the bank transaction and candidate ledger entry to RECONCILED.
            </p>
            <div>
              <label className="text-xs text-slate-600 font-medium">Approval Notes (Optional)</label>
              <textarea
                value={approvalNotes}
                onChange={(e) => setApprovalNotes(e.target.value)}
                placeholder="e.g. Cross-referenced with invoice #INV-4921"
                className="w-full text-xs p-2.5 border border-slate-300 rounded-lg mt-1 h-20"
              />
            </div>
            <div className="flex justify-end gap-2">
              <button
                onClick={() => setActiveModal('NONE')}
                className="px-3.5 py-1.5 border border-slate-300 rounded-lg text-xs font-semibold text-slate-700 hover:bg-slate-50"
              >
                Cancel
              </button>
              <button
                onClick={handleApprove}
                className="px-4 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-xs font-semibold shadow-sm"
              >
                Confirm Approval
              </button>
            </div>
          </div>
        </div>
      )}

      {activeModal === 'REJECT' && (
        <div className="fixed inset-0 bg-slate-900/50 flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-xl max-w-md w-full p-6 space-y-4 shadow-xl">
            <h3 className="text-base font-bold text-slate-900 flex items-center gap-2">
              <XCircle className="w-5 h-5 text-rose-600" />
              Reject Match Candidate
            </h3>
            <p className="text-xs text-slate-600">
              The proposed ledger entry will be disassociated and the bank transaction reset to UNMATCHED.
            </p>
            <div>
              <label className="text-xs text-slate-600 font-medium">Rejection Reason (Required)</label>
              <textarea
                value={rejectReason}
                onChange={(e) => setRejectReason(e.target.value)}
                placeholder="e.g. AI incorrectly suggested vendor credit for unrelated billing item."
                className="w-full text-xs p-2.5 border border-slate-300 rounded-lg mt-1 h-20"
                required
              />
            </div>
            <div className="flex justify-end gap-2">
              <button
                onClick={() => setActiveModal('NONE')}
                className="px-3.5 py-1.5 border border-slate-300 rounded-lg text-xs font-semibold text-slate-700 hover:bg-slate-50"
              >
                Cancel
              </button>
              <button
                onClick={handleReject}
                disabled={!rejectReason.trim()}
                className="px-4 py-1.5 bg-rose-600 hover:bg-rose-700 text-white rounded-lg text-xs font-semibold shadow-sm disabled:opacity-50"
              >
                Confirm Rejection
              </button>
            </div>
          </div>
        </div>
      )}

      {activeModal === 'UNRESOLVED' && (
        <div className="fixed inset-0 bg-slate-900/50 flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-xl max-w-md w-full p-6 space-y-4 shadow-xl">
            <h3 className="text-base font-bold text-slate-900 flex items-center gap-2">
              <HelpCircle className="w-5 h-5 text-amber-500" />
              Mark as Unresolved Exception
            </h3>
            <p className="text-xs text-slate-600">
              Move to unresolved exceptions for further accounting review or supplier contact.
            </p>
            <div>
              <label className="text-xs text-slate-600 font-medium">Reason / Action Required</label>
              <textarea
                value={unresolvedReason}
                onChange={(e) => setUnresolvedReason(e.target.value)}
                placeholder="e.g. Waiting for vendor to provide itemized credit note"
                className="w-full text-xs p-2.5 border border-slate-300 rounded-lg mt-1 h-20"
              />
            </div>
            <div className="flex justify-end gap-2">
              <button
                onClick={() => setActiveModal('NONE')}
                className="px-3.5 py-1.5 border border-slate-300 rounded-lg text-xs font-semibold text-slate-700 hover:bg-slate-50"
              >
                Cancel
              </button>
              <button
                onClick={handleMarkUnresolved}
                disabled={!unresolvedReason.trim()}
                className="px-4 py-1.5 bg-amber-600 hover:bg-amber-700 text-white rounded-lg text-xs font-semibold shadow-sm disabled:opacity-50"
              >
                Save Unresolved
              </button>
            </div>
          </div>
        </div>
      )}

      {activeModal === 'INVESTIGATE' && (
        <div className="fixed inset-0 bg-slate-900/50 flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-xl max-w-md w-full p-6 space-y-4 shadow-xl">
            <h3 className="text-base font-bold text-slate-900 flex items-center gap-2">
              <AlertTriangle className="w-5 h-5 text-purple-600" />
              Request Formal Investigation
            </h3>
            <p className="text-xs text-slate-600">
              Escalates priority to HIGH and tags finance management for immediate review.
            </p>
            <div>
              <label className="text-xs text-slate-600 font-medium">Investigation Notes</label>
              <textarea
                value={investigationNotes}
                onChange={(e) => setInvestigationNotes(e.target.value)}
                placeholder="e.g. Discrepancy suggests possible double wire transfer or fraudulent debit."
                className="w-full text-xs p-2.5 border border-slate-300 rounded-lg mt-1 h-20"
              />
            </div>
            <div className="flex justify-end gap-2">
              <button
                onClick={() => setActiveModal('NONE')}
                className="px-3.5 py-1.5 border border-slate-300 rounded-lg text-xs font-semibold text-slate-700 hover:bg-slate-50"
              >
                Cancel
              </button>
              <button
                onClick={handleInvestigation}
                disabled={!investigationNotes.trim()}
                className="px-4 py-1.5 bg-purple-600 hover:bg-purple-700 text-white rounded-lg text-xs font-semibold shadow-sm disabled:opacity-50"
              >
                Escalate Investigation
              </button>
            </div>
          </div>
        </div>
      )}

      {activeModal === 'NOTE' && (
        <div className="fixed inset-0 bg-slate-900/50 flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-xl max-w-md w-full p-6 space-y-4 shadow-xl">
            <h3 className="text-base font-bold text-slate-900 flex items-center gap-2">
              <MessageSquare className="w-5 h-5 text-indigo-600" />
              Add Reviewer Note
            </h3>
            <div className="space-y-3">
              <div>
                <label className="text-xs text-slate-600 font-medium">Note Type</label>
                <select
                  value={noteType}
                  onChange={(e) => setNoteType(e.target.value)}
                  className="w-full text-xs p-2 border border-slate-300 rounded-lg mt-1"
                >
                  <option value="GENERAL">General Observation</option>
                  <option value="INVESTIGATION_REQUEST">Investigation Request</option>
                  <option value="APPROVAL_JUSTIFICATION">Approval Justification</option>
                  <option value="REJECTION_REASON">Rejection Reason</option>
                </select>
              </div>
              <div>
                <label className="text-xs text-slate-600 font-medium">Content</label>
                <textarea
                  value={newNoteContent}
                  onChange={(e) => setNewNoteContent(e.target.value)}
                  placeholder="Observation notes, external reference link, email correspondence summary..."
                  className="w-full text-xs p-2.5 border border-slate-300 rounded-lg mt-1 h-24"
                />
              </div>
            </div>
            <div className="flex justify-end gap-2">
              <button
                onClick={() => setActiveModal('NONE')}
                className="px-3.5 py-1.5 border border-slate-300 rounded-lg text-xs font-semibold text-slate-700 hover:bg-slate-50"
              >
                Cancel
              </button>
              <button
                onClick={handleAddNote}
                disabled={!newNoteContent.trim()}
                className="px-4 py-1.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-xs font-semibold shadow-sm disabled:opacity-50"
              >
                Save Note
              </button>
            </div>
          </div>
        </div>
      )}

      {activeModal === 'REMAP' && (
        <div className="fixed inset-0 bg-slate-900/50 flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-xl max-w-md w-full p-6 space-y-4 shadow-xl">
            <h3 className="text-base font-bold text-slate-900 flex items-center gap-2">
              <ArrowRightLeft className="w-5 h-5 text-indigo-600" />
              Remap Match Candidate
            </h3>
            <p className="text-xs text-slate-600">
              Replace current candidate with selected ledger entry. Deterministic validation will be recalculated.
            </p>
            <div className="space-y-3">
              <div>
                <label className="text-xs text-slate-600 font-medium">Target Ledger ID</label>
                <input
                  type="text"
                  value={remapLedgerId}
                  onChange={(e) => setRemapLedgerId(e.target.value)}
                  className="w-full text-xs p-2 border border-slate-300 rounded font-mono"
                />
              </div>
              <div>
                <label className="text-xs text-slate-600 font-medium">Remap Justification</label>
                <textarea
                  value={remapReason}
                  onChange={(e) => setRemapReason(e.target.value)}
                  placeholder="e.g. Correct invoice payment confirmed in ERP ledger"
                  className="w-full text-xs p-2.5 border border-slate-300 rounded-lg mt-1 h-20"
                />
              </div>
            </div>
            <div className="flex justify-end gap-2">
              <button
                onClick={() => setActiveModal('NONE')}
                className="px-3.5 py-1.5 border border-slate-300 rounded-lg text-xs font-semibold text-slate-700 hover:bg-slate-50"
              >
                Cancel
              </button>
              <button
                onClick={handleRemap}
                disabled={!remapLedgerId || !remapReason.trim()}
                className="px-4 py-1.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-xs font-semibold shadow-sm disabled:opacity-50"
              >
                Apply Remap
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
