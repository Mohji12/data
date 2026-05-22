import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';

export default function ResetPassword() {
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const navigate = useNavigate();

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    // TODO: replace with API
    navigate('/login');
  };

  return (
    <div className="min-h-screen bg-chalk-warm flex items-center justify-center px-4">
      <div className="w-full max-w-[400px]">
        <Link to="/" className="font-mono text-[10px] text-mint tracking-[0.2em] uppercase mb-8 block">DR. HARISH CCM</Link>
        <h1 className="font-display font-extrabold text-4xl text-slate mb-2">New Password</h1>
        <p className="font-sans text-sm text-ink-muted mb-10">Choose a new password for your account.</p>
        <form onSubmit={handleSubmit} className="space-y-5">
          <div>
            <label className="font-mono text-[11px] text-ink-faint uppercase tracking-[0.12em] mb-2 block">New Password</label>
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} className="w-full bg-chalk border border-border-soft rounded-sm py-3.5 px-4 font-sans text-[15px] text-ink focus:border-mint/50 focus:ring-1 focus:ring-mint/15 outline-none" required />
          </div>
          <div>
            <label className="font-mono text-[11px] text-ink-faint uppercase tracking-[0.12em] mb-2 block">Confirm Password</label>
            <input type="password" value={confirm} onChange={(e) => setConfirm(e.target.value)} className="w-full bg-chalk border border-border-soft rounded-sm py-3.5 px-4 font-sans text-[15px] text-ink focus:border-mint/50 focus:ring-1 focus:ring-mint/15 outline-none" required />
          </div>
          <button type="submit" className="magnetic w-full bg-slate text-chalk rounded-sm py-4 font-sans font-semibold hover:bg-slate-light transition-all">
            Update Password
          </button>
        </form>
      </div>
    </div>
  );
}
