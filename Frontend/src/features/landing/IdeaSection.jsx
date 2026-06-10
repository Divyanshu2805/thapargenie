import { Check, ChevronLeft, ChevronRight, LoaderCircle } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';

import { LogoGlyph, LogoMark } from '@/components/brand/Brand';

import { prefersReducedMotion, useInView } from './landing-hooks';
import { SectionHeading } from './ui';

// "The idea": a before/after slider (the scattered way vs. one answer) and the sources
// that flow into ThaparGenie.

const SOURCES = [
  { name: 'Fee structure', kind: 'PDF', meta: 'Accounts' },
  { name: 'Hostel rules', kind: 'DOC', meta: 'Hostel office' },
  { name: 'Academic calendar', kind: 'PDF', meta: 'Registrar' },
  { name: 'Exam notice', kind: 'NEW', meta: 'Notice board' },
  { name: 'UCS301 syllabus', kind: 'PDF', meta: 'CSED' },
  { name: 'Scholarships', kind: 'WEB', meta: 'thapar.edu' },
  { name: 'Placement stats', kind: 'XLS', meta: 'Placement cell' },
  { name: 'Regulations', kind: 'PDF', meta: 'Academics' },
];

// Where the source cards sit around the logo (percent of the box, as an ellipse).
const RX = 34;
const RY = 41;

const TABS = ['Fee_structure_final_v2.pdf', 'Hostel rules (old?)', 'Notice 214', 'Academic calendar', 'thapar.edu/…', 'Scholarships'];

function BeforeAfter() {
  const ref = useRef(null);
  const inView = useInView(ref, { once: true });
  const [pos, setPos] = useState(90);
  const [dragging, setDragging] = useState(false);
  const [touched, setTouched] = useState(false);

  // On first sight the divider sweeps in from the right, showing there's something to drag.
  useEffect(() => {
    if (!inView || touched) return undefined;
    const id = window.setTimeout(() => setPos(50), 450);
    return () => window.clearTimeout(id);
  }, [inView, touched]);

  const follow = (event) => {
    const rect = ref.current.getBoundingClientRect();
    setPos(Math.min(100, Math.max(0, ((event.clientX - rect.left) / rect.width) * 100)));
  };

  const onKeyDown = (event) => {
    const steps = { ArrowLeft: -5, ArrowRight: 5, Home: -100, End: 100 };
    if (!(event.key in steps)) return;
    event.preventDefault();
    setTouched(true);
    setPos((value) => Math.min(100, Math.max(0, value + steps[event.key])));
  };

  return (
    <div
      ref={ref}
      data-reveal
      style={{ '--d': '260ms', '--pos': `${pos}%` }}
      data-dragging={dragging || undefined}
      data-touched={touched || undefined}
      className="lp-compare"
      onPointerDown={(event) => {
        setTouched(true);
        setDragging(true);
        event.currentTarget.setPointerCapture(event.pointerId);
        follow(event);
      }}
      onPointerMove={(event) => dragging && follow(event)}
      onPointerUp={() => setDragging(false)}
      onPointerCancel={() => setDragging(false)}
    >
      {/* Before: tabs, a long PDF, a search, a doubt. */}
      <div className="lp-compare__before" aria-hidden="true">
        <div className="lp-tabs">
          {TABS.map((tab, index) => (
            <span key={tab} className="lp-tabs__tab" style={{ '--i': index }}>
              {tab}
            </span>
          ))}
          <span className="lp-tabs__more">+6</span>
        </div>
        <div className="lp-mess lp-mess--pdf">
          <p className="lp-mess__title">Academic_Regulations.pdf</p>
          <p className="lp-mess__meta">Page 17 of 86</p>
          {[88, 72, 94, 60, 80, 70].map((width, index) => (
            <span key={index} className="lp-mess__line" style={{ width: `${width}%` }} />
          ))}
          <span className="lp-mess__thumb" />
        </div>
        <div className="lp-mess lp-mess--search">
          <LoaderCircle className="size-3.5 animate-spin" />
          hostel fee girls 2026 site:thapar.edu
        </div>
        <div className="lp-mess lp-mess--note">Is this notice still current??</div>
        <span className="lp-compare__tag lp-compare__tag--before">Before · 12 tabs</span>
      </div>

      {/* After: one question, one answer, its source. */}
      <div className="lp-compare__after" aria-hidden="true">
        <div className="lp-answer-card">
          <div className="flex items-center gap-2">
            <LogoMark className="size-6 rounded-md" />
            <span className="text-[12px] font-semibold">ThaparGenie</span>
          </div>
          <p className="lp-answer-card__q">Hostel fee for first-year girls?</p>
          <p className="lp-answer-card__a">
            <strong>₹98,000</strong> a year for a twin-sharing room, plus mess
            <span className="lp-answer-card__cite">1</span>
          </p>
          <span className="lp-answer-card__src">
            <span>1</span>Hostel fee structure.pdf · p. 3
          </span>
        </div>
        <span className="lp-compare__tag lp-compare__tag--after">With ThaparGenie · 1 answer</span>
      </div>

      <div className="lp-compare__divider" aria-hidden="true" />
      <button
        type="button"
        role="slider"
        aria-label="Compare before and after ThaparGenie"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.round(pos)}
        onKeyDown={onKeyDown}
        className="lp-compare__handle"
      >
        <ChevronLeft className="size-4" />
        <ChevronRight className="size-4" />
      </button>
      <span aria-hidden="true" className="lp-compare__hint">
        Drag
      </span>
    </div>
  );
}

// Questions the orbit plays through, and which sources (by index in SOURCES) each one reads.
const QUERIES = [
  { q: 'Hostel fee for first-years?', uses: [0, 1] },
  { q: 'When are the mid-sems?', uses: [2, 3] },
  { q: 'UCS301 kitne credits ka hai?', uses: [4, 7] },
  { q: 'How do I apply for a scholarship?', uses: [5] },
  { q: 'Placement stats for CSE?', uses: [6] },
];

/** Plays one query at a time: ask, light each source in turn, answer, then the next. */
function useOrbit(enabled) {
  const [state, setState] = useState({ query: 0, step: 0 });
  useEffect(() => {
    if (!enabled) return undefined;
    const { uses } = QUERIES[state.query];
    const answered = state.step > uses.length;
    const delay = state.step === 0 ? 900 : answered ? 2600 : 850;
    const id = window.setTimeout(() => {
      setState((current) =>
        current.step > QUERIES[current.query].uses.length
          ? { query: (current.query + 1) % QUERIES.length, step: 0 }
          : { ...current, step: current.step + 1 },
      );
    }, delay);
    return () => window.clearTimeout(id);
  }, [enabled, state]);
  return state;
}

function SourceOrbit() {
  const ref = useRef(null);
  const inView = useInView(ref);
  const [still] = useState(prefersReducedMotion);
  const live = useOrbit(inView && !still);
  const { query, step } = still ? { query: 0, step: QUERIES[0].uses.length + 1 } : live;
  const { q, uses } = QUERIES[query];
  const lit = uses.slice(0, step);
  const answered = step > uses.length;
  const reading = !answered && step > 0 ? SOURCES[uses[step - 1]].name : null;

  return (
    <div ref={ref} data-reveal className="landing-converge" data-answered={answered || undefined} aria-hidden="true">
      <svg className="landing-converge__lines" viewBox="0 0 100 100" preserveAspectRatio="none">
        {SOURCES.map((source, index) => {
          const angle = (index / SOURCES.length) * Math.PI * 2 - Math.PI / 2;
          const x = 50 + Math.cos(angle) * RX;
          const y = 50 + Math.sin(angle) * RY;
          const on = lit.includes(index);
          return (
            <g key={source.name}>
              <line x1={x} y1={y} x2="50" y2="50" style={{ '--i': index }} data-on={on || undefined} />
              <line
                x1={x}
                y1={y}
                x2="50"
                y2="50"
                pathLength="100"
                className="landing-converge__beam"
                data-on={on || undefined}
              />
            </g>
          );
        })}
      </svg>
      <div className="landing-converge__rings" />
      {SOURCES.map((source, index) => {
        const angle = (index / SOURCES.length) * Math.PI * 2 - Math.PI / 2;
        return (
          <span
            key={source.name}
            className="landing-chip"
            data-lit={lit.includes(index) || undefined}
            data-idle={(step > 0 && !uses.includes(index)) || undefined}
            style={{ '--x': `${50 + Math.cos(angle) * RX}%`, '--y': `${50 + Math.sin(angle) * RY}%`, '--i': index }}
          >
            <span className="lp-filetype" data-kind={source.kind}>
              {source.kind}
            </span>
            <span className="min-w-0 text-left leading-tight">
              <span className="block truncate font-semibold">{source.name}</span>
              <span className="block truncate text-[10.5px] font-medium text-muted-foreground">{source.meta}</span>
            </span>
          </span>
        );
      })}
      <span key={`ask-${query}`} className="landing-converge__ask">
        {q}
      </span>
      <span className="landing-converge__core">
        <LogoGlyph motion={answered ? 'none' : 'think'} className="h-[55%] w-auto" />
      </span>
      <span key={`out-${query}-${answered ? 'done' : step}`} className="landing-converge__out" data-done={answered || undefined}>
        {answered ? (
          <>
            <Check className="size-3.5" strokeWidth={3} />
            Answer ready · {uses.length} {uses.length === 1 ? 'source' : 'sources'}
          </>
        ) : reading ? (
          <>
            <LoaderCircle className="size-3.5 animate-spin" />
            Reading {reading}…
          </>
        ) : (
          <>
            <LoaderCircle className="size-3.5 animate-spin" />
            Understanding the question…
          </>
        )}
      </span>
    </div>
  );
}

export default function IdeaSection() {
  return (
    <section id="idea" className="landing-section mx-auto grid max-w-[76rem] items-center gap-14 px-4 sm:px-6 lg:grid-cols-2 lg:gap-16 lg:px-8">
      <div>
        <SectionHeading index="01" align="left" eyebrow="The idea" title="College information lives in a" gold="hundred places.">
          The fee structure is in one PDF, the hostel rules in another, and the date you need is buried in a notice from
          three weeks ago. ThaparGenie reads all of it, so you can just ask.
        </SectionHeading>
        <div className="mt-10">
          <BeforeAfter />
        </div>
      </div>
      <SourceOrbit />
    </section>
  );
}

