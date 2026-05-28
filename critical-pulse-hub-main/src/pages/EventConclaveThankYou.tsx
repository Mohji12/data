import { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { CheckCircle } from 'lucide-react';
import Navbar from '@/components/Navbar';
import Footer from '@/components/Footer';
import { apiClient } from '@/lib/apiClient';

import { EVENT_DISPLAY_NAME, EVENT_SLUG } from '@/lib/eventConclave';

const API_BASE = `/events/${EVENT_SLUG}`;

export default function EventConclaveThankYou() {
  const [searchParams] = useSearchParams();
  const regNumber = searchParams.get('reg') || '';
  const regId = searchParams.get('id') || '';
  const [emailNote, setEmailNote] = useState<string | null>(null);

  useEffect(() => {
    const id = regId.trim();
    if (!id || !/^\d+$/.test(id)) return;

    apiClient(`/events/${EVENT_SLUG}/registrations/${id}/confirm`, { method: 'POST' })
      .then((res: { email_sent?: boolean; payment_status?: string; message?: string }) => {
        if (res.payment_status && res.payment_status.toLowerCase() !== 'credit') {
          setEmailNote('Your payment is still processing. A confirmation email will be sent once payment is confirmed.');
          return;
        }
        if (res.email_sent) {
          setEmailNote('A confirmation email with your registration number has been sent to your inbox.');
        } else {
          setEmailNote(
            'Registration is complete. If you do not receive a confirmation email within a few minutes, check spam or contact +91 8095218493.',
          );
        }
      })
      .catch(() => {
        setEmailNote(
          'Registration is complete. If you do not receive a confirmation email within a few minutes, check spam or contact support.',
        );
      });
  }, [regId]);

  return (
    <div className="min-h-screen bg-chalk-warm">
      <Navbar />
      <div className="flex items-center justify-center px-4 py-20">
        <div className="text-center max-w-[520px]">
          <div className="w-16 h-16 rounded-full bg-mint-pale border border-mint/30 flex items-center justify-center mx-auto mb-8">
            <CheckCircle size={28} className="text-mint" />
          </div>
          <h1 className="font-display font-black text-4xl text-slate mb-4">THANK YOU.</h1>
          <p className="font-sans text-lg text-ink-secondary mb-2">
            Your registration for {EVENT_DISPLAY_NAME} is confirmed.
          </p>
          {regNumber && (
            <p className="font-mono text-lg text-slate bg-chalk border border-mint/20 rounded-sm py-3 px-6 my-6 inline-block">
              Registration no. {regNumber}
            </p>
          )}
          <p className="font-sans text-sm text-ink-muted mb-10">
            {emailNote ??
              'You will receive a confirmation email with your registration number shortly.'}
          </p>
          <div className="flex flex-wrap justify-center gap-4">
            <Link
              to="/"
              className="magnetic bg-slate text-chalk rounded-sm px-8 py-3 font-sans font-semibold text-sm hover:bg-slate-light transition-all"
            >
              Back to Home
            </Link>
          </div>
        </div>
      </div>
      <Footer />
    </div>
  );
}
