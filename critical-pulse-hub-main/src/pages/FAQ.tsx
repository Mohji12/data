import Navbar from '@/components/Navbar';
import Footer from '@/components/Footer';
import { faqData } from '@/lib/mockData';
import { useState } from 'react';
import { ChevronDown } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

export default function FAQ() {
  const [openItem, setOpenItem] = useState<string | null>(null);
  
  // Flatten all items from all categories into a single list
  const allItems = faqData.flatMap(category => category.items);

  return (
    <div className="min-h-screen">
      <Navbar />
      <section className="bg-chalk-warm pt-32 pb-24 px-6">
        <div className="max-w-[740px] mx-auto">
          <div className="font-mono text-[11px] text-mint mb-4 tracking-[0.16em] uppercase">FAQ</div>
          <h1 className="font-display font-black text-slate mb-12" style={{ fontSize: 'clamp(48px, 7vw, 80px)' }}>QUESTIONS.</h1>
          
          <div className="space-y-2">
            {allItems.map((item, i) => (
              <div key={i} className="border border-border-soft rounded-sm overflow-hidden bg-white">
                <button onClick={() => setOpenItem(openItem === item.q ? null : item.q)}
                  className="w-full flex items-center justify-between p-5 text-left hover:bg-ink-ghost transition-colors">
                  <span className="font-sans text-[15px] font-medium text-ink pr-4">{item.q}</span>
                  <ChevronDown size={16} className={`text-ink-faint shrink-0 transition-transform ${openItem === item.q ? 'rotate-180' : ''}`} />
                </button>
                <AnimatePresence>
                  {openItem === item.q && (
                    <motion.div initial={{ height: 0 }} animate={{ height: 'auto' }} exit={{ height: 0 }} className="overflow-hidden">
                      <div className="px-5 pb-5 font-sans text-[15px] text-ink-muted leading-[1.7] border-t border-border-soft/50 pt-4">{item.a}</div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            ))}
          </div>
        </div>
      </section>
      <Footer />
    </div>
  );
}
