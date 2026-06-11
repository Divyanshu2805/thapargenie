import { ArrowUp, Sparkles } from 'lucide-react';
import { useEffect } from 'react';
import { Link } from 'react-router-dom';

import { Ambient } from '@/components/ambient';
import { LogoGlyph } from '@/components/brand/Brand';
import { useTypewriter } from '@/hooks/use-typewriter';
import { preloadLanding } from '@/features/landing/load';
import { useSlideClick } from '@/lib/page-slide';

import './AuthShell.css';

// Example questions that type themselves out in the brand panel.
const EXAMPLES = [
  'When does the odd semester start?',
  'What is the hostel fee for first-years?',
  'How do I apply for a merit scholarship?',
  'What is the attendance rule for exams?',
  'Where is the admissions office?',
];

function TypedPrompt() {
  const { text } = useTypewriter(EXAMPLES);
  return (
    <div className="auth-hero__prompt icon-nudge" aria-hidden="true">
      <Sparkles className="auth-hero__prompt-icon" />
      <span className="auth-hero__prompt-text">
        {text}
        <span className="auth-hero__caret" />
      </span>
      <span className="auth-hero__prompt-send">
        <ArrowUp />
      </span>
    </div>
  );
}

// The logo leads back to the landing page, sliding left to right like going back.
const toLanding = { back: true, ready: () => Boolean(document.querySelector('.landing')) };

export default function AuthShell({ title, description, children }) {
  const home = useSlideClick(toLanding);
  // Fetch the landing page ahead so the slide back to it never waits on a download.
  useEffect(() => {
    preloadLanding().catch(() => {});
  }, []);
  return (
    <main className="auth-page">
      <aside className="auth-hero" aria-hidden="true">
        <div className="auth-page__overlay" />
        <div className="auth-hero__content">
          <div className="auth-hero__center">
            <Link to="/" onClick={home} tabIndex={-1} className="auth-hero__home">
              <span className="auth-hero__orb"><span className="auth-hero__mark"><LogoGlyph motion="loop" /></span></span>
              <p className="auth-hero__name">Thapar<strong className="genie-sparkles">Genie</strong></p>
            </Link>
            <p className="auth-hero__tagline">Your campus assistant for Thapar Institute.</p>
            <TypedPrompt />
            <p className="auth-hero__caption">
              Answers come from official TIET documents, and every answer links to its source.
            </p>
          </div>
          <p className="auth-hero__foot">Thapar Institute of Engineering &amp; Technology, Patiala</p>
        </div>
      </aside>
      <div className="auth-panel">
        <Ambient />
        <section className="auth-card" aria-labelledby="auth-title">
          <Link to="/" onClick={home} aria-label="ThaparGenie home" className="auth-card__logo"><LogoGlyph motion="draw" /></Link>
          <h1 id="auth-title">{title}</h1>
          {description ? <p className="auth-card__description">{description}</p> : null}
          {children}
        </section>
        <p className="auth-panel__legal">
          By continuing you agree to how we handle data in the <Link to="/privacy">privacy notice</Link>.
        </p>
      </div>
    </main>
  );
}
