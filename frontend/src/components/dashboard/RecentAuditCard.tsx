import React from 'react';
import { Link } from 'react-router-dom';

export interface AuditActivityItem {
  id: string;
  actor: string;
  action: string;
  referenceId: string;
  timestampText: string;
}

interface RecentAuditCardProps {
  events: AuditActivityItem[];
}

export const RecentAuditCard: React.FC<RecentAuditCardProps> = ({ events }) => {
  return (
    <div className="bg-surface-container-lowest border border-outline-variant rounded-lg p-5 flex flex-col gap-3 shadow-sm">
      <div className="flex items-center justify-between">
        <h2 className="font-title text-title-lg text-on-surface">Recent audit activity</h2>
        <Link to="/audit" className="font-label text-label-md text-primary hover:underline">
          Full log
        </Link>
      </div>

      <div className="flex flex-col divide-y divide-outline-variant">
        {events.map((evt) => (
          <div key={evt.id} className="py-2.5 flex flex-col gap-0.5">
            <span className="font-body text-body-sm text-on-surface">
              <strong className="font-semibold text-on-surface">{evt.actor}</strong> {evt.action}
            </span>
            <span className="font-mono text-mono-sm text-on-surface-muted tabular-nums">
              {evt.referenceId} · {evt.timestampText}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
};
