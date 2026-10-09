import {
  ArrowUp,
  BookOpen,
  Brain,
  Briefcase,
  Building2,
  CalendarDays,
  Check,
  GraduationCap,
  IndianRupee,
  Info,
  Languages,
  Landmark,
  Megaphone,
  MessageSquareText,
  Mic,
  Moon,
  PenLine,
  Quote,
  RotateCcw,
  Search,
  SearchX,
  Share2,
  ShieldCheck,
  Smartphone,
  Sun,
  Users,
} from 'lucide-react';
import { Fragment, useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';

import { useAuth } from '@/auth/AuthContext';
import { Ambient } from '@/components/ambient';
import { Brand, LogoGlyph, LogoMark } from '@/components/brand/Brand';
import { useTheme } from '@/components/theme-provider';
import { useSlideClick, useSlideNavigate } from '@/lib/page-slide';
import { cn } from '@/lib/utils';

import AdminSection from './AdminSection';
import campusPhoto from './assets/campus-tinted.webp';
import {
  BranchVisual,
  CiteVisual,
  FollowVisual,
  HonestVisual,
  InstallVisual,
  NoticesVisual,
  ShareVisual,
  VoiceVisual,
} from './FeatureVisuals';
import HeroDemo from './HeroDemo';
import IdeaSection from './IdeaSection';
import {
  prefersReducedMotion,
  useCountUp,
  useCycle,
  useInView,
  usePointerEffects,
  useReveal,
  useScrollSpy,
  useScrollState,
} from './landing-hooks';
import PrivacySection from './PrivacySection';
import { Cta, SectionHeading } from './ui';
import { scrollToTop, startSmoothScroll } from '@/lib/smooth-scroll';
import './landing.css';

// The public landing page at "/": what ThaparGenie is, how it answers, and a way in.

const NAV_LINKS = [
  { id: 'idea', num: '01', label: 'The idea' },
  { id: 'how', num: '02', label: 'How it works' },
  { id: 'features', num: '03', label: 'Features' },
  { id: 'privacy', num: '04', label: 'Privacy' },
  { id: 'admins', num: '05', label: 'For admins' },
  { id: 'faq', num: '06', label: 'FAQ' },
];
const PROOF = [
  [Quote, 'Cited', 'Every answer links its source'],
  [ShieldCheck, 'Honest', 'Says so when it doesn’t know'],
  [Languages, 'Bilingual', 'English, Hinglish or voice'],
];

const RAIL_LINKS = NAV_LINKS;
const SPY_IDS = ['top', ...RAIL_LINKS.map((link) => link.id)];

const TOPICS = [
  { icon: IndianRupee, label: 'Fees & scholarships' },
  { icon: Building2, label: 'Hostels & campus life' },
  { icon: GraduationCap, label: 'Admissions' },
  { icon: CalendarDays, label: 'Academic calendar' },
  { icon: BookOpen, label: 'Courses & syllabus' },
  { icon: Landmark, label: 'Rules & regulations' },
  { icon: Megaphone, label: 'Notices' },
  { icon: Briefcase, label: 'Placements' },
  { icon: Users, label: 'Departments & faculty' },
  { icon: Info, label: 'Offices & contacts' },
];

const STEPS = [
  {
    icon: Brain,
    title: 'Understands',
    text: 'Reads English or Hinglish, fixes typos, and carries context from earlier messages, so “and for girls?” just works.',
  },
  {
    icon: Search,
    title: 'Searches',
    text: 'Looks through every official document by meaning and by exact words, so codes like UCS301 are never missed.',
  },
  {
    icon: BookOpen,
    title: 'Reads',
    text: 'Ranks what it found and keeps only the passages that actually answer you, with the text around them.',
  },
  {
    icon: PenLine,
    title: 'Writes & checks',
    text: 'Streams a clear answer with numbered citations, then checks it against the sources. If they disagree, it says so.',
  },
];

const FAQS = [
  {
    q: 'Who can use ThaparGenie?',
    a: 'Students of Thapar Institute of Engineering & Technology. Create an account with your email or sign in with Google; depending on how the admins have set things up, your account may need a quick approval first.',
  },
  {
    q: 'Where do the answers come from?',
    a: 'Only from official TIET documents and pages that the admins have added: fee structures, regulations, calendars, syllabi, notices and more. Every answer links to the exact source, down to the page of a PDF.',
  },
  {
    q: 'Can it see my marks, attendance or fee dues?',
    a: 'No. Personal records live behind the Webkiosk login, and ThaparGenie never has access to them. Ask about them and it will point you to Webkiosk.',
  },
  {
    q: 'What if an answer is wrong or missing?',
    a: 'Give it a thumbs down and say why. Admins review every report, fix or add the document, and the next student gets the right answer. When the knowledge base doesn’t cover something, ThaparGenie says so instead of guessing.',
  },
  {
    q: 'Does it work on my phone?',
    a: 'Yes. It works in any modern browser, and you can install it to your home screen like an app. You can even ask by voice.',
  },
  {
    q: 'What happens to my chats?',
    a: 'They’re yours: rename, pin, search, export or delete them whenever you like. Chats you leave untouched for 180 days are deleted automatically.',
  },
];

/* ------------------------------------------------------------------ Navigation */

function ThemeToggle() {
  const { resolvedTheme, setTheme } = useTheme();
  const dark = resolvedTheme === 'dark';
  return (
    <button
      type="button"
      onClick={() => setTheme(dark ? 'light' : 'dark')}
      aria-label={dark ? 'Switch to light theme' : 'Switch to dark theme'}
      className="lp-nav__icon lp-theme hidden sm:inline-grid"
      data-dark={dark || undefined}
    >
      <Sun className="lp-theme__sun" />
      <Moon className="lp-theme__moon" />
    </button>
  );
}

function LandingNav() {
  const { scrolled } = useScrollState();
  const spied = useScrollSpy(SPY_IDS);
  const active = scrolled ? spied : null;
  const [open, setOpen] = useState(false);
  const [hover, setHover] = useState(null);
  const listRef = useRef(null);
  const barRef = useRef(null);
  const [marks, setMarks] = useState({ hover: null, active: null });
  const leaveTimer = useRef(0);

  // Brief exits (slipping off the bar between links) keep the highlight instead of dropping it.
  const hoverOn = (id) => {
    clearTimeout(leaveTimer.current);
    setHover(id);
  };
  const hoverOff = () => {
    clearTimeout(leaveTimer.current);
    leaveTimer.current = setTimeout(() => setHover(null), 140);
  };
  useEffect(() => () => clearTimeout(leaveTimer.current), []);

  // A soft highlight glides to the hovered link; a small dot marks the section you're reading.
  // When either one hides it fades out in place instead of sliding back to the start.
  useEffect(() => {
    const measure = (id, last) => {
      const node = id ? listRef.current?.querySelector(`[data-id="${id}"]`) : null;
      const now = performance.now();
      // Only once it has fully faded does it reappear on the link; while still visible it glides over.
      const snap = !last || (!last.shown && now - last.hiddenAt > 300);
      if (node) return { left: node.offsetLeft, width: node.offsetWidth, shown: true, snap };
      if (!last) return null;
      return last.shown ? { ...last, shown: false, snap: false, hiddenAt: now } : last;
    };
    const frame = requestAnimationFrame(() =>
      setMarks((last) => ({ hover: measure(hover, last.hover), active: measure(active, last.active) })),
    );
    return () => cancelAnimationFrame(frame);
  }, [hover, active, scrolled]);

  // Reading progress, drawn as a hairline along the bar's bottom edge.
  useEffect(() => {
    const node = barRef.current;
    if (!node) return undefined;
    let frame = 0;
    const update = () => {
      frame = 0;
      const max = document.documentElement.scrollHeight - window.innerHeight;
      node.style.setProperty('--p', (max > 0 ? window.scrollY / max : 0).toFixed(4));
    };
    const onScroll = () => {
      if (!frame) frame = requestAnimationFrame(update);
    };
    update();
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => {
      window.removeEventListener('scroll', onScroll);
      if (frame) cancelAnimationFrame(frame);
    };
  }, []);

  const solid = scrolled || open;
  return (
    <header className="lp-nav" data-solid={solid || undefined}>
      <div ref={barRef} className="lp-nav__bar">
        <a href="#top" aria-label="ThaparGenie, back to top" className="landing-brand" data-solid={solid || undefined}>
          <Brand />
        </a>

        <nav aria-label="Sections" className="hidden lg:block">
          <ul ref={listRef} className="lp-nav__links" onPointerLeave={hoverOff}>
            <span
              aria-hidden="true"
              className="lp-nav__hover"
              data-shown={marks.hover?.shown || undefined}
              data-snap={marks.hover?.snap || undefined}
              style={marks.hover ? { translate: `${marks.hover.left}px -50%`, width: marks.hover.width } : undefined}
            />
            <span
              aria-hidden="true"
              className="lp-nav__dot"
              data-shown={marks.active?.shown || undefined}
              data-snap={marks.active?.snap || undefined}
              style={marks.active ? { translate: `${marks.active.left + marks.active.width / 2 - 2}px 0` } : undefined}
            />
            {NAV_LINKS.map((link) => (
              <li key={link.id}>
                <a
                  href={`#${link.id}`}
                  data-id={link.id}
                  aria-current={active === link.id ? 'true' : undefined}
                  onPointerEnter={() => hoverOn(link.id)}
                  onFocus={() => hoverOn(link.id)}
                  onBlur={hoverOff}
                  className="lp-nav__link"
                >
                  {link.label}
                </a>
              </li>
            ))}
          </ul>
        </nav>

        <div className="ml-auto flex items-center gap-1">
          <ThemeToggle />
          <Cta to="/login/" size="sm" blend={solid}>
            Sign in
          </Cta>
          <button
            type="button"
            onClick={() => setOpen((value) => !value)}
            aria-expanded={open}
            aria-controls="landing-mobile-nav"
            aria-label={open ? 'Close menu' : 'Open menu'}
            className="lp-nav__icon lp-burger lg:hidden"
            data-open={open || undefined}
          >
            <span />
            <span />
          </button>
        </div>

        <span aria-hidden="true" className="lp-nav__progress" />

        {open ? (
          <nav id="landing-mobile-nav" aria-label="Sections" className="lp-nav__sheet lg:hidden">
            {RAIL_LINKS.map((link, index) => (
              <a key={link.id} href={`#${link.id}`} onClick={() => setOpen(false)} style={{ '--i': index }}>
                <span className="lp-nav__sheetnum">{link.num}</span>
                {link.label}
              </a>
            ))}
          </nav>
        ) : null}
      </div>
    </header>
  );
}

function ScrollTop() {
  const ref = useRef(null);
  useEffect(() => {
    let frame = 0;
    const update = () => {
      frame = 0;
      const node = ref.current;
      if (!node) return;
      const max = document.documentElement.scrollHeight - window.innerHeight;
      const progress = max > 0 ? window.scrollY / max : 0;
      node.style.setProperty('--progress', progress.toFixed(4));
      node.toggleAttribute('data-shown', window.scrollY > 700);
    };
    const onScroll = () => {
      if (!frame) frame = requestAnimationFrame(update);
    };
    update();
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => {
      window.removeEventListener('scroll', onScroll);
      if (frame) cancelAnimationFrame(frame);
    };
  }, []);
  return (
    <button ref={ref} type="button" className="lp-top" aria-label="Back to top" onClick={scrollToTop}>
      <svg viewBox="0 0 48 48" aria-hidden="true">
        <circle cx="24" cy="24" r="21" className="lp-top__track" />
        <circle cx="24" cy="24" r="21" pathLength="1" className="lp-top__ring" />
      </svg>
      <ArrowUp className="size-4" />
    </button>
  );
}

/** Numbered section rail on wide screens; the section you're reading stretches out. */
function SectionRail() {
  const active = useScrollSpy(SPY_IDS);
  return (
    <nav aria-label="Page sections" className="lp-rail" data-shown={(active && active !== 'top') || undefined}>
      {RAIL_LINKS.map((link) => (
        <a key={link.id} href={`#${link.id}`} aria-current={active === link.id ? 'true' : undefined} className="lp-rail__item">
          <span className="lp-rail__num">{link.num}</span>
          <span aria-hidden="true" className="lp-rail__bar" />
          <span className="lp-rail__label">{link.label}</span>
        </a>
      ))}
    </nav>
  );
}

/* ------------------------------------------------------------------ Hero */

const HERO_LINES = [
  ['Every answer', false],
  ['about Thapar,', false],
  ['straight from', true],
  ['the source.', true],
];

function Hero() {
  const ref = useRef(null);
  const lightRef = useRef(null);

  // The photo drifts slower than the page and the copy fades as you scroll past. The value is
  // set only on the two layers that use it (it doesn't inherit; see landing.css), so a scroll
  // restyles them alone rather than the whole hero.
  useEffect(() => {
    const node = ref.current;
    if (!node || prefersReducedMotion()) return undefined;
    const layers = node.querySelectorAll('.lp-hero__photo, .lp-hero__copy');
    let frame = 0;
    let last = '';
    const update = () => {
      frame = 0;
      const value = Math.min(window.scrollY, 1200).toFixed(0);
      if (value === last) return;
      last = value;
      layers.forEach((layer) => layer.style.setProperty('--scroll', value));
    };
    const onScroll = () => {
      if (!frame) frame = requestAnimationFrame(update);
    };
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => {
      window.removeEventListener('scroll', onScroll);
      if (frame) cancelAnimationFrame(frame);
    };
  }, []);

  // The warm light follows the pointer; only the light layer is touched.
  const onPointerMove = (event) => {
    const light = lightRef.current;
    if (!light) return;
    const rect = event.currentTarget.getBoundingClientRect();
    light.style.setProperty('--px', `${event.clientX - rect.left}px`);
    light.style.setProperty('--py', `${event.clientY - rect.top}px`);
  };

  return (
    <section id="top" ref={ref} onPointerMove={onPointerMove} className="lp-hero relative isolate overflow-hidden text-white">
      <div aria-hidden="true" className="lp-hero__photo" style={{ '--photo': `url(${campusPhoto})` }} />
      <div aria-hidden="true" className="lp-hero__tint" />
      <div ref={lightRef} aria-hidden="true" className="lp-hero__light" />
      <div aria-hidden="true" className="lp-grain" />
      <div aria-hidden="true" className="landing-stars">
        {Array.from({ length: 12 }, (_, index) => (
          <span
            key={index}
            style={{
              left: `${(index * 37 + 11) % 100}%`,
              top: `${(index * 53 + 7) % 88}%`,
              animationDelay: `${(index * 0.7) % 5}s`,
              scale: `${0.6 + ((index * 7) % 5) / 8}`,
            }}
          />
        ))}
      </div>

      <div className="lp-hero__inner relative mx-auto grid max-w-[76rem] items-center gap-14 px-4 pt-32 pb-24 sm:px-6 sm:pt-40 lg:grid-cols-[1.05fr_1fr] lg:gap-12 lg:px-8 lg:pt-44 lg:pb-32">
        <div className="lp-hero__copy text-center lg:text-left">
          <h1 className="landing-h1">
            {HERO_LINES.map(([text, gold], index) => (
              <Fragment key={text}>
                <span className="lp-line">
                  <span className="lp-line__inner" style={{ '--i': index }}>
                    {gold ? <span className="landing-gold">{text}</span> : text}
                  </span>
                </span>{' '}
              </Fragment>
            ))}
          </h1>

          <p className="landing-enter mx-auto mt-7 max-w-xl text-base leading-relaxed text-white/75 sm:text-lg lg:mx-0" style={{ '--d': '650ms' }}>
            Fee structures, hostel rules, exam dates, syllabi and notices, scattered across dozens of PDFs and pages.
            Ask in plain English or Hinglish and get a clear answer, with every fact linked to where it came from.
          </p>

          <dl className="landing-enter lp-proof mt-10" style={{ '--d': '800ms' }}>
            {PROOF.map(([Icon, title, text], index) => (
              <div key={title} className="lp-proof__item" style={{ '--i': index }}>
                <dt>
                  <Icon className="size-4" />
                  {title}
                </dt>
                <dd>{text}</dd>
              </div>
            ))}
          </dl>
        </div>

        <div className="landing-enter mx-auto w-full max-w-lg lg:max-w-none" style={{ '--d': '450ms' }}>
          <HeroDemo />
        </div>
      </div>

      <a href="#topics" className="lp-hero__scroll" aria-label="Scroll to the topics">
        <span />
      </a>
    </section>
  );
}

/* ------------------------------------------------------------------ Topics & numbers */

function TopicMarquee() {
  const row = (items, reverse) => (
    <div className="landing-marquee" data-reverse={reverse || undefined}>
      <div className="landing-marquee__track">
        {[...items, ...items, ...items, ...items].map((topic, index) => {
          const Icon = topic.icon;
          return (
            <span key={`${topic.label}-${index}`} aria-hidden={index >= items.length || undefined} className="lp-topic">
              <span className="lp-topic__icon">
                <Icon className="size-3.5" />
              </span>
              {topic.label}
            </span>
          );
        })}
      </div>
    </div>
  );
  return (
    <section id="topics" aria-label="Topics ThaparGenie can answer" className="py-16 sm:py-20">
      <p data-reveal className="mb-8 text-center text-[13px] font-semibold tracking-[0.14em] text-muted-foreground uppercase">
        Ask about anything official at TIET
      </p>
      <div className="grid gap-3">
        {row(TOPICS.slice(0, 5), false)}
        {row(TOPICS.slice(5), true)}
      </div>
    </section>
  );
}

function Stat({ value, label, note, index }) {
  const ref = useRef(null);
  const inView = useInView(ref, { once: true });
  const shown = useCountUp(value, inView);
  return (
    <div ref={ref} data-reveal style={{ '--d': `${index * 90}ms` }} className="lp-stat">
      <span className="lp-stat__index">0{index + 1}</span>
      <p className="lp-stat__value">{shown}</p>
      <p className="lp-stat__label">{label}</p>
      <p className="lp-stat__note">{note}</p>
    </div>
  );
}

function Stats() {
  return (
    <section aria-label="ThaparGenie in numbers" className="mx-auto max-w-[76rem] px-4 sm:px-6 lg:px-8">
      <div className="lp-stats">
        <Stat index={0} value={12} label="topic areas" note="from fees to faculty" />
        <Stat index={1} value={4} label="steps per answer" note="understand, search, read, write" />
        <Stat index={2} value={2} label="languages" note="English and Hinglish" />
        <Stat index={3} value={180} label="days of idle" note="then chats delete themselves" />
      </div>
    </section>
  );
}

/* ------------------------------------------------------------------ How it works */

function StepVisual({ index }) {
  if (index === 0) {
    return (
      <div className="lp-viz lp-viz--understand">
        <span className="lp-viz__raw">hostel fee girls??</span>
        <span className="lp-viz__chips">
          {['Hostel fee', 'First-year girls', '2026–27'].map((chip, i) => (
            <span key={chip} style={{ '--i': i }}>
              {chip}
            </span>
          ))}
        </span>
      </div>
    );
  }
  if (index === 1) {
    return (
      <div className="lp-viz lp-viz--search">
        {[
          ['By meaning', ['Hostel charges', 'Mess fee', 'Room rent']],
          ['Exact words', ['UCS301', 'BE COE']],
        ].map(([lane, hits], lindex) => (
          <div key={lane} className="lp-viz__lane">
            <span className="lp-viz__lanelabel">{lane}</span>
            <span className="lp-viz__hits">
              {hits.map((hit, i) => (
                <span key={hit} style={{ '--i': i + lindex * 3 }}>
                  {hit}
                </span>
              ))}
            </span>
          </div>
        ))}
        <span className="lp-viz__scan" />
      </div>
    );
  }
  if (index === 2) {
    return (
      <div className="lp-viz lp-viz--read">
        {[
          ['Hostel fee 2026–27 · p. 3', 94, true],
          ['Hostel rules · p. 4', 81, true],
          ['Mess menu · p. 1', 38, false],
          ['Sports fee · p. 2', 22, false],
        ].map(([name, score, kept], i) => (
          <span key={name} className="lp-viz__passage" data-kept={kept || undefined} style={{ '--i': i, '--score': `${score}%` }}>
            <span className="truncate">{name}</span>
            <span className="lp-viz__meter">
              <span />
            </span>
          </span>
        ))}
      </div>
    );
  }
  return (
    <div className="lp-viz lp-viz--write">
      <span className="lp-viz__line" style={{ '--w': '92%', '--i': 0 }} />
      <span className="lp-viz__line" style={{ '--w': '78%', '--i': 1 }}>
        <i>1</i>
      </span>
      <span className="lp-viz__line" style={{ '--w': '64%', '--i': 2 }}>
        <i>2</i>
      </span>
      <span className="lp-viz__check">
        <Check className="size-3" strokeWidth={3} />
        Checked against sources
      </span>
    </div>
  );
}

function HowItWorks() {
  const ref = useRef(null);
  const inView = useInView(ref);
  const [still] = useState(prefersReducedMotion);
  const { active, setActive, onAnimationEnd } = useCycle(STEPS.length);

  return (
    <section id="how" className="landing-section relative">
      <div aria-hidden="true" className="landing-band" />
      <div className="relative mx-auto max-w-[76rem] px-4 sm:px-6 lg:px-8">
        <SectionHeading index="02" eyebrow="How it works" title="Four careful steps," gold="a few seconds each.">
          Every question runs through the same pipeline, and you see it happen: understanding, searching, reading, then
          the answer streams in.
        </SectionHeading>

        <div
          ref={ref}
          className="lp-cycle landing-steps mt-16"
          data-running={(inView && !still) || undefined}
          style={{ '--step': active }}
          onAnimationEnd={onAnimationEnd}
        >
          <div aria-hidden="true" className="landing-steps__line">
            <span />
          </div>
          <ol className="grid gap-5 md:grid-cols-2 lg:grid-cols-4">
            {STEPS.map((step, index) => {
              const Icon = step.icon;
              return (
                <li
                  key={step.title}
                  data-reveal
                  data-spotlight
                  data-active={index === active || undefined}
                  data-done={index < active || undefined}
                  style={{ '--d': `${index * 120}ms` }}
                  onPointerEnter={() => setActive(index)}
                  className="lp-card lp-step icon-nudge relative overflow-hidden p-5"
                >
                  <StepVisual index={index} />
                  <div className="mt-5 flex items-center gap-3">
                    <span className="lp-step__icon">
                      <Icon className="size-[18px]" />
                    </span>
                    <h3 className="text-lg font-semibold tracking-tight">{step.title}</h3>
                    <span className="lp-step__num">0{index + 1}</span>
                  </div>
                  <p className="mt-3 text-sm leading-relaxed text-muted-foreground">{step.text}</p>
                  {index === active ? <span className="lp-progress" /> : null}
                </li>
              );
            })}
          </ol>
        </div>
      </div>
    </section>
  );
}

/* ------------------------------------------------------------------ Features */

function FeatureCard({ icon: Icon, title, text, className, delay, visual: Visual }) {
  return (
    <article
      data-reveal
      data-spotlight
      data-tilt
      style={{ '--d': delay }}
      className={cn('lp-card lp-feature icon-nudge group flex flex-col overflow-hidden p-4', className)}
    >
      <Visual />
      <div className="mt-4 flex items-center gap-2.5 px-1">
        <span className="lp-icon lp-icon--sm">
          <Icon className="size-4" />
        </span>
        <h3 className="text-base font-semibold tracking-tight">{title}</h3>
      </div>
      <p className="mt-2 px-1 text-sm leading-relaxed text-muted-foreground">{text}</p>
    </article>
  );
}

const FEATURES = [
  {
    icon: Quote,
    title: 'Every fact, cited',
    text: 'Numbered citations sit right next to each claim. Tap one to open the official PDF at the right page, or the original web page.',
    visual: CiteVisual,
    className: 'md:col-span-2',
  },
  {
    icon: SearchX,
    title: 'Honest when it doesn’t know',
    text: 'If the documents don’t cover it, ThaparGenie says so and points you to the right office or page. It never makes up a fee or a date.',
    visual: HonestVisual,
  },
  {
    icon: MessageSquareText,
    title: 'Follow-ups just work',
    text: 'It remembers the conversation. Ask about BE fees, then “and for hostel?” and it knows what you mean.',
    visual: FollowVisual,
  },
  {
    icon: Mic,
    title: 'Type, talk, or Hinglish',
    text: 'Ask the way you’d ask a senior. Tap the mic to speak instead of typing.',
    visual: VoiceVisual,
  },
  {
    icon: RotateCcw,
    title: 'Regenerate & branch',
    text: 'Try another answer, or edit your question. Every version is kept, so you can flip between them.',
    visual: BranchVisual,
  },
  {
    icon: Megaphone,
    title: 'Notices in one place',
    text: 'Important announcements, pinned where you’ll see them, with a dot for anything new since your last visit.',
    visual: NoticesVisual,
  },
  {
    icon: Share2,
    title: 'Share, print, export',
    text: 'Share one answer with a link, print or download a whole chat, or export all your history.',
    visual: ShareVisual,
  },
  {
    icon: Smartphone,
    title: 'Install it like an app',
    text: 'Add ThaparGenie to your home screen and open it in one tap, on Android, iPhone or desktop.',
    visual: InstallVisual,
  },
];

function Features() {
  return (
    <section id="features" className="landing-section mx-auto max-w-[76rem] px-4 sm:px-6 lg:px-8">
      <SectionHeading index="03" eyebrow="Features" title="Built for the questions students" gold="actually ask.">
        Not a general chatbot. A focused assistant that knows TIET, admits what it doesn’t know, and keeps up with new
        notices.
      </SectionHeading>

      <div className="mt-14 grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {FEATURES.map((feature, index) => (
          <FeatureCard key={feature.title} {...feature} delay={`${(index % 3) * 80}ms`} />
        ))}
      </div>
    </section>
  );
}

/* ------------------------------------------------------------------ FAQ, footer */

/** Hands a typed question on: straight to the chat box when signed in, through sign-in otherwise. */
function useAsk(signedIn) {
  const navigate = useSlideNavigate();
  return (question) => {
    const text = question.trim();
    if (!text) return;
    if (signedIn) navigate('/chat/', { state: { draft: text } });
    else navigate('/login/', { state: { from: '/chat/', draft: text } });
  };
}

function FaqAsk({ signedIn }) {
  const ask = useAsk(signedIn);
  const [draft, setDraft] = useState('');
  return (
    <form
      data-reveal
      style={{ '--d': '300ms' }}
      className="lp-faq-ask mt-8"
      data-filled={draft.trim() ? '' : undefined}
      onSubmit={(event) => {
        event.preventDefault();
        ask(draft);
      }}
    >
      <div className="flex items-center gap-3">
        <LogoMark motion="loop" className="size-10 shrink-0 rounded-xl" />
        <div className="min-w-0">
          <p className="text-[15px] font-semibold">Still wondering?</p>
          <p className="text-sm text-muted-foreground">Ask it here. We’ll keep your question while you sign in.</p>
        </div>
      </div>
      <div className="lp-faq-ask__field">
        <label htmlFor="faq-ask" className="sr-only">
          Ask ThaparGenie a question
        </label>
        <input
          id="faq-ask"
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          placeholder="Type any campus question…"
          maxLength={500}
          autoComplete="off"
        />
        <button type="submit" aria-label="Send question" disabled={!draft.trim()}>
          <ArrowUp className="size-4" />
        </button>
      </div>
    </form>
  );
}

function FaqItem({ item, index }) {
  return (
    <details data-reveal style={{ '--d': `${index * 60}ms` }} className="lp-faq">
      <summary>
        <span className="lp-faq__num">0{index + 1}</span>
        <span className="lp-faq__q">{item.q}</span>
        <span aria-hidden="true" className="lp-faq__send">
          <ArrowUp className="lp-faq__arrow" />
          <LogoGlyph className="lp-faq__glyph" />
        </span>
      </summary>
      <div className="lp-faq__reply">
        <span aria-hidden="true" className="lp-faq__avatar">
          <LogoGlyph className="h-3.5 w-auto" />
        </span>
        <div className="lp-faq__bubble">
          <span aria-hidden="true" className="lp-faq__dots">
            <i />
            <i />
            <i />
          </span>
          <p className="lp-faq__text">
            {item.a.split(' ').map((word, i) => (
              <Fragment key={i}>
                <span style={{ '--i': i }}>{word}</span>{' '}
              </Fragment>
            ))}
          </p>
        </div>
      </div>
    </details>
  );
}

function Faq({ signedIn }) {
  return (
    <section id="faq" className="landing-section mx-auto grid max-w-[76rem] gap-12 px-4 sm:px-6 lg:grid-cols-[0.85fr_1.15fr] lg:gap-16 lg:px-8">
      <div className="lg:sticky lg:top-28 lg:self-start">
        <SectionHeading index="06" align="left" eyebrow="FAQ" title="Questions," gold="answered.">
          Open a question and ThaparGenie answers it, the same way it answers yours.
        </SectionHeading>
        <FaqAsk signedIn={signedIn} />
      </div>
      <div className="grid content-start gap-3">
        {FAQS.map((item, index) => (
          <FaqItem key={item.q} item={item} index={index} />
        ))}
      </div>
    </section>
  );
}

function Footer() {
  const slide = useSlideClick();
  return (
    <footer className="lp-footer relative z-[1] overflow-hidden border-t">
      <div className="relative mx-auto flex max-w-[76rem] flex-col gap-8 px-4 pt-12 pb-8 sm:px-6 md:flex-row md:items-start md:justify-between lg:px-8">
        <div className="max-w-sm">
          <Brand />
          <p className="mt-3 text-sm text-muted-foreground">
            Answers about Thapar Institute of Engineering &amp; Technology, Patiala, grounded in official sources.
          </p>
        </div>
        <nav aria-label="Footer" className="grid grid-cols-2 gap-x-12 gap-y-2.5 text-sm sm:grid-cols-3">
          <a href="#how" className="lp-footlink">How it works</a>
          <a href="#features" className="lp-footlink">Features</a>
          <a href="#faq" className="lp-footlink">FAQ</a>
          <Link to="/privacy" className="lp-footlink">Privacy notice</Link>
          <Link to="/login/" onClick={slide} className="lp-footlink">Sign in</Link>
          <a href="https://webkiosk.thapar.edu" target="_blank" rel="noreferrer" className="lp-footlink">Webkiosk</a>
        </nav>
      </div>
      <p aria-hidden="true" data-reveal className="lp-footer__word">
        ThaparGenie
      </p>
      <div className="relative border-t">
        <p className="mx-auto max-w-[76rem] px-4 py-5 text-xs text-muted-foreground sm:px-6 lg:px-8">
          © {new Date().getFullYear()} ThaparGenie. Always double-check important details with the linked official source.
        </p>
      </div>
    </footer>
  );
}

export default function LandingPage() {
  const { user } = useAuth();
  const signedIn = Boolean(user);
  const rootRef = useReveal();
  usePointerEffects(rootRef);
  // Momentum scrolling: the wheel glides to a stop instead of jumping in steps.
  useEffect(() => startSmoothScroll(), []);

  return (
    <div ref={rootRef} className="landing min-h-dvh overflow-x-clip bg-background text-foreground">
      <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:top-3 focus:left-3 focus:z-[60] focus:rounded-lg focus:bg-card focus:px-4 focus:py-2 focus:shadow-lift">
        Skip to content
      </a>
      <Ambient fixed />
      <LandingNav />
      <SectionRail />
      <main id="main" className="relative z-[1]">
        <Hero />
        <TopicMarquee />
        <Stats />
        <IdeaSection />
        <HowItWorks />
        <Features />
        <PrivacySection />
        <AdminSection />
        <Faq signedIn={signedIn} />
      </main>
      <Footer />
      <ScrollTop />
    </div>
  );
}
