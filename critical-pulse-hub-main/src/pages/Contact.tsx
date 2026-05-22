import Navbar from '@/components/Navbar';
import Footer from '@/components/Footer';
import { Mail, Phone, MapPin, Instagram, Linkedin, Facebook } from 'lucide-react';
import { useState } from 'react';

export default function Contact() {
  const [form, setForm] = useState({ name: '', email: '', message: '' });
  const update = (k: string, v: string) => setForm({ ...form, [k]: v });

  return (
    <div className="min-h-screen">
      <Navbar />
      <section className="bg-chalk-warm pt-32 pb-24 px-6 lg:px-12">
        <div className="max-w-[1400px] mx-auto">
          <div className="font-mono text-[11px] text-mint mb-4 tracking-[0.16em] uppercase">CONTACT</div>
          <h1 className="font-display font-black text-slate mb-16" style={{ fontSize: 'clamp(48px, 7vw, 80px)' }}>GET IN TOUCH.</h1>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-16">
            {/* Address Card */}
            <div className="bg-white border border-border-soft rounded-sm p-8 shadow-sm hover:shadow-md transition-all duration-300 text-center flex flex-col items-center">
              <div className="w-12 h-12 rounded-full bg-blue-50 flex items-center justify-center mb-6">
                <MapPin size={24} className="text-blue-600" />
              </div>
              <h3 className="font-display font-bold text-xl text-slate mb-4">Address</h3>
              <div className="font-sans text-[14px] text-ink-muted leading-relaxed">
                <div className="font-bold text-slate uppercase tracking-tight mb-2">HARISH CRITICAL CARE CLASSES</div>
                D 302, Purva Westend, Kudlu Gate, Service Road, <br />
                Bengaluru-560068
              </div>
            </div>

            {/* Course Queries Card */}
            <div className="bg-white border border-border-soft rounded-sm p-8 shadow-sm hover:shadow-md transition-all duration-300 text-center flex flex-col items-center">
              <div className="w-12 h-12 rounded-full bg-blue-50 flex items-center justify-center mb-6">
                <Mail size={24} className="text-blue-600" />
              </div>
              <h3 className="font-display font-bold text-xl text-slate mb-4">Course Queries</h3>
              <div className="font-sans text-[14px] text-ink-muted leading-relaxed">
                <div className="font-bold text-slate mb-2">Dr. Harish Mallapura Maheshwarappa</div>
                <div className="mb-1">Phone +91 8095218493</div>
                <div>Email: dr.harishmm@rocketmail.com</div>
              </div>
            </div>

            {/* Registration Queries Card */}
            <div className="bg-white border border-border-soft rounded-sm p-8 shadow-sm hover:shadow-md transition-all duration-300 text-center flex flex-col items-center">
              <div className="w-12 h-12 rounded-full bg-blue-50 flex items-center justify-center mb-6">
                <Mail size={24} className="text-blue-600" />
              </div>
              <h3 className="font-display font-bold text-xl text-slate mb-4">Registration Queries</h3>
              <div className="font-sans text-[14px] text-ink-muted leading-relaxed">
                <div className="font-bold text-slate mb-2">Mr. Mohan Gola</div>
                <div className="mb-1">Phone +91 8625877312</div>
                <div>Email: mohangola47@gmail.com</div>
              </div>
            </div>
          </div>
          <div className="max-w-[600px] mx-auto space-y-8">
            <div className="bg-chalk border border-border rounded-sm p-8">
              <h2 className="font-display font-bold text-2xl text-slate mb-6 text-center">Send a Message</h2>
              <form className="space-y-5" onSubmit={(e) => e.preventDefault()}>
                <div>
                  <label className="font-mono text-[11px] text-ink-faint uppercase tracking-[0.12em] mb-2 block">Name</label>
                  <input value={form.name} onChange={e => update('name', e.target.value)} className="w-full bg-chalk-warm border border-border-soft rounded-sm py-3.5 px-4 font-sans text-[15px] text-ink focus:border-mint/50 focus:ring-1 focus:ring-mint/15 outline-none" />
                </div>
                <div>
                  <label className="font-mono text-[11px] text-ink-faint uppercase tracking-[0.12em] mb-2 block">Email</label>
                  <input type="email" value={form.email} onChange={e => update('email', e.target.value)} className="w-full bg-chalk-warm border border-border-soft rounded-sm py-3.5 px-4 font-sans text-[15px] text-ink focus:border-mint/50 focus:ring-1 focus:ring-mint/15 outline-none" />
                </div>
                <div>
                  <label className="font-mono text-[11px] text-ink-faint uppercase tracking-[0.12em] mb-2 block">Message</label>
                  <textarea value={form.message} onChange={e => update('message', e.target.value)} rows={5} className="w-full bg-chalk-warm border border-border-soft rounded-sm py-3.5 px-4 font-sans text-[15px] text-ink focus:border-mint/50 focus:ring-1 focus:ring-mint/15 outline-none resize-none" />
                </div>
                <button type="submit" className="magnetic bg-slate text-chalk rounded-sm px-8 py-3 font-sans font-semibold text-sm hover:bg-slate-light transition-all">Send Message →</button>
              </form>
            </div>

            <div className="bg-white border border-border-soft rounded-sm p-8 shadow-sm">
              <h2 className="font-display font-bold text-xl text-slate mb-6 text-center">Social Profiles</h2>
              <div className="flex gap-4 justify-center">
                <a
                  href="https://www.instagram.com/dr.harish.mallapura?r=nametag"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="w-12 h-12 rounded-full bg-chalk-cool border border-border-soft flex items-center justify-center text-slate hover:bg-slate hover:text-chalk transition-all duration-300"
                  title="Instagram"
                >
                  <Instagram size={20} />
                </a>
                <a
                  href="https://www.linkedin.com/in/harish-d-b5a74243"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="w-12 h-12 rounded-full bg-chalk-cool border border-border-soft flex items-center justify-center text-slate hover:bg-slate hover:text-chalk transition-all duration-300"
                  title="LinkedIn"
                >
                  <Linkedin size={20} />
                </a>
                <a
                  href="https://www.facebook.com/dr.harish.mm"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="w-12 h-12 rounded-full bg-chalk-cool border border-border-soft flex items-center justify-center text-slate hover:bg-slate hover:text-chalk transition-all duration-300"
                  title="Facebook"
                >
                  <Facebook size={20} />
                </a>
              </div>
            </div>
          </div>
        </div>
      </section>
      <Footer />
    </div>
  );
}
