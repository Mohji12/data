import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuthStore } from '@/store/authStore';

export default function Login() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const { login } = useAuthStore();
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      await login(email, password);
      // Redirection logic based on the role set in useAuthStore
      const user = useAuthStore.getState().user;
      if (user?.role === 'admin') {
        navigate('/admin');
      } else {
        navigate('/dashboard');
      }
    } catch (err: any) {
      alert(err.message || 'Error occurred during login. Please check your credentials.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex">
      {/* Left panel */}
      <div className="hidden lg:flex lg:w-[42%] bg-monitor-bg scanline flex-col justify-between p-12 relative overflow-hidden">
        <Link to="/" className="flex items-center gap-2">
          <img
            src="/hero/logo.png"
            alt="Critical Care Medicine Logo"
            className="h-8 w-auto object-contain"
          />
          <span className="font-mono text-xs text-chalk/50 tracking-[0.2em] uppercase">DR. HARISH</span>
        </Link>

        <div>
          <h1 className="font-display font-black text-chalk leading-[0.92] mt-10" style={{ fontSize: 'clamp(44px, 6vw, 72px)' }}>
            WELCOME<br />BACK,<br />DOCTOR.
          </h1>
          <div className="space-y-4 mt-10">
            {['Pre-recorded sessions, any time', 'Exam-oriented MCQ bank', 'Direct faculty access', 'Performance analytics'].map((t) => (
              <div key={t} className="flex items-center gap-3">
                <span className="font-mono text-xs text-mint">→</span>
                <span className="font-sans text-sm text-chalk/60">{t}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="font-sans text-[13px] text-chalk/30">
          New here?{' '}
          <Link to="/register" className="text-mint hover:text-mint-light transition-colors">Register →</Link>
        </div>
      </div>

      {/* Right panel */}
      <div className="flex-1 bg-chalk-warm flex items-center justify-center px-6">
        <div className="w-full max-w-[380px]">
          <div className="font-mono text-xs text-ink-faint tracking-[0.2em] uppercase mb-8">SIGN IN</div>
          <h2 className="font-display font-extrabold text-4xl text-slate mb-1">Sign In</h2>
          <p className="font-sans text-sm text-ink-muted mb-10">Enter credentials to continue.</p>

          <form onSubmit={handleSubmit} className="space-y-5">
            <div>
              <label className="font-mono text-xs text-ink-faint uppercase tracking-[0.12em] mb-2 block">Email or Username</label>
              <input
                type="text"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full bg-chalk border border-border-soft rounded-sm py-3.5 px-4 font-sans text-[15px] text-ink focus:border-mint/50 focus:ring-1 focus:ring-mint/15 outline-none transition-all"
                placeholder="doctor@hospital.com or admin"
                required
              />
            </div>
            <div>
              <label className="font-mono text-xs text-ink-faint uppercase tracking-[0.12em] mb-2 block">Password</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full bg-chalk border border-border-soft rounded-sm py-3.5 px-4 font-sans text-[15px] text-ink focus:border-mint/50 focus:ring-1 focus:ring-mint/15 outline-none transition-all"
                placeholder="••••••••"
                required
              />
              <Link to="/forgot-password" className="font-sans text-[13px] text-mint text-right mt-2 block hover:text-mint-dark">
                Forgot password?
              </Link>
            </div>
            <button
              type="submit"
              disabled={loading}
              className="magnetic w-full bg-slate text-chalk rounded-sm py-4 font-sans font-semibold mt-4 hover:bg-slate-light transition-all disabled:opacity-50"
            >
              {loading ? 'Signing in...' : 'Sign In'}
            </button>
          </form>

          <p className="font-sans text-[13px] text-ink-muted text-center mt-6">
            No account?{' '}
            <Link to="/register" className="text-mint hover:text-mint-dark">Register →</Link>
          </p>
          <p className="font-sans text-[12px] text-ink-faint text-center mt-3">
            Staff?{' '}
            <Link to="/admin/login" className="text-mint hover:text-mint-dark">Admin sign in</Link>
            {' — use username, not email.'}
          </p>

        </div>
      </div>
    </div>
  );
}
