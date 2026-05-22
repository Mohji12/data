import { Link } from 'react-router-dom';
import Navbar from '@/components/Navbar';
import Footer from '@/components/Footer';

/** Must match `batch_master.slug` / Register flow. */
export const BATCH_15_SLUG = 'batch-15';

const tierHeaders = [
  '25% Discount till 15th April 2026',
  'Early Bird Extended Discount 15% (16th April 2026 – 29th April 2026)',
  'Regular Without Discount (30th April 2026 Onwards)',
];

const indian = {
  label: 'Indian Delegates (INR)',
  registrationFee: ['30,000', '30,000', '30,000'],
  discount: ['7,500', '4,500', '0'],
  total: ['22,500 + 18% GST', '25,500 + 18% GST', '30,000 + 18% GST'],
  payable: ['26,550', '30,090', '35,400'],
};

const foreign = {
  label: 'Foreign Delegates (USD)',
  registrationFee: ['365', '365', '365'],
  discount: ['91', '55', '0'],
  total: ['274 + 18% GST', '310 + 18% GST', '365 + 18% GST'],
  payable: ['325', '366', '431'],
};

function FeeBlock({
  title,
  rows,
}: {
  title: string;
  rows: { name: string; cells: string[] }[];
}) {
  return (
    <div className="mb-8 last:mb-0">
      <div className="font-sans font-bold text-slate text-sm sm:text-base mb-3">{title}</div>
      <div className="overflow-x-auto rounded-sm border border-border-soft">
        <table className="w-full min-w-[640px] text-left text-sm border-collapse">
          <thead>
            <tr className="bg-slate text-chalk">
              <th className="font-sans font-semibold px-3 py-3 w-[28%] border-b border-white/10">Category</th>
              {tierHeaders.map((h) => (
                <th key={h} className="font-sans font-semibold px-3 py-3 text-[11px] sm:text-xs leading-snug border-b border-white/10 border-l border-white/10 align-bottom">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="bg-chalk">
            {rows.map((row) => (
              <tr key={row.name} className="border-b border-border-soft last:border-b-0">
                <td className="px-3 py-2.5 font-sans text-ink-secondary whitespace-nowrap">{row.name}</td>
                {row.cells.map((cell, i) => (
                  <td key={i} className="px-3 py-2.5 font-sans text-ink border-l border-border-soft tabular-nums">
                    {cell}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default function Batch15Registration() {
  const indianRows = [
    { name: 'Registration Fee', cells: indian.registrationFee },
    { name: 'Discount', cells: indian.discount },
    { name: 'Total', cells: indian.total },
    { name: 'Total Amount Payable', cells: indian.payable },
  ];
  const foreignRows = [
    { name: 'Registration Fee', cells: foreign.registrationFee },
    { name: 'Discount', cells: foreign.discount },
    { name: 'Total', cells: foreign.total },
    { name: 'Total Amount Payable', cells: foreign.payable },
  ];

  return (
    <div className="min-h-screen bg-chalk-warm flex flex-col">
      <Navbar />

      <section className="bg-[#0d9488] px-4 pt-10 pb-14 text-center">
        <h1 className="font-display font-black text-chalk tracking-tight" style={{ fontSize: 'clamp(32px, 5vw, 48px)' }}>
          Batch 15 Registration
        </h1>
        <nav className="mt-3 font-sans text-sm text-white/85" aria-label="Breadcrumb">
          <Link to="/" className="hover:text-white transition-colors">
            Home
          </Link>
          <span className="mx-2 opacity-70">•</span>
          <span className="text-white">Batch 15 Registration</span>
        </nav>
      </section>

      <main className="flex-1 w-full max-w-[900px] mx-auto px-4 sm:px-6 -mt-8 pb-16 relative z-10">
        <div className="bg-chalk border border-border-soft rounded-sm shadow-[0_12px_40px_rgba(26,35,50,0.08)] p-6 sm:p-10">
          <h2 className="font-display font-bold text-2xl sm:text-3xl text-slate mb-6">Registration Fee Structure</h2>

          <p className="font-sans text-sm sm:text-[15px] text-red-600 leading-relaxed mb-8">
            Dear Delegates,
            <br />
            Recorded videos of Batch 15 classes will be available till end of July 2026 (Total 6 months from 20th January 2026 to
            20th July 2026).
          </p>

          <div className="mb-2 font-sans font-bold text-slate text-lg border-b border-border-soft pb-3">Registration Fees</div>

          <div className="mt-6 space-y-10">
            <FeeBlock title={indian.label} rows={indianRows} />
            <FeeBlock title={foreign.label} rows={foreignRows} />
          </div>

          <div className="mt-10 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pt-8 border-t border-border-soft">
            <p className="font-sans text-xs text-ink-muted max-w-md">
              Select your package on the next step according to the date of registration. GST applies as shown above.
            </p>
            <Link
              to={`/register?batch=${encodeURIComponent(BATCH_15_SLUG)}`}
              className="magnetic inline-flex items-center justify-center rounded-sm bg-mint text-slate px-10 py-3.5 font-sans font-bold text-[15px] shadow-sm hover:bg-mint-light transition-colors text-center shrink-0"
            >
              Apply →
            </Link>
          </div>
        </div>
      </main>

      <Footer />
    </div>
  );
}
