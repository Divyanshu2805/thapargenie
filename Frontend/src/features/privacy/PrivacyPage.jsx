import { ArrowLeft } from 'lucide-react';
import { Link } from 'react-router-dom';

import { Brand } from '@/components/brand/Brand';
import { Button } from '@/components/ui/button';

const SECTIONS = [
  {
    title: 'What we store',
    body: [
      'Your account: email address, display name and sign-in provider, managed by Firebase Authentication.',
      'Optional preferences you enter in Settings: campus, programme and year of study.',
      'Your conversations: the questions you ask, the answers, the sources cited, and any feedback you give.',
      'Daily usage counts (how many questions were asked), which contain no question text.',
    ],
  },
  {
    title: 'Why we store it',
    body: [
      'To answer your questions using official TIET information and to keep your chat history available across devices.',
      'To enforce fair daily limits and keep the service reliable.',
      'To improve answers: administrators review answers marked unhelpful, shown without your name or email.',
    ],
  },
  {
    title: 'How long we keep it',
    body: [
      'Conversations are deleted automatically after 180 days without activity.',
      'Technical answer traces are kept for 30 days; usage counts for 13 months; the security audit log for one year.',
      'You can delete a single chat or all of your chats at any time, and export everything as a file.',
      'If you share an answer, a copy of that question and answer is visible to anyone with the link for 7 days (or until you turn it off), then deleted 30 days later. Deleting the chat deletes the link at once.',
    ],
  },
  {
    title: 'Who processes it',
    body: [
      'Firebase (Google) handles sign-in, email verification and password resets.',
      'Supabase hosts the database and uploaded official documents, in Mumbai, India.',
      'An AI model provider (Google Gemini by default) receives question text and retrieved official passages to write answers. It never receives your name, email or account id.',
      'If you speak a question, your browser turns the speech into text with its own service (Google in Chrome, Microsoft in Edge). ThaparGenie receives only the text, and no audio is recorded or kept.',
    ],
  },
  {
    title: 'Please remember',
    body: [
      'Don’t share personal information such as roll numbers, phone numbers or grades in your questions.',
      'Answers can be wrong. Check important details against the cited official source.',
      'Personal records such as grades, attendance and fee dues are only available through Webkiosk.',
    ],
  },
];

export default function PrivacyPage() {
  return (
    <div className="min-h-dvh bg-background">
      <header className="sticky top-0 z-10 border-b bg-background/80 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-3xl items-center justify-between px-4 sm:px-6">
          <Link to="/" className="rounded-lg outline-none focus-visible:ring-2 focus-visible:ring-ring/50">
            <Brand />
          </Link>
          <Button asChild variant="ghost" size="sm">
            <Link to="/">
              <ArrowLeft /> Back
            </Link>
          </Button>
        </div>
      </header>
      <main className="mx-auto max-w-3xl px-4 py-10 sm:px-6 sm:py-14">
        <p className="text-sm font-medium text-primary dark:text-accent-foreground">Privacy notice</p>
        <h1 className="mt-2 text-title">How ThaparGenie handles your data</h1>
        <p className="mt-4 text-muted-foreground">
          This notice explains what personal data ThaparGenie collects, why, how long it is kept and who processes it, in
          line with India’s Digital Personal Data Protection Act, 2023.
        </p>
        <div className="mt-10 space-y-10">
          {SECTIONS.map((section, index) => (
            <section key={section.title} aria-labelledby={`privacy-${index}`}>
              <h2 id={`privacy-${index}`} className="text-lg font-semibold">
                {section.title}
              </h2>
              <ul className="mt-3 space-y-2.5">
                {section.body.map((item) => (
                  <li key={item} className="flex gap-3 text-[15px] leading-relaxed text-foreground/85">
                    <span className="mt-2.5 size-1.5 shrink-0 rounded-full bg-primary/60" aria-hidden="true" />
                    {item}
                  </li>
                ))}
              </ul>
            </section>
          ))}
        </div>
      </main>
    </div>
  );
}
