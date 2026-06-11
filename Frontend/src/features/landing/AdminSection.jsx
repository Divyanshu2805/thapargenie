import {
  BookPlus,
  Check,
  ClipboardList,
  FileText,
  FileUp,
  FlaskConical,
  LayoutDashboard,
  LoaderCircle,
  Megaphone,
  MessageSquareWarning,
  SearchX,
  ThumbsDown,
} from 'lucide-react';
import { useRef, useState } from 'react';

import { LogoGlyph, LogoMark } from '@/components/brand/Brand';

import { prefersReducedMotion, useCycle, useInView } from './landing-hooks';
import { FakeCursor, SectionHeading } from './ui';

// "For admins": a small copy of the admin dashboard plays the feedback loop, one step at a
// time (a report, an FAQ, processing, a test). The steps on the side follow along.

const NAV = [
  { icon: LayoutDashboard, label: 'Overview' },
  { icon: MessageSquareWarning, label: 'Feedback' },
  { icon: SearchX, label: 'Knowledge gaps' },
  { icon: FileText, label: 'Documents' },
  { icon: FlaskConical, label: 'Playground' },
  { icon: Megaphone, label: 'Notices' },
];

const STEPS = [
  { nav: 'Feedback', title: 'A student flags an answer', text: 'A 👎 with a reason lands in Feedback, with the question and answer but never the student’s name.' },
  { nav: 'Feedback', title: 'An admin adds the missing fact', text: 'Create an FAQ straight from the report, or upload the new PDF.' },
  { nav: 'Documents', title: 'It’s processed in minutes', text: 'Read, split and indexed automatically, with live status. Old cached answers are cleared.' },
  { nav: 'Playground', title: 'The next student gets it right', text: 'Test the question in the playground: the new fact is found and cited.' },
];

const TOOLS = [
  { icon: FileUp, title: 'Upload anything official', text: 'PDFs, Word files, spreadsheets, web pages or quick FAQs, scanned pages included.' },
  { icon: SearchX, title: 'See the gaps', text: 'Unanswered questions, grouped and ranked by how often they’re asked.' },
  { icon: FlaskConical, title: 'Tune in the playground', text: 'See which passages a question found and why, then fix and re-test.' },
  { icon: ClipboardList, title: 'Stay in control', text: 'Approve users, post notices and banners, set limits, read the audit log.' },
];

function FeedbackScene() {
  return (
    <div className="lp-scene">
      <div className="lp-scene__head">
        <p className="lp-scene__title">Feedback</p>
        <span className="lp-seg">
          <span data-on="">Open · 3</span>
          <span>Resolved</span>
        </span>
      </div>
      <div className="lp-report">
        <div className="flex items-center gap-2">
          <span className="lp-pill lp-pill--bad">
            <ThumbsDown className="size-3" />
            Outdated
          </span>
          <span className="text-[11px] text-muted-foreground">Student 4F2A · 2 min ago</span>
        </div>
        <p className="lp-report__q">What is the hostel fee for first-year girls?</p>
        <p className="lp-report__a">The 2025–26 hostel fee for girls is…</p>
        <div className="lp-report__actions">
          <span className="lp-mini-btn lp-mini-btn--ghost">Dismiss</span>
          <span className="lp-mini-btn lp-mini-btn--ghost">Resolve</span>
          <span className="lp-mini-btn lp-mini-btn--primary lp-report__create">
            <BookPlus className="size-3" />
            Create FAQ
            <FakeCursor />
          </span>
        </div>
      </div>
      <div className="lp-report lp-report--dim">
        <span className="lp-pill">
          <ThumbsDown className="size-3" />
          Incomplete
        </span>
        <p className="lp-report__q">When does backlog registration close?</p>
      </div>
    </div>
  );
}

function FaqScene() {
  return (
    <div className="lp-scene">
      <div className="lp-scene__head">
        <p className="lp-scene__title">Add knowledge · FAQ</p>
        <span className="lp-pill">From feedback</span>
      </div>
      <label className="lp-field">
        <span>Question</span>
        <span className="lp-field__box">
          <span className="lp-type" style={{ '--chars': 38 }}>
            Hostel fee for first-year girls, 2026–27
          </span>
        </span>
      </label>
      <label className="lp-field">
        <span>Answer</span>
        <span className="lp-field__box lp-field__box--tall">
          <span className="lp-type lp-type--late" style={{ '--chars': 44 }}>
            ₹98,000 a year (twin sharing), plus mess.
          </span>
        </span>
      </label>
      <div className="flex items-center justify-between gap-2">
        <span className="lp-field__select">Hostel &amp; campus life</span>
        <span className="lp-mini-btn lp-mini-btn--primary lp-faq-save">
          Add to knowledge base
          <FakeCursor />
        </span>
      </div>
    </div>
  );
}

function DocumentsScene() {
  const rows = [
    { name: 'Fee structure 2026–27.pdf', kind: 'PDF' },
    { name: 'Academic calendar 2026–27.pdf', kind: 'PDF' },
  ];
  return (
    <div className="lp-scene">
      <div className="lp-scene__head">
        <p className="lp-scene__title">Documents</p>
        <span className="lp-pill">All categories</span>
      </div>
      <div className="lp-doc lp-doc--new">
        <span className="lp-filetype" data-kind="FAQ">FAQ</span>
        <span className="min-w-0 flex-1">
          <span className="block truncate text-[12px] font-semibold">Hostel fee for first-year girls</span>
          <span className="lp-doc__bar">
            <span />
          </span>
        </span>
        <span className="lp-status">
          <span className="lp-status__s lp-status__s--queued">Queued</span>
          <span className="lp-status__s lp-status__s--processing">
            <LoaderCircle className="size-3 animate-spin" />
            Processing
          </span>
          <span className="lp-status__s lp-status__s--ready">
            <Check className="size-3" strokeWidth={3} />
            Ready
          </span>
        </span>
      </div>
      {rows.map((row) => (
        <div key={row.name} className="lp-doc">
          <span className="lp-filetype" data-kind={row.kind}>
            {row.kind}
          </span>
          <span className="min-w-0 flex-1 truncate text-[12px] font-medium">{row.name}</span>
          <span className="lp-status">
            <span className="lp-status__s lp-status__s--static">
              <Check className="size-3" strokeWidth={3} />
              Ready
            </span>
          </span>
        </div>
      ))}
      <span className="lp-toast lp-toast--scene">Answer cache cleared</span>
    </div>
  );
}

function PlaygroundScene() {
  return (
    <div className="lp-scene">
      <div className="lp-scene__head">
        <p className="lp-scene__title">Playground</p>
        <span className="lp-pill lp-pill--good">
          <Check className="size-3" strokeWidth={3} />
          Answered
        </span>
      </div>
      <div className="lp-field__box">
        <span className="lp-type" style={{ '--chars': 29 }}>
          hostel fee for girls 1st year?
        </span>
      </div>
      <div className="lp-play">
        <span className="lp-play__avatar">
          <LogoGlyph className="h-3 w-auto" />
        </span>
        <p>
          First-year girls pay <strong>₹98,000 a year</strong> for a twin-sharing room, plus mess
          <span className="lp-play__cite">1</span>
        </p>
      </div>
      <div className="lp-play__sources">
        {[
          ['FAQ · Hostel fee 2026–27', 96],
          ['Hostel rules.pdf · p. 4', 61],
          ['Fee structure.pdf · p. 9', 44],
        ].map(([name, score], index) => (
          <span key={name} className="lp-play__source" style={{ '--i': index, '--score': `${score}%` }}>
            <span className="truncate">{name}</span>
            <span className="lp-play__score">
              <span />
            </span>
          </span>
        ))}
      </div>
    </div>
  );
}

// Small working visuals on the four tool cards. Each loops quietly once the card is on screen.

function UploadVisual() {
  const files = [
    ['PDF', 'Fee structure'],
    ['DOC', 'Hostel rules'],
    ['XLS', 'Placement stats'],
    ['WEB', 'thapar.edu page'],
  ];
  return (
    <div className="lp-tool__viz lp-tool__viz--upload" aria-hidden="true">
      <div className="lp-drop">
        {files.map(([kind, name], index) => (
          <span key={name} className="lp-drop__file" style={{ '--i': index }}>
            <span className="lp-filetype" data-kind={kind}>
              {kind}
            </span>
            <span className="truncate">{name}</span>
            <Check className="lp-drop__ok size-3" strokeWidth={3} />
          </span>
        ))}
        <span className="lp-drop__hint">
          <FileUp className="size-3.5" />
          Drop files here
        </span>
      </div>
    </div>
  );
}

function GapsVisual() {
  const gaps = [
    ['Hostel Wi-Fi setup?', 92],
    ['Bus to Patiala city?', 64],
    ['Canteen timings?', 41],
  ];
  return (
    <div className="lp-tool__viz lp-tool__viz--gaps" aria-hidden="true">
      {gaps.map(([question, share], index) => (
        <span key={question} className="lp-gap" style={{ '--i': index, '--share': `${share}%` }}>
          <span className="lp-gap__rank">{index + 1}</span>
          <span className="min-w-0 flex-1">
            <span className="block truncate">{question}</span>
            <span className="lp-gap__bar">
              <span />
            </span>
          </span>
        </span>
      ))}
    </div>
  );
}

function PlaygroundVisual() {
  const passages = [
    ['Regulations · p. 12', 94],
    ['Exam notice', 71],
    ['Hostel rules · p. 2', 23],
  ];
  return (
    <div className="lp-tool__viz lp-tool__viz--play" aria-hidden="true">
      <span className="lp-play-q">
        <FlaskConical className="size-3" />
        attendance rule for end-sems
      </span>
      {passages.map(([name, score], index) => (
        <span key={name} className="lp-play-row" data-top={index === 0 || undefined} style={{ '--i': index, '--score': `${score}%` }}>
          <span className="truncate">{name}</span>
          <span className="lp-play-row__meter">
            <span />
          </span>
          <span className="lp-play-row__num">{(score / 100).toFixed(2)}</span>
        </span>
      ))}
    </div>
  );
}

function ControlVisual() {
  const settings = [
    ['Require approval', true],
    ['Maintenance mode', false],
    ['Show banner', true],
  ];
  return (
    <div className="lp-tool__viz lp-tool__viz--control" aria-hidden="true">
      {settings.map(([label, on], index) => (
        <span key={label} className="lp-setting" data-on={on || undefined} style={{ '--i': index }}>
          {label}
          <span className="lp-switch">
            <span />
          </span>
        </span>
      ))}
    </div>
  );
}

const TOOL_VISUALS = [UploadVisual, GapsVisual, PlaygroundVisual, ControlVisual];

const SCENES = [FeedbackScene, FaqScene, DocumentsScene, PlaygroundScene];

export default function AdminSection() {
  const ref = useRef(null);
  const inView = useInView(ref);
  const [still] = useState(prefersReducedMotion);
  const { active, setActive, onAnimationEnd } = useCycle(STEPS.length);
  const Scene = SCENES[active];

  return (
    <section id="admins" className="landing-section mx-auto max-w-[76rem] px-4 sm:px-6 lg:px-8">
      <div className="grid items-end gap-6 lg:grid-cols-[1.1fr_1fr]">
        <SectionHeading index="05" align="left" eyebrow="For admins" title="Kept accurate by the people who" gold="run the campus." />
        <p data-reveal style={{ '--d': '200ms' }} className="max-w-md text-base leading-relaxed text-muted-foreground sm:text-lg lg:justify-self-end">
          A dashboard for the team behind the knowledge base. Every wrong answer a student reports becomes a fix the next
          student benefits from.
        </p>
      </div>

      <div
        ref={ref}
        className="lp-cycle mt-12 grid items-center gap-8 lg:grid-cols-[1.35fr_1fr] lg:gap-10"
        data-running={(inView && !still) || undefined}
        onAnimationEnd={onAnimationEnd}
      >
        <div data-reveal className="lp-dash" aria-hidden="true">
          <div className="lp-dash__top">
            <LogoMark className="size-6 rounded-md" />
            <span className="text-[12px] font-semibold">ThaparGenie</span>
            <span className="lp-pill">Admin</span>
            <span className="lp-dash__search">Search…</span>
            <span className="lp-dash__me">AD</span>
          </div>
          <div className="lp-dash__body">
            <nav className="lp-dash__nav">
              {NAV.map((item) => {
                const Icon = item.icon;
                return (
                  <span key={item.label} data-on={item.label === STEPS[active].nav || undefined}>
                    <Icon className="size-3.5" />
                    <span className="lp-dash__navlabel">{item.label}</span>
                  </span>
                );
              })}
            </nav>
            <div className="lp-dash__main">
              <Scene key={active} />
            </div>
          </div>
        </div>

        <ol className="grid gap-2.5">
          {STEPS.map((step, index) => (
            <li key={step.title} data-reveal style={{ '--d': `${index * 90}ms` }}>
              <button
                type="button"
                onClick={() => setActive(index)}
                data-active={index === active || undefined}
                className="lp-stepbtn"
              >
                <span className="lp-stepbtn__num">{index + 1}</span>
                <span className="min-w-0 text-left">
                  <span className="block text-[15px] font-semibold tracking-tight">{step.title}</span>
                  <span className="lp-stepbtn__text">{step.text}</span>
                </span>
                {index === active ? <span className="lp-progress" /> : null}
              </button>
            </li>
          ))}
        </ol>
      </div>

      <ul className="mt-12 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {TOOLS.map((tool, index) => {
          const Icon = tool.icon;
          const Visual = TOOL_VISUALS[index];
          return (
            <li key={tool.title} data-reveal data-tilt data-spotlight style={{ '--d': `${index * 80}ms` }} className="lp-card lp-tool icon-nudge p-4">
              <Visual />
              <div className="mt-4 flex items-center gap-2.5 px-1">
                <span className="lp-icon lp-icon--sm">
                  <Icon className="size-4" />
                </span>
                <h3 className="text-[15px] font-semibold tracking-tight">{tool.title}</h3>
              </div>
              <p className="mt-2 px-1 text-sm leading-relaxed text-muted-foreground">{tool.text}</p>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
