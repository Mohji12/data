import { Link } from 'react-router-dom';
import Navbar from '@/components/Navbar';
import Footer from '@/components/Footer';

/** Backend `batch_master` name "CCM 2" → slug `ccm-2` (see `marketingBatches` slugCandidates). */
export const CCM_PRACTICAL_BATCH_SLUG = 'ccm-2';

const tierHeaders = [
  '25% Discount till 15th April 2026',
  'Early Bird Extended Discount 15% 16th April 2026 to 29th April 2026',
  'Regular Without Discount 30th April 2026 Onwards',
];

const indian = {
  group: 'Indian Delegates (INR)',
  registrationFee: ['30,000', '30,000', '30,000'],
  discount: ['7,500', '4,500', '0'],
  total: ['22,500 + 18% GST', '25,500 + 18% GST', '30,000 + 18% GST'],
  payable: ['26,550', '30,090', '35,400'],
};

const foreign = {
  group: 'Foreign Delegates (USD)',
  registrationFee: ['365', '365', '365'],
  discount: ['90', '55', '0'],
  total: ['275 + 18% GST', '310 + 18% GST', '365 + 18% GST'],
  payable: ['325', '365', '430'],
};

const rowLabels = ['Registration Fee', 'Discount', 'Total', 'Total Amount Payable'] as const;

function CombinedFeesTable() {
  const renderBlock = (
    group: string,
    rows: { registrationFee: string[]; discount: string[]; total: string[]; payable: string[] },
  ) => {
    const cells = [rows.registrationFee, rows.discount, rows.total, rows.payable];
    return (
      <>
        {rowLabels.map((label, idx) => (
          <tr key={`${group}-${label}`}>
            {idx === 0 && (
              <td
                rowSpan={4}
                className="border border-slate/25 px-2 py-2.5 font-sans font-semibold text-slate align-middle bg-chalk-warm/50"
              >
                {group}
              </td>
            )}
            <td
              className={`border border-slate/25 px-2 py-2.5 font-sans text-ink-secondary ${
                label === 'Total Amount Payable' ? 'font-bold text-slate' : ''
              }`}
            >
              {label}
            </td>
            {cells[idx].map((cell, i) => (
              <td
                key={i}
                className={`border border-slate/25 px-2 py-2.5 font-sans tabular-nums text-ink ${
                  label === 'Total Amount Payable' ? 'font-bold text-slate' : ''
                }`}
              >
                {cell}
              </td>
            ))}
          </tr>
        ))}
      </>
    );
  };

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[720px] border-collapse text-sm border border-slate/40">
        <thead>
          <tr className="bg-slate text-chalk">
            <th colSpan={5} className="border border-slate px-3 py-3 font-sans font-bold text-center">
              Registration Fees
            </th>
          </tr>
          <tr className="bg-slate text-chalk">
            <th
              colSpan={2}
              className="border border-slate/20 px-2 py-3 font-sans font-semibold text-center text-xs sm:text-sm"
            >
              Category
            </th>
            {tierHeaders.map((h) => (
              <th
                key={h}
                className="border border-slate/20 px-2 py-3 font-sans font-semibold text-center text-[10px] sm:text-[11px] leading-snug align-bottom"
              >
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="bg-chalk text-center">
          {renderBlock(indian.group, indian)}
          {renderBlock(foreign.group, foreign)}
        </tbody>
      </table>
    </div>
  );
}

export default function PracticalSeriesBatchRegistration() {
  return (
    <div className="min-h-screen bg-chalk-warm flex flex-col">
      <Navbar />

      <section className="bg-[#0d9488] px-4 pt-10 pb-14 text-center">
        <h1 className="font-display font-black text-chalk tracking-tight" style={{ fontSize: 'clamp(28px, 5vw, 44px)' }}>
          Batch 2 Registration
        </h1>
        <nav className="mt-3 font-sans text-sm text-white/90 px-2 max-w-3xl mx-auto leading-relaxed" aria-label="Breadcrumb">
          <Link to="/" className="hover:text-white transition-colors">
            Home
          </Link>
          <span className="mx-2 text-cyan-200/90">•</span>
          <span>Batch 2 — Critical Care Medicine Practical Series Registration</span>
        </nav>
      </section>

      <main className="flex-1 w-full max-w-[960px] mx-auto px-4 sm:px-6 -mt-8 pb-16 relative z-10">
        <div className="bg-chalk border border-border-soft rounded-sm shadow-[0_12px_40px_rgba(26,35,50,0.08)] p-6 sm:p-10">
          <h2 className="font-display font-bold text-2xl sm:text-3xl text-slate mb-6 text-center">Registration Fee Structure</h2>

          <p className="font-sans text-sm sm:text-[15px] text-red-600 leading-relaxed mb-8 text-center">
            Dear Delegates,
            <br />
            Recorded window of the MCQs discussion will be open from 1st January to 30th June 2026.
          </p>

          <CombinedFeesTable />

          <div className="mt-10 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pt-8 border-t border-border-soft">
            <p className="font-sans text-xs text-ink-muted max-w-md text-center sm:text-left">
              Select your package on the next step according to the date of registration. GST applies as shown above.
            </p>
            <Link
              to={`/register?batch=${encodeURIComponent(CCM_PRACTICAL_BATCH_SLUG)}`}
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
