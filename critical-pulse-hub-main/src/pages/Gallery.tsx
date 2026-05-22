import Navbar from '@/components/Navbar';
import Footer from '@/components/Footer';
import { galleryImages } from '@/lib/mockData';
import { useState } from 'react';
import { ZoomIn, X, ChevronLeft, ChevronRight } from 'lucide-react';

export default function Gallery() {
  const [lightbox, setLightbox] = useState<number | null>(null);
  return (
    <div className="min-h-screen">
      <Navbar />
      <section className="bg-chalk pt-32 pb-24 px-6 lg:px-12">
        <div className="max-w-[1400px] mx-auto">
          <div className="font-mono text-[11px] text-mint mb-4 tracking-[0.16em] uppercase">GALLERY</div>
          <h1 className="font-display font-black text-slate mb-16" style={{ fontSize: 'clamp(48px, 7vw, 80px)' }}>MOMENTS.</h1>
          <div className="columns-1 md:columns-2 lg:columns-3 gap-3 space-y-3">
            {galleryImages.map((src, i) => (
              <div key={i} className="break-inside-avoid relative group cursor-pointer rounded-sm overflow-hidden" onClick={() => setLightbox(i)}>
                <img src={src} alt={`Gallery ${i + 1}`} className="img-doc w-full rounded-sm" />
                <div className="absolute inset-0 bg-slate/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                  <ZoomIn size={24} className="text-mint" />
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>
      {lightbox !== null && (
        <div className="fixed inset-0 z-50 bg-monitor-bg/95 backdrop-blur-sm flex items-center justify-center p-4" onClick={() => setLightbox(null)}>
          <button className="absolute top-6 right-6 text-chalk/60 hover:text-chalk" onClick={() => setLightbox(null)}><X size={24} /></button>
          <button className="absolute left-6 top-1/2 text-chalk/40 hover:text-mint" onClick={(e) => { e.stopPropagation(); setLightbox(Math.max(0, lightbox - 1)); }}><ChevronLeft size={32} /></button>
          <img src={galleryImages[lightbox]} alt="" className="img-doc max-w-full max-h-[85vh] rounded-sm" onClick={(e) => e.stopPropagation()} />
          <button className="absolute right-6 top-1/2 text-chalk/40 hover:text-mint" onClick={(e) => { e.stopPropagation(); setLightbox(Math.min(galleryImages.length - 1, lightbox + 1)); }}><ChevronRight size={32} /></button>
          <div className="absolute bottom-6 font-mono text-xs text-chalk/40">{lightbox + 1} / {galleryImages.length}</div>
        </div>
      )}
      <Footer />
    </div>
  );
}
