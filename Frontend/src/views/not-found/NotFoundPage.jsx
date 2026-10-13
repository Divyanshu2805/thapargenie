import { Link } from 'react-router-dom';

import { Brand } from '@/components/brand/Brand';
import { Cta } from '@/features/landing/ui';
import campusPhoto from '@/features/landing/assets/campus-tinted.webp';
import '@/features/landing/landing.css';

/**
 * The page for any address the app has no route for. It borrows the landing hero's look (campus
 * photo, the theme's maroon wash, gold type) so a wrong link still feels like ThaparGenie, and it
 * slides in the way the hero copy does. The tags in lib/page-meta.js mark it noindex.
 */
export default function NotFoundPage() {
  return (
    <main className="lp-hero relative isolate flex min-h-svh flex-col overflow-hidden text-white">
      <div aria-hidden="true" className="lp-hero__photo" style={{ '--photo': `url(${campusPhoto})` }} />
      <div aria-hidden="true" className="lp-hero__tint" />
      <div aria-hidden="true" className="lp-grain" />

      <header className="lp-wrap relative pt-7">
        <Link to="/" aria-label="ThaparGenie home" className="inline-flex text-white">
          <Brand />
        </Link>
      </header>

      <div className="lp-wrap relative flex flex-1 items-center py-16">
        <div className="lp-hero__copy mx-auto max-w-2xl text-center sm:mx-0 sm:text-left">
          <p className="text-sm font-semibold tracking-[0.2em] text-white/70 uppercase">Error 404</p>
          <h1 className="landing-h1 mt-4">
            <span className="landing-gold">404</span>
            <span className="block">This page isn&rsquo;t in the sources.</span>
          </h1>
          <p className="mx-auto mt-7 max-w-xl text-base leading-relaxed text-white/75 sm:mx-0 sm:text-lg">
            The link may be broken, or the page may have moved. Head back home, or ask ThaparGenie a question instead.
          </p>
          <div className="mt-9 flex flex-wrap items-center justify-center gap-x-7 gap-y-4 sm:justify-start">
            <Cta to="/">Go home</Cta>
            <Link to="/chat/" className="text-[0.95rem] font-semibold text-white transition-colors hover:text-[#ffd98a] focus-visible:text-[#ffd98a]">
              Ask a question &rarr;
            </Link>
          </div>
        </div>
      </div>
    </main>
  );
}
