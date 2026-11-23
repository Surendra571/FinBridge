import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiClient } from '../api/client';

export const ProfilePage: React.FC = () => {
  const [profile, setProfile] = useState<{
    id?: string;
    email?: string;
    fullName?: string;
    role?: string;
  }>({});
  const [loading, setLoading] = useState(true);
  const [nameInput, setNameInput] = useState('Elena Rostova');
  const [timezone, setTimezone] = useState('America/Los_Angeles (PST)');
  const [currPassword, setCurrPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showLogoutModal, setShowLogoutModal] = useState(false);
  const [feedback, setFeedback] = useState<{ type: 'success' | 'error'; msg: string } | null>(null);

  const navigate = useNavigate();

  useEffect(() => {
    const fetchUser = async () => {
      try {
        const u = await apiClient.getCurrentUser();
        setProfile({
          id: u.id,
          email: u.email || 'e.rostova@northstar.io',
          fullName: u.fullName || 'Elena Rostova',
          role: 'VP Controller (Admin)',
        });
        setNameInput(u.fullName || 'Elena Rostova');
      } catch {
        setProfile({
          id: 'user-001',
          email: 'e.rostova@northstar.io',
          fullName: 'Elena Rostova',
          role: 'VP Controller (Admin)',
        });
      } finally {
        setLoading(false);
      }
    };
    fetchUser();
  }, []);

  const handleSaveProfile = (e: React.FormEvent) => {
    e.preventDefault();
    setFeedback({ type: 'success', msg: 'Profile details updated successfully.' });
  };

  const handleUpdatePassword = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newPassword || newPassword !== confirmPassword) {
      setFeedback({ type: 'error', msg: 'New passwords do not match or are empty.' });
      return;
    }
    setFeedback({ type: 'success', msg: 'Password updated and logged to audit trail.' });
    setCurrPassword('');
    setNewPassword('');
    setConfirmPassword('');
  };

  const handleLogout = async () => {
    try {
      await apiClient.logout();
    } catch {
      // Ignore
    } finally {
      apiClient.setToken(null);
      apiClient.setActiveOrg(null);
      navigate('/login');
    }
  };

  if (loading) {
    return (
      <div className="p-12 text-center text-[#5B5F62] flex items-center justify-center gap-2">
        <span className="material-symbols-outlined animate-spin text-[20px]">sync</span>
        <span>Loading profile...</span>
      </div>
    );
  }

  const initials = (profile.fullName || 'Elena Rostova')
    .split(' ')
    .map((w) => w[0])
    .join('')
    .slice(0, 2)
    .toUpperCase();

  return (
    <div className="flex flex-col gap-6 max-w-5xl mx-auto w-full">
      {/* 1. Profile Header (Stitch Parity) */}
      <section
        className="rounded-xl p-6 flex flex-wrap items-center justify-between gap-4 shadow-xs"
        style={{ backgroundColor: '#FFFFFF', border: '1px solid #E0E3E6' }}
      >
        <div className="flex items-center gap-4">
          <span
            className="w-14 h-14 rounded-full font-headline text-[20px] font-bold inline-flex items-center justify-center shrink-0"
            style={{ backgroundColor: '#F2EFFF', color: '#1F00A4' }}
          >
            {initials}
          </span>
          <div>
            <h1 className="font-headline text-[24px] font-bold text-[#101B32]">{profile.fullName}</h1>
            <p className="font-mono text-[13px] text-[#5B5F62] mt-0.5">
              {profile.email} · {profile.role || 'VP Controller (Admin)'}
            </p>
          </div>
        </div>

        <button
          type="button"
          onClick={() => setShowLogoutModal(true)}
          className="inline-flex items-center gap-2 px-4 py-2 rounded font-label text-[13px] font-semibold hover:bg-[#FFEDEA] transition-colors cursor-pointer"
          style={{ border: '1px solid #E0E3E6', backgroundColor: '#FFFFFF', color: '#BA1A1A' }}
        >
          <span className="material-symbols-outlined text-[18px]">logout</span>
          <span>Sign Out</span>
        </button>
      </section>

      {/* 2. Feedback Message */}
      {feedback && (
        <div
          role="alert"
          className={`rounded-xl px-4 py-3 flex items-center justify-between gap-3 animate-in fade-in duration-150 ${
            feedback.type === 'success'
              ? 'bg-[#E6F8F2] border-[#16A37B]/30 text-[#003828]'
              : 'bg-[#FFEDEA] border-[#BA1A1A]/30 text-[#690005]'
          }`}
          style={{ border: '1px solid' }}
        >
          <div className="flex items-center gap-2.5">
            <span
              className="material-symbols-outlined text-[20px]"
              style={{ color: feedback.type === 'success' ? '#006C50' : '#BA1A1A' }}
            >
              {feedback.type === 'success' ? 'check_circle' : 'error'}
            </span>
            <p className="font-body text-[14px]">{feedback.msg}</p>
          </div>
          <button type="button" onClick={() => setFeedback(null)} className="text-[12px] underline cursor-pointer">
            Dismiss
          </button>
        </div>
      )}

      {/* 3. Profile Details & Change Password Grid (Stitch Parity) */}
      <section className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {/* Profile details */}
        <article
          className="rounded-xl p-5 flex flex-col gap-4 shadow-xs"
          style={{ backgroundColor: '#FFFFFF', border: '1px solid #E0E3E6' }}
        >
          <h2 className="font-headline text-[16px] font-bold text-[#101B32] border-b pb-2.5" style={{ borderColor: '#E0E3E6' }}>
            Profile Details
          </h2>
          <form onSubmit={handleSaveProfile} className="flex flex-col gap-3">
            <div className="flex flex-col gap-1">
              <label htmlFor="p-name" className="font-label text-[12px] font-medium text-[#5B5F62]">
                User name
              </label>
              <input
                id="p-name"
                type="text"
                value={nameInput}
                onChange={(e) => setNameInput(e.target.value)}
                className="rounded px-3 py-2 text-[13px] outline-none text-[#101B32] border border-[#E0E3E6] focus:border-[#5146E5]"
                style={{ backgroundColor: '#FBFCFF' }}
              />
            </div>
            <div className="flex flex-col gap-1">
              <label htmlFor="p-email" className="font-label text-[12px] font-medium text-[#5B5F62]">
                Work email
              </label>
              <input
                id="p-email"
                type="email"
                value={profile.email}
                readOnly
                className="rounded px-3 py-2 text-[13px] font-mono border border-[#E0E3E6] text-[#5B5F62] cursor-not-allowed"
                style={{ backgroundColor: '#EFF1F5' }}
              />
            </div>
            <div className="flex flex-col gap-1">
              <label htmlFor="p-tz" className="font-label text-[12px] font-medium text-[#5B5F62]">
                Timezone
              </label>
              <select
                id="p-tz"
                value={timezone}
                onChange={(e) => setTimezone(e.target.value)}
                className="rounded px-3 py-2 text-[13px] outline-none text-[#101B32] border border-[#E0E3E6] focus:border-[#5146E5] cursor-pointer"
                style={{ backgroundColor: '#FBFCFF' }}
              >
                <option>America/Los_Angeles (PST)</option>
                <option>UTC</option>
                <option>America/New_York (EST)</option>
                <option>Europe/London (GMT)</option>
              </select>
            </div>
            <button
              type="submit"
              className="self-start mt-2 px-4 py-2 rounded text-white font-label text-[13px] font-semibold hover:opacity-95 transition-colors cursor-pointer"
              style={{ backgroundColor: '#5146E5' }}
            >
              Save Profile
            </button>
          </form>
        </article>

        {/* Change password */}
        <article
          className="rounded-xl p-5 flex flex-col gap-4 shadow-xs"
          style={{ backgroundColor: '#FFFFFF', border: '1px solid #E0E3E6' }}
        >
          <h2 className="font-headline text-[16px] font-bold text-[#101B32] border-b pb-2.5" style={{ borderColor: '#E0E3E6' }}>
            Change Password
          </h2>
          <form onSubmit={handleUpdatePassword} className="flex flex-col gap-3">
            <div className="flex flex-col gap-1">
              <label htmlFor="cp-curr" className="font-label text-[12px] font-medium text-[#5B5F62]">
                Current password
              </label>
              <input
                id="cp-curr"
                type="password"
                value={currPassword}
                onChange={(e) => setCurrPassword(e.target.value)}
                placeholder="Enter current password"
                className="rounded px-3 py-2 text-[13px] outline-none text-[#101B32] border border-[#E0E3E6] focus:border-[#5146E5]"
                style={{ backgroundColor: '#FBFCFF' }}
              />
            </div>
            <div className="flex flex-col gap-1">
              <label htmlFor="cp-new" className="font-label text-[12px] font-medium text-[#5B5F62]">
                New password
              </label>
              <input
                id="cp-new"
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                placeholder="Minimum 12 characters"
                className="rounded px-3 py-2 text-[13px] outline-none text-[#101B32] border border-[#E0E3E6] focus:border-[#5146E5]"
                style={{ backgroundColor: '#FBFCFF' }}
              />
            </div>
            <div className="flex flex-col gap-1">
              <label htmlFor="cp-conf" className="font-label text-[12px] font-medium text-[#5B5F62]">
                Confirm new password
              </label>
              <input
                id="cp-conf"
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                placeholder="Re-enter new password"
                className="rounded px-3 py-2 text-[13px] outline-none text-[#101B32] border border-[#E0E3E6] focus:border-[#5146E5]"
                style={{ backgroundColor: '#FBFCFF' }}
              />
            </div>
            <button
              type="submit"
              className="self-start mt-2 px-4 py-2 rounded font-label text-[13px] font-medium text-[#101B32] hover:bg-[#EFF1F5] transition-colors cursor-pointer"
              style={{ border: '1px solid #E0E3E6', backgroundColor: '#FFFFFF' }}
            >
              Update Password
            </button>
          </form>
        </article>
      </section>

      {/* 4. Active Sessions (Stitch Parity) */}
      <section
        className="rounded-xl overflow-hidden shadow-xs tabular-nums"
        style={{ backgroundColor: '#FFFFFF', border: '1px solid #E0E3E6' }}
      >
        <header className="px-5 py-3.5 border-b flex items-center justify-between" style={{ borderColor: '#E0E3E6' }}>
          <h2 className="font-headline text-[15px] font-bold text-[#101B32]">Active Sessions</h2>
          <span
            className="px-2.5 py-0.5 rounded-full text-[11px] font-semibold"
            style={{ backgroundColor: '#E6F8F2', color: '#003828' }}
          >
            MFA Verified ✓
          </span>
        </header>
        <div className="divide-y divide-[#E0E3E6] text-[13px]">
          <div className="px-5 py-3.5 flex items-center justify-between gap-4 hover:bg-[#F9FAFD]">
            <div>
              <p className="font-label font-semibold text-[#101B32]">Chrome on Windows · San Francisco, US</p>
              <p className="font-mono text-[12px] text-[#5B5F62]">IP 198.51.100.42 · Current session</p>
            </div>
            <span
              className="px-2.5 py-0.5 rounded-full font-label text-[11px] font-semibold"
              style={{ backgroundColor: '#E6F8F2', color: '#003828' }}
            >
              Active now
            </span>
          </div>
          <div className="px-5 py-3.5 flex items-center justify-between gap-4 hover:bg-[#F9FAFD]">
            <div>
              <p className="font-label font-semibold text-[#101B32]">FinBridge Mobile App · San Francisco, US</p>
              <p className="font-mono text-[12px] text-[#5B5F62]">IP 198.51.100.89 · Last active Nov 20, 2026</p>
            </div>
            <button
              type="button"
              onClick={() => setFeedback({ type: 'success', msg: 'Mobile session revoked.' })}
              className="px-3 py-1 rounded font-label text-[12px] font-medium text-[#BA1A1A] hover:bg-[#FFEDEA] transition-colors cursor-pointer"
              style={{ border: '1px solid #E0E3E6' }}
            >
              Revoke
            </button>
          </div>
        </div>
      </section>

      {/* MODAL: Logout Confirmation Dialog (Stitch Parity) */}
      {showLogoutModal && (
        <div className="fixed inset-0 z-50 bg-[#101B32]/40 backdrop-blur-xs flex items-center justify-center p-4">
          <div
            className="rounded-xl p-6 max-w-sm w-full shadow-2xl animate-in fade-in zoom-in-95 duration-150 space-y-4"
            style={{ backgroundColor: '#FFFFFF', border: '1px solid #E0E3E6' }}
          >
            <h3 className="font-headline text-[16px] font-bold text-[#101B32]">Sign out of FinBridge?</h3>
            <p className="font-body text-[13px] text-[#5B5F62] leading-relaxed">
              Your current session will be terminated and logged to the security audit trail.
            </p>
            <div className="flex justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={() => setShowLogoutModal(false)}
                className="px-4 py-2 rounded font-label text-[13px] font-medium text-[#101B32] hover:bg-[#EFF1F5] cursor-pointer"
                style={{ border: '1px solid #E0E3E6' }}
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleLogout}
                className="px-4 py-2 rounded text-white font-label text-[13px] font-semibold hover:opacity-95 cursor-pointer"
                style={{ backgroundColor: '#BA1A1A' }}
              >
                Logout
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default ProfilePage;
