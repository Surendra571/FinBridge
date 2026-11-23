import React from 'react';
import { Link } from 'react-router-dom';

export interface PendingTaskItem {
  id: string;
  transactionId: string;
  counterparty: string;
  amountFormatted: string;
  evidenceBadge: string;
  evidenceVariant: 'warning' | 'info' | 'error';
}

interface PendingReviewTasksTableProps {
  tasks: PendingTaskItem[];
  totalCount: number;
  onApprove: (task: PendingTaskItem) => void;
}

export const PendingReviewTasksTable: React.FC<PendingReviewTasksTableProps> = ({
  tasks,
  totalCount,
  onApprove,
}) => {
  return (
    <div className="bg-surface-container-lowest border border-outline-variant rounded-lg overflow-hidden shadow-sm">
      <div className="px-5 py-4 border-b border-outline-variant flex items-center justify-between">
        <h2 className="font-title text-title-lg text-on-surface">Pending review tasks</h2>
        <Link to="/reviews" className="font-label text-label-md text-primary hover:underline">
          View all {totalCount.toLocaleString()}
        </Link>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-left border-collapse">
          <thead className="bg-surface-container border-b border-outline-variant">
            <tr>
              <th scope="col" className="px-4 py-2.5 font-label text-label-md text-on-surface-muted">
                Transaction
              </th>
              <th scope="col" className="px-4 py-2.5 font-label text-label-md text-on-surface-muted">
                Counterparty
              </th>
              <th scope="col" className="px-4 py-2.5 font-label text-label-md text-on-surface-muted text-right">
                Amount
              </th>
              <th scope="col" className="px-4 py-2.5 font-label text-label-md text-on-surface-muted">
                Evidence
              </th>
              <th scope="col" className="px-4 py-2.5 font-label text-label-md text-on-surface-muted text-right">
                Action
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-outline-variant">
            {tasks.map((task) => (
              <tr key={task.id} className="hover:bg-surface-container-low transition-colors">
                <td className="px-4 py-3 font-mono text-mono-sm text-on-surface-variant tabular-nums">
                  {task.transactionId}
                </td>
                <td className="px-4 py-3 font-title text-title-md text-on-surface">
                  {task.counterparty}
                </td>
                <td className="px-4 py-3 font-mono text-mono-md text-on-surface text-right tabular-nums font-medium">
                  {task.amountFormatted}
                </td>
                <td className="px-4 py-3">
                  <span
                    className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full font-label text-label-sm ${
                      task.evidenceVariant === 'warning'
                        ? 'bg-warning-container text-on-warning-container'
                        : task.evidenceVariant === 'info'
                        ? 'bg-info-container text-on-info-container'
                        : 'bg-error-container text-on-error-container'
                    }`}
                  >
                    {task.evidenceBadge}
                  </span>
                </td>
                <td className="px-4 py-3 text-right">
                  <button
                    type="button"
                    onClick={() => onApprove(task)}
                    className="px-3 py-1 rounded bg-primary text-on-primary hover:bg-on-primary-container font-label text-label-sm transition-colors duration-state-change shadow-sm"
                  >
                    Approve
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};
