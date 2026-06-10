import { ArrowUp, Check, FileText, Globe, LoaderCircle, Mic, SquareArrowOutUpRight } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';

import { LogoGlyph, LogoMark } from '@/components/brand/Brand';
import { cn } from '@/lib/utils';

import { prefersReducedMotion, useInView } from './landing-hooks';

// A scripted conversation that plays in the hero: the question is typed, the answer
// pipeline runs through its stages, then the answer streams in with its citations.
// The content is illustrative; the page says so under the window.

const STAGES = ['Understanding', 'Searching', 'Reading', 'Writing'];
const CITE_UNITS = 2;
const ROW_UNITS = 8;

const SCENES = [
  {
    question: 'What is the hostel fee for first-year girls?',
    answer: [
      { p: ['For 2026–27, first-year girls stay in twin-sharing rooms. The yearly charges are', { cite: 1 }, ':'] },
      {
        table: [
          ['Room rent', '₹98,000'],
          ['Mess', '₹52,000'],
          ['Security (refundable)', '₹10,000'],
        ],
      },
      { p: ['You can pay in two instalments on the fee portal', { cite: 2 }, '.'] },
    ],
    sources: [
      { icon: FileText, title: 'Hostel fee structure 2026–27.pdf', meta: 'Page 3' },
      { icon: Globe, title: 'thapar.edu · Fee payment', meta: 'Web page' },
    ],
  },
  {
    question: 'attendance kam hai, end-sem de sakte hain kya?',
    answer: [
      { p: ['You need at least ', { b: '75% attendance' }, ' in each course to sit the end-semester exam', { cite: 1 }, '.'] },
      {
        p: [
          'A shortfall for medical reasons can be condoned if you apply through your department with supporting documents',
          { cite: 1 },
          '.',
        ],
      },
    ],
    sources: [{ icon: FileText, title: 'Academic regulations.pdf', meta: 'Page 12' }],
  },
  {
    question: 'What is my CGPA this semester?',
    answer: [
      { p: ['I can’t see personal records like marks, attendance or CGPA.'] },
      { p: ['Those live on ', { b: 'Webkiosk' }, ', which you open with your college login.'] },
    ],
    sources: [{ icon: SquareArrowOutUpRight, title: 'webkiosk.thapar.edu', meta: 'Open Webkiosk' }],
  },
];

function unitsOf(answer) {
  return answer.reduce((total, block) => {
    if (block.table) return total + block.table.length * ROW_UNITS;
    return (
      total +
      block.p.reduce((sum, token) => {
        if (typeof token === 'string') return sum + token.length;
        if (token.b) return sum + token.b.length;
        return sum + CITE_UNITS;
      }, 0)
    );
  }, 0);
}

function Cite({ n }) {
  return (
    <sup className="landing-pop mx-0.5 inline-flex h-4 min-w-4 -translate-y-0.5 items-center justify-center rounded-md bg-accent px-1 text-[10px] font-semibold text-accent-foreground">
      {n}
    </sup>
  );
}

function renderAnswer(answer, budget) {
  let left = budget;
  const out = [];
  answer.forEach((block, index) => {
    if (left <= 0) return;
    if (block.table) {
      const rows = Math.min(block.table.length, Math.ceil(left / ROW_UNITS));
      left -= block.table.length * ROW_UNITS;
      out.push(
        <div key={index} className="overflow-hidden rounded-lg border">
          <table className="w-full text-left text-[12.5px]">
            <tbody>
              {block.table.slice(0, rows).map(([label, value]) => (
                <tr key={label} className="landing-row border-b last:border-b-0">
                  <td className="px-3 py-1.5 text-muted-foreground">{label}</td>
                  <td className="px-3 py-1.5 text-right font-semibold tabular-nums">{value}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>,
      );
      return;
    }
    const parts = [];
    block.p.forEach((token, part) => {
      if (left <= 0) return;
      if (typeof token === 'string') {
        parts.push(token.slice(0, left));
        left -= token.length;
      } else if (token.b) {
        parts.push(<strong key={part}>{token.b.slice(0, left)}</strong>);
        left -= token.b.length;
      } else {
        parts.push(<Cite key={part} n={token.cite} />);
        left -= CITE_UNITS;
      }
    });
    out.push(<p key={index}>{parts}</p>);
  });
  return out;
}

function useScript(enabled) {
  const [state, setState] = useState({ scene: 0, phase: 'typing', n: 0 });

  useEffect(() => {
    if (!enabled) return undefined;
    const scene = SCENES[state.scene];
    let delay;
    let next;
    switch (state.phase) {
      case 'typing':
        if (state.n < scene.question.length) {
          delay = 34 + Math.random() * 40;
          next = { ...state, n: state.n + 1 };
        } else {
          delay = 500;
          next = { ...state, phase: 'stages', n: 0 };
        }
        break;
      case 'stages':
        if (state.n < STAGES.length - 1) {
          delay = state.n === 0 ? 700 : 620;
          next = { ...state, n: state.n + 1 };
        } else {
          delay = 420;
          next = { ...state, phase: 'answer', n: 0 };
        }
        break;
      case 'answer': {
        const total = unitsOf(scene.answer);
        if (state.n < total) {
          delay = 24;
          next = { ...state, n: Math.min(total, state.n + 3) };
        } else {
          delay = 250;
          next = { ...state, phase: 'done', n: 0 };
        }
        break;
      }
      case 'done':
        delay = 4600;
        next = { ...state, phase: 'leaving' };
        break;
      default:
        delay = 480;
        next = { scene: (state.scene + 1) % SCENES.length, phase: 'typing', n: 0 };
    }
    const id = window.setTimeout(() => setState(next), delay);
    return () => window.clearTimeout(id);
  }, [enabled, state]);

  return state;
}

function StageRow({ phase, n }) {
  // How many stages are finished, and which one is running.
  const finished = phase === 'stages' ? n : phase === 'answer' ? STAGES.length - 1 : STAGES.length;
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {STAGES.map((stage, index) => {
        const done = index < finished;
        const active = index === finished;
        return (
          <span
            key={stage}
            className={cn(
              'inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-medium transition-all duration-300',
              done && 'border-transparent bg-success/10 text-success',
              active && 'border-primary/30 bg-accent text-accent-foreground',
              !done && !active && 'text-muted-foreground/60',
            )}
          >
            {done ? (
              <Check className="size-3" strokeWidth={3} />
            ) : active ? (
              <LoaderCircle className="size-3 animate-spin" />
            ) : (
              <span className="size-1.5 rounded-full bg-current opacity-50" />
            )}
            {stage}
          </span>
        );
      })}
    </div>
  );
}

export default function HeroDemo() {
  const frameRef = useRef(null);
  const tiltRef = useRef(null);
  const onScreen = useInView(frameRef);
  const [still] = useState(prefersReducedMotion);
  const live = useScript(onScreen && !still);
  // Without motion, show the first conversation already answered.
  const state = still ? { scene: 0, phase: 'done', n: 0 } : live;
  const scene = SCENES[state.scene];
  const asked = state.phase !== 'typing';
  const answering = state.phase === 'answer' || state.phase === 'done' || state.phase === 'leaving';
  const answered = state.phase === 'done' || state.phase === 'leaving';
  const budget = answered ? Infinity : state.phase === 'answer' ? state.n : 0;

  const onPointerMove = (event) => {
    const node = tiltRef.current;
    if (!node || still || event.pointerType !== 'mouse') return;
    const rect = node.getBoundingClientRect();
    const x = (event.clientX - rect.left) / rect.width - 0.5;
    const y = (event.clientY - rect.top) / rect.height - 0.5;
    node.style.setProperty('--ry', `${x * 7}deg`);
    node.style.setProperty('--rx', `${y * -7}deg`);
  };
  const onPointerLeave = () => {
    tiltRef.current?.style.setProperty('--ry', '0deg');
    tiltRef.current?.style.setProperty('--rx', '0deg');
  };

  return (
    <div ref={frameRef} className="landing-demo relative" onPointerMove={onPointerMove} onPointerLeave={onPointerLeave}>
      <div aria-hidden="true" className="landing-demo__glow" />

      <div ref={tiltRef} className="landing-demo__tilt">
        <div
          role="img"
          aria-label="A sample ThaparGenie conversation: a question is answered with citations to official documents."
          className="relative flex h-[34rem] flex-col overflow-hidden rounded-2xl bg-card text-card-foreground shadow-[0_40px_120px_-30px_rgb(0_0_0/0.65)] ring-1 ring-white/15 sm:h-[31rem]"
        >
          {/* Window bar */}
          <div className="flex items-center gap-2.5 border-b px-4 py-3">
            <LogoMark motion="loop" className="size-7 rounded-lg" />
            <div className="min-w-0 leading-tight">
              <p className="text-[13px] font-semibold">ThaparGenie</p>
              <p className="flex items-center gap-1.5 text-[11px] text-muted-foreground">
                <span className="landing-live size-1.5 rounded-full bg-success" />
                Answers from official TIET sources
              </p>
            </div>
            <div className="ml-auto flex gap-1.5" aria-hidden="true">
              <span className="size-2.5 rounded-full bg-muted-foreground/20" />
              <span className="size-2.5 rounded-full bg-muted-foreground/20" />
              <span className="size-2.5 rounded-full bg-muted-foreground/20" />
            </div>
          </div>

          {/* Thread */}
          <div
            className={cn(
              'flex flex-1 flex-col gap-3.5 overflow-hidden px-4 pt-4 text-[13px] leading-relaxed transition-all duration-500',
              state.phase === 'leaving' && '-translate-y-3 opacity-0',
            )}
          >
            {asked ? (
              <div className="landing-bubble ml-auto max-w-[85%] rounded-2xl rounded-br-md bg-primary px-3.5 py-2 text-primary-foreground shadow-sm">
                {scene.question}
              </div>
            ) : null}

            {asked ? (
              <div className="landing-bubble flex gap-2.5">
                <span className="mt-0.5 inline-flex size-6 shrink-0 items-center justify-center rounded-md bg-white ring-1 ring-black/5">
                  <LogoGlyph motion={answered ? 'none' : 'think'} className="h-3.5 w-auto" />
                </span>
                <div className="min-w-0 flex-1 space-y-2.5">
                  <StageRow phase={state.phase} n={state.n} />
                  {answering ? (
                    <div className={cn('space-y-2.5', !answered && 'streaming-caret')}>{renderAnswer(scene.answer, budget)}</div>
                  ) : null}
                  {answered ? (
                    <div className="grid gap-1.5 pt-0.5">
                      {scene.sources.map((source, index) => {
                        const Icon = source.icon;
                        return (
                          <div
                            key={source.title}
                            className="landing-source flex items-center gap-2 rounded-lg border bg-muted/50 px-2.5 py-1.5"
                            style={{ '--d': `${index * 120}ms` }}
                          >
                            <span className="inline-flex size-4 items-center justify-center rounded bg-accent text-[10px] font-semibold text-accent-foreground">
                              {index + 1}
                            </span>
                            <Icon className="size-3.5 text-muted-foreground" />
                            <span className="truncate text-[12px] font-medium">{source.title}</span>
                            <span className="ml-auto shrink-0 text-[11px] text-muted-foreground">{source.meta}</span>
                          </div>
                        );
                      })}
                    </div>
                  ) : null}
                </div>
              </div>
            ) : null}
          </div>

          {/* Composer */}
          <div className="p-3">
            <div className="flex items-center gap-2 rounded-xl border bg-field px-3 py-2">
              <span className="min-w-0 flex-1 truncate text-[13px]">
                {state.phase === 'typing' ? (
                  <>
                    {scene.question.slice(0, state.n)}
                    <span className="landing-caret" />
                  </>
                ) : (
                  <span className="text-muted-foreground">Ask about fees, hostels, exams…</span>
                )}
              </span>
              <Mic className="size-4 text-muted-foreground" />
              <span
                className={cn(
                  'inline-flex size-7 items-center justify-center rounded-lg bg-primary text-primary-foreground transition-transform duration-200',
                  state.phase === 'typing' && state.n === scene.question.length && 'scale-110',
                )}
              >
                <ArrowUp className="size-4" />
              </span>
            </div>
          </div>
        </div>

        {/* Floating notes around the window */}
        <div aria-hidden="true" className="landing-float landing-float--a hidden sm:flex">
          <Check className="size-3.5 text-success" strokeWidth={3} />
          Checked against the sources
        </div>
        <div aria-hidden="true" className="landing-float landing-float--b hidden sm:flex">
          <span className="font-semibold text-primary dark:text-accent-foreground">EN</span>
          <span className="text-muted-foreground">+</span>
          <span className="font-semibold text-primary dark:text-accent-foreground">Hinglish</span>
        </div>
      </div>

      <p className="mt-9 text-center text-xs text-white/55">Sample conversation, for illustration.</p>
    </div>
  );
}
