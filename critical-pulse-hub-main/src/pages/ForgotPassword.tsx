import { useState } from 'react';
import { Link } from 'react-router-dom';

export default function ForgotPassword() {
  const [email, setEmail] = useState('');
  const [sent, setSent] = useState(false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setSent(true);
  };

  return (
    <div className="min-h-screen bg-chalk-warm flex items-center justify-center px-4">
      <div className="w-full max-w-[400px]">
        <Link to="/" className="font-mono text-[10px] text-mint tracking-[0.2em] uppercase mb-8 block">DR. HARISH CCM</Link>
        <h1 className="font-display font-extrabold text-4xl text-slate mb-2">Reset Password</h1>
        <p className="font-sans text-sm text-ink-muted mb-10">
          {sent ? 'Check your email for a reset link.' : 'Enter your email to receive a reset link.'}
        </p>
        {!sent ? (
          <form onSubmit={handleSubmit} className="space-y-5">
            <div>
              <label className="font-mono text-[11px] text-ink-faint uppercase tracking-[0.12em] mb-2 block">Email</label>
              <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} className="w-full bg-chalk border border-border-soft rounded-sm py-3.5 px-4 font-sans text-[15px] text-ink focus:border-mint/50 focus:ring-1 focus:ring-mint/15 outline-none" required />
            </div>
            <button type="submit" className="magnetic w-full bg-slate text-chalk rounded-sm py-4 font-sans font-semibold hover:bg-slate-light transition-all">
              Send Reset Link
            </button>
          </form>
        ) : (
          <div className="bg-mint-pale border border-mint/20 rounded-sm p-6 text-center">
            <div className="font-mono text-sm text-slate">Reset link sent to {email}</div>
          </div>
        )}
        <p className="font-sans text-[13px] text-ink-muted text-center mt-6">
          <Link to="/login" className="text-mint hover:text-mint-dark">← Back to Sign In</Link>
        </p>
      </div>
    </div>
  );
}
