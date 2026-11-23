import React from 'react';
import { Link } from 'react-router-dom';

export interface ReconciliationRunItem {
  id: string;
  sourceLabel: string;
  processedText: string;
  matchRateText: string;
}

interface RecentRunsCardProps {
  runs: ReconciliationRunItem[];
}

export const RecentRunsCard: React.FC<RecentRunsCardProps> = ({ runs }) => {
  return (
    <div className="bg-surface-container-lowest border border-outline-variant rounded-lg overflow-hidden shadow-sm">
      <div className="px-5 py-4 border-b border-outline-variant flex items-center justify-between">
        <h2 className="font-title text-title-lg text-on-surface">Recent reconciliation runs</h2>
        <Link to="/reconciliation" className="font-label text-label-md text-primary hover:underline">
          Run history
        </Link>
      </div>

      <div className="divide-y divide-outline-variant">
        {runs.map((run) => (
          <div key={run.id} className="px-5 py-3.5 flex items-center justify-between gap-4 hover:bg-surface-container-low transition-colors">
            <div className="flex flex-col gap-0.5">
              <span className="font-mono text-mono-sm text-on-surface tabular-nums font-medium">
                {run.sourceLabel}
              </span>
              <span className="font-body text-body-sm text-on-surface-muted tabular-nums">
                {run.processedText}
              </span>
            </div>
            <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-success-container text-on-success-container font-label text-label-sm tabular-nums font-semibold shrink-0">
              {run.matchRateText}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
};
