import React from 'react';

export interface DayActivity {
  dayLabel: string;
  totalK: string;
  pendingPx: number;
  matchedPx: number;
  isToday?: boolean;
}

interface ActivityChartProps {
  days?: DayActivity[];
}

const defaultDays: DayActivity[] = [
  { dayLabel: 'Nov 15', totalK: '1.6k', pendingPx: 12, matchedPx: 80 },
  { dayLabel: 'Nov 16', totalK: '1.4k', pendingPx: 8, matchedPx: 64 },
  { dayLabel: 'Nov 17', totalK: '1.9k', pendingPx: 16, matchedPx: 96 },
  { dayLabel: 'Nov 18', totalK: '2.1k', pendingPx: 16, matchedPx: 112 },
  { dayLabel: 'Nov 19', totalK: '1.7k', pendingPx: 12, matchedPx: 80 },
  { dayLabel: 'Nov 20', totalK: '2.0k', pendingPx: 12, matchedPx: 96 },
  { dayLabel: 'Nov 21', totalK: '1.7k', pendingPx: 12, matchedPx: 80, isToday: true },
];

export const ActivityChart: React.FC<ActivityChartProps> = ({ days = defaultDays }) => {
  return (
    <div
      className="lg:col-span-6 rounded-lg p-5 flex flex-col justify-between gap-4 shadow-sm"
      style={{ backgroundColor: '#FFFFFF', border: '1px solid #E0E3E6' }}
    >
      <div className="flex items-center justify-between gap-2 flex-wrap">
        <div className="flex flex-col gap-0.5">
          <h2 className="font-title text-[16px] font-semibold text-[#101B32]">Reconciliation activity over time</h2>
          <p className="font-body text-[12px] text-[#5B5F62]">Daily transaction volume (Nov 15 – Nov 21)</p>
        </div>
        <div className="flex items-center gap-3">
          <span className="inline-flex items-center gap-1.5 font-label text-[12px] text-[#44474A]">
            <span className="w-2.5 h-2.5 rounded-xs inline-block" style={{ backgroundColor: '#16A37B' }}></span>
            Matched
          </span>
          <span className="inline-flex items-center gap-1.5 font-label text-[12px] text-[#44474A]">
            <span className="w-2.5 h-2.5 rounded-xs inline-block" style={{ backgroundColor: '#E9A23B' }}></span>
            Pending
          </span>
        </div>
      </div>

      {/* 7-column Daily Activity Bar Chart matching Stitch */}
      <div
        className="grid grid-cols-7 gap-3 items-end h-40 pt-2 pb-2"
        style={{ borderBottom: '1px solid #E0E3E6' }}
      >
        {days.map((d, idx) => (
          <div key={idx} className="flex flex-col items-center gap-1 h-full justify-end">
            <span
              className={`font-mono text-[12px] tabular-nums ${
                d.isToday ? 'text-[#101B32] font-bold' : 'text-[#5B5F62]'
              }`}
            >
              {d.totalK}
            </span>
            <div className="w-full max-w-[32px] flex flex-col gap-0.5 rounded-xs overflow-hidden">
              {/* Amber Pending Top */}
              <div
                className="w-full transition-all duration-300"
                style={{ height: `${d.pendingPx}px`, backgroundColor: '#E9A23B' }}
                title={`Pending: ${d.totalK}`}
              ></div>
              {/* Emerald Matched Bottom */}
              <div
                className="w-full transition-all duration-300"
                style={{ height: `${d.matchedPx}px`, backgroundColor: '#16A37B' }}
                title={`Matched: ${d.totalK}`}
              ></div>
            </div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-7 gap-3 text-center">
        {days.map((d, idx) => (
          <span
            key={idx}
            className={`font-label text-[12px] ${
              d.isToday ? 'text-[#101B32] font-semibold' : 'text-[#5B5F62]'
            }`}
          >
            {d.dayLabel}
          </span>
        ))}
      </div>
    </div>
  );
};
