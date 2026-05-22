import { Link } from 'react-router-dom';

const footerLinks = [
  {
    title: 'PROGRAMME',
    links: [
      { label: 'Batch 15', to: '/courses' },
      { label: 'EDIC Prep', to: '/courses' },
      { label: 'Practical Series', to: '/courses' },
      { label: 'Pricing', to: '/courses' },
    ],
  },
  {
    title: 'RESOURCES',
    links: [
      { label: 'Faculty', to: '/faculty' },
      { label: 'Membership', to: '/membership' },
      { label: 'Publications', to: '/publications' },
      { label: 'Awards', to: '/awards' },
      { label: 'Gallery', to: '/gallery' },
      { label: 'FAQ', to: '/faq' },
    ],
  },
  {
    title: 'ACCOUNT',
    links: [
      { label: 'Sign In', to: '/login' },
      { label: 'Register', to: '/register' },
      { label: 'Dashboard', to: '/dashboard' },
      { label: 'Contact', to: '/contact' },
    ],
  },
  {
    title: 'SOCIAL',
    links: [
      { label: 'Instagram', to: 'https://www.instagram.com/dr.harish.mallapura?r=nametag' },
      { label: 'LinkedIn', to: 'https://www.linkedin.com/in/harish-d-b5a74243' },
      { label: 'Facebook', to: 'https://www.facebook.com/dr.harish.mm' },
    ],
  },
];

export default function Footer() {
  return (
    <footer className="bg-monitor-bg scanline relative overflow-hidden">
      {/* Decorative + */}
      <div className="absolute right-0 top-0 font-display font-black text-[400px] text-chalk/[0.02] leading-none pointer-events-none select-none">
        +
      </div>

      <div className="max-w-[1400px] mx-auto px-6 lg:px-12">
        {/* Top */}
        <div className="flex flex-col lg:flex-row justify-between pb-16 pt-20 border-b border-monitor-line">
          <div className="lg:w-[45%] mb-12 lg:mb-0">
            <h2 className="font-display font-extrabold text-6xl lg:text-7xl text-chalk/80 leading-[0.88]">
              MASTER<br />CRITICAL<br />CARE<br />MEDICINE
            </h2>
            <p className="font-sans text-[15px] text-chalk/40 mt-6 max-w-[280px] leading-relaxed">
              India's most rigorous online masterclass for ICU doctors. <br />Built by Dr. Harish Mallapura Maheshwarappa
            </p>
          </div>
          <div className="lg:w-[55%] grid grid-cols-2 sm:grid-cols-4 gap-8">
            {footerLinks.map((section) => (
              <div key={section.title}>
                <h3 className="font-mono text-xs text-chalk/30 tracking-wider mb-4">{section.title}</h3>
                <ul className="space-y-3">
                  {section.links.map((link) => (
                    <li key={link.label}>
                      {link.to.startsWith('http') ? (
                        <a
                          href={link.to}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="font-mono text-xs text-chalk/30 hover:text-chalk/70 transition-colors"
                        >
                          {link.label}
                        </a>
                      ) : (
                        <Link
                          to={link.to}
                          className="font-mono text-xs text-chalk/30 hover:text-chalk/70 transition-colors"
                        >
                          {link.label}
                        </Link>
                      )}
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </div>

        {/* Bottom */}
        <div className="flex flex-col sm:flex-row justify-between items-center pt-8 pb-8">
          <span className="font-mono text-[11px] text-chalk/20">
            © 2026 Dr Harish Critical Care Medicine
          </span>
          <Link to="/faq" className="font-mono text-[11px] text-mint-dark hover:text-mint transition-colors mt-2 sm:mt-0">
            Terms & Conditions
          </Link>
        </div>
      </div>
    </footer>
  );
}
