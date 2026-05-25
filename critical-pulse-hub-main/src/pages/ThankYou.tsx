import { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { CheckCircle } from 'lucide-react';
import { apiClient } from '@/lib/apiClient';

export default function ThankYou() {
  const [searchParams] = useSearchParams();
  const registrationId = searchParams.get('reg');
  const [emailNote, setEmailNote] = useState<string | null>(null);

  useEffect(() => {
    const reg = registrationId?.trim();
    if (!reg || !/^\d+$/.test(reg)) return;

    apiClient(`/registration/${reg}/confirm`, { method: 'POST' })
      .then((res: { email_sent?: boolean; payment_status?: string; message?: string }) => {
        if (res.payment_status && res.payment_status.toLowerCase() !== 'credit') {
          setEmailNote('Your payment is still processing. Login details will be emailed once payment is confirmed.');
          return;
        }
        if (res.email_sent) {
          setEmailNote('A confirmation email with login details has been sent to your inbox.');
        } else {
          setEmailNote(
            'Registration is complete. If you do not receive a confirmation email within a few minutes, check spam or contact support.',
          );
        }
      })
      .catch(() => {
        setEmailNote(
          'Registration is complete. If you do not receive a confirmation email within a few minutes, check spam or contact support.',
        );
      });
  }, [registrationId]);

  return (
    <div className="min-h-screen bg-chalk-warm flex items-center justify-center px-4">
      <div className="text-center max-w-[480px]">
        <div className="w-16 h-16 rounded-full bg-mint-pale border border-mint/30 flex items-center justify-center mx-auto mb-8">
          <CheckCircle size={28} className="text-mint" />
        </div>
        <h1 className="font-display font-black text-5xl text-slate mb-4">THANK YOU.</h1>
        <p className="font-sans text-lg text-ink-secondary mb-2">Registration complete, Doctor.</p>
        <p className="font-sans text-sm text-ink-muted mb-10">
          {emailNote ??
            "You'll receive a confirmation email with login credentials and course access details shortly."}
        </p>
        <div className="flex flex-wrap justify-center gap-4">
          <Link
            to="/dashboard"
            className="magnetic bg-slate text-chalk rounded-sm px-8 py-3 font-sans font-semibold text-sm hover:bg-slate-light transition-all"
          >
            Go to Dashboard
          </Link>
          <Link
            to="/"
            className="border border-border-strong text-ink-secondary rounded-sm px-8 py-3 font-sans text-sm hover:border-slate-400 transition-all"
          >
            Back to Home
          </Link>
        </div>
      </div>
    </div>
  );
}
