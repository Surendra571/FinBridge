import React from 'react';

export interface ExceptionCategoryItem {
  label: string;
  count: number;
  barColor: string;
  widthPercentage: number;
}

interface ExceptionCategoriesCardProps {
  totalFlagged?: number;
  items?: ExceptionCategoryItem[];
}

const defaultItems: ExceptionCategoryItem[] = [
  { label: 'FX variance', count: 412, barColor: '#E9A23B', widthPercentage: 68 },
  { label: 'Missing GL ref', count: 388, barColor: '#BA1A1A', widthPercentage: 62 },
  { label: 'Date cut-off (+2d)', count: 310, barColor: '#6B9DFF', widthPercentage: 50 },
  { label: 'Split batch', count: 285, barColor: '#5146E5', widthPercentage: 44 },
];

export const ExceptionCategoriesCard: React.FC<ExceptionCategoriesCardProps> = ({
  totalFlagged = 1630,
  items = defaultItems,
}) => {
  return (
    <div
      className="lg:col-span-3 rounded-lg p-5 flex flex-col justify-between gap-4 shadow-sm"
      style={{ backgroundColor: '#FFFFFF', border: '1px solid #E0E3E6' }}
    >
      <div className="flex flex-col gap-0.5">
        <h2 className="font-title text-[16px] font-semibold text-[#101B32]">Exception categories</h2>
        <p className="font-body text-[12px] text-[#5B5F62] tabular-nums">
          {totalFlagged.toLocaleString()} flagged items
        </p>
      </div>

      <div className="flex flex-col gap-3">
        {items.map((cat, idx) => (
          <div key={idx} className="flex flex-col gap-1">
            <div className="flex justify-between font-body text-[13px]">
              <span className="text-[#101B32]">{cat.label}</span>
              <span className="font-mono text-[12px] tabular-nums text-[#44474A] font-medium">
                {cat.count.toLocaleString()}
              </span>
            </div>
            <div className="w-full h-2 rounded-full overflow-hidden" style={{ backgroundColor: '#EFF1F5' }}>
              <div
                className="h-2 rounded-full transition-all duration-300"
                style={{ width: `${cat.widthPercentage}%`, backgroundColor: cat.barColor }}
              ></div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
