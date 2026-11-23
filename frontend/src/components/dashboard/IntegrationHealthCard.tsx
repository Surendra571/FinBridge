import React from 'react';
import { Link } from 'react-router-dom';

export interface IntegrationHealthItem {
  id: string;
  name: string;
  lastSyncText: string;
  status: 'healthy' | 'warning' | 'error';
}

interface IntegrationHealthCardProps {
  items: IntegrationHealthItem[];
}

export const IntegrationHealthCard: React.FC<IntegrationHealthCardProps> = ({ items }) => {
  return (
    <div className="bg-surface-container-lowest border border-outline-variant rounded-lg p-5 flex flex-col gap-3 shadow-sm">
      <div className="flex items-center justify-between">
        <h2 className="font-title text-title-lg text-on-surface">Integration health</h2>
        <Link to="/simulator" className="font-label text-label-md text-primary hover:underline">
          Manage
        </Link>
      </div>

      <div className="flex flex-col divide-y divide-outline-variant">
        {items.map((item) => (
          <div key={item.id} className="py-2.5 flex items-center justify-between gap-2">
            <span className="font-body text-body-md text-on-surface truncate">{item.name}</span>
            <span
              className={`inline-flex items-center gap-1.5 font-label text-label-sm tabular-nums shrink-0 ${
                item.status === 'healthy'
                  ? 'text-success'
                  : item.status === 'warning'
                  ? 'text-warning'
                  : 'text-error'
              }`}
            >
              <span
                className={`w-2 h-2 rounded-full ${
                  item.status === 'healthy'
                    ? 'bg-trust-emerald'
                    : item.status === 'warning'
                    ? 'bg-review-amber'
                    : 'bg-error'
                }`}
              ></span>
              {item.lastSyncText}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
};
