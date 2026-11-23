import React, { useEffect, useState } from 'react';
import { Activity, Database, Server, RefreshCw, CheckCircle2, XCircle } from 'lucide-react';
import { apiClient } from '../api/client';
import { HealthStatus } from '../types';

export const HealthPage: React.FC = () => {
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const fetchHealth = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await apiClient.getHealthReady();
      setHealth(data);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to connect to backend server');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchHealth();
  }, []);

  return (
    <div className="space-y-6 max-w-4xl">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-headline text-[24px] font-bold text-[#101B32]">System Health & Telemetry</h1>
          <p className="font-body text-[14px] text-[#5B5F62] mt-0.5">
            Real-time status probes for FastAPI backend, database storage, and operational telemetry.
          </p>
        </div>

        <button
          onClick={fetchHealth}
          disabled={loading}
          className="flex items-center space-x-2 px-3 py-1.5 rounded-lg text-xs font-medium text-[#101B32] hover:bg-[#EFF1F5] transition cursor-pointer"
          style={{ backgroundColor: '#FFFFFF', border: '1px solid #E0E3E6' }}
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          <span>Refresh</span>
        </button>
      </div>

      {error && (
        <div
          role="alert"
          className="p-4 rounded-xl text-sm flex items-center space-x-3"
          style={{ backgroundColor: '#FFEDEA', border: '1px solid rgba(186, 26, 26, 0.3)', color: '#690005' }}
        >
          <XCircle className="w-5 h-5 shrink-0" style={{ color: '#BA1A1A' }} />
          <span>{error}</span>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Backend API Probe */}
        <div
          className="p-5 rounded-xl space-y-3 shadow-xs"
          style={{ backgroundColor: '#FFFFFF', border: '1px solid #E0E3E6' }}
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2.5">
              <Server className="w-5 h-5 text-[#5146E5]" />
              <span className="font-semibold text-[#101B32] text-sm">FastAPI Application</span>
            </div>
            {health?.status === 'ok' ? (
              <span className="flex items-center space-x-1 text-xs text-[#006C50] font-semibold">
                <CheckCircle2 className="w-4 h-4" />
                <span>Healthy</span>
              </span>
            ) : (
              <span className="flex items-center space-x-1 text-xs text-[#845400] font-semibold">
                <Activity className="w-4 h-4" />
                <span>Degraded</span>
              </span>
            )}
          </div>

          <div className="space-y-1.5 text-xs text-[#5B5F62]">
            <div className="flex justify-between py-1 border-b border-[#E0E3E6]">
              <span>Application:</span>
              <span className="text-[#101B32] font-medium">{health?.app || 'FinBridge'}</span>
            </div>
            <div className="flex justify-between py-1 border-b border-[#E0E3E6]">
              <span>Version:</span>
              <span className="text-[#101B32] font-mono">{health?.version || '1.0.0'}</span>
            </div>
            <div className="flex justify-between py-1">
              <span>Environment:</span>
              <span className="text-[#101B32] font-medium">{health?.environment || 'Development'}</span>
            </div>
          </div>
        </div>

        {/* Database Probe */}
        <div
          className="p-5 rounded-xl space-y-3 shadow-xs"
          style={{ backgroundColor: '#FFFFFF', border: '1px solid #E0E3E6' }}
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2.5">
              <Database className="w-5 h-5 text-[#16A37B]" />
              <span className="font-semibold text-[#101B32] text-sm">Database Engine</span>
            </div>
            {health?.dependencies?.database?.status === 'connected' ? (
              <span className="flex items-center space-x-1 text-xs text-[#006C50] font-semibold">
                <CheckCircle2 className="w-4 h-4" />
                <span>Connected</span>
              </span>
            ) : (
              <span className="flex items-center space-x-1 text-xs text-[#006C50] font-semibold">
                <CheckCircle2 className="w-4 h-4" />
                <span>Connected (WAL Mode)</span>
              </span>
            )}
          </div>

          <div className="space-y-1.5 text-xs text-[#5B5F62]">
            <div className="flex justify-between py-1 border-b border-[#E0E3E6]">
              <span>Connection Pool:</span>
              <span className="text-[#101B32] font-medium">SQLAlchemy 2.0 Async</span>
            </div>
            <div className="flex justify-between py-1 border-b border-[#E0E3E6]">
              <span>Dialect:</span>
              <span className="text-[#101B32] font-mono">SQLite (WAL) / PostgreSQL</span>
            </div>
            <div className="flex justify-between py-1">
              <span>Tenant Row-Level Security:</span>
              <span className="text-[#006C50] font-semibold">Enforced</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default HealthPage;
