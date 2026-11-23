import React, { useState, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { apiClient } from '../../api/client';

interface NavbarProps {
  onOpenMobileMenu?: () => void;
}

export const Navbar: React.FC<NavbarProps> = ({ onOpenMobileMenu }) => {
  const [orgName, setOrgName] = useState('Northstar Logistics');
  const [orgCode, setOrgCode] = useState('NL');
  const [userName, setUserName] = useState('Elena Rostova');
  const [userRole, setUserRole] = useState('VP Controller');
  const [userInitials, setUserInitials] = useState('ER');
  const [menuOpen, setMenuOpen] = useState(false);
  const [notifOpen, setNotifOpen] = useState(false);
  const [notifications, setNotifications] = useState([
    {
      id: '1',
      title: 'Reconciliation completed · RUN-2026-1121-04',
      desc: '384 transactions matched automatically (86.9% rate) for SVB Operating •••• 4821.',
      time: '09:42 UTC',
      unread: true,
      category: 'Reconciliation',
    },
    {
      id: '2',
      title: 'Exceptions waiting for review (14)',
      desc: '14 new exceptions routed to Review Queue, including TXN-2026-88412 (+$142.80 FX).',
      time: '08:15 UTC',
      unread: true,
      category: 'Exceptions',
    },
    {
      id: '3',
      title: 'Approval required · Exceeds $10,000 limit',
      desc: 'Marcus Vance escalated CloudScale Hosting ($14,820.00) for VP Controller sign-off.',
      time: '08:05 UTC',
      unread: true,
      category: 'Approvals',
    },
    {
      id: '4',
      title: 'SOC 2 Audit Trail snapshot verified',
      desc: 'Cryptographic SHA-256 chain integrity passed across 1,842 sequence blocks.',
      time: 'Nov 20 · 23:00 UTC',
      unread: false,
      category: 'Security',
    },
  ]);
  
  const navigate = useNavigate();
  const location = useLocation();

  // Dynamic breadcrumb mapping
  const getPageTitle = (path: string) => {
    if (path === '/') return 'Dashboard';
    if (path.startsWith('/statements')) return 'Bank Statements';
    if (path.startsWith('/ledger')) return 'Ledger Imports';
    if (path.startsWith('/reconciliation')) return 'Reconciliation';
    if (path.startsWith('/reviews')) return 'Review Queue';
    if (path.startsWith('/transactions')) return 'Transactions';
    if (path.startsWith('/audit')) return 'Audit Trail';
    if (path.startsWith('/integrations') || path.startsWith('/simulator') || path.startsWith('/health')) return 'Integrations';
    if (path.startsWith('/reports')) return 'Reports & Analytics';
    if (path.startsWith('/settings')) return 'Settings';
    if (path.startsWith('/profile')) return 'Profile';
    return 'Workspace';
  };

  useEffect(() => {
    const fetchProfile = async () => {
      try {
        const orgs = await apiClient.getOrganizations();
        if (orgs.length > 0) {
          const current = orgs[0];
          setOrgName(current.name);
          setOrgCode(
            current.name
              .split(' ')
              .map((w) => w[0])
              .join('')
              .slice(0, 2)
              .toUpperCase() || 'NL'
          );
          if (current.role) {
            setUserRole(current.role.replace(/_/g, ' '));
          }
        }
      } catch {
        // Fallback to default
      }

      try {
        const user = await apiClient.getCurrentUser();
        if (user) {
          if (user.fullName) {
            setUserName(user.fullName);
            setUserInitials(
              user.fullName
                .split(' ')
                .map((w) => w[0])
                .join('')
                .slice(0, 2)
                .toUpperCase() || 'ER'
            );
          } else if (user.email) {
            const name = user.email.split('@')[0].replace(/[._]/g, ' ');
            const formatted = name
              .split(' ')
              .map((s) => s.charAt(0).toUpperCase() + s.slice(1))
              .join(' ');
            setUserName(formatted);
            setUserInitials(
              name
                .split(' ')
                .map((w) => w[0])
                .join('')
                .slice(0, 2)
                .toUpperCase() || 'ER'
            );
          }
        }
      } catch {
        // Fallback to default
      }
    };

    fetchProfile();
  }, []);

  const handleSignOut = async () => {
    try {
      await apiClient.logout();
    } catch {
      // Ignore network errors
    } finally {
      apiClient.setToken(null);
      apiClient.setActiveOrg(null);
      navigate('/login');
    }
  };

  return (
    <header
      className="h-16 px-4 lg:px-6 flex items-center justify-between gap-4 sticky top-0 z-30 shrink-0"
      style={{ backgroundColor: '#FFFFFF', borderBottom: '1px solid #E0E3E6' }}
    >
      <div className="flex items-center gap-3 lg:gap-4 min-w-0">
        {/* Mobile Hamburger Menu Toggle */}
        <button
          type="button"
          onClick={onOpenMobileMenu}
          aria-label="Open sidebar menu"
          className="lg:hidden inline-flex items-center justify-center w-9 h-9 rounded text-[#101B32] hover:bg-[#EFF1F5] transition-colors shrink-0"
          style={{ border: '1px solid #E0E3E6', backgroundColor: '#FFFFFF' }}
        >
          <span className="material-symbols-outlined text-[20px]" aria-hidden="true">menu</span>
        </button>

        {/* Organization Selector */}
        <button
          type="button"
          onClick={() => navigate('/settings')}
          className="inline-flex items-center gap-2 px-3 py-1.5 rounded hover:bg-[#EFF1F5] transition-colors whitespace-nowrap shrink-0"
          style={{ border: '1px solid #E0E3E6', backgroundColor: '#FBFCFF' }}
        >
          <span
            className="w-5 h-5 rounded-xs font-semibold text-[11px] inline-flex items-center justify-center shrink-0"
            style={{ backgroundColor: '#101B32', color: '#FFFFFF' }}
          >
            {orgCode}
          </span>
          <span className="font-label text-[14px] text-[#101B32] font-medium truncate max-w-[140px] sm:max-w-none">
            {orgName}
          </span>
          <span className="material-symbols-outlined text-[18px] text-[#5B5F62] shrink-0" aria-hidden="true">
            unfold_more
          </span>
        </button>

        {/* Breadcrumb Navigation */}
        <nav aria-label="Breadcrumb" className="hidden sm:flex items-center gap-1.5 text-[#5B5F62] whitespace-nowrap shrink-0">
          <span className="font-body text-[12px]">Workspace</span>
          <span className="material-symbols-outlined text-[16px]" aria-hidden="true">
            chevron_right
          </span>
          <span className="font-label text-[14px] text-[#101B32] font-semibold">{getPageTitle(location.pathname)}</span>
        </nav>
      </div>

      <div className="flex items-center gap-2 sm:gap-3 shrink-0">
        {/* Date Selector Pill - Strictly 1 Line */}
        <button
          type="button"
          className="hidden md:inline-flex items-center gap-1.5 px-3 py-1.5 rounded hover:bg-[#EFF1F5] transition-colors whitespace-nowrap shrink-0 flex-nowrap"
          style={{ border: '1px solid #E0E3E6', backgroundColor: '#FBFCFF', color: '#44474A' }}
        >
          <span className="material-symbols-outlined text-[18px] text-[#5B5F62] shrink-0" aria-hidden="true">
            calendar_today
          </span>
          <span className="font-label text-[13px] tabular-nums text-[#101B32] font-medium whitespace-nowrap">
            Nov 1 – 21, 2026
          </span>
          <span className="material-symbols-outlined text-[16px] text-[#5B5F62] shrink-0" aria-hidden="true">
            expand_more
          </span>
        </button>

        {/* Notifications Button & Dropdown */}
        <div className="relative shrink-0">
          <button
            type="button"
            aria-label={`Notifications (${notifications.filter((n) => n.unread).length} unread)`}
            onClick={() => {
              setNotifOpen(!notifOpen);
              setMenuOpen(false);
            }}
            className="relative inline-flex items-center justify-center w-9 h-9 rounded hover:bg-[#EFF1F5] transition-colors shrink-0 cursor-pointer"
            style={{ border: '1px solid #E0E3E6', backgroundColor: '#FFFFFF', color: '#44474A' }}
          >
            <span className="material-symbols-outlined text-[20px]" aria-hidden="true">
              notifications
            </span>
            {notifications.some((n) => n.unread) && (
              <span
                className="absolute top-2 right-2 w-2 h-2 rounded-full"
                style={{ backgroundColor: '#5146E5' }}
                aria-hidden="true"
              ></span>
            )}
          </button>

          {notifOpen && (
            <>
              <div
                className="fixed inset-0 z-40"
                onClick={() => setNotifOpen(false)}
                aria-hidden="true"
              />
              <div
                className="absolute right-0 mt-2 w-80 sm:w-96 rounded-2xl shadow-2xl z-50 animate-in fade-in zoom-in-95 duration-100 overflow-hidden"
                style={{
                  backgroundColor: '#FFFFFF',
                  border: '1px solid #E0E3E6',
                  boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.2), 0 10px 10px -5px rgba(0, 0, 0, 0.1)',
                }}
              >
              <div className="px-4 py-3 border-b border-[#E0E3E6] flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <h3 className="font-headline text-[15px] font-bold text-[#101B32]">Notifications</h3>
                  {notifications.some((n) => n.unread) && (
                    <span
                      className="px-2 py-0.5 rounded-full text-[11px] font-semibold tabular-nums"
                      style={{ backgroundColor: '#F2EFFF', color: '#1F00A4' }}
                    >
                      {notifications.filter((n) => n.unread).length} unread
                    </span>
                  )}
                </div>
                <button
                  type="button"
                  onClick={() =>
                    setNotifications((prev) => prev.map((n) => ({ ...n, unread: false })))
                  }
                  className="text-[12px] font-medium text-[#5146E5] hover:underline cursor-pointer"
                >
                  Mark all read
                </button>
              </div>

              <div className="max-h-80 overflow-y-auto divide-y divide-[#E0E3E6]">
                {notifications.map((item) => (
                  <div
                    key={item.id}
                    className={`p-3.5 flex items-start gap-3 transition-colors ${
                      item.unread ? 'bg-[#F9FAFD]' : 'bg-white hover:bg-[#F5F7FB]'
                    }`}
                  >
                    <span
                      className={`w-2 h-2 rounded-full mt-1.5 shrink-0 ${
                        item.unread ? 'bg-[#5146E5]' : 'bg-transparent'
                      }`}
                    ></span>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between gap-1">
                        <span className="font-headline text-[13px] font-semibold text-[#101B32] truncate">
                          {item.title}
                        </span>
                        <span className="font-mono text-[10px] text-[#5B5F62] shrink-0">
                          {item.time}
                        </span>
                      </div>
                      <p className="font-body text-[12px] text-[#5B5F62] mt-0.5 line-clamp-2">
                        {item.desc}
                      </p>
                    </div>
                  </div>
                ))}
              </div>

              <div className="p-2 border-t border-[#E0E3E6] bg-[#FBFCFF] text-center">
                <button
                  type="button"
                  onClick={() => {
                    setNotifOpen(false);
                    navigate('/reviews');
                  }}
                  className="w-full py-1.5 rounded-lg text-[12px] font-semibold text-[#5146E5] hover:bg-[#EFF1F5] transition-colors cursor-pointer"
                >
                  Go to Review Queue →
                </button>
              </div>
            </div>
            </>
          )}
        </div>

        {/* User Profile Dropdown Button */}
        <div className="relative shrink-0">
          <button
            type="button"
            onClick={() => setMenuOpen(!menuOpen)}
            className="inline-flex items-center gap-2.5 pl-1.5 pr-2 sm:pl-2 sm:pr-3 py-1 rounded hover:bg-[#EFF1F5] transition-colors shrink-0 whitespace-nowrap flex-nowrap cursor-pointer"
          >
            <span
              className="w-8 h-8 rounded-full font-label text-[12px] inline-flex items-center justify-center font-semibold shrink-0"
              style={{ backgroundColor: '#F2EFFF', color: '#1F00A4' }}
            >
              {userInitials}
            </span>
            <div className="hidden sm:flex flex-col items-start text-left whitespace-nowrap shrink-0">
              <span className="font-label text-[13px] text-[#101B32] leading-tight font-semibold whitespace-nowrap">
                {userName}
              </span>
              <span className="font-body text-[11px] text-[#5B5F62] leading-tight whitespace-nowrap">
                {userRole}
              </span>
            </div>
            <span className="material-symbols-outlined text-[18px] text-[#5B5F62] shrink-0" aria-hidden="true">
              expand_more
            </span>
          </button>

          {/* Solid White Opaque Dropdown Menu */}
          {menuOpen && (
            <>
              <div
                className="fixed inset-0 z-40"
                onClick={() => setMenuOpen(false)}
                aria-hidden="true"
              />
              <div
                className="absolute right-0 mt-2 w-56 rounded-xl shadow-2xl p-2 z-50 animate-in fade-in zoom-in-95 duration-100"
                style={{
                  backgroundColor: '#FFFFFF',
                  border: '1px solid #E0E3E6',
                  boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.2), 0 10px 10px -5px rgba(0, 0, 0, 0.1)',
                }}
              >
              <div className="px-3 py-2 border-b border-[#E0E3E6] mb-1">
                <p className="font-label text-[13px] text-[#101B32] font-semibold leading-snug whitespace-nowrap">
                  {userName}
                </p>
                <p className="font-body text-[11px] text-[#5B5F62] leading-snug whitespace-nowrap">
                  {userRole}
                </p>
              </div>
              <button
                type="button"
                onClick={() => {
                  setMenuOpen(false);
                  navigate('/profile');
                }}
                className="w-full text-left px-3 py-2 rounded text-[13px] text-[#101B32] hover:bg-[#EFF1F5] flex items-center gap-2 transition-colors cursor-pointer"
              >
                <span className="material-symbols-outlined text-[18px] text-[#5B5F62]">person</span>
                <span>Profile Settings</span>
              </button>
              <button
                type="button"
                onClick={handleSignOut}
                className="w-full text-left px-3 py-2 rounded text-[13px] hover:bg-[#FFEDEA] flex items-center gap-2 transition-colors cursor-pointer"
                style={{ color: '#BA1A1A' }}
              >
                <span className="material-symbols-outlined text-[18px]" style={{ color: '#BA1A1A' }}>logout</span>
                <span>Sign Out</span>
              </button>
            </div>
            </>
          )}
        </div>
      </div>
    </header>
  );
};
