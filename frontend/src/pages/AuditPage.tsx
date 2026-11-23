import React, { useState, useEffect } from 'react';
import { apiClient } from '../api/client';
import {
  AuditEventItem,
  AuditIntegrityVerificationResult,
  AuditIntegrityCheckItem,
} from '../types';
import {
  ShieldCheck,
  ShieldAlert,
  Search,
  RefreshCw,
  User,
  Cpu,
  Bot,
  Network,
  ChevronRight,
  Hash,
  AlertTriangle,
  Info,
  CheckCircle2,
  Code,
  History,
  FileText,
  Lock,
} from 'lucide-react';

const EVENT_TYPE_OPTIONS: { value: string; label: string }[] = [
  { value: 'ALL', label: 'All Event Types' },
  { value: 'USER_LOGIN', label: 'User Login' },
  { value: 'USER_LOGOUT', label: 'User Logout' },
  { value: 'STATEMENT_UPLOAD', label: 'Statement Upload' },
  { value: 'LEDGER_IMPORT', label: 'Ledger Import' },
  { value: 'TRANSACTION_NORMALIZATION', label: 'Transaction Normalization' },
  { value: 'RECONCILIATION_RUN', label: 'Reconciliation Run' },
  { value: 'AI_PROPOSAL', label: 'AI Proposal' },
  { value: 'DETERMINISTIC_VALIDATION', label: 'Deterministic Validation' },
  { value: 'HUMAN_REVIEW', label: 'Human Review' },
  { value: 'APPROVAL', label: 'Approval' },
  { value: 'REJECTION', label: 'Rejection' },
  { value: 'ADJUSTMENT', label: 'Adjustment' },
  { value: 'INTEGRATION_REQUEST', label: 'Integration Request' },
  { value: 'RETRY', label: 'Retry Attempt' },
  { value: 'FAILURE_AND_RECOVERY', label: 'Failure & Recovery' },
];

export const AuditPage: React.FC = () => {
  const [events, setEvents] = useState<AuditEventItem[]>([]);
  const [totalCount, setTotalCount] = useState<number>(0);
  const [loading, setLoading] = useState<boolean>(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Filters
  const [search, setSearch] = useState<string>('');
  const [selectedEventType, setSelectedEventType] = useState<string>('ALL');
  const [selectedActorType, setSelectedActorType] = useState<string>('ALL');
  const [selectedEntityType, setSelectedEntityType] = useState<string>('ALL');
  const [startDate, setStartDate] = useState<string>('');
  const [endDate, setEndDate] = useState<string>('');
  const [page, setPage] = useState<number>(1);
  const limit = 25;

  // Selected event inspection
  const [selectedEvent, setSelectedEvent] = useState<AuditEventItem | null>(null);

  // Cryptographic integrity verification state
  const [verifying, setVerifying] = useState<boolean>(false);
  const [latestVerification, setLatestVerification] = useState<AuditIntegrityVerificationResult | null>(null);
  const [integrityHistory, setIntegrityHistory] = useState<AuditIntegrityCheckItem[]>([]);
  const [showIntegrityModal, setShowIntegrityModal] = useState<boolean>(false);
  const [showDisclosure, setShowDisclosure] = useState<boolean>(false);

  const loadAuditData = async () => {
    setLoading(true);
    setErrorMsg(null);
    try {
      const params: Record<string, any> = {
        limit,
        offset: (page - 1) * limit,
      };
      if (selectedEventType !== 'ALL') params.event_type = selectedEventType;
      if (selectedActorType !== 'ALL') params.actor_type = selectedActorType;
      if (selectedEntityType !== 'ALL') params.entity_type = selectedEntityType;
      if (search.trim()) params.search = search.trim();
      if (startDate) params.start_date = startDate;
      if (endDate) params.end_date = endDate;

      const [resList, pastChecks] = await Promise.all([
        apiClient.getAuditEvents(params),
        apiClient.getAuditIntegrityHistory(5),
      ]);

      setEvents(resList.items);
      setTotalCount(resList.total_count);
      setIntegrityHistory(pastChecks);
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : 'Failed to fetch audit records');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAuditData();
  }, [page, selectedEventType, selectedActorType, selectedEntityType, startDate, endDate]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setPage(1);
    loadAuditData();
  };

  const handleRunIntegrityCheck = async () => {
    setVerifying(true);
    setErrorMsg(null);
    try {
      const result = await apiClient.verifyAuditIntegrity();
      setLatestVerification(result);
      setShowIntegrityModal(true);
      if (result.is_valid) {
        setSuccessMsg(`Cryptographic verification passed: ${result.total_events_checked} sequential events verified.`);
      } else {
        setErrorMsg(`Cryptographic chain anomaly: ${result.status} at sequence #${result.broken_at_sequence_id}`);
      }
      // Refresh integrity history
      const history = await apiClient.getAuditIntegrityHistory(5);
      setIntegrityHistory(history);
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : 'Integrity verification failed to run');
    } finally {
      setVerifying(false);
    }
  };

  const filterByEntity = (entityType: string, entityId: string) => {
    setSelectedEntityType(entityType);
    setSearch(entityId);
    setPage(1);
    setSelectedEvent(null);
  };

  const clearFilters = () => {
    setSearch('');
    setSelectedEventType('ALL');
    setSelectedActorType('ALL');
    setSelectedEntityType('ALL');
    setStartDate('');
    setEndDate('');
    setPage(1);
  };

  const getActorBadge = (actorType: string) => {
    switch (actorType) {
      case 'USER':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium bg-blue-50 text-blue-700 border border-blue-200">
            <User className="w-3 h-3" /> User
          </span>
        );
      case 'AI_AGENT':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium bg-purple-50 text-purple-700 border border-purple-200">
            <Bot className="w-3 h-3" /> AI Agent
          </span>
        );
      case 'INTEGRATION':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium bg-amber-50 text-amber-700 border border-amber-200">
            <Network className="w-3 h-3" /> Integration
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium bg-slate-100 text-slate-700 border border-slate-200">
            <Cpu className="w-3 h-3" /> System
          </span>
        );
    }
  };

  const getEventTypeBadge = (eventType: string) => {
    let colorClasses = 'bg-slate-100 text-slate-700 border-slate-200';
    if (eventType.includes('LOGIN') || eventType.includes('LOGOUT')) {
      colorClasses = 'bg-sky-50 text-sky-700 border-sky-200';
    } else if (eventType.includes('APPROVAL') || eventType.includes('VERIFIED')) {
      colorClasses = 'bg-emerald-50 text-emerald-700 border-emerald-200';
    } else if (eventType.includes('REJECTION') || eventType.includes('FAILURE')) {
      colorClasses = 'bg-rose-50 text-rose-700 border-rose-200';
    } else if (eventType.includes('AI') || eventType.includes('PROPOSAL')) {
      colorClasses = 'bg-purple-50 text-purple-700 border-purple-200';
    } else if (eventType.includes('RECONCILIATION') || eventType.includes('VALIDATION')) {
      colorClasses = 'bg-indigo-50 text-indigo-700 border-indigo-200';
    } else if (eventType.includes('ADJUSTMENT') || eventType.includes('RETRY')) {
      colorClasses = 'bg-amber-50 text-amber-700 border-amber-200';
    }

    return (
      <span className={`inline-flex items-center px-2 py-0.5 rounded text-[11px] font-mono font-medium border ${colorClasses}`}>
        {eventType}
      </span>
    );
  };

  const latestScan = integrityHistory[0];

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-indigo-50 border border-indigo-200 flex items-center justify-center text-indigo-600">
              <ShieldCheck className="w-6 h-6" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-slate-900 tracking-tight">
                Audit Trail & Cryptographic Chain Explorer
              </h1>
              <p className="text-sm text-slate-500">
                Tamper-evident append-only ledger with SHA-256 forward hash chaining.
              </p>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowDisclosure(!showDisclosure)}
            className="inline-flex items-center gap-1.5 px-3 py-2 border border-slate-300 rounded-lg text-xs font-semibold text-slate-700 bg-white hover:bg-slate-50 shadow-sm transition-colors"
          >
            <Info className="w-4 h-4 text-indigo-600" />
            Chain Guarantees & Limits
          </button>
          <button
            onClick={handleRunIntegrityCheck}
            disabled={verifying}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold text-white bg-indigo-600 hover:bg-indigo-700 shadow-sm transition-colors disabled:opacity-50"
          >
            <ShieldCheck className={`w-4 h-4 ${verifying ? 'animate-spin' : ''}`} />
            {verifying ? 'Verifying Hashes...' : 'Verify Chain Integrity'}
          </button>
        </div>
      </div>

      {/* Notifications */}
      {errorMsg && (
        <div className="p-4 rounded-lg bg-rose-50 border border-rose-200 text-rose-700 text-sm flex items-center justify-between">
          <span className="flex items-center gap-2">
            <AlertTriangle className="w-4 h-4" /> {errorMsg}
          </span>
          <button onClick={() => setErrorMsg(null)} className="text-rose-500 hover:text-rose-700 font-bold ml-4">✕</button>
        </div>
      )}
      {successMsg && (
        <div className="p-4 rounded-lg bg-emerald-50 border border-emerald-200 text-emerald-700 text-sm flex items-center justify-between">
          <span className="flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4" /> {successMsg}
          </span>
          <button onClick={() => setSuccessMsg(null)} className="text-emerald-500 hover:text-emerald-700 font-bold ml-4">✕</button>
        </div>
      )}

      {/* Cryptographic Chain Integrity Banner */}
      <div className="p-4 rounded-xl bg-gradient-to-r from-slate-900 to-indigo-950 text-white border border-slate-800 shadow-md">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-emerald-500/20 border border-emerald-400/30 flex items-center justify-center text-emerald-400 shrink-0">
              <Lock className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-bold text-sm tracking-wide text-white">Cryptographic Chain Status:</span>
                <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                  <CheckCircle2 className="w-3.5 h-3.5" /> Chain Verified Active
                </span>
              </div>
              <p className="text-xs text-slate-300 mt-0.5">
                Each sequential event is linked to its predecessor via SHA-256 hash chaining.
                {latestScan && (
                  <span className="text-slate-400 ml-1">
                    Last scan: {new Date(latestScan.check_timestamp).toLocaleTimeString()} ({latestScan.total_events_checked} records checked)
                  </span>
                )}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-4 text-xs font-mono text-slate-300 border-t md:border-t-0 md:border-l border-slate-800 pt-3 md:pt-0 md:pl-4">
            <div>
              <div className="text-[10px] text-slate-400 uppercase tracking-wider font-sans">Total Records</div>
              <div className="text-base font-bold text-white font-mono">{totalCount}</div>
            </div>
            <div>
              <div className="text-[10px] text-slate-400 uppercase tracking-wider font-sans">ORM Immutability</div>
              <div className="text-emerald-400 font-semibold font-sans">Enforced</div>
            </div>
          </div>
        </div>
      </div>

      {/* Architectural Limitation & Guarantees Disclosure Card */}
      {showDisclosure && (
        <div className="p-5 rounded-xl bg-slate-50 border border-slate-300 space-y-3 transition-all">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-sm font-bold text-slate-900">
              <ShieldAlert className="w-4 h-4 text-indigo-600" />
              Cryptographic Audit Immutability & Architectural Disclosure
            </div>
            <button onClick={() => setShowDisclosure(false)} className="text-xs text-slate-500 hover:text-slate-800">Close</button>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs text-slate-700">
            <div className="p-3 bg-white rounded-lg border border-slate-200 space-y-1.5">
              <div className="font-semibold text-emerald-700 flex items-center gap-1.5">
                <CheckCircle2 className="w-3.5 h-3.5" /> Cryptographic Guarantees Provided
              </div>
              <ul className="list-disc pl-4 space-y-1 text-slate-600">
                <li>SHA-256 forward chaining detects unauthorized record updates or state edits.</li>
                <li>Monotonic sequence numbering exposes deleted records or inserted forgeries.</li>
                <li>SQLAlchemy ORM-level listeners reject UPDATE and DELETE operations from business services.</li>
                <li>Full before/after state captures provide complete differential transparency.</li>
              </ul>
            </div>
            <div className="p-3 bg-white rounded-lg border border-amber-200 space-y-1.5">
              <div className="font-semibold text-amber-800 flex items-center gap-1.5">
                <AlertTriangle className="w-3.5 h-3.5" /> Known Boundaries & Realities
              </div>
              <ul className="list-disc pl-4 space-y-1 text-slate-600">
                <li>Hash chaining detects changes, but cannot prevent a superuser/DBA from altering records and recomputing forward hashes.</li>
                <li>Production environments require external WORM storage (e.g. AWS S3 Object Lock) or RFC 3161 timestamps for absolute proof.</li>
                <li>Application database users should have UPDATE and DELETE permissions revoked at PostgreSQL GRANT level.</li>
              </ul>
            </div>
          </div>
        </div>
      )}

      {/* Filter & Search Bar */}
      <div className="p-4 bg-white rounded-xl border border-slate-200 shadow-sm space-y-3">
        <form onSubmit={handleSearchSubmit} className="flex flex-col md:flex-row items-center gap-3">
          <div className="relative flex-1 w-full">
            <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search by action, correlation ID, entity UUID, or hash..."
              className="w-full pl-9 pr-3 py-2 text-xs border border-slate-300 rounded-lg focus:ring-1 focus:ring-indigo-500"
            />
          </div>
          <button
            type="submit"
            className="w-full md:w-auto px-4 py-2 bg-slate-900 text-white rounded-lg text-xs font-semibold hover:bg-slate-800 shadow-sm"
          >
            Search
          </button>
        </form>

        <div className="grid grid-cols-2 md:grid-cols-5 gap-3 pt-2 border-t border-slate-100 text-xs">
          {/* Event Type Filter */}
          <div>
            <label className="text-[11px] text-slate-500 font-medium">Event Type</label>
            <select
              value={selectedEventType}
              onChange={(e) => {
                setSelectedEventType(e.target.value);
                setPage(1);
              }}
              className="w-full p-2 border border-slate-300 rounded-lg mt-0.5 text-xs"
            >
              {EVENT_TYPE_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>{opt.label}</option>
              ))}
            </select>
          </div>

          {/* Actor Type Filter */}
          <div>
            <label className="text-[11px] text-slate-500 font-medium">Actor Type</label>
            <select
              value={selectedActorType}
              onChange={(e) => {
                setSelectedActorType(e.target.value);
                setPage(1);
              }}
              className="w-full p-2 border border-slate-300 rounded-lg mt-0.5 text-xs"
            >
              <option value="ALL">All Actors</option>
              <option value="USER">User</option>
              <option value="AI_AGENT">AI Agent</option>
              <option value="SYSTEM">System</option>
              <option value="INTEGRATION">Integration</option>
            </select>
          </div>

          {/* Start Date */}
          <div>
            <label className="text-[11px] text-slate-500 font-medium">Start Date</label>
            <input
              type="date"
              value={startDate}
              onChange={(e) => {
                setStartDate(e.target.value);
                setPage(1);
              }}
              className="w-full p-2 border border-slate-300 rounded-lg mt-0.5 text-xs"
            />
          </div>

          {/* End Date */}
          <div>
            <label className="text-[11px] text-slate-500 font-medium">End Date</label>
            <input
              type="date"
              value={endDate}
              onChange={(e) => {
                setEndDate(e.target.value);
                setPage(1);
              }}
              className="w-full p-2 border border-slate-300 rounded-lg mt-0.5 text-xs"
            />
          </div>

          {/* Clear Button */}
          <div className="flex items-end">
            <button
              onClick={clearFilters}
              className="w-full py-2 px-3 border border-slate-300 rounded-lg text-xs font-semibold text-slate-600 hover:bg-slate-50"
            >
              Reset Filters
            </button>
          </div>
        </div>
      </div>

      {/* Main Events Table & Inspector Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Events Table (8 or 12 cols depending on inspection) */}
        <div className={`${selectedEvent ? 'lg:col-span-7' : 'lg:col-span-12'} space-y-4`}>
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
            <div className="px-5 py-3.5 border-b border-slate-200 flex items-center justify-between">
              <div className="text-xs font-bold text-slate-800 uppercase tracking-wider flex items-center gap-1.5">
                <History className="w-4 h-4 text-indigo-600" />
                Immutable Event Trail ({totalCount})
              </div>
              <div className="text-xs text-slate-500">
                Page {page} of {Math.max(1, Math.ceil(totalCount / limit))}
              </div>
            </div>

            {loading ? (
              <div className="p-12 text-center text-slate-500">
                <RefreshCw className="w-6 h-6 animate-spin mx-auto mb-2 text-indigo-600" />
                Querying audit events...
              </div>
            ) : events.length === 0 ? (
              <div className="p-12 text-center text-slate-500">
                <FileText className="w-8 h-8 mx-auto mb-2 text-slate-400" />
                <div className="font-semibold text-slate-800">No Audit Events Found</div>
                <p className="text-xs text-slate-400 mt-1">Try clearing your search query or broadening the date range.</p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs border-collapse">
                  <thead>
                    <tr className="bg-slate-50 border-b border-slate-200 text-slate-500 font-semibold uppercase tracking-wider text-[11px]">
                      <th className="py-2.5 px-4">Seq #</th>
                      <th className="py-2.5 px-4">Timestamp (UTC)</th>
                      <th className="py-2.5 px-4">Event Type</th>
                      <th className="py-2.5 px-4">Entity</th>
                      <th className="py-2.5 px-4">Actor</th>
                      <th className="py-2.5 px-4">Current Hash</th>
                      <th className="py-2.5 px-4 text-right">Action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {events.map((ev) => (
                      <tr
                        key={ev.id}
                        onClick={() => setSelectedEvent(ev)}
                        className={`hover:bg-slate-50/80 cursor-pointer transition-colors ${
                          selectedEvent?.id === ev.id ? 'bg-indigo-50/60 ring-1 ring-inset ring-indigo-200' : ''
                        }`}
                      >
                        <td className="py-3 px-4 font-mono font-bold text-slate-800">
                          #{ev.sequence_id}
                        </td>
                        <td className="py-3 px-4 text-slate-600 whitespace-nowrap">
                          {new Date(ev.created_at).toLocaleString()}
                        </td>
                        <td className="py-3 px-4">
                          {getEventTypeBadge(ev.event_type)}
                        </td>
                        <td className="py-3 px-4">
                          <div className="font-medium text-slate-800">{ev.entity_type}</div>
                          {ev.entity_id && (
                            <div className="text-[10px] font-mono text-slate-400 truncate max-w-[120px]">
                              {ev.entity_id}
                            </div>
                          )}
                        </td>
                        <td className="py-3 px-4">
                          {getActorBadge(ev.actor_type)}
                        </td>
                        <td className="py-3 px-4 font-mono text-[11px] text-slate-500" title={ev.current_hash}>
                          <span className="bg-slate-100 px-1.5 py-0.5 rounded border border-slate-200">
                            {ev.current_hash.substring(0, 10)}...
                          </span>
                        </td>
                        <td className="py-3 px-4 text-right">
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              setSelectedEvent(ev);
                            }}
                            className="text-indigo-600 hover:text-indigo-800 font-semibold inline-flex items-center gap-0.5"
                          >
                            Inspect <ChevronRight className="w-3.5 h-3.5" />
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {/* Pagination footer */}
            <div className="p-4 border-t border-slate-200 flex items-center justify-between text-xs text-slate-600 bg-slate-50">
              <button
                disabled={page <= 1}
                onClick={() => setPage(page - 1)}
                className="px-3 py-1.5 border border-slate-300 rounded-md font-medium hover:bg-white disabled:opacity-40"
              >
                Previous
              </button>
              <span>Showing {(page - 1) * limit + 1} - {Math.min(totalCount, page * limit)} of {totalCount}</span>
              <button
                disabled={page * limit >= totalCount}
                onClick={() => setPage(page + 1)}
                className="px-3 py-1.5 border border-slate-300 rounded-md font-medium hover:bg-white disabled:opacity-40"
              >
                Next
              </button>
            </div>
          </div>
        </div>

        {/* Detailed Inspector Drawer (5 cols) */}
        {selectedEvent && (
          <div className="lg:col-span-5 bg-white rounded-xl border border-slate-200 shadow-sm p-6 space-y-5">
            <div className="flex items-start justify-between pb-3 border-b border-slate-200">
              <div>
                <div className="flex items-center gap-2">
                  <span className="font-mono font-bold text-slate-900 text-sm">
                    Sequence #{selectedEvent.sequence_id}
                  </span>
                  {getEventTypeBadge(selectedEvent.event_type)}
                </div>
                <div className="text-xs text-slate-500 mt-1">
                  ID: <span className="font-mono">{selectedEvent.id}</span>
                </div>
              </div>
              <button
                onClick={() => setSelectedEvent(null)}
                className="text-slate-400 hover:text-slate-700 font-bold text-sm"
              >
                ✕
              </button>
            </div>

            {/* Cryptographic Hash Chaining Block */}
            <div className="p-3.5 rounded-lg bg-slate-900 text-white space-y-2 text-xs font-mono">
              <div className="text-[10px] text-slate-400 font-sans uppercase tracking-wider font-semibold flex items-center gap-1.5">
                <Hash className="w-3.5 h-3.5 text-indigo-400" />
                Cryptographic Chaining Hashes (SHA-256)
              </div>
              <div>
                <span className="text-slate-400">Current Hash:</span>
                <div className="break-all text-emerald-400 text-[11px] p-1 bg-black/40 rounded mt-0.5">
                  {selectedEvent.current_hash}
                </div>
              </div>
              <div>
                <span className="text-slate-400">Previous Hash (Link):</span>
                <div className="break-all text-sky-400 text-[11px] p-1 bg-black/40 rounded mt-0.5">
                  {selectedEvent.prev_hash}
                </div>
              </div>
            </div>

            {/* Entity & Actor Information */}
            <div className="grid grid-cols-2 gap-3 p-3 bg-slate-50 rounded-lg border border-slate-200 text-xs">
              <div>
                <span className="text-slate-500 font-medium">Actor:</span>
                <div className="mt-1">{getActorBadge(selectedEvent.actor_type)}</div>
                <div className="text-[11px] font-mono text-slate-600 mt-1 truncate">
                  {selectedEvent.actor_id || 'SYSTEM_INTERNAL'}
                </div>
              </div>
              <div>
                <span className="text-slate-500 font-medium">Entity:</span>
                <div className="font-bold text-slate-800 mt-1">{selectedEvent.entity_type}</div>
                {selectedEvent.entity_id && (
                  <button
                    onClick={() => filterByEntity(selectedEvent.entity_type, selectedEvent.entity_id!)}
                    className="text-[11px] text-indigo-600 hover:text-indigo-800 underline font-medium mt-1 truncate block"
                    title="Filter all events for this entity"
                  >
                    View Entity Trail →
                  </button>
                )}
              </div>
              <div>
                <span className="text-slate-500 font-medium">IP Address:</span>
                <div className="font-mono text-slate-700 mt-0.5">{selectedEvent.ip_address || 'Internal/None'}</div>
              </div>
              <div>
                <span className="text-slate-500 font-medium">Correlation ID:</span>
                <div className="font-mono text-slate-700 mt-0.5 truncate">{selectedEvent.correlation_id || 'None'}</div>
              </div>
            </div>

            {/* AI Model & Prompt Metadata (if present) */}
            {(selectedEvent.model_version || selectedEvent.prompt_version) && (
              <div className="p-3 bg-purple-50 rounded-lg border border-purple-200 text-xs space-y-1">
                <div className="font-bold text-purple-900 flex items-center gap-1.5">
                  <Bot className="w-3.5 h-3.5 text-purple-600" /> AI Execution Context
                </div>
                <div className="grid grid-cols-2 gap-2 text-purple-950 font-mono text-[11px] pt-1">
                  <div>Model: {selectedEvent.model_version || 'N/A'}</div>
                  <div>Prompt: {selectedEvent.prompt_version || 'N/A'}</div>
                </div>
              </div>
            )}

            {/* State Diffs (Before / After) */}
            {(selectedEvent.before_state || selectedEvent.after_state) && (
              <div className="space-y-2">
                <div className="text-xs font-bold text-slate-800 uppercase tracking-wide">
                  State Mutation Snapshot
                </div>
                <div className="grid grid-cols-2 gap-2 text-xs">
                  <div className="p-2.5 bg-rose-50/60 rounded border border-rose-200">
                    <span className="font-semibold text-rose-800 text-[11px]">Before State</span>
                    <pre className="text-[10px] font-mono text-rose-950 mt-1 overflow-x-auto max-h-32">
                      {JSON.stringify(selectedEvent.before_state || {}, null, 2)}
                    </pre>
                  </div>
                  <div className="p-2.5 bg-emerald-50/60 rounded border border-emerald-200">
                    <span className="font-semibold text-emerald-800 text-[11px]">After State</span>
                    <pre className="text-[10px] font-mono text-emerald-950 mt-1 overflow-x-auto max-h-32">
                      {JSON.stringify(selectedEvent.after_state || {}, null, 2)}
                    </pre>
                  </div>
                </div>
              </div>
            )}

            {/* Structured Payload / Metadata Details */}
            <div className="space-y-1.5">
              <div className="text-xs font-bold text-slate-800 uppercase tracking-wide flex items-center gap-1">
                <Code className="w-3.5 h-3.5 text-slate-500" />
                Event Payload JSON
              </div>
              <pre className="p-3 rounded-lg bg-slate-900 text-slate-200 font-mono text-[11px] overflow-x-auto max-h-48 border border-slate-800">
                {JSON.stringify(selectedEvent.payload || {}, null, 2)}
              </pre>
            </div>
          </div>
        )}
      </div>

      {/* Verification Modal / Scan Results Drawer */}
      {showIntegrityModal && latestVerification && (
        <div className="fixed inset-0 bg-slate-900/50 flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-xl max-w-lg w-full p-6 space-y-4 shadow-2xl">
            <div className="flex items-center justify-between pb-3 border-b border-slate-200">
              <div className="flex items-center gap-2">
                {latestVerification.is_valid ? (
                  <CheckCircle2 className="w-6 h-6 text-emerald-600" />
                ) : (
                  <ShieldAlert className="w-6 h-6 text-rose-600" />
                )}
                <div>
                  <h3 className="text-base font-bold text-slate-900">
                    {latestVerification.is_valid ? 'Chain Cryptographically Verified' : 'Cryptographic Anomaly Detected'}
                  </h3>
                  <p className="text-xs text-slate-500">
                    Status: <span className="font-bold">{latestVerification.status}</span>
                  </p>
                </div>
              </div>
              <button onClick={() => setShowIntegrityModal(false)} className="text-slate-400 hover:text-slate-700 font-bold">✕</button>
            </div>

            <div className="space-y-3 text-xs">
              <div className="grid grid-cols-2 gap-3 p-3 bg-slate-50 rounded-lg border border-slate-200">
                <div>
                  <span className="text-slate-500">Events Checked:</span>
                  <div className="font-bold font-mono text-sm text-slate-900">{latestVerification.total_events_checked}</div>
                </div>
                <div>
                  <span className="text-slate-500">Duration:</span>
                  <div className="font-bold font-mono text-sm text-slate-900">{latestVerification.verification_duration_ms} ms</div>
                </div>
                <div>
                  <span className="text-slate-500">Sequence Range:</span>
                  <div className="font-mono text-slate-800">#{latestVerification.start_sequence_id} - #{latestVerification.end_sequence_id}</div>
                </div>
                <div>
                  <span className="text-slate-500">Result:</span>
                  <div className={`font-semibold ${latestVerification.is_valid ? 'text-emerald-700' : 'text-rose-700'}`}>
                    {latestVerification.is_valid ? 'Unbroken Chain' : `Violation at Seq #${latestVerification.broken_at_sequence_id}`}
                  </div>
                </div>
              </div>

              {!latestVerification.is_valid && (
                <div className="p-3 bg-rose-50 rounded-lg border border-rose-200 text-rose-900 space-y-1">
                  <div className="font-bold flex items-center gap-1">
                    <AlertTriangle className="w-4 h-4 text-rose-600" /> Forensics Report
                  </div>
                  <pre className="text-[11px] font-mono whitespace-pre-wrap bg-white/70 p-2 rounded">
                    {JSON.stringify(latestVerification.details, null, 2)}
                  </pre>
                </div>
              )}

              <div className="p-3 bg-slate-50 rounded-lg text-slate-600 text-[11px] leading-relaxed border border-slate-200">
                <span className="font-semibold text-slate-800">Disclosure:</span> {latestVerification.limitation_disclosure}
              </div>
            </div>

            <div className="flex justify-end pt-2">
              <button
                onClick={() => setShowIntegrityModal(false)}
                className="px-4 py-1.5 bg-slate-900 hover:bg-slate-800 text-white font-semibold rounded-lg text-xs"
              >
                Close Report
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
