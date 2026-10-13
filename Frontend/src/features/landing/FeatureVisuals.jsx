import {
  Archive,
  CalendarCheck,
  Check,
  Copy,
  CornerDownRight,
  Download,
  History,
  Laptop,
  Link2,
  Megaphone,
  MessageSquare,
  Mic,
  Moon,
  Pencil,
  Pin,
  Printer,
  Search,
  SearchX,
  Share2,
  ShieldCheck,
  Smartphone,
  Sparkles,
  Sun,
  TriangleAlert,
} from 'lucide-react';

import { LogoGlyph } from '@/components/brand/Brand';

// Small working visuals for the feature cards. Each loops quietly once its card is on screen
// (the card carries data-play, which adds .is-visible); landing.css holds the timing.

export function CiteVisual() {
  return (
    <div className="lp-fviz lp-fviz--cite" aria-hidden="true">
      <p className="lp-cite__text">
        Mid-semester exams run in the second week of October
        <span className="lp-cite__mark lp-cite__mark--a">1</span>, and the datesheet goes up on the notice board a week
        before
        <span className="lp-cite__mark lp-cite__mark--b">2</span>.
      </p>
      <div className="lp-cite__previews">
        <div className="lp-cite__preview lp-cite__preview--a">
          <div className="lp-cite__head">
            <span className="lp-filetype" data-kind="PDF">
              PDF
            </span>
            <span className="min-w-0">
              <span className="block truncate font-semibold">Academic calendar 2026–27.pdf</span>
              <span className="block text-muted-foreground">Page 2</span>
            </span>
          </div>
          <span className="lp-cite__line" style={{ width: '90%' }} />
          <span className="lp-cite__line lp-cite__line--hit" style={{ width: '76%' }} />
          <span className="lp-cite__line" style={{ width: '62%' }} />
        </div>
        <div className="lp-cite__preview lp-cite__preview--b">
          <div className="lp-cite__head">
            <span className="lp-filetype" data-kind="NEW">
              NEW
            </span>
            <span className="min-w-0">
              <span className="block truncate font-semibold">Notice · Examinations</span>
              <span className="block text-muted-foreground">Notice board</span>
            </span>
          </div>
          <span className="lp-cite__line" style={{ width: '70%' }} />
          <span className="lp-cite__line" style={{ width: '84%' }} />
          <span className="lp-cite__line lp-cite__line--hit" style={{ width: '58%' }} />
        </div>
      </div>
    </div>
  );
}

export function HonestVisual() {
  return (
    <div className="lp-fviz lp-fviz--honest" aria-hidden="true">
      <span className="lp-honest__q">Hostel Wi-Fi password?</span>
      <div className="lp-honest__search">
        <span>Searching official documents</span>
        <span className="lp-honest__bar">
          <span />
        </span>
      </div>
      <div className="lp-honest__result">
        <SearchX className="size-3.5 shrink-0" />
        <span className="min-w-0">
          <span className="block font-semibold text-foreground">Not in the official documents</span>
          <span className="block">Try the hostel office instead.</span>
        </span>
      </div>
    </div>
  );
}

export function VerifyVisual() {
  const figures = ['₹98,000', '2026–27', '15 July'];
  return (
    <div className="lp-fviz lp-fviz--verify" aria-hidden="true">
      <p className="lp-verify__text">
        The hostel fee is <b style={{ '--i': 0 }}>{figures[0]}</b> for <b style={{ '--i': 1 }}>{figures[1]}</b>, due by{' '}
        <b style={{ '--i': 2 }}>{figures[2]}</b>.
      </p>
      <div className="lp-verify__row">
        {figures.map((figure, index) => (
          <span key={figure} className="lp-verify__chip" style={{ '--i': index }}>
            <Check className="size-3" strokeWidth={3} />
            {figure}
          </span>
        ))}
      </div>
      <span className="lp-verify__ok">
        <ShieldCheck className="size-3.5 shrink-0" />
        Every figure found in a cited source
      </span>
    </div>
  );
}

export function FreshVisual() {
  const docs = [
    ['Fee structure 2026–27.pdf', 'Current', false],
    ['Fee structure 2024–25.pdf', 'Outdated', true],
  ];
  return (
    <div className="lp-fviz lp-fviz--fresh" aria-hidden="true">
      {docs.map(([name, state, old], index) => (
        <div key={name} className="lp-fresh__doc" data-old={old || undefined} style={{ '--i': index }}>
          <span className="min-w-0 flex-1 truncate">{name}</span>
          <span className="lp-fresh__state">
            {old ? <TriangleAlert className="size-3" /> : <Check className="size-3" strokeWidth={3} />}
            {state}
          </span>
        </div>
      ))}
      <span className="lp-fresh__line">
        <CalendarCheck className="size-3.5 shrink-0" />
        <span className="min-w-0 truncate">
          Sources cover <b>2026–27</b> · latest 12 Jun 2026
        </span>
      </span>
    </div>
  );
}

export function ListVisual() {
  const hostels = 'ABCDEFGHIJKL'.split('');
  return (
    <div className="lp-fviz lp-fviz--list" aria-hidden="true">
      <span className="lp-list__q">List all the hostels</span>
      <div className="lp-list__grid">
        {hostels.map((letter, index) => (
          <span key={letter} style={{ '--i': index }}>
            {letter}
          </span>
        ))}
      </div>
      <span className="lp-list__count">
        <Check className="size-3" strokeWidth={3} />
        12 of 12 listed · whole page read
      </span>
    </div>
  );
}

export function HistoryVisual() {
  const chats = [
    [Pin, ' fee for first-years', true],
    [MessageSquare, ' rules and timings', false],
  ];
  return (
    <div className="lp-fviz lp-fviz--history" aria-hidden="true">
      <div className="lp-history__main">
        <div className="lp-history__search">
          <Search className="size-3.5 shrink-0 text-muted-foreground" />
          <span className="lp-history__typed">hostel</span>
          <kbd>Ctrl K</kbd>
        </div>
        {chats.map(([Icon, rest, pinned], index) => (
          <div key={rest} className="lp-history__chat" data-pinned={pinned || undefined} style={{ '--i': index }}>
            <Icon className="size-3 shrink-0" />
            <span className="min-w-0 flex-1 truncate">
              <mark>Hostel</mark>
              {rest}
            </span>
            <span className="lp-history__tools">
              <Pencil className="size-3" style={{ '--i': 0 }} />
              <Archive className="size-3" style={{ '--i': 1 }} />
            </span>
          </div>
        ))}
      </div>
      <div className="lp-history__sync">
        <span className="lp-history__devices">
          <Laptop className="size-5" />
          <span className="lp-history__link">
            <i />
            <i />
            <i />
          </span>
          <Smartphone className="size-4" />
        </span>
        Same chats on every device
      </div>
    </div>
  );
}

export function SuggestVisual() {
  const ideas = ['When is the fee due?', 'Can I pay in instalments?', 'Is there a late fine?'];
  return (
    <div className="lp-fviz lp-fviz--suggest" aria-hidden="true">
      <span className="lp-suggest__label">
        <Sparkles className="size-3" />
        Ask next
      </span>
      {ideas.map((idea, index) => (
        <span key={idea} className="lp-suggest__idea" style={{ '--i': index }}>
          <CornerDownRight className="size-3 shrink-0" />
          <span className="min-w-0 truncate">{idea}</span>
        </span>
      ))}
    </div>
  );
}

export function PersonalVisual() {
  const fields = [
    ['Campus', 'Patiala'],
    ['Programme', 'BE COE'],
    ['Year', '2nd'],
  ];
  return (
    <div className="lp-fviz lp-fviz--personal" aria-hidden="true">
      <div className="lp-personal__fields">
        {fields.map(([label, value], index) => (
          <span key={label} className="lp-personal__field" style={{ '--i': index }}>
            <span className="lp-personal__label">{label}</span>
            <span className="truncate font-semibold">{value}</span>
          </span>
        ))}
      </div>
      <div className="lp-personal__theme">
        <span className="lp-personal__thumb" />
        <span>
          <Sun className="size-3" />
          Light
        </span>
        <span>
          <Moon className="size-3" />
          Dark
        </span>
      </div>
    </div>
  );
}

export function FollowVisual() {
  return (
    <div className="lp-fviz lp-fviz--follow" aria-hidden="true">
      <span className="lp-follow__q lp-follow__q--a">BE COE fee for 2026–27?</span>
      <span className="lp-follow__a">
        <span />
        <span />
      </span>
      <span className="lp-follow__q lp-follow__q--b">and for hostel?</span>
      <span className="lp-follow__got">
        Understood:
        {['hostel fee', 'BE COE', '2026–27'].map((tag, index) => (
          <b key={tag} style={{ '--i': index }}>
            {tag}
          </b>
        ))}
      </span>
    </div>
  );
}

export function VoiceVisual() {
  return (
    <div className="lp-fviz lp-fviz--voice" aria-hidden="true">
      <div className="flex items-center gap-3">
        <span className="lp-voice__mic">
          <Mic className="size-4" />
        </span>
        <span className="lp-voice__wave">
          {Array.from({ length: 16 }, (_, index) => (
            <span key={index} style={{ '--i': index }} />
          ))}
        </span>
      </div>
      <span className="lp-voice__text">
        <span className="lp-voice__typed">attendance kam hai, end-sem de sakte hain?</span>
      </span>
    </div>
  );
}

export function BranchVisual() {
  const versions = [
    ['92%', '74%', '55%'],
    ['80%', '88%', '40%'],
    ['66%', '90%', '70%'],
  ];
  return (
    <div className="lp-fviz lp-fviz--branch" aria-hidden="true">
      <div className="lp-branch__card">
        {versions.map((lines, index) => (
          <span key={index} className="lp-branch__version" style={{ '--i': index }}>
            {lines.map((width, line) => (
              <span key={line} className="lp-branch__line" style={{ width }} />
            ))}
          </span>
        ))}
      </div>
      <div className="lp-branch__bar">
        <span className="lp-branch__count">
          ‹
          <span className="lp-branch__nums">
            {[1, 2, 3].map((n) => (
              <span key={n} style={{ '--i': n - 1 }}>
                {n} / 3
              </span>
            ))}
          </span>
          ›
        </span>
        <History className="lp-branch__icon size-3.5" />
      </div>
    </div>
  );
}

export function NoticesVisual() {
  const notices = [
    ['Examinations', 'Datesheet for mid-semester exams'],
    ['Hostel', 'Room allotment for returning students'],
  ];
  return (
    <div className="lp-fviz lp-fviz--notices" aria-hidden="true">
      <div className="lp-notice lp-notice--pinned">
        <Megaphone className="size-3.5 shrink-0" />
        <span className="min-w-0 flex-1 truncate">Important · exam form deadline</span>
        <Pin className="size-3 shrink-0" />
      </div>
      {notices.map(([topic, title], index) => (
        <div key={title} className="lp-notice" style={{ '--i': index }}>
          <span className="lp-notice__dot" />
          <span className="min-w-0 flex-1">
            <span className="block text-[9.5px] font-bold tracking-wide text-muted-foreground uppercase">{topic}</span>
            <span className="block truncate">{title}</span>
          </span>
        </div>
      ))}
    </div>
  );
}

export function ShareVisual() {
  return (
    <div className="lp-fviz lp-fviz--share" aria-hidden="true">
      <div className="lp-share__link">
        <Link2 className="size-3.5 shrink-0 text-muted-foreground" />
        <span className="min-w-0 flex-1 truncate">…/s/8f2a91c4</span>
        <span className="lp-share__copy">
          <Copy className="size-3" />
          Copy
        </span>
      </div>
      <div className="flex gap-1.5">
        {[Share2, Printer, Download].map((Icon, index) => (
          <span key={index} className="lp-share__tile" style={{ '--i': index }}>
            <Icon className="size-3.5" />
          </span>
        ))}
      </div>
      <span className="lp-share__toast">
        <Check className="size-3" strokeWidth={3} />
        Link copied, valid for 7 days
      </span>
    </div>
  );
}

export function InstallVisual() {
  return (
    <div className="lp-fviz lp-fviz--install" aria-hidden="true">
      <div className="lp-phone">
        <div className="lp-phone__grid">
          {Array.from({ length: 7 }, (_, index) => (
            <span key={index} className="lp-phone__app" />
          ))}
          <span className="lp-phone__app lp-phone__app--genie">
            <LogoGlyph className="h-[60%] w-auto" />
          </span>
        </div>
        <div className="lp-phone__sheet">
          <span className="font-semibold">Add to Home Screen</span>
          <span className="lp-phone__add">Add</span>
        </div>
      </div>
    </div>
  );
}
