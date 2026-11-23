import React from 'react';
import { PendingTaskItem } from './PendingReviewTasksTable';

interface ApproveModalProps {
  task: PendingTaskItem | null;
  isOpen: boolean;
  onClose: () => void;
  onConfirm: (task: PendingTaskItem) => void;
}

export const ApproveModal: React.FC<ApproveModalProps> = ({
  task,
  isOpen,
  onClose,
  onConfirm,
}) => {
  if (!isOpen || !task) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-midnight-navy/60 backdrop-blur-sm animate-in fade-in duration-200">
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="modal-title"
        className="w-full max-w-md rounded-xl bg-surface-container-lowest border border-outline-variant shadow-lg overflow-hidden flex flex-col"
      >
        {/* Modal Header */}
        <header className="px-6 py-4 border-b border-outline-variant flex items-center justify-between">
          <h2 id="modal-title" className="font-title text-title-lg text-on-surface">
            Approve exception match?
          </h2>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="w-8 h-8 rounded border border-outline-variant inline-flex items-center justify-center text-on-surface-muted hover:text-on-surface hover:bg-surface-container transition-colors"
          >
            <span className="material-symbols-outlined text-title-md" aria-hidden="true">
              close
            </span>
          </button>
        </header>

        {/* Modal Body */}
        <div className="px-6 py-5 flex flex-col gap-3">
          <div className="p-3.5 rounded-lg bg-surface-container-low border border-outline-variant flex flex-col gap-1">
            <span className="font-label text-label-sm text-on-surface-muted">Target Transaction</span>
            <span className="font-mono text-mono-md text-on-surface font-semibold">
              {task.transactionId} · {task.amountFormatted}
            </span>
            <span className="font-body text-body-sm text-on-surface-variant">
              Counterparty: {task.counterparty}
            </span>
          </div>

          <p className="font-body text-body-md text-on-surface-variant tabular-nums leading-relaxed">
            Confirm posting this exception match to NetSuite GL and recording the immutable audit record.
          </p>
        </div>

        {/* Modal Footer */}
        <footer className="px-6 py-4 bg-surface-container-low border-t border-outline-variant flex justify-end gap-2.5">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 rounded border border-outline-variant bg-surface-container-lowest text-on-surface hover:bg-surface-container font-label text-label-md transition-colors"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={() => onConfirm(task)}
            className="px-4 py-2 rounded bg-primary text-on-primary hover:bg-on-primary-container font-label text-label-md transition-colors shadow-sm"
          >
            Approve &amp; post
          </button>
        </footer>
      </div>
    </div>
  );
};
