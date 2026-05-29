import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Award, Download, LogOut } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { apiClient, apiDownload } from '@/lib/apiClient';
import { useAuthStore } from '@/store/authStore';

export default function Certificate() {
  const { user, logout } = useAuthStore();
  const navigate = useNavigate();
  const [downloading, setDownloading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const { data: summary, isLoading } = useQuery({
    queryKey: ['dashboardSummary'],
    queryFn: () => apiClient('/dashboard/summary'),
    enabled: !!user?.id,
  });

  const canDownload = !!summary?.certificate?.enabled;
  const certificateOnly = !!summary?.certificate_only;

  const handleDownload = async () => {
    setError(null);
    setDownloading(true);
    try {
      const safeName = (summary?.name || user?.name || 'certificate').replace(/\s+/g, '_');
      await apiDownload('/certificate/download.pdf', `${safeName}_certificate.pdf`);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Download failed');
    } finally {
      setDownloading(false);
    }
  };

  if (isLoading) {
    return <div className="p-8 font-mono text-sm text-ink-faint">Loading…</div>;
  }

  return (
    <div>
      <div className="bg-chalk border-b border-border-soft px-6 lg:px-8 py-6">
        <h1 className="font-display font-bold text-3xl text-slate">
          {certificateOnly ? 'Your certificate' : 'Download certificate'}
        </h1>
        <p className="font-sans text-sm text-ink-muted mt-2">
          {certificateOnly
            ? 'Your course access has ended. You can download your completion certificate below.'
            : 'Download your course completion certificate as a PDF.'}
        </p>
      </div>

      <div className="p-6 lg:p-8 max-w-2xl">
        <div className="bg-chalk border border-border-soft rounded-sm p-8">
          <div className="flex items-start gap-4">
            <div className="w-12 h-12 rounded-sm bg-mint-pale border border-mint/30 flex items-center justify-center shrink-0">
              <Award size={22} className="text-slate" />
            </div>
            <div className="flex-1">
              <div className="font-display font-bold text-xl text-slate">
                {summary?.name || user?.name || 'Learner'}
              </div>
              <div className="font-sans text-sm text-ink-muted mt-1">
                {summary?.subscription || user?.subscription || 'Batch'}
              </div>
              {!canDownload && (
                <p className="font-sans text-sm text-amber mt-4">
                  {summary?.certificate?.reason || 'Certificate download is not available for your account.'}
                </p>
              )}
              {error && (
                <p className="font-sans text-sm text-red-600 mt-4">{error}</p>
              )}
              <div className="flex flex-wrap gap-3 mt-6">
                <button
                  type="button"
                  onClick={() => void handleDownload()}
                  disabled={!canDownload || downloading}
                  className="magnetic inline-flex items-center gap-2 bg-slate text-chalk rounded-sm px-5 py-3 font-sans text-sm font-semibold hover:bg-slate-light disabled:opacity-50"
                >
                  <Download size={16} />
                  {downloading ? 'Preparing PDF…' : 'Download certificate (PDF)'}
                </button>
                {certificateOnly && (
                  <button
                    type="button"
                    onClick={() => {
                      logout();
                      navigate('/');
                    }}
                    className="inline-flex items-center gap-2 border border-border-soft rounded-sm px-5 py-3 font-sans text-sm text-ink-secondary hover:bg-chalk-warm"
                  >
                    <LogOut size={16} />
                    Sign out
                  </button>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
