import { useQuery } from '@tanstack/react-query';
import {
  ArrowUpRight,
  BookOpen,
  Check,
  Briefcase,
  Building2,
  CalendarDays,
  CircleHelp,
  ExternalLink,
  GraduationCap,
  IndianRupee,
  Info,
  Landmark,
  Lightbulb,
  Megaphone,
  MessageSquareQuote,
  Users,
  XCircle,
} from 'lucide-react';
import { Link, useNavigate } from 'react-router-dom';

import { PageHeader } from '@/components/layout/PageHeader';
import { SplitSection } from '@/components/split-section';
import { Skeleton } from '@/components/ui/skeleton';
import { useAppConfig } from '@/hooks/use-app-config';
import { chatKeys, getCoverage } from '@/lib/api/chat';
import { formatDate, formatNumber } from '@/lib/format';
import { cn } from '@/lib/utils';

// The "What can I ask?" page. Topics come from the knowledge base;
// the examples and limits below are written for students.

const TOPICS = {
  fees_scholarships: {
    icon: IndianRupee,
    examples: ['What is the BE fee for 2026-27?', 'Which scholarships can first-year students apply for?'],
  },
  admissions: { icon: GraduationCap, examples: ['What is the eligibility for BE admission?', 'When does PhD admission open?'] },
  academic_calendar: { icon: CalendarDays, examples: ['When do the odd semester classes start?', 'When are the mid-semester exams?'] },
  hostel_campus_life: { icon: Building2, examples: ['What is the hostel fee for girls?', 'What time does the library close?'] },
  courses_syllabus: { icon: BookOpen, examples: ['What is taught in UCS301?', 'How many credits is a minor degree?'] },
  rules_regulations: { icon: Landmark, examples: ['What is the attendance rule for exams?', 'What is the anti-ragging policy?'] },
  notices: { icon: Megaphone, examples: ['When is backlog registration?', 'Is there a notice about auxiliary exams?'] },
  placements: { icon: Briefcase, examples: ['What was the average placement package?', 'How do I register for placements?'] },
  departments: { icon: Users, examples: ['Which programmes does the ECE department offer?', 'Who heads the Computer Science department?'] },
  faculty: { icon: Users, examples: ['Who teaches in the Chemistry department?', 'What is Dr. Sharma’s research area?'] },
  about_contact: { icon: Info, examples: ['What is the phone number of the admissions office?', 'Where is the accounts office?'] },
  faq: { icon: MessageSquareQuote, examples: ['How do I get a bonafide certificate?', 'How do I reset my Webkiosk password?'] },
};

const NOT_COVERED = [
  {
    title: 'Your personal records',
    text: 'Marks, attendance, results and fee dues are only on Webkiosk.',
    link: { href: 'https://webkiosk.thapar.edu', label: 'Open Webkiosk' },
  },
  { title: 'Other colleges and general questions', text: 'Answers come only from official Thapar Institute documents.' },
  {
    title: 'Decisions and exceptions',
    text: 'Fee waivers, grade appeals or rule exceptions are decided by the office concerned; I can tell you whom to ask.',
  },
  { title: 'Live status', text: 'Portal outages or changes announced today may not be in the documents yet.' },
];

const TIPS = [
  'Ask one thing at a time.',
  'Name the programme, year, campus or hostel: “BE COE fee for 2026-27”, not “my fee”.',
  'Follow-up questions work: “and for girls?” after a hostel fee answer.',
  'English or Hinglish are both fine.',
  'Add your campus, programme and year in Settings for more relevant answers.',
  'Always check important details with the linked source.',
];

function TopicCard({ topic, index, alone, onPick }) {
  const spec = TOPICS[topic.category] || { icon: CircleHelp, examples: [] };
  const Icon = spec.icon;
  return (
    <li
      style={{ '--i': index }}
      className={cn(
        // icon-nudge: hovering anywhere on the card animates its topic icon.
        'group/topic icon-nudge flex flex-col rounded-2xl border bg-card p-5 shadow-soft transition-[border-color,box-shadow,translate] duration-200 hover:-translate-y-0.5 hover:border-primary/40 hover:shadow-lift',
        // An odd one out sits centred under the others instead of hugging the left.
        alone && 'sm:col-span-2 sm:mx-auto sm:w-[calc(50%-0.5rem)]',
      )}
    >
      <div className="flex items-start gap-3.5">
        <span className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-accent text-accent-foreground transition-colors duration-200 group-hover/topic:bg-primary group-hover/topic:text-primary-foreground">
          <Icon className="size-[18px]" aria-hidden="true" />
        </span>
        <div className="min-w-0">
          <h3 className="text-heading">{topic.label}</h3>
          <p className="text-xs text-muted-foreground">
            {formatNumber(topic.documents)} document{topic.documents === 1 ? '' : 's'}
            {topic.updated_at ? ` · updated ${formatDate(topic.updated_at)}` : ''}
          </p>
        </div>
      </div>
      {spec.examples.length ? (
        <div className="mt-4 flex flex-1 flex-col gap-2">
          {spec.examples.map((example) => (
            <button
              key={example}
              type="button"
              onClick={() => onPick(example)}
              className="group/example flex items-center justify-between gap-3 rounded-xl border border-transparent bg-field px-3.5 py-2.5 text-left text-sm transition-[background-color,border-color,color,box-shadow] duration-200 outline-none hover:border-primary/40 hover:bg-primary/15 hover:text-accent-foreground focus-visible:border-primary/40 focus-visible:bg-primary/15 focus-visible:ring-2 focus-visible:ring-ring/50"
            >
              <span>{example}</span>
              <ArrowUpRight
                className="size-4 shrink-0 text-muted-foreground opacity-0 transition-opacity duration-150 group-hover/example:text-primary group-hover/example:opacity-100 group-focus-visible/example:opacity-100 dark:group-hover/example:text-accent-foreground"
                aria-hidden="true"
              />
            </button>
          ))}
        </div>
      ) : null}
    </li>
  );
}

export default function HelpPage() {
  const navigate = useNavigate();
  const { data: config } = useAppConfig();
  const coverage = useQuery({ queryKey: chatKeys.coverage, queryFn: ({ signal }) => getCoverage({ signal }), staleTime: 300_000 });
  // The question goes into the box on a new chat; the student sends it.
  const pick = (question) => navigate('/chat/', { state: { draft: question } });

  return (
    <div className="page-wide space-y-2">
      <PageHeader
        title="What can I ask?"
        description="Answers come from official Thapar Institute documents, with a link to each source."
      />

      <div>
        <SplitSection
          icon={BookOpen}
          title="Topics I can answer"
          description={`${
            coverage.data
              ? `From ${formatNumber(coverage.data.total_documents)} official document${coverage.data.total_documents === 1 ? '' : 's'}. `
              : ''
          }Pick an example to start a chat with it.`}
          bare
        >
          {coverage.isPending ? (
            <div className="grid gap-4 sm:grid-cols-2" aria-hidden="true">
              {[0, 1, 2, 3].map((item) => (
                <Skeleton key={item} className="h-40 rounded-xl" />
              ))}
            </div>
          ) : coverage.isError ? (
            <p className="text-sm text-muted-foreground">The topic list couldn’t be loaded. You can still ask any question about the institute.</p>
          ) : (
            <ul className="stagger grid gap-4 sm:grid-cols-2">
              {coverage.data.categories.map((topic, index, all) => (
                <TopicCard
                  key={topic.category}
                  topic={topic}
                  index={index}
                  alone={all.length % 2 === 1 && index === all.length - 1}
                  onPick={pick}
                />
              ))}
            </ul>
          )}
        </SplitSection>

        <SplitSection icon={XCircle} tone="danger" title="What I can’t help with" description="Some things only an office or Webkiosk can answer.">
          {NOT_COVERED.map((item) => (
            <div key={item.title} className="px-5 py-4 transition-colors hover:bg-hover sm:px-6">
              <p className="text-sm font-semibold">{item.title}</p>
              <p className="mt-0.5 text-sm text-muted-foreground">{item.text}</p>
              {item.link ? (
                <a
                  href={item.link.href}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="mt-1 inline-flex items-center gap-1 text-sm font-medium text-primary hover:underline dark:text-accent-foreground"
                >
                  {item.link.label} <ExternalLink className="size-3" aria-hidden="true" />
                </a>
              ) : null}
            </div>
          ))}
        </SplitSection>

        <SplitSection icon={Lightbulb} title="Tips for better answers" description="Small changes that make answers more precise.">
          {TIPS.map((tip) => (
            <div key={tip} className="flex gap-3 px-5 py-3.5 text-sm transition-colors hover:bg-hover sm:px-6">
              <Check className="mt-0.5 size-4 shrink-0 text-success" aria-hidden="true" />
              <span>{tip}</span>
            </div>
          ))}
        </SplitSection>
      </div>

      <p className="text-center text-sm text-muted-foreground">
        {typeof config?.remaining_today === 'number'
          ? `You have ${config.remaining_today} question${config.remaining_today === 1 ? '' : 's'} left today. `
          : ''}
        Chats you don’t use for 180 days are deleted.{' '}
        <Link to="/privacy" className="text-primary hover:underline dark:text-accent-foreground">
          How your data is handled
        </Link>
      </p>
    </div>
  );
}
