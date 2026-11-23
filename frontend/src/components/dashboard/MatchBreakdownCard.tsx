import React from 'react';

export interface BreakdownData {
  totalCount: number;
  matchedCount: number;
  matchedPct: number;
  pendingCount: number;
  pendingPct: number;
  unmatchedCount: number;
  unmatchedPct: number;
}

interface MatchBreakdownCardProps {
  data: BreakdownData;
}

export const MatchBreakdownCard: React.FC<MatchBreakdownCardProps> = ({ data }) => {
  return (
    <div
      className="lg:col-span-3 rounded-lg p-5 flex flex-col justify-between gap-4 shadow-sm"
      style={{ backgroundColor: '#FFFFFF', border: '1px solid #E0E3E6' }}
    >
      <div className="flex flex-col gap-0.5">
        <h2 className="font-title text-[16px] font-semibold text-[#101B32]">Match breakdown</h2>
        <p className="font-body text-[12px] text-[#5B5F62] tabular-nums">
          {data.totalCount.toLocaleString()} total lines
        </p>
      </div>

      {/* Multi-segment Segmented Progress Bar */}
      <div
        className="w-full h-4 rounded-full overflow-hidden flex gap-0.5"
        style={{ backgroundColor: '#EFF1F5' }}
      >
        <div
          className="h-full transition-all duration-300"
          style={{ width: `${data.matchedPct}%`, backgroundColor: '#16A37B' }}
          title={`Matched: ${data.matchedPct.toFixed(1)}%`}
        ></div>
        <div
          className="h-full transition-all duration-300"
          style={{ width: `${data.pendingPct}%`, backgroundColor: '#E9A23B' }}
          title={`Pending review: ${data.pendingPct.toFixed(1)}%`}
        ></div>
        <div
          className="h-full transition-all duration-300"
          style={{ width: `${data.unmatchedPct}%`, backgroundColor: '#BA1A1A' }}
          title={`Unmatched: ${data.unmatchedPct.toFixed(1)}%`}
        ></div>
      </div>

      <div className="flex flex-col gap-2.5">
        <div className="flex items-center justify-between">
          <span className="inline-flex items-center gap-2 font-body text-[13px] text-[#101B32]">
            <span className="w-2.5 h-2.5 rounded-xs shrink-0 inline-block" style={{ backgroundColor: '#16A37B' }}></span>
            Matched
          </span>
          <span className="font-mono text-[13px] text-[#101B32] tabular-nums">
            {data.matchedCount.toLocaleString()} ({data.matchedPct.toFixed(1)}%)
          </span>
        </div>

        <div className="flex items-center justify-between">
          <span className="inline-flex items-center gap-2 font-body text-[13px] text-[#101B32]">
            <span className="w-2.5 h-2.5 rounded-xs shrink-0 inline-block" style={{ backgroundColor: '#E9A23B' }}></span>
            Pending review
          </span>
          <span className="font-mono text-[13px] text-[#101B32] tabular-nums">
            {data.pendingCount.toLocaleString()} ({data.pendingPct.toFixed(1)}%)
          </span>
        </div>

        <div className="flex items-center justify-between">
          <span className="inline-flex items-center gap-2 font-body text-[13px] text-[#101B32]">
            <span className="w-2.5 h-2.5 rounded-xs shrink-0 inline-block" style={{ backgroundColor: '#BA1A1A' }}></span>
            Unmatched
          </span>
          <span className="font-mono text-[13px] text-[#101B32] tabular-nums">
            {data.unmatchedCount.toLocaleString()} ({data.unmatchedPct.toFixed(1)}%)
          </span>
        </div>
      </div>
    </div>
  );
};
