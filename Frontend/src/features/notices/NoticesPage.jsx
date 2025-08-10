import { useQuery } from '@tanstack/react-query';
import { AlertTriangle, ExternalLink, FileText, Megaphone, Pin } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { useLocation } from 'react-router-dom';
import { toast } from 'sonner';

import { PageHeader } from '@/components/layout/PageHeader';
import { SplitSection } from '@/components/split-section';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { CATEGORIES, labelOf } from '@/features/admin/constants';
import Markdown from '@/features/chat/Markdown';
import { markNoticesSeen } from '@/features/notices/seen';
import { useAppConfig } from '@/hooks/use-app-config';
import { listNotices, listOfficialNotices, noticeKeys, openOfficialNotice } from '@/lib/api/notices';
import { formatDate, formatRelative } from '@/lib/format';
import { cn } from '@/lib/utils';

// A body longer than this is collapsed to four lines with "Read more".
const LONG_BODY = 280;

/** Pinned first, then important, then newest. */
export function sortNotices(notices) {
  return [...notices].sort(
    (a, b) =>
      Number(b.is_pinned) - Number(a.is_pinned) ||
      Number(b.importance === 'important') - Number(a.importance === 'important') ||
      Date.parse(b.publish_at) - Date.parse(a.publish_at),
  );
}

function isLong(body) {
  return body.length > LONG_BODY || body.split('\n').length > 4;
}

function Loading() {
  return (
    <div className="space-y-3 p-5 sm:p-6" aria-busy="true">
      <Skeleton className="h-4 w-1/3" />
      <Skeleton className="h-4 w-4/5" />
      <Skeleton className="h-4 w-2/3" />
    </div>
  );
}

function LoadError({ what, onRetry }) {
  return (
    <div className="flex items-center justify-between gap-3 p-5 text-sm text-muted-foreground sm:p-6">
      Couldn’t load {what}.
      <Button variant="outline" size="sm" onClick={onRetry}>
        Try again
      </Button>
    </div>
  );
}

function CategoryChips({ categories, value, onChange }) {
  if (categories.length < 2) return null;
  const chips = [{ value: '', label: 'All' }, ...categories.map((category) => ({ value: category, label: labelOf(CATEGORIES, category) }))];
  return (
    <div role="radiogroup" aria-label="Filter by topic" className="flex flex-wrap gap-2 px-5 py-4 sm:px-6">
      {chips.map((chip) => {
        const selected = value === chip.value;
        return (
          <button
            key={chip.value || 'all'}
            type="button"
            role="radio"
            aria-checked={selected}
            onClick={() => onChange(chip.value)}
            className={cn(
              'rounded-full border px-3 py-1 text-xs font-medium transition-colors duration-150 outline-none hover:border-primary/40 hover:bg-hover focus-visible:ring-2 focus-visible:ring-ring/50',
              selected && 'border-primary bg-accent text-accent-foreground hover:bg-accent',
            )}
          >
            {chip.label}
          </button>
        );
      })}
    </div>
  );
}

function NoticeCard({ notice, highlighted }) {
  const long = isLong(notice.body || '');
  const [expanded, setExpanded] = useState(highlighted);
  const important = notice.importance === 'important';
  return (
    <li
      id={`notice-${notice.id}`}
      className={cn('scroll-mt-24 px-5 py-5 sm:px-6', important && 'bg-destructive/[0.04]', highlighted && 'animate-rise')}
    >
      <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
        {notice.is_pinned ? (
          <span className="inline-flex items-center gap-1 font-medium text-foreground">
            <Pin className="size-3.5 text-gold" aria-hidden="true" /> Pinned
          </span>
        ) : null}
        {important ? (
          <Badge variant="destructive">
            <AlertTriangle aria-hidden="true" /> Important
          </Badge>
        ) : null}
        <Badge variant="brand">{labelOf(CATEGORIES, notice.category)}</Badge>
        <time dateTime={notice.publish_at} title={formatDate(notice.publish_at)}>
          {formatRelative(notice.publish_at)}
        </time>
        {notice.expires_at ? <span>· until {formatDate(notice.expires_at, { day: 'numeric', month: 'short' })}</span> : null}
      </div>
      <h3 className="mt-2 text-base font-semibold leading-snug">{notice.title}</h3>
      {notice.body ? (
        <div className="mt-1.5">
          <Markdown content={notice.body} className={cn('text-sm', long && !expanded && 'line-clamp-4')} />
          {long ? (
            <button
              type="button"
              onClick={() => setExpanded((value) => !value)}
              aria-expanded={expanded}
              className="mt-1 rounded text-sm font-medium text-primary outline-none hover:underline focus-visible:ring-2 focus-visible:ring-ring/50"
            >
              {expanded ? 'Show less' : 'Read more'}
            </button>
          ) : null}
        </div>
      ) : null}
      {notice.link_url ? (
        <a
          href={notice.link_url}
          target="_blank"
          rel="noopener noreferrer nofollow"
          className="mt-3 inline-flex items-center gap-1.5 rounded text-sm font-medium text-primary outline-none hover:underline focus-visible:ring-2 focus-visible:ring-ring/50"
        >
          Read the official notice <ExternalLink className="size-3.5" aria-hidden="true" />
        </a>
      ) : null}
    </li>
  );
}

function PostedNotices({ highlight }) {
  const [category, setCategory] = useState('');
  const { data, isPending, isError, refetch } = useQuery({
    queryKey: noticeKeys.list(),
    queryFn: ({ signal }) => listNotices({}, { signal }),
  });
  const notices = useMemo(() => sortNotices(data?.results || []), [data]);
  const categories = useMemo(() => [...new Set(notices.map((notice) => notice.category))], [notices]);
  const shown = category ? notices.filter((notice) => notice.category === category) : notices;

  useEffect(() => {
    if (!highlight || !data) return;
    document.getElementById(`notice-${highlight}`)?.scrollIntoView({ block: 'start' });
  }, [highlight, data]);

  return (
    <SplitSection icon={Megaphone} title="Notices" description="Deadlines, exam dates, hostel updates and new rules, posted by the team.">
      {isPending ? (
        <Loading />
      ) : isError ? (
        <LoadError what="notices" onRetry={() => refetch()} />
      ) : notices.length === 0 ? (
        <p className="p-5 text-sm text-muted-foreground sm:p-6">No notices right now. New ones will show up here.</p>
      ) : (
        <>
          <CategoryChips categories={categories} value={category} onChange={setCategory} />
          <ul className="divide-y">
            {shown.map((notice) => (
              <NoticeCard key={notice.id} notice={notice} highlighted={notice.id === highlight} />
            ))}
          </ul>
        </>
      )}
    </SplitSection>
  );
}

function isWebUrl(url) {
  try {
    return new URL(url).protocol === 'https:';
  } catch {
    return false;
  }
}

async function openDocument(document) {
  if (document.source_url && isWebUrl(document.source_url)) {
    window.open(document.source_url, '_blank', 'noopener,noreferrer');
    return;
  }
  // Open the tab synchronously so popup blockers allow it, then point it at the signed URL.
  const tab = window.open('about:blank', '_blank');
  if (tab) tab.opener = null;
  try {
    const { url } = await openOfficialNotice(document.id);
    if (!isWebUrl(url)) throw new Error('Unexpected link.');
    if (tab) tab.location.href = url;
    else window.open(url, '_blank', 'noopener,noreferrer');
  } catch (error) {
    tab?.close();
    toast.error('Couldn’t open the document', { description: error.message });
  }
}

function OfficialDocuments() {
  const { data, isPending, isError, refetch } = useQuery({
    queryKey: noticeKeys.official,
    queryFn: ({ signal }) => listOfficialNotices({}, { signal }),
  });
  const documents = data?.results || [];
  return (
    <SplitSection
      icon={FileText}
      title="New official documents"
      description="Official notices added to ThaparGenie in the last 30 days. You can also ask about them."
      flush
    >
      {isPending ? (
        <Loading />
      ) : isError ? (
        <LoadError what="documents" onRetry={() => refetch()} />
      ) : documents.length === 0 ? (
        <p className="p-5 text-sm text-muted-foreground sm:p-6">Nothing new in the last 30 days.</p>
      ) : (
        <ul className="divide-y">
          {documents.map((document) => (
            <li key={document.id}>
              <button
                type="button"
                onClick={() => openDocument(document)}
                className="flex w-full items-center gap-3 px-5 py-3.5 text-left transition-colors duration-150 outline-none hover:bg-hover focus-visible:bg-hover sm:px-6"
              >
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm font-medium">{document.title}</span>
                  <span className="block text-xs text-muted-foreground">Added {formatRelative(document.processed_at)}</span>
                </span>
                <ExternalLink className="size-4 shrink-0 text-muted-foreground" aria-label="Open" />
              </button>
            </li>
          ))}
        </ul>
      )}
    </SplitSection>
  );
}

export default function NoticesPage() {
  const { data: config } = useAppConfig();
  const { hash } = useLocation();
  const highlight = hash.startsWith('#notice-') ? hash.slice('#notice-'.length) : null;
  const latest = config?.latest_notice_at;

  // Visiting the page clears the sidebar dot, up to the newest notice there is.
  useEffect(() => {
    if (config) markNoticesSeen(latest);
  }, [config, latest]);

  return (
    <div className="page-wide space-y-6">
      <PageHeader title="Notices" description="What changed recently at TIET, in one place." />
      <div>
        <PostedNotices highlight={highlight} />
        <OfficialDocuments />
      </div>
    </div>
  );
}
