import React, { useState } from 'react';
import { useSearchParams, Link, useNavigate } from 'react-router-dom';
import { apiClient } from '../api/client';
import { ShieldCheck, CheckCircle2, AlertCircle, ArrowRight } from 'lucide-react';

export const VerifyEmailPage: React.FC = () => {
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token') || '';
  const emailParam = searchParams.get('email') || '';

  const [email, setEmail] = useState(emailParam);
  const [otpCode, setOtpCode] = useState('');
  const [status, setStatus] = useState<'idle' | 'loading' | 'success' | 'error'>('idle');
  const [message, setMessage] = useState('');
  const [otpNotice, setOtpNotice] = useState<string | null>(null);
  const navigate = useNavigate();

  const handleVerifyOtp = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email || !otpCode) {
      setStatus('error');
      setMessage('Please enter both your work email and 6-digit OTP code.');
      return;
    }

    setStatus('loading');
    try {
      await apiClient.verifyOtp(email, otpCode);
      setStatus('success');
      setMessage('Email verified successfully! Session established.');
      setTimeout(() => navigate('/'), 1200);
    } catch (err: unknown) {
      setStatus('error');
      setMessage(err instanceof Error ? err.message : 'Invalid or expired OTP code.');
    }
  };

  const handleResendOtp = async () => {
    if (!email) {
      setStatus('error');
      setMessage('Please enter your work email to receive a new OTP.');
      return;
    }
    try {
      const res = await apiClient.resendOtp(email);
      setOtpNotice(res.message);
    } catch (err: unknown) {
      setStatus('error');
      setMessage(err instanceof Error ? err.message : 'Failed to resend OTP.');
    }
  };

  const handleVerifyToken = async () => {
    if (!token) return;
    setStatus('loading');
    try {
      const res = await apiClient.verifyEmail(token);
      setStatus('success');
      setMessage(res.message || 'Email verified successfully!');
      setTimeout(() => navigate('/login'), 1200);
    } catch (err: unknown) {
      setStatus('error');
      setMessage(err instanceof Error ? err.message : 'Verification token expired or invalid.');
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 flex flex-col justify-center items-center p-4 sm:p-6 lg:p-8">
      <div className="w-full max-w-md bg-white rounded-3xl shadow-2xl p-8 sm:p-10 text-slate-800">
        <div className="text-center mb-6">
          <div className="w-12 h-12 rounded-2xl bg-indigo-600 flex items-center justify-center text-white mx-auto mb-4 shadow-lg shadow-indigo-600/30">
            <ShieldCheck className="w-7 h-7" />
          </div>
          <h2 className="text-2xl font-extrabold text-slate-900 tracking-tight">Verify Your Email</h2>
          <p className="mt-1 text-xs text-slate-500">
            Enter the 6-digit verification code sent to your inbox
          </p>
        </div>

        {status === 'success' ? (
          <div className="text-center py-4">
            <CheckCircle2 className="w-12 h-12 text-emerald-600 mx-auto mb-3" />
            <h3 className="text-lg font-bold text-slate-900">Verification Confirmed</h3>
            <p className="text-xs text-slate-600 mt-1">{message}</p>
            <div className="mt-6">
              <Link
                to="/"
                className="inline-flex items-center gap-2 px-6 py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl text-xs font-semibold shadow-md transition"
              >
                Enter Workspace
                <ArrowRight className="w-3.5 h-3.5" />
              </Link>
            </div>
          </div>
        ) : (
          <div>
            {status === 'error' && (
              <div className="mb-4 p-3 rounded-xl bg-rose-50 border border-rose-200 flex items-start gap-2.5">
                <AlertCircle className="w-4 h-4 text-rose-600 flex-shrink-0 mt-0.5" />
                <span className="text-xs text-rose-800 font-medium">{message}</span>
              </div>
            )}

            {otpNotice && (
              <div className="mb-4 p-3 rounded-xl bg-emerald-50 border border-emerald-200 flex items-start gap-2.5">
                <CheckCircle2 className="w-4 h-4 text-emerald-600 flex-shrink-0 mt-0.5" />
                <span className="text-xs text-emerald-800 font-medium">{otpNotice}</span>
              </div>
            )}

            {token ? (
              <div className="text-center">
                <p className="text-xs text-slate-600 mb-4">
                  We found a token link in your URL. Click below to verify immediately:
                </p>
                <button
                  onClick={handleVerifyToken}
                  disabled={status === 'loading'}
                  className="w-full py-3 px-4 rounded-xl text-xs font-semibold text-white bg-indigo-600 hover:bg-indigo-700 shadow-md transition disabled:opacity-50"
                >
                  {status === 'loading' ? 'Verifying...' : 'Verify with Token'}
                </button>
              </div>
            ) : (
              <form onSubmit={handleVerifyOtp} className="space-y-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-600 mb-1">Work Email</label>
                  <input
                    type="email"
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="you@company.com"
                    className="block w-full px-3.5 py-2.5 bg-slate-50 border border-slate-300 rounded-xl text-slate-900 text-xs sm:text-sm focus:outline-none focus:ring-2 focus:ring-indigo-600 focus:bg-white transition"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-600 mb-1">6-Digit OTP Code</label>
                  <input
                    type="text"
                    required
                    maxLength={6}
                    value={otpCode}
                    onChange={(e) => setOtpCode(e.target.value.replace(/\D/g, ''))}
                    placeholder="123456"
                    className="block w-full text-center tracking-[0.4em] text-2xl font-bold px-3.5 py-2.5 bg-slate-50 border border-slate-300 rounded-xl text-slate-900 focus:outline-none focus:ring-2 focus:ring-indigo-600 focus:bg-white transition"
                  />
                  <div className="mt-2 flex items-center justify-between text-xs text-slate-500">
                    <span>Didn't receive code?</span>
                    <button
                      type="button"
                      onClick={handleResendOtp}
                      className="font-medium text-indigo-600 hover:underline"
                    >
                      Resend OTP
                    </button>
                  </div>
                </div>

                <button
                  type="submit"
                  disabled={status === 'loading' || otpCode.length < 4}
                  className="w-full py-3.5 px-4 rounded-xl shadow-lg shadow-indigo-600/20 text-xs font-semibold text-white bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 transition"
                >
                  {status === 'loading' ? 'Verifying...' : 'Verify OTP & Log In'}
                </button>
              </form>
            )}

            <div className="mt-6 text-center text-xs text-slate-500">
              <Link to="/login" className="font-semibold text-indigo-600 hover:underline">
                ← Return to Login
              </Link>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
