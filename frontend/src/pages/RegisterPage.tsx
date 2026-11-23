import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { apiClient } from '../api/client';
import { ShieldCheck, Eye, EyeOff, AlertCircle, CheckCircle2 } from 'lucide-react';

export const RegisterPage: React.FC = () => {
  const [firstName, setFirstName] = useState('');
  const [lastName, setLastName] = useState('');
  const [email, setEmail] = useState('');
  const [country, setCountry] = useState('United States');
  const [phone, setPhone] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);

  // OTP Stage
  const [step, setStep] = useState<'form' | 'otp'>('form');
  const [otpCode, setOtpCode] = useState('');
  const [devOtpHint, setDevOtpHint] = useState<string | null>(null);
  const [otpNotice, setOtpNotice] = useState<string | null>(null);

  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const navigate = useNavigate();

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (password !== confirmPassword) {
      setError('Passwords do not match. Please re-enter.');
      return;
    }
    if (password.length < 8) {
      setError('Password must be at least 8 characters long.');
      return;
    }

    setIsLoading(true);
    const fullName = `${firstName.trim()} ${lastName.trim()}`.trim() || 'Finance User';

    try {
      const regResp = await apiClient.register({
        full_name: fullName,
        email,
        password,
      });

      if (regResp.otp) {
        setDevOtpHint(regResp.otp);
      }
      setStep('otp');
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Registration failed. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleVerifyOtp = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsLoading(true);

    try {
      await apiClient.verifyOtp(email, otpCode);

      // Create initial organization if none
      const orgSlug = `${firstName.toLowerCase().replace(/[^a-z0-9]/g, '')}-finance-${Date.now().toString().slice(-4)}`;
      try {
        const newOrg = await apiClient.createOrganization({
          name: `${firstName}'s Finance Workspace`,
          slug: orgSlug,
          base_currency: 'USD',
        });
        apiClient.setActiveOrg(newOrg.id);
      } catch {
        // Fallback to existing orgs if already assigned
        const orgs = await apiClient.getOrganizations();
        if (orgs.length > 0) {
          apiClient.setActiveOrg(orgs[0].id);
        }
      }

      navigate('/');
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Invalid or expired OTP. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleResendOtp = async () => {
    try {
      const res = await apiClient.resendOtp(email);
      setOtpNotice(res.message);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to resend OTP.');
    }
  };

  return (
    <div className="min-h-screen bg-slate-900 flex flex-col justify-center items-center p-4 sm:p-6 lg:p-8">
      <div className="w-full max-w-5xl bg-white rounded-3xl shadow-2xl overflow-hidden grid grid-cols-1 lg:grid-cols-12 min-h-[660px]">
        {/* Left Green Banner (5 / 12) */}
        <div className="hidden lg:flex lg:col-span-5 bg-[#2E9B44] p-12 flex-col justify-center items-center text-center text-white relative">
          <div className="max-w-xs flex flex-col items-center">
            <div className="w-16 h-16 rounded-2xl bg-white/10 backdrop-blur-md flex items-center justify-center mb-6 shadow-inner border border-white/20">
              <ShieldCheck className="w-10 h-10 text-white" />
            </div>
            <h1 className="text-3xl font-extrabold tracking-tight">FinBridge™</h1>
            <p className="mt-3 text-lg font-medium text-emerald-50">
              Simple Credit & Reconciliation Management
            </p>
            <p className="mt-1 text-xs text-emerald-100/80">for Individuals and Businesses</p>
          </div>
        </div>

        {/* Right Form Panel (7 / 12) */}
        <div className="lg:col-span-7 p-8 sm:p-12 flex flex-col justify-between bg-white text-slate-800">
          <div>
            <div className="mb-6">
              <h2 className="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight">
                {step === 'otp' ? 'Verify Your Email' : 'Create Account'}
              </h2>
              <p className="mt-1.5 text-xs sm:text-sm text-slate-500">
                {step === 'otp'
                  ? `Enter the 6-digit OTP code sent to ${email}`
                  : 'Start managing your finances with FinBridge'}
              </p>
            </div>

            {error && (
              <div className="mb-5 p-3.5 rounded-xl bg-rose-50 border border-rose-200 flex items-start gap-2.5">
                <AlertCircle className="w-4 h-4 text-rose-600 flex-shrink-0 mt-0.5" />
                <span className="text-xs text-rose-800 font-medium">{error}</span>
              </div>
            )}

            {devOtpHint && step === 'otp' && (
              <div className="mb-5 p-3.5 rounded-xl bg-indigo-50 border border-indigo-200 flex items-center justify-between">
                <span className="text-xs text-indigo-900">
                  Verification Code (Dev Mode): <strong className="font-mono text-sm">{devOtpHint}</strong>
                </span>
                <button
                  type="button"
                  onClick={() => setOtpCode(devOtpHint)}
                  className="text-xs font-semibold text-indigo-700 underline"
                >
                  Auto-fill
                </button>
              </div>
            )}

            {otpNotice && (
              <div className="mb-5 p-3.5 rounded-xl bg-emerald-50 border border-emerald-200 flex items-start gap-2.5">
                <CheckCircle2 className="w-4 h-4 text-emerald-600 flex-shrink-0 mt-0.5" />
                <span className="text-xs text-emerald-800 font-medium">{otpNotice}</span>
              </div>
            )}

            {step === 'otp' ? (
              /* OTP Verification View */
              <form onSubmit={handleVerifyOtp} className="space-y-6 pt-2">
                <div>
                  <label className="block text-xs font-semibold text-slate-600 mb-2">
                    Enter 6-Digit OTP Code
                  </label>
                  <input
                    type="text"
                    required
                    maxLength={6}
                    value={otpCode}
                    onChange={(e) => setOtpCode(e.target.value.replace(/\D/g, ''))}
                    placeholder="123456"
                    className="block w-full text-center tracking-[0.5em] text-3xl font-bold px-4 py-3.5 bg-slate-50 border border-slate-300 rounded-xl text-slate-900 focus:outline-none focus:ring-2 focus:ring-[#2E9B44] focus:bg-white transition"
                  />
                  <div className="mt-2.5 flex items-center justify-between text-xs text-slate-500">
                    <span>Didn't receive code?</span>
                    <button
                      type="button"
                      onClick={handleResendOtp}
                      className="font-medium text-[#2E9B44] hover:underline"
                    >
                      Resend OTP
                    </button>
                  </div>
                </div>

                <button
                  type="submit"
                  disabled={isLoading || otpCode.length < 4}
                  className="w-full py-3.5 px-4 rounded-xl shadow-lg shadow-emerald-700/20 text-sm font-semibold text-white bg-[#2E9B44] hover:bg-[#258239] focus:outline-none focus:ring-2 focus:ring-emerald-600 disabled:opacity-50 transition"
                >
                  {isLoading ? 'Verifying...' : 'Verify Account & Continue'}
                </button>

                <div className="text-center">
                  <button
                    type="button"
                    onClick={() => setStep('form')}
                    className="text-xs text-slate-500 hover:text-slate-800"
                  >
                    ← Edit registration details
                  </button>
                </div>
              </form>
            ) : (
              /* Registration Form (Matching Image 2) */
              <form className="space-y-4" onSubmit={handleRegister}>
                {/* First Name & Last Name (2 Cols) */}
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-semibold text-slate-600 mb-1">First Name</label>
                    <input
                      type="text"
                      required
                      value={firstName}
                      onChange={(e) => setFirstName(e.target.value)}
                      placeholder="First name"
                      className="block w-full px-3.5 py-2.5 bg-slate-50 border border-slate-300 rounded-xl text-slate-900 text-xs sm:text-sm placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-[#2E9B44] focus:bg-white transition"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-semibold text-slate-600 mb-1">Last Name</label>
                    <input
                      type="text"
                      required
                      value={lastName}
                      onChange={(e) => setLastName(e.target.value)}
                      placeholder="Last name"
                      className="block w-full px-3.5 py-2.5 bg-slate-50 border border-slate-300 rounded-xl text-slate-900 text-xs sm:text-sm placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-[#2E9B44] focus:bg-white transition"
                    />
                  </div>
                </div>

                {/* Email */}
                <div>
                  <label className="block text-xs font-semibold text-slate-600 mb-1">Email</label>
                  <input
                    type="email"
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="Enter your email"
                    className="block w-full px-3.5 py-2.5 bg-slate-50 border border-slate-300 rounded-xl text-slate-900 text-xs sm:text-sm placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-[#2E9B44] focus:bg-white transition"
                  />
                </div>

                {/* Country */}
                <div>
                  <label className="block text-xs font-semibold text-slate-600 mb-1">Country</label>
                  <select
                    value={country}
                    onChange={(e) => setCountry(e.target.value)}
                    className="block w-full px-3.5 py-2.5 bg-slate-50 border border-slate-300 rounded-xl text-slate-900 text-xs sm:text-sm focus:outline-none focus:ring-2 focus:ring-[#2E9B44] focus:bg-white transition"
                  >
                    <option value="United States">🇺🇸 United States</option>
                    <option value="India">🇮🇳 India</option>
                    <option value="United Kingdom">🇬🇧 United Kingdom</option>
                    <option value="Botswana">🇧🇼 Botswana</option>
                    <option value="Singapore">🇸🇬 Singapore</option>
                    <option value="Germany">🇩🇪 Germany</option>
                  </select>
                </div>

                {/* Phone Number */}
                <div>
                  <label className="block text-xs font-semibold text-slate-600 mb-1">Phone Number</label>
                  <input
                    type="tel"
                    value={phone}
                    onChange={(e) => setPhone(e.target.value)}
                    placeholder="Enter your phone number"
                    className="block w-full px-3.5 py-2.5 bg-slate-50 border border-slate-300 rounded-xl text-slate-900 text-xs sm:text-sm placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-[#2E9B44] focus:bg-white transition"
                  />
                </div>

                {/* Password */}
                <div>
                  <label className="block text-xs font-semibold text-slate-600 mb-1">Password</label>
                  <div className="relative rounded-xl">
                    <input
                      type={showPassword ? 'text' : 'password'}
                      required
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      placeholder="Create a password"
                      className="block w-full px-3.5 py-2.5 pr-10 bg-slate-50 border border-slate-300 rounded-xl text-slate-900 text-xs sm:text-sm placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-[#2E9B44] focus:bg-white transition"
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword(!showPassword)}
                      className="absolute inset-y-0 right-0 pr-3 flex items-center text-slate-400 hover:text-slate-600"
                    >
                      {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                    </button>
                  </div>
                </div>

                {/* Confirm Password */}
                <div>
                  <label className="block text-xs font-semibold text-slate-600 mb-1">Confirm Password</label>
                  <div className="relative rounded-xl">
                    <input
                      type={showConfirmPassword ? 'text' : 'password'}
                      required
                      value={confirmPassword}
                      onChange={(e) => setConfirmPassword(e.target.value)}
                      placeholder="Confirm your password"
                      className="block w-full px-3.5 py-2.5 pr-10 bg-slate-50 border border-slate-300 rounded-xl text-slate-900 text-xs sm:text-sm placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-[#2E9B44] focus:bg-white transition"
                    />
                    <button
                      type="button"
                      onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                      className="absolute inset-y-0 right-0 pr-3 flex items-center text-slate-400 hover:text-slate-600"
                    >
                      {showConfirmPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                    </button>
                  </div>
                </div>

                <button
                  type="submit"
                  disabled={isLoading}
                  className="w-full mt-2 py-3.5 px-4 rounded-xl shadow-lg shadow-emerald-700/20 text-sm font-semibold text-white bg-[#2E9B44] hover:bg-[#258239] focus:outline-none focus:ring-2 focus:ring-emerald-600 disabled:opacity-50 transition"
                >
                  {isLoading ? 'Creating Account...' : 'Create Account'}
                </button>
              </form>
            )}
          </div>

          <div className="mt-6 text-center text-xs text-slate-500">
            Already have an account?{' '}
            <Link to="/login" className="font-semibold text-[#2E9B44] hover:underline">
              Login
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
};
