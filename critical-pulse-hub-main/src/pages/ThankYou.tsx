import { Link } from 'react-router-dom';
import { CheckCircle } from 'lucide-react';

export default function ThankYou() {
  return (
    <div className="min-h-screen bg-chalk-warm flex items-center justify-center px-4">
      <div className="text-center max-w-[480px]">
        <div className="w-16 h-16 rounded-full bg-mint-pale border border-mint/30 flex items-center justify-center mx-auto mb-8">
          <CheckCircle size={28} className="text-mint" />
        </div>
        <h1 className="font-display font-black text-5xl text-slate mb-4">THANK YOU.</h1>
        <p className="font-sans text-lg text-ink-secondary mb-2">Registration complete, Doctor.</p>
        <p className="font-sans text-sm text-ink-muted mb-10">
          You'll receive a confirmation email with login credentials and course access details within 24 hours.
        </p>
        <div className="flex flex-wrap justify-center gap-4">
          <Link to="/dashboard" className="magnetic bg-slate text-chalk rounded-sm px-8 py-3 font-sans font-semibold text-sm hover:bg-slate-light transition-all">
            Go to Dashboard
          </Link>
          <Link to="/" className="border border-border-strong text-ink-secondary rounded-sm px-8 py-3 font-sans text-sm hover:border-slate-400 transition-all">
            Back to Home
          </Link>
        </div>
      </div>
    </div>
  );
}
