import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import { apiClient } from '@/lib/apiClient';
import { InputOTP, InputOTPGroup, InputOTPSlot } from '@/components/ui/input-otp';
import {
  PASSWORD_EXACT_LENGTH,
  PASSWORD_EXACT_MESSAGE,
  PasswordEightHint,
} from '@/components/PasswordEightHint';

type Step = 'email' | 'verify';

export default function ForgotPassword() {
  const navigate = useNavigate();
  const [step, setStep] = useState<Step>('email');
  const [email, setEmail] = useState('');
  const [otp, setOtp] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [loading, setLoading] = useState(false);

  const requestOtp = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      const res = await apiClient('/auth/forgot-password/request-otp', {
        method: 'POST',
        body: JSON.stringify({ email: email.trim() }),
      });
      toast.success(res?.message || 'Verification code sent.');
      setStep('verify');
      setOtp('');
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : 'Could not send code.');
    } finally {
      setLoading(false);
    }
  };

  const resetPassword = async (e: React.FormEvent) => {
    e.preventDefault();
    if (password.length !== PASSWORD_EXACT_LENGTH) {
      toast.error(PASSWORD_EXACT_MESSAGE);
      return;
    }
    if (password !== confirm) {
      toast.error('Passwords do not match.');
      return;
    }
    setLoading(true);
    try {
      const res = await apiClient('/auth/forgot-password/reset', {
        method: 'POST',
        body: JSON.stringify({
          email: email.trim(),
          otp: otp.trim(),
          password,
        }),
      });
      toast.success(res?.message || 'Password updated.');
      navigate('/login');
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : 'Could not reset password.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-chalk-warm flex items-center justify-center px-4">
      <div className="w-full max-w-[400px]">
        <Link to="/" className="font-mono text-[10px] text-mint tracking-[0.2em] uppercase mb-8 block">
          DR. HARISH CCM
        </Link>
        <h1 className="font-display font-extrabold text-4xl text-slate mb-2">Reset Password</h1>
        <p className="font-sans text-sm text-ink-muted mb-10">
          {step === 'email'
            ? 'Enter your registered email. We will send a one-time verification code.'
            : `Enter the code sent to ${email} and choose a new password.`}
        </p>

        {step === 'email' ? (
          <form onSubmit={requestOtp} className="space-y-5">
            <div>
              <label className="font-mono text-[11px] text-ink-faint uppercase tracking-[0.12em] mb-2 block">
                Email
              </label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full bg-chalk border border-border-soft rounded-sm py-3.5 px-4 font-sans text-[15px] text-ink focus:border-mint/50 focus:ring-1 focus:ring-mint/15 outline-none"
                required
                autoComplete="email"
              />
            </div>
            <button
              type="submit"
              disabled={loading}
              className="magnetic w-full bg-slate text-chalk rounded-sm py-4 font-sans font-semibold hover:bg-slate-light transition-all disabled:opacity-50"
            >
              {loading ? 'Sending…' : 'Send verification code'}
            </button>
          </form>
        ) : (
          <form onSubmit={resetPassword} className="space-y-5">
            <div>
              <label className="font-mono text-[11px] text-ink-faint uppercase tracking-[0.12em] mb-2 block">
                Verification code
              </label>
              <div className="flex justify-center">
                <InputOTP maxLength={6} value={otp} onChange={setOtp}>
                  <InputOTPGroup>
                    <InputOTPSlot index={0} />
                    <InputOTPSlot index={1} />
                    <InputOTPSlot index={2} />
                    <InputOTPSlot index={3} />
                    <InputOTPSlot index={4} />
                    <InputOTPSlot index={5} />
                  </InputOTPGroup>
                </InputOTP>
              </div>
            </div>
            <div>
              <label className="font-mono text-[11px] text-ink-faint uppercase tracking-[0.12em] mb-2 block">
                New password (exactly 8 characters)
              </label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full bg-chalk border border-border-soft rounded-sm py-3.5 px-4 font-sans text-[15px] text-ink focus:border-mint/50 focus:ring-1 focus:ring-mint/15 outline-none"
                required
                minLength={PASSWORD_EXACT_LENGTH}
                maxLength={PASSWORD_EXACT_LENGTH}
                autoComplete="new-password"
              />
              <PasswordEightHint value={password} />
            </div>
            <div>
              <label className="font-mono text-[11px] text-ink-faint uppercase tracking-[0.12em] mb-2 block">
                Confirm password
              </label>
              <input
                type="password"
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
                className="w-full bg-chalk border border-border-soft rounded-sm py-3.5 px-4 font-sans text-[15px] text-ink focus:border-mint/50 focus:ring-1 focus:ring-mint/15 outline-none"
                required
                minLength={PASSWORD_EXACT_LENGTH}
                maxLength={PASSWORD_EXACT_LENGTH}
                autoComplete="new-password"
              />
              {confirm.length > 0 && confirm !== password && (
                <p className="font-sans text-[12px] text-amber-700 mt-1.5">Passwords do not match.</p>
              )}
            </div>
            <button
              type="submit"
              disabled={
                loading ||
                otp.length < 4 ||
                password.length !== PASSWORD_EXACT_LENGTH ||
                confirm !== password
              }
              className="magnetic w-full bg-slate text-chalk rounded-sm py-4 font-sans font-semibold hover:bg-slate-light transition-all disabled:opacity-50"
            >
              {loading ? 'Updating…' : 'Update password'}
            </button>
            <button
              type="button"
              disabled={loading}
              onClick={() => {
                setStep('email');
                setOtp('');
              }}
              className="w-full font-sans text-[13px] text-mint hover:text-mint-dark disabled:opacity-50"
            >
              Resend code (change email)
            </button>
          </form>
        )}

        <p className="font-sans text-[13px] text-ink-muted text-center mt-6">
          <Link to="/login" className="text-mint hover:text-mint-dark">
            ← Back to Sign In
          </Link>
        </p>
      </div>
    </div>
  );
}
