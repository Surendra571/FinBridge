import React, { useState, useEffect } from 'react';
import { apiClient } from '../api/client';
import { Organization } from '../types';

type SettingsTab =
  | 'profile'
  | 'team'
  | 'roles'
  | 'banks'
  | 'rules'
  | 'policies'
  | 'security';

type StatusBannerState = 'none' | 'saved' | 'perm';

interface TeamMember {
  id: string;
  name: string;
  email: string;
  role: string;
  status: 'Active' | 'Invited';
  lastActive: string;
}

const initialTeamMembers: TeamMember[] = [
  {
    id: '1',
    name: 'Elena Rostova',
    email: 'elena.rostova@northstarlogistics.com',
    role: 'Admin',
    status: 'Active',
    lastActive: 'Nov 21, 2026 · 09:42Z',
  },
  {
    id: '2',
    name: 'Marcus Vance',
    email: 'm.vance@northstarlogistics.com',
    role: 'Finance Manager',
    status: 'Active',
    lastActive: 'Nov 21, 2026 · 09:15Z',
  },
  {
    id: '3',
    name: 'Priya Nair',
    email: 'p.nair@northstarlogistics.com',
    role: 'Accountant',
    status: 'Active',
    lastActive: 'Nov 20, 2026 · 17:30Z',
  },
  {
    id: '4',
    name: 'David Chen',
    email: 'd.chen@deloitte-audit.com',
    role: 'Auditor',
    status: 'Invited',
    lastActive: 'Pending acceptance',
  },
];

export const OrganizationSettingsPage: React.FC = () => {
  const [activeTab, setActiveTab] = useState<SettingsTab>('team');
  const [statusBanner, setStatusBanner] = useState<StatusBannerState>('none');
  const [showConfirmModal, setShowConfirmModal] = useState<boolean>(false);
  const [showInviteModal, setShowInviteModal] = useState<boolean>(false);
  const [showNewOrgModal, setShowNewOrgModal] = useState<boolean>(false);

  // Tenant / Organization state from backend
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [activeOrgId, setActiveOrgId] = useState<string | null>(apiClient.getActiveOrg());
  const [newOrgName, setNewOrgName] = useState('');
  const [newOrgSlug, setNewOrgSlug] = useState('');
  const [newOrgCurrency, setNewOrgCurrency] = useState('USD');
  const [isCreatingOrg, setIsCreatingOrg] = useState(false);
  const [feedback, setFeedback] = useState<{ type: 'success' | 'error'; msg: string } | null>(null);

  // Team state
  const [teamMembers, setTeamMembers] = useState<TeamMember[]>(initialTeamMembers);
  const [inviteName, setInviteName] = useState('');
  const [inviteEmail, setInviteEmail] = useState('');
  const [inviteRole, setInviteRole] = useState('Accountant');

  useEffect(() => {
    const loadOrgs = async () => {
      try {
        const orgs = await apiClient.getOrganizations();
        setOrganizations(orgs);
        if (orgs.length > 0 && !activeOrgId) {
          setActiveOrgId(orgs[0].id);
          apiClient.setActiveOrg(orgs[0].id);
        }
      } catch (err: unknown) {
        console.error('Failed to load organizations', err);
      }
    };
    loadOrgs();
  }, [activeOrgId]);

  const handleCreateOrg = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsCreatingOrg(true);
    setFeedback(null);
    try {
      const created = await apiClient.createOrganization({
        name: newOrgName,
        slug: newOrgSlug.trim() || newOrgName.toLowerCase().replace(/[^a-z0-9]/g, '-'),
        base_currency: newOrgCurrency,
      });
      setOrganizations((prev) => [...prev, created]);
      setActiveOrgId(created.id);
      apiClient.setActiveOrg(created.id);
      setNewOrgName('');
      setNewOrgSlug('');
      setShowNewOrgModal(false);
      setFeedback({ type: 'success', msg: `Organization '${created.name}' created and activated.` });
      setStatusBanner('saved');
    } catch (err: unknown) {
      setFeedback({ type: 'error', msg: err instanceof Error ? err.message : 'Failed to create organization' });
    } finally {
      setIsCreatingOrg(false);
    }
  };

  const handleSwitchOrg = (orgId: string) => {
    setActiveOrgId(orgId);
    apiClient.setActiveOrg(orgId);
    const target = organizations.find((o) => o.id === orgId);
    setFeedback({ type: 'success', msg: `Switched active tenant workspace to ${target?.name || 'organization'}.` });
  };

  const handleInviteSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!inviteEmail) return;
    const newMember: TeamMember = {
      id: String(Date.now()),
      name: inviteName || inviteEmail.split('@')[0],
      email: inviteEmail,
      role: inviteRole,
      status: 'Invited',
      lastActive: 'Pending acceptance',
    };
    setTeamMembers((prev) => [...prev, newMember]);
    setInviteName('');
    setInviteEmail('');
    setShowInviteModal(false);
    setFeedback({ type: 'success', msg: `Invitation sent to ${inviteEmail}.` });
    setStatusBanner('saved');
  };

  return (
    <div className="flex flex-col gap-6">
      {/* 1. Header & State Switcher (Stitch Parity) */}
      <section className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="font-headline text-[24px] font-bold text-[#101B32]">Organization Settings</h1>
          <p className="font-body text-[14px] text-[#5B5F62] mt-0.5">
            Manage team roles, deterministic matching rules, approval limits, and security controls.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2.5">
          <div
            className="inline-flex items-center gap-1 p-1 rounded-lg"
            style={{ backgroundColor: '#EFF1F5', border: '1px solid #E0E3E6' }}
          >
            <button
              type="button"
              onClick={() => setStatusBanner('none')}
              className={`px-2.5 py-1 rounded font-label text-[12px] transition-colors cursor-pointer ${
                statusBanner === 'none'
                  ? 'bg-white text-[#101B32] font-semibold shadow-xs'
                  : 'text-[#5B5F62] hover:text-[#101B32]'
              }`}
            >
              Default
            </button>
            <button
              type="button"
              onClick={() => setStatusBanner('saved')}
              className={`px-2.5 py-1 rounded font-label text-[12px] transition-colors cursor-pointer ${
                statusBanner === 'saved'
                  ? 'bg-white text-[#101B32] font-semibold shadow-xs'
                  : 'text-[#5B5F62] hover:text-[#101B32]'
              }`}
            >
              Saved State
            </button>
            <button
              type="button"
              onClick={() => setStatusBanner('perm')}
              className={`px-2.5 py-1 rounded font-label text-[12px] transition-colors cursor-pointer ${
                statusBanner === 'perm'
                  ? 'bg-white text-[#101B32] font-semibold shadow-xs'
                  : 'text-[#5B5F62] hover:text-[#101B32]'
              }`}
            >
              Permission Error
            </button>
          </div>

          <button
            type="button"
            onClick={() => setShowConfirmModal(true)}
            className="px-4 py-2 rounded text-white font-label text-[14px] font-semibold hover:opacity-95 transition-colors cursor-pointer"
            style={{ backgroundColor: '#5146E5' }}
          >
            Save changes
          </button>
        </div>
      </section>

      {/* 2. Feedback Notifications */}
      {feedback && (
        <div
          className={`p-4 rounded-xl border flex items-center justify-between gap-3 animate-in fade-in duration-150 ${
            feedback.type === 'success'
              ? 'bg-[#E6F8F2] border-[#16A37B]/30 text-[#003828]'
              : 'bg-[#FFEDEA] border-[#BA1A1A]/30 text-[#690005]'
          }`}
        >
          <div className="flex items-center gap-2.5">
            <span
              className="material-symbols-outlined text-[20px]"
              style={{ color: feedback.type === 'success' ? '#006C50' : '#BA1A1A' }}
            >
              {feedback.type === 'success' ? 'check_circle' : 'error'}
            </span>
            <span className="font-body text-[14px]">{feedback.msg}</span>
          </div>
          <button
            type="button"
            onClick={() => setFeedback(null)}
            className="text-[12px] underline cursor-pointer"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* 3. Saved & Permission Error Banners (Stitch Parity) */}
      {statusBanner === 'saved' && (
        <section
          className="rounded-xl px-4 py-3 flex items-center justify-between gap-3 animate-in fade-in duration-150"
          style={{ backgroundColor: '#E6F8F2', border: '1px solid rgba(0, 108, 80, 0.3)', color: '#003828' }}
        >
          <div className="flex items-center gap-2.5">
            <span className="material-symbols-outlined text-[20px]" style={{ color: '#006C50' }} aria-hidden="true">
              check_circle
            </span>
            <p className="font-body text-[14px]">
              Settings saved and recorded in the SOC 2 Audit Trail.
            </p>
          </div>
          <button
            type="button"
            onClick={() => setStatusBanner('none')}
            className="font-label text-[12px] underline cursor-pointer"
          >
            Dismiss
          </button>
        </section>
      )}

      {statusBanner === 'perm' && (
        <section
          className="rounded-xl px-4 py-3 flex items-center justify-between gap-3 animate-in fade-in duration-150"
          style={{ backgroundColor: '#FFEDEA', border: '1px solid rgba(186, 26, 26, 0.3)', color: '#690005' }}
        >
          <div className="flex items-center gap-2.5">
            <span className="material-symbols-outlined text-[20px]" style={{ color: '#BA1A1A' }} aria-hidden="true">
              lock
            </span>
            <p className="font-body text-[14px]">
              Permission denied: Accountant role cannot modify Approval Policies or Security settings. Admin clearance required.
            </p>
          </div>
          <span
            className="px-2 py-0.5 rounded-full font-label text-[11px] font-semibold"
            style={{ backgroundColor: '#FFFFFF', color: '#BA1A1A', border: '1px solid #E0E3E6' }}
          >
            403 Forbidden
          </span>
        </section>
      )}

      {/* 4. The 7 Settings Tabs (Stitch Parity) */}
      <nav
        aria-label="Settings sections"
        className="flex flex-wrap items-center gap-1.5 border-b pb-3"
        style={{ borderColor: '#E0E3E6' }}
      >
        {[
          { id: 'profile', label: 'Organization Profile' },
          { id: 'team', label: 'Team Members' },
          { id: 'roles', label: 'Roles and Permissions' },
          { id: 'banks', label: 'Bank Accounts' },
          { id: 'rules', label: 'Matching Rules' },
          { id: 'policies', label: 'Approval Policies' },
          { id: 'security', label: 'Security' },
        ].map((tab) => {
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              type="button"
              onClick={() => setActiveTab(tab.id as SettingsTab)}
              className={`px-3 py-1.5 rounded-lg font-label text-[13px] font-medium transition-all duration-150 cursor-pointer ${
                isActive
                  ? 'bg-[#101B32] text-white shadow-xs'
                  : 'text-[#5B5F62] hover:bg-[#EFF1F5] hover:text-[#101B32]'
              }`}
            >
              {tab.label}
            </button>
          );
        })}
      </nav>

      {/* 5. TAB PANELS */}

      {/* TAB: Team Members (Default Visible in Stitch) */}
      {activeTab === 'team' && (
        <section
          className="rounded-xl overflow-hidden shadow-xs"
          style={{ backgroundColor: '#FFFFFF', border: '1px solid #E0E3E6' }}
        >
          <header className="px-5 py-4 border-b flex items-center justify-between gap-3" style={{ borderColor: '#E0E3E6' }}>
            <div>
              <h2 className="font-headline text-[16px] font-bold text-[#101B32]">Team Members</h2>
              <p className="font-body text-[13px] text-[#5B5F62] mt-0.5">
                Assign Admin, Finance Manager, Accountant, or Auditor roles with fine-grained access.
              </p>
            </div>
            <button
              type="button"
              onClick={() => setShowInviteModal(true)}
              className="px-3.5 py-2 rounded text-white font-label text-[13px] font-medium hover:opacity-95 transition-colors cursor-pointer"
              style={{ backgroundColor: '#5146E5' }}
            >
              Invite member
            </button>
          </header>

          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse tabular-nums">
              <thead>
                <tr
                  className="border-b font-label text-[12px] text-[#5B5F62]"
                  style={{ backgroundColor: '#EFF1F5', borderColor: '#E0E3E6' }}
                >
                  <th className="py-3 px-4 font-semibold">Name</th>
                  <th className="py-3 px-3 font-semibold">Email</th>
                  <th className="py-3 px-3 font-semibold">Role</th>
                  <th className="py-3 px-3 font-semibold">Invitation status</th>
                  <th className="py-3 px-3 font-semibold">Last active</th>
                  <th className="py-3 px-4 text-right font-semibold">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#E0E3E6] font-body text-[13px]">
                {teamMembers.map((member) => (
                  <tr key={member.id} className="hover:bg-[#F9FAFD] transition-colors">
                    <td className="py-3.5 px-4 font-label font-semibold text-[#101B32]">{member.name}</td>
                    <td className="py-3.5 px-3 font-mono text-[12px] text-[#5B5F62]">{member.email}</td>
                    <td className="py-3.5 px-3">
                      <span
                        className="px-2.5 py-0.5 rounded-full text-[11px] font-semibold"
                        style={{
                          backgroundColor:
                            member.role === 'Admin'
                              ? '#F2EFFF'
                              : member.role === 'Finance Manager'
                              ? '#EDF0FF'
                              : member.role === 'Auditor'
                              ? '#FFF4E5'
                              : '#EFF1F5',
                          color:
                            member.role === 'Admin'
                              ? '#1F00A4'
                              : member.role === 'Finance Manager'
                              ? '#002E6A'
                              : member.role === 'Auditor'
                              ? '#845400'
                              : '#101B32',
                        }}
                      >
                        {member.role}
                      </span>
                    </td>
                    <td className="py-3.5 px-3">
                      <span
                        className="px-2.5 py-0.5 rounded-full text-[11px] font-semibold"
                        style={{
                          backgroundColor: member.status === 'Active' ? '#E6F8F2' : '#FFF4E5',
                          color: member.status === 'Active' ? '#003828' : '#845400',
                        }}
                      >
                        {member.status}
                      </span>
                    </td>
                    <td className="py-3.5 px-3 text-[#5B5F62] text-[12px]">{member.lastActive}</td>
                    <td className="py-3.5 px-4 text-right">
                      {member.status === 'Invited' ? (
                        <button
                          type="button"
                          onClick={() => {
                            setTeamMembers((prev) => prev.filter((m) => m.id !== member.id));
                            setFeedback({ type: 'success', msg: `Revoked invitation for ${member.email}.` });
                          }}
                          className="font-label text-[12px] text-[#BA1A1A] hover:underline cursor-pointer font-medium"
                        >
                          Revoke
                        </button>
                      ) : (
                        <button
                          type="button"
                          onClick={() => setFeedback({ type: 'success', msg: `Role editor opened for ${member.name}.` })}
                          className="font-label text-[12px] text-[#5146E5] hover:underline cursor-pointer font-medium"
                        >
                          Edit role
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {/* TAB: Organization Profile */}
      {activeTab === 'profile' && (
        <div className="space-y-6">
          <section
            className="rounded-xl p-6 shadow-xs space-y-4"
            style={{ backgroundColor: '#FFFFFF', border: '1px solid #E0E3E6' }}
          >
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b pb-4" style={{ borderColor: '#E0E3E6' }}>
              <div>
                <h2 className="font-headline text-[18px] font-bold text-[#101B32]">Tenant Workspaces</h2>
                <p className="font-body text-[13px] text-[#5B5F62] mt-0.5">
                  Select your active organization or provision additional isolated corporate entities.
                </p>
              </div>
              <button
                type="button"
                onClick={() => setShowNewOrgModal(true)}
                className="px-3.5 py-2 rounded text-white font-label text-[13px] font-medium hover:opacity-95 transition-colors cursor-pointer self-start sm:self-auto"
                style={{ backgroundColor: '#5146E5' }}
              >
                + New Organization
              </button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 pt-2">
              {organizations.map((org) => {
                const isActive = org.id === activeOrgId;
                return (
                  <div
                    key={org.id}
                    onClick={() => handleSwitchOrg(org.id)}
                    className={`p-4 rounded-xl border transition-all cursor-pointer ${
                      isActive
                        ? 'ring-2 ring-[#5146E5] border-[#5146E5] bg-[#F2EFFF]/40 shadow-xs'
                        : 'bg-white border-[#E0E3E6] hover:border-[#101B32]'
                    }`}
                  >
                    <div className="flex items-start justify-between">
                      <h3 className="font-label text-[15px] font-bold text-[#101B32]">{org.name}</h3>
                      {isActive && (
                        <span
                          className="px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider"
                          style={{ backgroundColor: '#5146E5', color: '#FFFFFF' }}
                        >
                          Active
                        </span>
                      )}
                    </div>
                    <p className="font-mono text-[12px] text-[#5B5F62] mt-1">slug: {org.slug}</p>
                    <div className="mt-3 flex items-center justify-between text-[12px] text-[#5B5F62]">
                      <span>
                        Currency: <strong className="text-[#101B32]">{org.baseCurrency}</strong>
                      </span>
                      <span
                        className="px-2 py-0.5 rounded font-mono text-[11px]"
                        style={{ backgroundColor: '#EFF1F5', color: '#101B32' }}
                      >
                        {org.role || 'ADMIN'}
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          </section>

          <section
            className="rounded-xl p-6 shadow-xs space-y-4"
            style={{ backgroundColor: '#FFFFFF', border: '1px solid #E0E3E6' }}
          >
            <h2 className="font-headline text-[16px] font-bold text-[#101B32]">Organization Metadata</h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4 text-[13px]">
              <div className="p-3 rounded-lg border border-[#E0E3E6] bg-[#FBFCFF]">
                <span className="text-[#5B5F62] text-[11px] block">Primary Entity</span>
                <span className="font-semibold text-[#101B32]">Northstar Logistics Inc.</span>
              </div>
              <div className="p-3 rounded-lg border border-[#E0E3E6] bg-[#FBFCFF]">
                <span className="text-[#5B5F62] text-[11px] block">Base Reporting Currency</span>
                <span className="font-semibold text-[#101B32]">USD ($) · Fixed Cent Math</span>
              </div>
              <div className="p-3 rounded-lg border border-[#E0E3E6] bg-[#FBFCFF]">
                <span className="text-[#5B5F62] text-[11px] block">Fiscal Calendar</span>
                <span className="font-semibold text-[#101B32]">January 1 – December 31</span>
              </div>
            </div>
          </section>
        </div>
      )}

      {/* TAB: Roles and Permissions */}
      {activeTab === 'roles' && (
        <section
          className="rounded-xl p-6 shadow-xs space-y-4"
          style={{ backgroundColor: '#FFFFFF', border: '1px solid #E0E3E6' }}
        >
          <div>
            <h2 className="font-headline text-[18px] font-bold text-[#101B32]">Roles and Permissions</h2>
            <p className="font-body text-[13px] text-[#5B5F62] mt-0.5">
              Role-based access control (RBAC) enforced by zero-trust backend authorization policies.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2">
            {[
              {
                role: 'Admin',
                badge: 'Full Access',
                badgeColor: '#F2EFFF',
                textColor: '#1F00A4',
                desc: 'Full administrative control over tenant settings, user invitations, bank connections, and audit log exports.',
              },
              {
                role: 'Finance Manager',
                badge: 'Approve up to $25,000',
                badgeColor: '#EDF0FF',
                textColor: '#002E6A',
                desc: 'Authority to review flagged exceptions, execute automated runs, and approve high-value transactions up to $25k.',
              },
              {
                role: 'Accountant',
                badge: 'Reconcile & Prepare',
                badgeColor: '#EFF1F5',
                textColor: '#101B32',
                desc: 'Upload bank statements and ledger files, run matching passes, and submit proposed reconciliations for approval.',
              },
              {
                role: 'Auditor',
                badge: 'Read-Only Compliance',
                badgeColor: '#FFF4E5',
                textColor: '#845400',
                desc: 'Read-only visibility across historical reconciliation runs, cryptographic audit trails, and multi-currency reports.',
              },
            ].map((r) => (
              <div key={r.role} className="p-4 rounded-xl border border-[#E0E3E6] bg-[#FBFCFF] flex flex-col gap-2">
                <div className="flex items-center justify-between">
                  <h3 className="font-label text-[15px] font-bold text-[#101B32]">{r.role}</h3>
                  <span
                    className="px-2.5 py-0.5 rounded-full text-[11px] font-semibold"
                    style={{ backgroundColor: r.badgeColor, color: r.textColor }}
                  >
                    {r.badge}
                  </span>
                </div>
                <p className="font-body text-[13px] text-[#5B5F62] leading-relaxed">{r.desc}</p>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* TAB: Bank Accounts */}
      {activeTab === 'banks' && (
        <section
          className="rounded-xl p-6 shadow-xs space-y-4"
          style={{ backgroundColor: '#FFFFFF', border: '1px solid #E0E3E6' }}
        >
          <div>
            <h2 className="font-headline text-[18px] font-bold text-[#101B32]">Bank Accounts</h2>
            <p className="font-body text-[13px] text-[#5B5F62] mt-0.5">
              Configured financial institutions with strict currency boundaries.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-2">
            {[
              { name: 'SVB Operating', num: '•••• 4821', cur: 'USD', bal: '$4,182,410.50', status: 'Connected' },
              { name: 'Deutsche Bank', num: '•••• 9012', cur: 'EUR', bal: '€812,940.20', status: 'Connected' },
              { name: 'HDFC Corporate', num: '•••• 3104', cur: 'INR', bal: '₹18,450,210.00', status: 'Connected' },
            ].map((acc) => (
              <div key={acc.name} className="p-4 rounded-xl border border-[#E0E3E6] bg-[#FBFCFF] space-y-2">
                <div className="flex items-start justify-between">
                  <div>
                    <h3 className="font-label text-[14px] font-semibold text-[#101B32]">{acc.name}</h3>
                    <p className="font-mono text-[12px] text-[#5B5F62]">{acc.num}</p>
                  </div>
                  <span
                    className="px-2 py-0.5 rounded-full text-[10px] font-semibold"
                    style={{ backgroundColor: '#E6F8F2', color: '#003828' }}
                  >
                    {acc.status}
                  </span>
                </div>
                <div className="pt-2 flex justify-between items-baseline border-t border-[#E0E3E6]">
                  <span className="text-[12px] text-[#5B5F62]">Balance</span>
                  <span className="font-mono text-[14px] font-bold text-[#101B32]">{acc.bal}</span>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* TAB: Matching Rules */}
      {activeTab === 'rules' && (
        <section
          className="rounded-xl p-6 shadow-xs space-y-4"
          style={{ backgroundColor: '#FFFFFF', border: '1px solid #E0E3E6' }}
        >
          <div>
            <h2 className="font-headline text-[18px] font-bold text-[#101B32]">Matching Rule Settings</h2>
            <p className="font-body text-[13px] text-[#5B5F62] mt-0.5">
              Deterministic reconciliation criteria applied in order during engine execution.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2">
            <div className="p-4 rounded-xl border border-[#E0E3E6] bg-[#FBFCFF] space-y-3">
              <h3 className="font-label text-[14px] font-semibold text-[#101B32]">Engine Tolerances</h3>
              <div className="space-y-2 text-[13px]">
                <div className="flex justify-between items-center py-1 border-b border-[#E0E3E6]">
                  <span className="text-[#5B5F62]">Date window</span>
                  <span className="font-mono font-medium text-[#101B32]">±3 business days</span>
                </div>
                <div className="flex justify-between items-center py-1 border-b border-[#E0E3E6]">
                  <span className="text-[#5B5F62]">Amount tolerance</span>
                  <span className="font-mono font-medium text-[#101B32]">$0.00 strict (FX flagged)</span>
                </div>
                <div className="flex justify-between items-center py-1">
                  <span className="text-[#5B5F62]">Merchant similarity threshold</span>
                  <span className="font-mono font-medium text-[#101B32]">85% minimum Levenshtein</span>
                </div>
              </div>
            </div>

            <div className="p-4 rounded-xl border border-[#E0E3E6] bg-[#FBFCFF] space-y-3">
              <h3 className="font-label text-[14px] font-semibold text-[#101B32]">Reference Parsing</h3>
              <div className="space-y-2 text-[13px]">
                <div className="flex justify-between items-center py-1 border-b border-[#E0E3E6]">
                  <span className="text-[#5B5F62]">Reference matching</span>
                  <span className="font-mono font-medium text-[#101B32]">Exact + Invoice # tokenization</span>
                </div>
                <div className="flex justify-between items-center py-1 border-b border-[#E0E3E6]">
                  <span className="text-[#5B5F62]">Direction convention</span>
                  <span className="font-mono font-medium text-[#101B32]">Inverted Cash Flow (Bank vs GL)</span>
                </div>
                <div className="flex justify-between items-center py-1">
                  <span className="text-[#5B5F62]">Multi-line grouping</span>
                  <span className="font-mono font-medium text-[#101B32]">Enabled (1-to-N batch matches)</span>
                </div>
              </div>
            </div>
          </div>
        </section>
      )}

      {/* TAB: Approval Policies */}
      {activeTab === 'policies' && (
        <section
          className="rounded-xl p-6 shadow-xs space-y-4"
          style={{ backgroundColor: '#FFFFFF', border: '1px solid #E0E3E6' }}
        >
          <div>
            <h2 className="font-headline text-[18px] font-bold text-[#101B32]">Approval Policies & Governance</h2>
            <p className="font-body text-[13px] text-[#5B5F62] mt-0.5">
              Maker-checker requirements and threshold limits before general ledger posting.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2">
            <div className="p-4 rounded-xl border border-[#E0E3E6] bg-[#FBFCFF] space-y-2.5 text-[13px]">
              <div className="flex justify-between items-center pb-2 border-b border-[#E0E3E6]">
                <span className="text-[#5B5F62]">Maker-checker requirement</span>
                <span
                  className="px-2 py-0.5 rounded-full font-label text-[11px] font-semibold"
                  style={{ backgroundColor: '#E6F8F2', color: '#003828' }}
                >
                  Enforced
                </span>
              </div>
              <div className="flex justify-between items-center pb-2 border-b border-[#E0E3E6]">
                <span className="text-[#5B5F62]">Accountant approval limit</span>
                <span className="font-mono font-semibold text-[#101B32]">$5,000.00</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-[#5B5F62]">Finance Manager approval limit</span>
                <span className="font-mono font-semibold text-[#101B32]">$25,000.00</span>
              </div>
            </div>

            <div className="p-4 rounded-xl border border-[#E0E3E6] bg-[#FBFCFF] space-y-2.5 text-[13px]">
              <div className="flex justify-between items-center pb-2 border-b border-[#E0E3E6]">
                <span className="text-[#5B5F62]">VP Controller sign-off</span>
                <span className="font-mono font-semibold text-[#101B32]">&gt; $25,000.00</span>
              </div>
              <div className="flex justify-between items-center pb-2 border-b border-[#E0E3E6]">
                <span className="text-[#5B5F62]">Authorized reviewers</span>
                <span className="font-medium text-[#101B32]">Elena Rostova, Marcus Vance</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-[#5B5F62]">Attestation requirement</span>
                <span className="font-mono text-[#5146E5] font-medium">Digital Signature &amp; Reason Code</span>
              </div>
            </div>
          </div>
        </section>
      )}

      {/* TAB: Security */}
      {activeTab === 'security' && (
        <section
          className="rounded-xl p-6 shadow-xs space-y-4"
          style={{ backgroundColor: '#FFFFFF', border: '1px solid #E0E3E6' }}
        >
          <div>
            <h2 className="font-headline text-[18px] font-bold text-[#101B32]">Security & Secrets Management</h2>
            <p className="font-body text-[13px] text-[#5B5F62] mt-0.5">
              SOC 2 Type II controls, cryptographic audit trail signatures, and encrypted token vaults.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-2 text-[13px]">
            <div className="p-4 rounded-xl border border-[#E0E3E6] bg-[#FBFCFF] space-y-2">
              <span className="font-label font-bold text-[#101B32] block">Single Sign-On (SSO)</span>
              <p className="text-[#5B5F62]">SAML 2.0 / Okta integration active. Passwordless hardware tokens enforced.</p>
              <span
                className="inline-block px-2 py-0.5 rounded-full text-[10px] font-semibold"
                style={{ backgroundColor: '#E6F8F2', color: '#003828' }}
              >
                MFA Enforced
              </span>
            </div>

            <div className="p-4 rounded-xl border border-[#E0E3E6] bg-[#FBFCFF] space-y-2">
              <span className="font-label font-bold text-[#101B32] block">KMS Token Vault</span>
              <p className="text-[#5B5F62]">ERP connector secrets and API keys encrypted with AES-256-GCM envelope keys.</p>
              <span
                className="inline-block px-2 py-0.5 rounded-full text-[10px] font-semibold"
                style={{ backgroundColor: '#EDF0FF', color: '#002E6A' }}
              >
                Encrypted at Rest
              </span>
            </div>

            <div className="p-4 rounded-xl border border-[#E0E3E6] bg-[#FBFCFF] space-y-2">
              <span className="font-label font-bold text-[#101B32] block">Audit Integrity</span>
              <p className="text-[#5B5F62]">Every ledger change and approval logs a SHA-256 chained sequence event.</p>
              <span
                className="inline-block px-2 py-0.5 rounded-full text-[10px] font-semibold"
                style={{ backgroundColor: '#F2EFFF', color: '#1F00A4' }}
              >
                SOC 2 Verified
              </span>
            </div>
          </div>
        </section>
      )}

      {/* 6. Quick Policy & Rule Summary Strip (Stitch Parity) */}
      <section className="grid grid-cols-1 lg:grid-cols-3 gap-4 tabular-nums">
        <article
          className="rounded-xl p-4 flex flex-col gap-1.5 shadow-xs"
          style={{ backgroundColor: '#FFFFFF', border: '1px solid #E0E3E6' }}
        >
          <h3 className="font-label text-[14px] font-bold text-[#101B32]">Matching rules</h3>
          <p className="font-body text-[12px] text-[#5B5F62] leading-relaxed">
            Date window: ±3d · Amount: $0.00 strict · Reference: Exact + Invoice # · Merchant: 85%
          </p>
        </article>

        <article
          className="rounded-xl p-4 flex flex-col gap-1.5 shadow-xs"
          style={{ backgroundColor: '#FFFFFF', border: '1px solid #E0E3E6' }}
        >
          <h3 className="font-label text-[14px] font-bold text-[#101B32]">Approval policies</h3>
          <p className="font-body text-[12px] text-[#5B5F62] leading-relaxed">
            Maker-checker enforced · Limits: $5k Accountant / $25k Manager · Reviewers: E. Rostova, M. Vance
          </p>
        </article>

        <article
          className="rounded-xl p-4 flex flex-col gap-1.5 shadow-xs"
          style={{ backgroundColor: '#FFFFFF', border: '1px solid #E0E3E6' }}
        >
          <h3 className="font-label text-[14px] font-bold text-[#101B32]">Security &amp; secrets</h3>
          <p className="font-body text-[12px] text-[#5B5F62] leading-relaxed">
            SAML SSO + MFA enforced · API secrets redacted in KMS Vault (never exposed in UI)
          </p>
        </article>
      </section>

      {/* MODAL: Confirmation Dialog (Stitch Parity) */}
      {showConfirmModal && (
        <div className="fixed inset-0 z-50 bg-[#101B32]/40 backdrop-blur-xs flex items-center justify-center p-4">
          <div
            className="rounded-xl p-6 max-w-md w-full shadow-2xl animate-in fade-in zoom-in-95 duration-150 space-y-4"
            style={{ backgroundColor: '#FFFFFF', border: '1px solid #E0E3E6' }}
          >
            <div className="flex items-start justify-between gap-3">
              <h3 className="font-headline text-[16px] font-bold text-[#101B32]">Confirm policy update</h3>
              <button
                type="button"
                onClick={() => setShowConfirmModal(false)}
                className="text-[#5B5F62] hover:text-[#101B32] cursor-pointer"
              >
                <span className="material-symbols-outlined text-[20px]">close</span>
              </button>
            </div>
            <p className="font-body text-[13px] text-[#5B5F62] leading-relaxed">
              Updating organization settings applies immediately to active reconciliation runs and logs an immutable SOC 2 audit event.
            </p>
            <div className="flex justify-end gap-2.5 pt-2">
              <button
                type="button"
                onClick={() => setShowConfirmModal(false)}
                className="px-4 py-2 rounded font-label text-[13px] font-medium text-[#101B32] hover:bg-[#EFF1F5] cursor-pointer"
                style={{ border: '1px solid #E0E3E6' }}
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={() => {
                  setShowConfirmModal(false);
                  setStatusBanner('saved');
                  setFeedback({ type: 'success', msg: 'Organization settings updated and verified.' });
                }}
                className="px-4 py-2 rounded text-white font-label text-[13px] font-semibold hover:opacity-95 cursor-pointer"
                style={{ backgroundColor: '#5146E5' }}
              >
                Confirm save
              </button>
            </div>
          </div>
        </div>
      )}

      {/* MODAL: Invite Team Member */}
      {showInviteModal && (
        <div className="fixed inset-0 z-50 bg-[#101B32]/40 backdrop-blur-xs flex items-center justify-center p-4">
          <div
            className="rounded-xl p-6 max-w-md w-full shadow-2xl animate-in fade-in zoom-in-95 duration-150 space-y-4"
            style={{ backgroundColor: '#FFFFFF', border: '1px solid #E0E3E6' }}
          >
            <div className="flex items-start justify-between gap-3">
              <h3 className="font-headline text-[16px] font-bold text-[#101B32]">Invite Team Member</h3>
              <button
                type="button"
                onClick={() => setShowInviteModal(false)}
                className="text-[#5B5F62] hover:text-[#101B32] cursor-pointer"
              >
                <span className="material-symbols-outlined text-[20px]">close</span>
              </button>
            </div>

            <form onSubmit={handleInviteSubmit} className="space-y-4">
              <div>
                <label className="block text-[12px] font-medium text-[#5B5F62] mb-1">Full Name</label>
                <input
                  type="text"
                  required
                  value={inviteName}
                  onChange={(e) => setInviteName(e.target.value)}
                  placeholder="e.g. Alex Morgan"
                  className="w-full px-3 py-2 rounded-lg text-[13px] outline-none text-[#101B32] border border-[#E0E3E6] focus:border-[#5146E5]"
                />
              </div>

              <div>
                <label className="block text-[12px] font-medium text-[#5B5F62] mb-1">Work Email</label>
                <input
                  type="email"
                  required
                  value={inviteEmail}
                  onChange={(e) => setInviteEmail(e.target.value)}
                  placeholder="name@company.com"
                  className="w-full px-3 py-2 rounded-lg text-[13px] outline-none text-[#101B32] border border-[#E0E3E6] focus:border-[#5146E5]"
                />
              </div>

              <div>
                <label className="block text-[12px] font-medium text-[#5B5F62] mb-1">Role &amp; Permissions</label>
                <select
                  value={inviteRole}
                  onChange={(e) => setInviteRole(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg text-[13px] outline-none text-[#101B32] border border-[#E0E3E6] focus:border-[#5146E5] cursor-pointer"
                >
                  <option value="Admin">Admin (Full Control)</option>
                  <option value="Finance Manager">Finance Manager (Approve up to $25k)</option>
                  <option value="Accountant">Accountant (Reconcile &amp; Prepare)</option>
                  <option value="Auditor">Auditor (Read-Only Compliance)</option>
                </select>
              </div>

              <div className="flex justify-end gap-2.5 pt-2">
                <button
                  type="button"
                  onClick={() => setShowInviteModal(false)}
                  className="px-4 py-2 rounded font-label text-[13px] font-medium text-[#101B32] hover:bg-[#EFF1F5] cursor-pointer"
                  style={{ border: '1px solid #E0E3E6' }}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 rounded text-white font-label text-[13px] font-semibold hover:opacity-95 cursor-pointer"
                  style={{ backgroundColor: '#5146E5' }}
                >
                  Send Invitation
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL: Create New Organization */}
      {showNewOrgModal && (
        <div className="fixed inset-0 z-50 bg-[#101B32]/40 backdrop-blur-xs flex items-center justify-center p-4">
          <div
            className="rounded-xl p-6 max-w-md w-full shadow-2xl animate-in fade-in zoom-in-95 duration-150 space-y-4"
            style={{ backgroundColor: '#FFFFFF', border: '1px solid #E0E3E6' }}
          >
            <div className="flex items-start justify-between gap-3">
              <h3 className="font-headline text-[16px] font-bold text-[#101B32]">Create Organization</h3>
              <button
                type="button"
                onClick={() => setShowNewOrgModal(false)}
                className="text-[#5B5F62] hover:text-[#101B32] cursor-pointer"
              >
                <span className="material-symbols-outlined text-[20px]">close</span>
              </button>
            </div>

            <form onSubmit={handleCreateOrg} className="space-y-4">
              <div>
                <label className="block text-[12px] font-medium text-[#5B5F62] mb-1">Organization Name</label>
                <input
                  type="text"
                  required
                  value={newOrgName}
                  onChange={(e) => {
                    setNewOrgName(e.target.value);
                    if (!newOrgSlug) {
                      setNewOrgSlug(e.target.value.toLowerCase().replace(/[^a-z0-9]/g, '-'));
                    }
                  }}
                  placeholder="e.g. Apex Global Payments Inc."
                  className="w-full px-3 py-2 rounded-lg text-[13px] outline-none text-[#101B32] border border-[#E0E3E6] focus:border-[#5146E5]"
                />
              </div>

              <div>
                <label className="block text-[12px] font-medium text-[#5B5F62] mb-1">URL Workspace Slug</label>
                <input
                  type="text"
                  required
                  value={newOrgSlug}
                  onChange={(e) => setNewOrgSlug(e.target.value)}
                  placeholder="apex-payments"
                  className="w-full px-3 py-2 rounded-lg text-[13px] outline-none text-[#101B32] border border-[#E0E3E6] focus:border-[#5146E5]"
                />
              </div>

              <div>
                <label className="block text-[12px] font-medium text-[#5B5F62] mb-1">Base Currency</label>
                <select
                  value={newOrgCurrency}
                  onChange={(e) => setNewOrgCurrency(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg text-[13px] outline-none text-[#101B32] border border-[#E0E3E6] focus:border-[#5146E5] cursor-pointer"
                >
                  <option value="USD">USD — US Dollar</option>
                  <option value="EUR">EUR — Euro</option>
                  <option value="INR">INR — Indian Rupee</option>
                  <option value="GBP">GBP — British Pound</option>
                </select>
              </div>

              <div className="flex justify-end gap-2.5 pt-2">
                <button
                  type="button"
                  onClick={() => setShowNewOrgModal(false)}
                  className="px-4 py-2 rounded font-label text-[13px] font-medium text-[#101B32] hover:bg-[#EFF1F5] cursor-pointer"
                  style={{ border: '1px solid #E0E3E6' }}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isCreatingOrg}
                  className="px-4 py-2 rounded text-white font-label text-[13px] font-semibold hover:opacity-95 cursor-pointer disabled:opacity-50"
                  style={{ backgroundColor: '#5146E5' }}
                >
                  {isCreatingOrg ? 'Creating...' : 'Create Tenant'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default OrganizationSettingsPage;
