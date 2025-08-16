import { useQuery } from '@tanstack/react-query';
import {
  ArrowRight,
  BarChart3,
  CalendarClock,
  CheckCircle2,
  Database,
  Gauge,
  MessageSquareText,
  SearchX,
  ThumbsUp,
  Timer,
  Zap,
} from 'lucide-react';
import { useState } from 'react';
import { Link } from 'react-router-dom';

import { PageHeader } from '@/components/layout/PageHeader';
import ExportCsvButton from '@/features/admin/ExportCsvButton';
import QualitySection from '@/features/admin/QualitySection';
import { SplitSection } from '@/components/split-section';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { BarList, ColumnChart, Meter } from '@/features/admin/charts';
import { EmptyState, ErrorState } from '@/features/admin/components';
import { ANSWER_TYPES } from '@/features/admin/constants';
import { adminKeys, exportStatsCsv, getStats, listGaps } from '@/lib/api/admin';
import { formatBytes, formatCompact, formatDate, formatMs, formatNumber, formatPercent, formatRelative } from '@/lib/format';

/** One figure in the "At a glance" strip. */
function StatTile({ icon: Icon, label, value, hint }) {
  return (
    <div className="flex min-w-0 flex-col p-5 sm:p-6">
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <Icon className="size-4 shrink-0" aria-hidden="true" />
        <span className="truncate">{label}</span>
      </div>
      <p className="mt-3 text-metric tabular-nums">{value}</p>
      {hint ? <p className="mt-1.5 text-xs leading-relaxed text-muted-foreground">{hint}</p> : null}
    </div>
  );
}

function SectionLink({ to, children }) {
  return (
    <Button asChild variant="outline" size="sm">
      <Link to={to}>
        {children} <ArrowRight aria-hidden="true" />
      </Link>
    </Button>
  );
}

function Figure({ label, value, large }) {
  return (
    <div className="min-w-0">
      <dt className="text-sm text-muted-foreground">{label}</dt>
      <dd className={large ? 'mt-1 text-metric tabular-nums' : 'mt-1 text-base font-semibold tabular-nums'}>{value}</dd>
    </div>
  );
}

function OverviewSkeleton() {
  return (
    <div className="space-y-8 pt-2" aria-busy="true" aria-label="Loading statistics">
      {[0, 1].map((item) => (
        <div key={item} className="grid gap-4 lg:grid-cols-[16rem_minmax(0,1fr)] lg:gap-10">
          <div className="space-y-3">
            <Skeleton className="size-10 rounded-xl" />
            <Skeleton className="h-4 w-32" />
            <Skeleton className="h-3 w-48" />
          </div>
          <Skeleton className="h-44 rounded-2xl" />
        </div>
      ))}
    </div>
  );
}

export function summarize(stats) {
  const types = stats.answer_types || {};
  const answered = (types.answered || 0) + (types.cached || 0);
  const judged = answered + (types.no_answer || 0);
  const { up = 0, down = 0 } = stats.feedback || {};
  return {
    answeredRate: judged ? answered / judged : null,
    satisfaction: up + down ? up / (up + down) : null,
    ratings: up + down,
  };
}

export default function OverviewPage() {
  const [range, setRange] = useState('7d');
  const stats = useQuery({ queryKey: adminKeys.stats(range), queryFn: () => getStats(range), refetchInterval: 60_000 });
  const gaps = useQuery({ queryKey: adminKeys.gaps('30d'), queryFn: () => listGaps('30d') });

  const header = (
    <PageHeader
      title="Overview"
      description="Questions, answer quality, speed and the knowledge base."
      actions={
        <>
          <ExportCsvButton request={() => exportStatsCsv(range)} fallbackName="thapargenie-stats.csv" label="Export daily stats" />
          <Tabs value={range} onValueChange={setRange}>
            <TabsList aria-label="Time range">
              <TabsTrigger value="7d">7 days</TabsTrigger>
              <TabsTrigger value="30d">30 days</TabsTrigger>
            </TabsList>
          </Tabs>
        </>
      }
    />
  );

  if (stats.isPending) {
    return (
      <div className="page-wide space-y-6">
        {header}
        <OverviewSkeleton />
      </div>
    );
  }
  if (stats.isError) {
    return (
      <div className="page-wide space-y-6">
        {header}
        <ErrorState error={stats.error} onRetry={() => stats.refetch()} />
      </div>
    );
  }

  const data = stats.data;
  const { answeredRate, satisfaction, ratings } = summarize(data);
  const daily = data.daily.map((day) => ({
    label: formatDate(day.day, { weekday: 'short', day: 'numeric', month: 'short' }),
    shortLabel: formatDate(day.day, { day: 'numeric', month: 'short' }),
    value: day.questions,
    detail: `${formatNumber(day.cached)} from cache`,
  }));
  const typeRows = Object.entries(data.answer_types)
    .map(([type, value]) => ({ label: ANSWER_TYPES[type] || type, value }))
    .sort((a, b) => b.value - a.value);
  const typeTotal = typeRows.reduce((sum, row) => sum + row.value, 0);
  const knowledge = data.knowledge;
  const docsByStatus = knowledge.documents_by_status || {};
  const totalDocs = Object.values(docsByStatus).reduce((sum, value) => sum + value, 0);
  const busy = (docsByStatus.queued || 0) + (docsByStatus.processing || 0);

  return (
    <div className="page-wide space-y-2">
      {header}

      <div>
        <SplitSection icon={Gauge} title="At a glance" description={`The last ${data.range_days} days. Refreshes every minute.`} flush>
          <div className="stagger grid grid-cols-2 divide-border xl:grid-cols-4 [&>*]:border-border max-xl:[&>*:nth-child(-n+2)]:border-b max-xl:[&>*:nth-child(odd)]:border-r xl:[&>*:not(:last-child)]:border-r">
            <StatTile
              icon={MessageSquareText}
              label="Questions"
              value={formatCompact(data.totals.questions)}
              hint={`${formatNumber(data.totals.answers)} answers`}
            />
            <StatTile
              icon={CheckCircle2}
              label="Answered"
              value={formatPercent(answeredRate)}
              hint={`${formatNumber(data.answer_types.no_answer || 0)} not found in the knowledge base`}
            />
            <StatTile
              icon={ThumbsUp}
              label="Helpful"
              value={formatPercent(satisfaction)}
              hint={ratings ? `${formatNumber(ratings)} ratings · ${formatNumber(data.feedback.open_reviews)} to review` : 'No ratings yet'}
            />
            <StatTile
              icon={Timer}
              label="Answer time (p50)"
              value={formatMs(data.latency.uncached_p50_ms)}
              hint={`p95 ${formatMs(data.latency.uncached_p95_ms)} · cached ${formatMs(data.latency.p50_ms)}`}
            />
          </div>
        </SplitSection>

        <QualitySection quality={data.quality} />

        <SplitSection icon={BarChart3} title="Activity" description="Questions per day, and how each answer ended." flush>
          <div className="px-5 pt-6 pb-5 sm:px-6">
            <h3 className="mb-6 text-sm font-semibold">Questions per day</h3>
            {data.totals.questions ? (
              <ColumnChart data={daily} title="Questions per day" valueLabel="Questions" />
            ) : (
              <EmptyState icon={MessageSquareText} title="No questions yet">
                Activity appears here as students start asking.
              </EmptyState>
            )}
          </div>
          <div className="border-t px-5 py-5 sm:px-6">
            <h3 className="mb-4 text-sm font-semibold">Answer outcomes</h3>
            {typeRows.length ? (
              <BarList data={typeRows} total={typeTotal} />
            ) : (
              <p className="text-sm text-muted-foreground">No answers in this period.</p>
            )}
          </div>
        </SplitSection>

        <SplitSection icon={Zap} title="Usage today" description="AI calls against the daily budget. Asking pauses for everyone when it runs out." flush>
          <div className="space-y-6 px-5 py-5 sm:px-6">
            <div>
              <div className="mb-2.5 flex items-baseline justify-between text-sm">
                <span className="font-semibold">AI calls</span>
                <span className="font-medium tabular-nums">
                  {formatNumber(data.budget.llm_calls_today)}{' '}
                  <span className="text-muted-foreground">/ {formatNumber(data.budget.global_daily_llm_calls)}</span>
                </span>
              </div>
              <Meter value={data.budget.llm_calls_today} max={data.budget.global_daily_llm_calls} label="AI calls used today" />
            </div>
            <dl className="grid grid-cols-2 gap-6">
              <Figure label="Cache hit rate" value={formatPercent(data.cache_hit_rate)} />
              <Figure label="Database size" value={formatBytes(data.database_bytes)} />
            </dl>
          </div>
        </SplitSection>

        <SplitSection
          icon={Database}
          title="Knowledge base"
          description={busy ? `${busy} document${busy === 1 ? '' : 's'} processing right now.` : 'Every document is processed.'}
          actions={<SectionLink to="/admin/documents">Documents</SectionLink>}
          flush
        >
          <dl className="grid grid-cols-2 gap-6 px-5 py-5 sm:px-6 lg:grid-cols-4">
            <Figure label="Documents" value={formatNumber(totalDocs)} large />
            <Figure label="Searchable passages" value={formatCompact(knowledge.searchable_chunks)} large />
            <Figure label="Failed" value={formatNumber(docsByStatus.failed || 0)} large />
            <Figure label="Cached answers" value={formatNumber(knowledge.cache_entries)} large />
          </dl>
          {knowledge.expiring?.length ? (
            <div className="border-t px-5 py-5 sm:px-6">
              <div className="mb-3 flex items-baseline justify-between gap-3">
                <h3 className="flex items-center gap-1.5 text-sm font-semibold">
                  <CalendarClock className="size-4 text-warning" aria-hidden="true" />
                  Expiring soon
                </h3>
                <Link
                  to="/admin/documents?validity=expiring"
                  className="inline-flex shrink-0 items-center gap-1 text-xs font-medium text-primary hover:underline dark:text-accent-foreground"
                >
                  {knowledge.expiring_soon > knowledge.expiring.length ? `All ${formatNumber(knowledge.expiring_soon)}` : 'View'}
                  <ArrowRight className="size-3" aria-hidden="true" />
                </Link>
              </div>
              <ul className="divide-y rounded-xl border">
                {knowledge.expiring.map((item) => (
                  <li key={item.id} className="flex items-center gap-3 px-3.5 py-2.5 text-sm transition-colors hover:bg-hover">
                    <Link to={`/admin/documents/${item.id}`} className="min-w-0 flex-1 truncate hover:underline" title={item.title}>
                      {item.title}
                    </Link>
                    {/* "T00:00" makes the date local, so it never shows the day before. */}
                    <span className="shrink-0 text-xs text-muted-foreground tabular-nums">{formatDate(`${item.valid_until}T00:00`)}</span>
                  </li>
                ))}
              </ul>
              <p className="mt-2 text-xs text-muted-foreground">Each is marked not current the day after its date.</p>
            </div>
          ) : null}
        </SplitSection>

        <SplitSection
          icon={SearchX}
          title="Knowledge gaps"
          description="Questions nobody got an answer to in the last 30 days."
          actions={<SectionLink to="/admin/gaps">All gaps</SectionLink>}
          flush
        >
          {gaps.data?.results?.length ? (
            <ul className="divide-y">
              {gaps.data.results.slice(0, 5).map((gap) => (
                <li key={gap.query} className="flex items-center gap-3 px-5 py-3.5 text-sm transition-colors hover:bg-hover sm:px-6">
                  <span className="min-w-0 flex-1 truncate" title={gap.query}>
                    {gap.query}
                  </span>
                  <span className="shrink-0 rounded-full bg-muted px-2 py-0.5 text-xs font-medium tabular-nums">{gap.count}×</span>
                  <span className="w-20 shrink-0 text-right text-xs text-muted-foreground">{formatRelative(gap.last_seen)}</span>
                </li>
              ))}
            </ul>
          ) : (
            <EmptyState icon={SearchX} title={gaps.isPending ? 'Loading…' : 'No gaps'}>
              {gaps.isPending ? null : 'Every question in this period found an answer.'}
            </EmptyState>
          )}
        </SplitSection>
      </div>
    </div>
  );
}
