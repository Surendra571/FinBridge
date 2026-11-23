import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { apiClient } from '../api/client';

type LoginPreviewState = 'default' | 'invalid-email' | 'wrong-password' | 'loading' | 'success' | 'server-error';

export const LoginPage: React.FC = () => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [rememberMe, setRememberMe] = useState(true);

  // Field validation and API state
  const [emailError, setEmailError] = useState<string | null>(null);
  const [passwordError, setPasswordError] = useState<string | null>(null);
  const [serverError, setServerError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  // Unverified email OTP modal state
  const [showOtpModal, setShowOtpModal] = useState(false);
  const [otpCode, setOtpCode] = useState('');
  const [otpMessage, setOtpMessage] = useState<string | null>(null);
  const [isVerifyingOtp, setIsVerifyingOtp] = useState(false);

  const navigate = useNavigate();

  // Interactive Preview State Switcher (from Stitch specification)
  const setPreviewState = (state: LoginPreviewState) => {
    setEmailError(null);
    setPasswordError(null);
    setServerError(null);
    setSuccessMessage(null);
    setIsLoading(false);
    setShowOtpModal(false);

    if (state === 'invalid-email') {
      setEmail('elena.rostova@');
      setEmailError('Enter a valid corporate email address.');
    } else if (state === 'wrong-password') {
      setEmail('elena.rostova@northstarlogistics.com');
      setPassword('WrongPass999!');
      setPasswordError('Incorrect password. 4 attempts remaining.');
    } else if (state === 'loading') {
      setIsLoading(true);
    } else if (state === 'success') {
      setSuccessMessage('Identity verified. Redirecting to Northstar Logistics workspace…');
    } else if (state === 'server-error') {
      setServerError('Unable to reach identity provider (HTTP 503). Retry in a few moments.');
    } else {
      // Default: clean empty inputs
      setEmail('');
      setPassword('');
    }
  };

  const handleLoginSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setEmailError(null);
    setPasswordError(null);
    setServerError(null);
    setSuccessMessage(null);

    const trimmedEmail = email.trim();
    if (!trimmedEmail || !trimmedEmail.includes('@') || !trimmedEmail.includes('.')) {
      setEmailError('Enter a valid corporate email address.');
      return;
    }
    if (!password) {
      setPasswordError('Please enter your password.');
      return;
    }

    setIsLoading(true);

    try {
      await apiClient.login({ email: trimmedEmail, password });
      setSuccessMessage('Identity verified. Redirecting to workspace…');

      const orgs = await apiClient.getOrganizations();
      if (orgs.length > 0) {
        apiClient.setActiveOrg(orgs[0].id);
      }

      setTimeout(() => {
        navigate('/');
      }, 700);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Invalid credentials. Please try again.';
      if (msg.toLowerCase().includes('not been verified')) {
        setShowOtpModal(true);
        setServerError('Account email has not been verified. Please enter your verification code.');
      } else if (msg.toLowerCase().includes('password') || msg.toLowerCase().includes('credential')) {
        setPasswordError('Incorrect password. Please verify and try again.');
      } else {
        setServerError(msg);
      }
    } finally {
      setIsLoading(false);
    }
  };

  const handleVerifyOtp = async (e: React.FormEvent) => {
    e.preventDefault();
    setServerError(null);
    setIsVerifyingOtp(true);
    try {
      await apiClient.verifyOtp(email, otpCode);
      setSuccessMessage('Email verified successfully! Redirecting...');
      const orgs = await apiClient.getOrganizations();
      if (orgs.length > 0) {
        apiClient.setActiveOrg(orgs[0].id);
      }
      setTimeout(() => navigate('/'), 600);
    } catch (err: unknown) {
      setServerError(err instanceof Error ? err.message : 'Invalid OTP. Please check and try again.');
    } finally {
      setIsVerifyingOtp(false);
    }
  };

  const handleResendOtp = async () => {
    try {
      const res = await apiClient.resendOtp(email);
      setOtpMessage(res.message);
    } catch (err: unknown) {
      setServerError(err instanceof Error ? err.message : 'Failed to resend OTP.');
    }
  };

  return (
    <div className="font-body antialiased min-h-screen" style={{ backgroundColor: '#F5F7FB', color: '#101B32' }}>
      <div className="min-h-screen grid grid-cols-1 lg:grid-cols-12">
        {/* Left Column: Midnight Navy Brand & Trust Panel */}
        <aside
          className="lg:col-span-5 p-8 lg:p-12 flex flex-col justify-between gap-8 min-h-screen select-none"
          style={{ backgroundColor: '#101B32', color: '#FFFFFF' }}
        >
          {/* Top Logo & Tagline */}
          <div className="flex items-center gap-3">
            <svg width="32" height="32" viewBox="0 0 28 28" fill="none" aria-hidden="true" className="shrink-0">
              <rect width="28" height="28" rx="6" fill="#5146E5" />
              <path d="M5 17.5C5 13.3579 8.58172 10 14 10C19.4183 10 23 13.3579 23 17.5" stroke="#FFFFFF" strokeWidth="2" strokeLinecap="round" />
              <path d="M5 19.5H23" stroke="#6B9DFF" strokeWidth="1.75" strokeLinecap="round" />
              <circle cx="14" cy="10" r="2" fill="#16A37B" />
            </svg>
            <div className="flex flex-col">
              <span className="font-headline text-[16px] font-semibold text-white leading-tight">FinBridge</span>
              <span className="font-label text-[11px] text-white/70">Finance. Connected. Verified.</span>
            </div>
          </div>

          {/* Center Brand Message & Product Description */}
          <div className="flex flex-col gap-6 max-w-md">
            <div className="flex flex-col gap-3">
              <h1 className="font-headline text-[32px] font-bold text-white leading-tight">
                Every bank transaction verified against your ledger.
              </h1>
              <p className="font-body text-[15px] text-white/80 leading-relaxed">
                FinBridge connects commercial bank feeds and ERP ledgers with deterministic financial rules, AI-assisted matching, and an immutable audit trail built for close-ready finance teams.
              </p>
            </div>

            {/* Operational Trust Anchors */}
            <div className="pt-6 flex flex-col gap-4" style={{ borderTop: '1px solid rgba(255, 255, 255, 0.15)' }}>
              <div className="flex items-start gap-3">
                <span className="material-symbols-outlined text-[20px] mt-0.5" style={{ color: '#16A37B' }} aria-hidden="true">
                  verified_user
                </span>
                <div className="flex flex-col gap-0.5">
                  <span className="font-title text-[14px] text-white font-semibold">Deterministic rule validation</span>
                  <span className="font-body text-[12px] text-white/70">
                    Every proposed match carries rule IDs, variance deltas, and evidence before GL posting.
                  </span>
                </div>
              </div>

              <div className="flex items-start gap-3">
                <span className="material-symbols-outlined text-[20px] mt-0.5" style={{ color: '#6B9DFF' }} aria-hidden="true">
                  history
                </span>
                <div className="flex flex-col gap-0.5">
                  <span className="font-title text-[14px] text-white font-semibold">Audit-ready close trail</span>
                  <span className="font-body text-[12px] text-white/70">
                    Every approval, rejection, and period lock is timestamped for internal and external auditors.
                  </span>
                </div>
              </div>
            </div>
          </div>

          {/* Bottom Compliance Footer */}
          <div className="flex items-center gap-3 text-white/60">
            <span className="w-2 h-2 rounded-full shrink-0" style={{ backgroundColor: '#16A37B' }} aria-hidden="true" />
            <span className="font-label text-[12px]">SOC 2 Type II · ISO 27001 · SAML 2.0 SSO</span>
          </div>
        </aside>

        {/* Right Column: Clean White Login Panel */}
        <main
          className="lg:col-span-7 p-6 lg:p-12 flex flex-col items-center justify-center gap-6"
          style={{ backgroundColor: '#F5F7FB' }}
        >
          <section
            aria-labelledby="login-heading"
            className="w-full max-w-md rounded-xl p-8 flex flex-col gap-6 shadow-sm"
            style={{ backgroundColor: '#FFFFFF', border: '1px solid #E0E3E6' }}
          >
            <header className="flex flex-col gap-1.5">
              <h2 id="login-heading" className="font-headline text-[24px] font-semibold text-[#101B32]">
                {showOtpModal ? 'Verify Your Email' : 'Sign in to FinBridge'}
              </h2>
              <p className="font-body text-[14px] text-[#5B5F62]">
                {showOtpModal
                  ? `Enter the 6-digit code sent to ${email}`
                  : 'Enter your work credentials to access your organization workspace.'}
              </p>
            </header>

            {/* Server Error Banner */}
            {serverError && (
              <div
                role="alert"
                className="rounded-lg p-3.5 flex items-start gap-2.5"
                style={{ backgroundColor: '#FFEDEA', border: '1px solid rgba(186, 26, 26, 0.2)', color: '#690005' }}
              >
                <span className="material-symbols-outlined text-[20px] shrink-0 mt-0.5" style={{ color: '#BA1A1A' }} aria-hidden="true">
                  error
                </span>
                <div className="flex flex-col gap-0.5">
                  <span className="font-title text-[14px] font-semibold">Authentication issue</span>
                  <span className="font-body text-[12px]">{serverError}</span>
                </div>
              </div>
            )}

            {/* Success Banner */}
            {successMessage && (
              <div
                role="status"
                className="rounded-lg p-3.5 flex items-start gap-2.5"
                style={{ backgroundColor: '#E6F8F2', border: '1px solid rgba(0, 108, 80, 0.2)', color: '#003828' }}
              >
                <span className="material-symbols-outlined text-[20px] shrink-0 mt-0.5" style={{ color: '#006C50' }} aria-hidden="true">
                  check_circle
                </span>
                <div className="flex flex-col gap-0.5">
                  <span className="font-title text-[14px] font-semibold">Identity verified</span>
                  <span className="font-body text-[12px]">{successMessage}</span>
                </div>
              </div>
            )}

            {/* OTP Verification Form */}
            {showOtpModal ? (
              <form onSubmit={handleVerifyOtp} className="flex flex-col gap-5">
                <div className="flex flex-col gap-1.5">
                  <label htmlFor="otp-input" className="font-label text-[12px] text-[#101B32] font-medium">
                    6-Digit Verification Code
                  </label>
                  <input
                    id="otp-input"
                    type="text"
                    required
                    maxLength={6}
                    value={otpCode}
                    onChange={(e) => setOtpCode(e.target.value.replace(/\D/g, ''))}
                    placeholder="123456"
                    className="w-full text-center tracking-[0.5em] text-2xl font-bold font-mono px-3.5 py-2.5 bg-white border border-[#E0E3E6] text-[#101B32] rounded focus:border-[#5146E5] focus:ring-1 focus:ring-[#5146E5] outline-none"
                  />
                  <div className="mt-1 flex items-center justify-between font-body text-[12px] text-[#5B5F62]">
                    <span>Didn't receive code?</span>
                    <button
                      type="button"
                      onClick={handleResendOtp}
                      className="text-[#5146E5] hover:underline font-medium"
                    >
                      Resend Code
                    </button>
                  </div>
                  {otpMessage && <p className="text-[12px] text-[#006C50] mt-1">{otpMessage}</p>}
                </div>

                <button
                  type="submit"
                  disabled={isVerifyingOtp || otpCode.length !== 6}
                  className="w-full py-2.5 px-4 rounded text-white font-label text-[14px] font-semibold transition-colors disabled:opacity-50"
                  style={{ backgroundColor: '#5146E5' }}
                >
                  {isVerifyingOtp ? 'Verifying...' : 'Verify Email & Continue'}
                </button>
              </form>
            ) : (
              /* Normal Sign-in Form */
              <form onSubmit={handleLoginSubmit} className="flex flex-col gap-5">
                {/* Work Email Field */}
                <div className="flex flex-col gap-1.5">
                  <label htmlFor="email" className="font-label text-[12px] text-[#101B32] font-medium">
                    Work email
                  </label>
                  <input
                    id="email"
                    type="email"
                    name="email"
                    autoComplete="email"
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="name@company.com"
                    className="w-full px-3.5 py-2.5 bg-white border border-[#E0E3E6] text-[#101B32] placeholder-[#74777B] rounded text-[14px] focus:border-[#5146E5] focus:ring-1 focus:ring-[#5146E5] outline-none transition-colors"
                  />
                  {emailError && (
                    <span className="font-body text-[12px] text-[#BA1A1A] flex items-center gap-1 mt-0.5">
                      <span className="material-symbols-outlined text-[14px]">error</span>
                      {emailError}
                    </span>
                  )}
                </div>

                {/* Password Field */}
                <div className="flex flex-col gap-1.5">
                  <div className="flex items-center justify-between">
                    <label htmlFor="password" className="font-label text-[12px] text-[#101B32] font-medium">
                      Password
                    </label>
                    <Link
                      to="/forgot-password"
                      className="font-label text-[12px] text-[#5146E5] hover:underline font-medium"
                    >
                      Forgot password?
                    </Link>
                  </div>
                  <div className="relative">
                    <input
                      id="password"
                      type={showPassword ? 'text' : 'password'}
                      name="password"
                      autoComplete="current-password"
                      required
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      placeholder="Enter your password"
                      className="w-full px-3.5 py-2.5 bg-white border border-[#E0E3E6] text-[#101B32] placeholder-[#74777B] rounded text-[14px] focus:border-[#5146E5] focus:ring-1 focus:ring-[#5146E5] outline-none transition-colors pr-10"
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword(!showPassword)}
                      aria-label={showPassword ? 'Hide password' : 'Show password'}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-[#74777B] hover:text-[#101B32] p-0.5"
                    >
                      <span className="material-symbols-outlined text-[18px]">
                        {showPassword ? 'visibility_off' : 'visibility'}
                      </span>
                    </button>
                  </div>
                  {passwordError && (
                    <span className="font-body text-[12px] text-[#BA1A1A] flex items-center gap-1 mt-0.5">
                      <span className="material-symbols-outlined text-[14px]">error</span>
                      {passwordError}
                    </span>
                  )}
                </div>

                {/* Remember Me Checkbox */}
                <div className="flex items-center gap-2">
                  <input
                    id="remember"
                    type="checkbox"
                    checked={rememberMe}
                    onChange={(e) => setRememberMe(e.target.checked)}
                    className="w-4 h-4 rounded border-[#E0E3E6] text-[#5146E5] focus:ring-[#5146E5] cursor-pointer"
                  />
                  <label htmlFor="remember" className="font-body text-[14px] text-[#101B32] cursor-pointer select-none">
                    Remember me for 30 days
                  </label>
                </div>

                {/* Submit Button */}
                <button
                  type="submit"
                  disabled={isLoading}
                  className="w-full inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded text-white font-label text-[14px] font-semibold transition-colors disabled:opacity-50 cursor-pointer shadow-sm hover:opacity-95"
                  style={{ backgroundColor: '#5146E5' }}
                >
                  {isLoading ? (
                    <>
                      <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                      <span>Verifying credentials...</span>
                    </>
                  ) : (
                    <span>Sign in</span>
                  )}
                </button>

                {/* Quick Demo Credentials Autofill */}
                <div className="pt-2 flex items-center justify-center gap-2 text-[12px] text-[#5B5F62]">
                  <span>Quick demo:</span>
                  <button
                    type="button"
                    onClick={() => {
                      setEmail('admin@finbridge.com');
                      setPassword('AdminPass123!');
                    }}
                    className="px-2 py-0.5 rounded border border-[#E0E3E6] bg-[#FBFCFF] hover:bg-[#EFF1F5] text-[#101B32] font-mono text-[11px]"
                  >
                    Admin
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setEmail('elena.rostova@northstarlogistics.com');
                      setPassword('ElenaPass123!');
                    }}
                    className="px-2 py-0.5 rounded border border-[#E0E3E6] bg-[#FBFCFF] hover:bg-[#EFF1F5] text-[#101B32] font-mono text-[11px]"
                  >
                    Elena
                  </button>
                </div>
              </form>
            )}

            {/* Account Registration Link */}
            <footer className="text-center pt-2" style={{ borderTop: '1px solid #E0E3E6' }}>
              <p className="font-body text-[14px] text-[#5B5F62]">
                New to FinBridge?{' '}
                <Link to="/register" className="font-label text-[#101B32] hover:text-[#5146E5] font-semibold">
                  Create account
                </Link>
              </p>
            </footer>
          </section>

          {/* Prototype State Switcher matching Stitch specification */}
          <div
            className="flex flex-wrap items-center justify-center gap-1.5 p-1.5 rounded-lg text-[11px]"
            style={{ backgroundColor: '#FFFFFF', border: '1px solid #E0E3E6' }}
          >
            <span className="text-[#5B5F62] px-2 font-medium">Preview States:</span>
            <button
              type="button"
              onClick={() => setPreviewState('default')}
              className="px-2 py-1 rounded hover:bg-[#EFF1F5] text-[#101B32] font-medium"
            >
              Default
            </button>
            <button
              type="button"
              onClick={() => setPreviewState('invalid-email')}
              className="px-2 py-1 rounded hover:bg-[#EFF1F5] text-[#BA1A1A] font-medium"
            >
              Invalid Email
            </button>
            <button
              type="button"
              onClick={() => setPreviewState('wrong-password')}
              className="px-2 py-1 rounded hover:bg-[#EFF1F5] text-[#BA1A1A] font-medium"
            >
              Wrong Password
            </button>
            <button
              type="button"
              onClick={() => setPreviewState('loading')}
              className="px-2 py-1 rounded hover:bg-[#EFF1F5] text-[#5146E5] font-medium"
            >
              Loading
            </button>
            <button
              type="button"
              onClick={() => setPreviewState('success')}
              className="px-2 py-1 rounded hover:bg-[#EFF1F5] text-[#006C50] font-medium"
            >
              Success
            </button>
            <button
              type="button"
              onClick={() => setPreviewState('server-error')}
              className="px-2 py-1 rounded hover:bg-[#EFF1F5] text-[#845400] font-medium"
            >
              503 Server Error
            </button>
          </div>
        </main>
      </div>
    </div>
  );
};
