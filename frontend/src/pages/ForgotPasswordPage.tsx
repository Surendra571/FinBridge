import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { apiClient } from '../api/client';
import { ShieldCheck, Mail, ArrowRight, AlertCircle, CheckCircle } from 'lucide-react';

export const ForgotPasswordPage: React.FC = () => {
  const [email, setEmail] = useState('');
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsLoading(true);

    try {
      await apiClient.forgotPassword(email);
      setSubmitted(true);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Request failed. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-900 flex flex-col justify-center py-12 sm:px-6 lg:px-8">
      <div className="sm:mx-auto sm:w-full sm:max-w-md text-center">
        <div className="inline-flex items-center justify-center p-3 bg-brand-indigo/10 rounded-2xl border border-brand-indigo/30 mb-4">
          <ShieldCheck className="w-8 h-8 text-brand-sky" />
        </div>
        <h2 className="text-3xl font-extrabold text-white tracking-tight">FinBridge</h2>
        <p className="mt-2 text-sm text-slate-400">Password Recovery</p>
      </div>

      <div className="mt-8 sm:mx-auto sm:w-full sm:max-w-md">
        <div className="bg-slate-850 py-8 px-6 shadow-2xl rounded-2xl border border-slate-800 sm:px-10">
          {submitted ? (
            <div className="text-center py-4">
              <CheckCircle className="w-12 h-12 text-brand-emerald mx-auto mb-3" />
              <h3 className="text-lg font-semibold text-white">Reset Link Dispatched</h3>
              <p className="text-sm text-slate-400 mt-2">
                If an account exists for <span className="text-white font-medium">{email}</span>, a secure password reset link has been dispatched to your inbox.
              </p>
              <div className="mt-6">
                <Link
                  to="/login"
                  className="inline-flex items-center gap-2 text-sm font-medium text-brand-sky hover:underline"
                >
                  Return to Sign In
                </Link>
              </div>
            </div>
          ) : (
            <form className="space-y-6" onSubmit={handleSubmit}>
              <h3 className="text-xl font-semibold text-white">Reset Your Password</h3>
              <p className="text-xs text-slate-400">
                Enter your verified email address and we will generate a time-limited recovery link.
              </p>

              {error && (
                <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/20 flex items-start gap-3">
                  <AlertCircle className="w-5 h-5 text-rose-400 flex-shrink-0 mt-0.5" />
                  <span className="text-sm text-rose-300">{error}</span>
                </div>
              )}

              <div>
                <label className="block text-sm font-medium text-slate-300">Work Email</label>
                <div className="mt-1 relative rounded-xl shadow-sm">
                  <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none">
                    <Mail className="h-4 w-4 text-slate-400" />
                  </div>
                  <input
                    type="email"
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="treasury@acme.com"
                    className="block w-full pl-10 pr-4 py-2.5 bg-slate-900/60 border border-slate-700 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-brand-indigo text-sm"
                  />
                </div>
              </div>

              <button
                type="submit"
                disabled={isLoading}
                className="w-full flex justify-center items-center gap-2 py-3 px-4 border border-transparent rounded-xl shadow-sm text-sm font-medium text-white bg-brand-indigo hover:bg-brand-indigo/90 focus:outline-none focus:ring-2 focus:ring-brand-indigo disabled:opacity-50 transition"
              >
                {isLoading ? (
                  <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                ) : (
                  <>
                    <span>Send Reset Link</span>
                    <ArrowRight className="w-4 h-4" />
                  </>
                )}
              </button>

              <div className="text-center pt-2">
                <Link to="/login" className="text-xs text-slate-400 hover:text-white">
                  Remember password? <span className="text-brand-sky">Sign in</span>
                </Link>
              </div>
            </form>
          )}
        </div>
      </div>
    </div>
  );
};
