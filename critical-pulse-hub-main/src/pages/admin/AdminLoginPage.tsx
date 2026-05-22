import { useState, useEffect } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { useAuthStore } from '@/store/authStore';

export default function AdminLoginPage() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();
  const loginAsAdmin = useAuthStore((s) => s.loginAsAdmin);
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const user = useAuthStore((s) => s.user);

  const from = (location.state as { from?: { pathname?: string } } | null)?.from?.pathname || '/admin';

  useEffect(() => {
    if (isAuthenticated && user?.role === 'admin') {
      navigate(from, { replace: true });
    }
    if (isAuthenticated && user?.role === 'student') {
      navigate('/dashboard', { replace: true });
    }
  }, [isAuthenticated, user, navigate, from]);

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await loginAsAdmin(username, password);
      navigate(from, { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Login failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-monitor-bg scanline flex flex-col">
      <div className="flex-1 flex items-center justify-center px-6 py-16">
        <div className="w-full max-w-[400px] bg-chalk border border-border-soft rounded-sm shadow-xl p-8">
          <div className="font-mono text-[10px] text-mint tracking-[0.2em] uppercase mb-4">Staff access</div>
          <h1 className="font-display font-black text-3xl text-slate mb-2">Admin sign in</h1>
          <p className="font-sans text-sm text-ink-muted mb-8">Use your legacy admin username and password.</p>

          {error && (
            <div className="mb-6 text-sm text-red-600 bg-red-50 border border-red-100 rounded-sm px-4 py-3">{error}</div>
          )}

          <form onSubmit={onSubmit} className="space-y-5">
            <div>
              <label className="font-mono text-[10px] text-ink-faint uppercase tracking-[0.12em] mb-2 block">Username</label>
              <input
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                autoComplete="username"
                className="w-full bg-chalk-warm border border-border-soft rounded-sm py-3.5 px-4 font-sans text-[15px] text-ink focus:border-mint/50 outline-none"
                required
              />
            </div>
            <div>
              <label className="font-mono text-[10px] text-ink-faint uppercase tracking-[0.12em] mb-2 block">Password</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="current-password"
                className="w-full bg-chalk-warm border border-border-soft rounded-sm py-3.5 px-4 font-sans text-[15px] text-ink focus:border-mint/50 outline-none"
                required
              />
            </div>
            <button
              type="submit"
              disabled={loading}
              className="w-full magnetic bg-slate text-chalk rounded-sm py-3.5 font-sans font-semibold text-sm hover:bg-slate-light disabled:opacity-50 transition-all"
            >
              {loading ? 'Signing in…' : 'Sign in'}
            </button>
          </form>

          <p className="mt-8 text-center font-sans text-xs text-ink-muted">
            <Link to="/login" className="text-mint hover:text-mint-dark">
              Student login →
            </Link>
            {' · '}
            <Link to="/" className="text-ink-faint hover:text-ink">
              Home
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
