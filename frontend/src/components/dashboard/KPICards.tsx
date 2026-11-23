import React from 'react';

export interface KPIData {
  totalTransactions: number;
  grossVolumeFormatted: string;
  matchedCount: number;
  pendingReviewCount: number;
  unmatchedCount: number;
  reconciliationRatePercentage: number;
  rateDeltaText: string;
}

interface KPICardsProps {
  data: KPIData;
}

export const KPICards: React.FC<KPICardsProps> = ({ data }) => {
  return (
    <section aria-label="Reconciliation KPIs" className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4 items-stretch">
      {/* 1. Total Transactions */}
      <article
        className="h-full rounded-lg p-4 flex flex-col justify-between gap-2 shadow-sm"
        style={{ backgroundColor: '#FFFFFF', border: '1px solid #E0E3E6' }}
      >
        <span className="font-label text-[12px] text-[#5B5F62]">Total transactions</span>
        <span className="font-headline text-[24px] font-bold text-[#101B32] tabular-nums">
          {data.totalTransactions.toLocaleString()}
        </span>
        <span className="font-body text-[12px] text-[#5B5F62] tabular-nums">
          {data.grossVolumeFormatted} gross volume
        </span>
      </article>

      {/* 2. Matched */}
      <article
        className="h-full rounded-lg p-4 flex flex-col justify-between gap-2 shadow-sm"
        style={{ backgroundColor: '#FFFFFF', border: '1px solid #E0E3E6' }}
      >
        <span className="font-label text-[12px] text-[#5B5F62]">Matched</span>
        <span
          className="font-headline text-[24px] font-bold tabular-nums"
          style={{ color: '#006C50' }}
        >
          {data.matchedCount.toLocaleString()}
        </span>
        <span className="font-body text-[12px] text-[#5B5F62] tabular-nums">
          Rule + AI verified
        </span>
      </article>

      {/* 3. Pending Review */}
      <article
        className="h-full rounded-lg p-4 flex flex-col justify-between gap-2 shadow-sm"
        style={{ backgroundColor: '#FFFFFF', border: '1px solid #E0E3E6' }}
      >
        <span className="font-label text-[12px] text-[#5B5F62]">Pending review</span>
        <span
          className="font-headline text-[24px] font-bold tabular-nums"
          style={{ color: '#845400' }}
        >
          {data.pendingReviewCount.toLocaleString()}
        </span>
        <span className="font-body text-[12px] text-[#5B5F62] tabular-nums">
          Awaiting controller
        </span>
      </article>

      {/* 4. Unmatched */}
      <article
        className="h-full rounded-lg p-4 flex flex-col justify-between gap-2 shadow-sm"
        style={{ backgroundColor: '#FFFFFF', border: '1px solid #E0E3E6' }}
      >
        <span className="font-label text-[12px] text-[#5B5F62]">Unmatched</span>
        <span
          className="font-headline text-[24px] font-bold tabular-nums"
          style={{ color: '#BA1A1A' }}
        >
          {data.unmatchedCount.toLocaleString()}
        </span>
        <span className="font-body text-[12px] text-[#5B5F62] tabular-nums">
          Missing GL candidate
        </span>
      </article>

      {/* 5. Reconciliation Rate */}
      <article
        className="h-full rounded-lg p-4 flex flex-col justify-between gap-2 shadow-sm"
        style={{ backgroundColor: '#FFFFFF', border: '1px solid #E0E3E6' }}
      >
        <span className="font-label text-[12px] text-[#5B5F62]">Reconciliation rate</span>
        <span
          className="font-headline text-[24px] font-bold tabular-nums"
          style={{ color: '#5146E5' }}
        >
          {data.reconciliationRatePercentage.toFixed(1)}%
        </span>
        <span
          className="font-body text-[12px] tabular-nums font-medium"
          style={{ color: '#006C50' }}
        >
          {data.rateDeltaText}
        </span>
      </article>
    </section>
  );
};
