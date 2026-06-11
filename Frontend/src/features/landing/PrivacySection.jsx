import { Download, MessageSquare, ThumbsDown, Trash2 } from 'lucide-react';

import { Contours } from '@/components/ambient';

import { FakeCursor, SectionHeading } from './ui';

// "Privacy by design", shown with small working copies of the real screens. Each mini UI
// loops a short CSS animation once the panel is on screen (.is-visible).

function Tile({ label, title, text, children }) {
  return (
    <article className="lp-glass flex flex-col">
      <p className="lp-glass__label">{label}</p>
      <div className="mt-3 flex flex-1 flex-col justify-center">{children}</div>
      <h3 className="mt-5 text-[15px] font-semibold tracking-tight">{title}</h3>
      <p className="mt-1 text-sm leading-relaxed text-muted-foreground">{text}</p>
    </article>
  );
}

function RequestInspector() {
  const identity = [
    ['name', 'Asha Rao'],
    ['email', 'asha.rao@thapar.edu'],
    ['account', 'uid_8f2a91c4…'],
  ];
  return (
    <div className="lp-screen lp-inspector" aria-hidden="true">
      <div className="lp-screen__bar">
        <span className="lp-screen__dots" />
        <span>POST · language model</span>
      </div>
      <div className="lp-inspector__body">
        <p className="lp-inspector__row">
          <span className="lp-inspector__key">question</span>
          <span className="lp-inspector__val">“What is the hostel fee for girls?”</span>
        </p>
        <p className="lp-inspector__row">
          <span className="lp-inspector__key">context</span>
          <span className="lp-inspector__val">3 passages · official documents</span>
        </p>
        <div className="lp-inspector__rule">never included</div>
        {identity.map(([key, value], index) => (
          <p key={key} className="lp-inspector__row lp-inspector__row--id" style={{ '--i': index }}>
            <span className="lp-inspector__key">{key}</span>
            <span className="lp-inspector__val">
              <span className="lp-inspector__secret">{value}</span>
              <span className="lp-inspector__bar" />
            </span>
          </p>
        ))}
      </div>
      <span className="lp-stamp">No identity</span>
    </div>
  );
}

function YourData() {
  return (
    <div className="lp-screen lp-yourdata" aria-hidden="true">
      <div className="lp-yourdata__row">
        <div>
          <p className="lp-yourdata__title">Export your chats</p>
          <p className="lp-yourdata__text">Download every conversation as a JSON file.</p>
        </div>
        <span className="lp-mini-btn lp-yourdata__export">
          <Download className="size-3" />
          <span className="lp-yourdata__idle">Export</span>
          <span className="lp-yourdata__busy">Preparing…</span>
          <FakeCursor />
        </span>
      </div>
      <div className="lp-yourdata__row">
        <div>
          <p className="lp-yourdata__title">Delete all chats</p>
          <p className="lp-yourdata__text">Removes every conversation. Can’t be undone.</p>
        </div>
        <span className="lp-mini-btn lp-mini-btn--danger">
          <Trash2 className="size-3" />
          Delete all
        </span>
      </div>
      <span className="lp-toast">
        <Download className="size-3" />
        thapargenie-chats.json saved
      </span>
    </div>
  );
}

function Pseudonymised() {
  return (
    <div className="lp-screen lp-pseudo" aria-hidden="true">
      <div className="flex items-center gap-2">
        <span className="lp-pseudo__avatar">
          <span className="lp-pseudo__real">AR</span>
          <span className="lp-pseudo__anon">#</span>
        </span>
        <span className="lp-pseudo__name">
          <span className="lp-pseudo__real">Asha Rao</span>
          <span className="lp-pseudo__anon">Student 4F2A</span>
        </span>
        <span className="lp-pseudo__badge">
          <ThumbsDown className="size-3" />
          Outdated
        </span>
      </div>
      <p className="lp-pseudo__quote">“What is the hostel fee for girls?”</p>
      <p className="lp-pseudo__hint">Admins review the answer, not the person.</p>
    </div>
  );
}

function AutoDelete() {
  return (
    <div className="lp-screen lp-autodelete" aria-hidden="true">
      <div className="lp-autodelete__chat">
        <MessageSquare className="size-3.5 shrink-0 text-muted-foreground" />
        <span className="truncate">Hostel fee for first-year girls</span>
        <span className="lp-autodelete__days">
          idle <b className="lp-autodelete__count" /> days
        </span>
      </div>
      <div className="lp-autodelete__track">
        <span className="lp-autodelete__fill" />
        <span className="lp-autodelete__tick" style={{ left: '0%' }}>0</span>
        <span className="lp-autodelete__tick" style={{ left: '50%' }}>90</span>
        <span className="lp-autodelete__tick" style={{ left: '100%' }}>180</span>
      </div>
      <span className="lp-autodelete__done">
        <Trash2 className="size-3" />
        Deleted automatically
      </span>
    </div>
  );
}

export default function PrivacySection() {
  return (
    <section id="privacy" className="landing-section mx-auto max-w-[76rem] px-4 sm:px-6 lg:px-8">
      <div data-reveal className="lp-privacy relative isolate overflow-hidden rounded-[2rem] px-5 py-14 sm:px-10 lg:px-12 lg:py-16">
        <Contours className="lp-privacy__contours" />
        <span aria-hidden="true" className="lp-privacy__glow" />
        <div className="relative grid items-end gap-6 lg:grid-cols-[1.1fr_1fr]">
          <SectionHeading index="04" align="left" eyebrow="Privacy by design" title="Ask freely. Your questions" gold="stay yours." />
          <p data-reveal style={{ '--d': '200ms' }} className="max-w-md text-base leading-relaxed text-muted-foreground sm:text-lg lg:justify-self-end">
            ThaparGenie collects as little as it can, keeps it for as short as it can, and hands you the controls.
            Here’s what that looks like inside the app.
          </p>
        </div>

        <div className="relative mt-12 grid gap-4 md:grid-cols-2">
          <Tile
            label="What the AI receives"
            title="Your identity stays out of the AI"
            text="Only the question and the passages that answer it are sent. Never your name, email or account."
          >
            <RequestInspector />
          </Tile>
          <Tile label="Settings · Your data" title="Yours to take or erase" text="Export everything as a file, or delete one chat or all of them.">
            <YourData />
          </Tile>
          <Tile label="Admin · Feedback" title="Admins don’t read your chats" text="Reports reach admins anonymised. Nobody browses conversations.">
            <Pseudonymised />
          </Tile>
          <Tile
            label="Retention"
            title="Deleted when idle"
            text="Chats you leave untouched for 180 days are removed on their own."
          >
            <AutoDelete />
          </Tile>
        </div>
      </div>
    </section>
  );
}
