import React from 'react';
import { NavLink, useLocation } from 'react-router-dom';

interface NavItem {
  name: string;
  href: string;
  icon: string;
  badge?: string;
  isExact?: boolean;
}

const navigationItems: NavItem[] = [
  { name: 'Dashboard', href: '/', icon: 'dashboard', isExact: true },
  { name: 'Bank Statements', href: '/statements', icon: 'account_balance' },
  { name: 'Ledger Imports', href: '/ledger', icon: 'menu_book' },
  { name: 'Reconciliation', href: '/reconciliation', icon: 'compare_arrows' },
  { name: 'Review Queue', href: '/reviews', icon: 'fact_check', badge: '940' },
  { name: 'Transactions', href: '/transactions', icon: 'receipt_long' },
  { name: 'Audit Trail', href: '/audit', icon: 'history' },
  { name: 'Integrations', href: '/integrations', icon: 'hub' },
  { name: 'Reports', href: '/reports', icon: 'summarize' },
  { name: 'Settings', href: '/settings', icon: 'settings' },
];

interface SidebarProps {
  mobileOpen?: boolean;
  onCloseMobile?: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({ mobileOpen = false, onCloseMobile }) => {
  const location = useLocation();

  const isItemActive = (item: NavItem) => {
    if (item.isExact) {
      return location.pathname === item.href;
    }
    return location.pathname === item.href || location.pathname.startsWith(item.href + '/');
  };

  const renderNav = () => (
    <aside
      className="w-64 shrink-0 min-h-screen flex flex-col justify-between select-none"
      style={{ backgroundColor: '#101B32', color: '#FFFFFF', borderRight: '1px solid #101B32' }}
    >
      <div className="flex flex-col">
        {/* Brand Header */}
        <div
          className="h-16 px-5 flex items-center justify-between shrink-0"
          style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.1)' }}
        >
          <div className="flex items-center gap-3">
            <svg width="28" height="28" viewBox="0 0 28 28" fill="none" aria-hidden="true" className="shrink-0">
              <rect width="28" height="28" rx="6" fill="#5146E5"></rect>
              <path d="M5 17.5C5 13.3579 8.58172 10 14 10C19.4183 10 23 13.3579 23 17.5" stroke="#FFFFFF" strokeWidth="2" strokeLinecap="round"></path>
              <path d="M5 19.5H23" stroke="#6B9DFF" strokeWidth="1.75" strokeLinecap="round"></path>
              <circle cx="14" cy="10" r="2" fill="#16A37B"></circle>
            </svg>
            <div className="flex flex-col">
              <span className="font-headline text-[16px] font-semibold text-white leading-tight">FinBridge</span>
              <span className="font-label text-[11px] text-white/60 leading-tight">Finance. Connected.</span>
            </div>
          </div>
          {onCloseMobile && (
            <button
              type="button"
              onClick={onCloseMobile}
              className="lg:hidden text-white/70 hover:text-white p-1 rounded"
              aria-label="Close navigation"
            >
              <span className="material-symbols-outlined text-title-lg">close</span>
            </button>
          )}
        </div>

        {/* Primary Navigation */}
        <nav aria-label="Main navigation" className="p-3 flex flex-col gap-1">
          {navigationItems.map((item) => {
            const active = isItemActive(item);
            return (
              <NavLink
                key={item.name}
                to={item.href}
                onClick={onCloseMobile}
                style={active ? { backgroundColor: '#5146E5', color: '#FFFFFF' } : undefined}
                className={`flex items-center justify-between px-3 py-2.5 rounded transition-colors duration-150 ${
                  active
                    ? 'font-semibold shadow-sm'
                    : 'text-white/80 hover:bg-white/10 hover:text-white'
                }`}
              >
                <div className="flex items-center gap-3">
                  <span className="material-symbols-outlined text-[20px]" aria-hidden="true">
                    {item.icon}
                  </span>
                  <span className="font-label text-[14px] font-medium">{item.name}</span>
                </div>
                {item.badge && (
                  <span
                    className="inline-flex items-center justify-center min-w-[20px] h-5 px-1.5 rounded-full text-[11px] font-semibold tabular-nums"
                    style={{ backgroundColor: '#FFF4E5', color: '#845400' }}
                  >
                    {item.badge}
                  </span>
                )}
              </NavLink>
            );
          })}
        </nav>
      </div>

      {/* Bottom Security / SOC 2 Banner */}
      <div
        className="p-4 m-3 rounded-lg flex flex-col gap-1"
        style={{
          backgroundColor: 'rgba(255, 255, 255, 0.05)',
          border: '1px solid rgba(255, 255, 255, 0.1)',
        }}
      >
        <div className="flex items-center gap-2">
          <span
            className="inline-block w-2 h-2 rounded-full shrink-0"
            style={{ backgroundColor: '#16A37B' }}
          ></span>
          <span className="font-label text-[12px] font-medium text-white">SOC 2 Audit Logging</span>
        </div>
        <p className="font-body text-[12px] text-white/70 tabular-nums">Period Nov 2026 · Open</p>
      </div>
    </aside>
  );

  return (
    <>
      {/* Desktop Persistent Sidebar */}
      <div className="hidden lg:block shrink-0">
        {renderNav()}
      </div>

      {/* Mobile Drawer Overlay */}
      {mobileOpen && (
        <div className="fixed inset-0 z-50 flex lg:hidden">
          <div
            className="fixed inset-0 bg-black/50 transition-opacity"
            onClick={onCloseMobile}
            aria-hidden="true"
          />
          <div className="relative flex-1 flex flex-col max-w-xs w-full shadow-2xl z-10">
            {renderNav()}
          </div>
        </div>
      )}
    </>
  );
};
