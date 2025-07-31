import { FileText, Globe } from 'lucide-react';
import { useState } from 'react';
import { toast } from 'sonner';

import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { formatSourceDate } from '@/features/chat/freshness';
import { openSource } from '@/lib/api/chat';

function sourceLocation(source) {
  const parts = [];
  if (source.heading_path) parts.push(source.heading_path);
  if (source.page_start) {
    parts.push(
      source.page_end && source.page_end !== source.page_start
        ? `pp. ${source.page_start}–${source.page_end}`
        : `p. ${source.page_start}`,
    );
  }
  return parts.join(' · ');
}

function isWebUrl(url) {
  try {
    return ['http:', 'https:'].includes(new URL(url).protocol);
  } catch {
    return false;
  }
}

/** Public pages open directly; stored files need a short-lived signed link from the API. */
async function openSourceInNewTab(source) {
  if (source.url && isWebUrl(source.url)) {
    window.open(source.url, '_blank', 'noopener,noreferrer');
    return;
  }
  if (!source.source_id) {
    toast('The source will be available when the answer finishes.');
    return;
  }
  // Open the tab synchronously so popup blockers allow it, then point it at the signed URL.
  const tab = window.open('about:blank', '_blank');
  if (tab) tab.opener = null;
  try {
    const { url } = await openSource(source.source_id);
    if (!isWebUrl(url)) throw new Error('Unexpected link.');
    if (tab) tab.location.href = url;
    else window.open(url, '_blank', 'noopener,noreferrer');
  } catch (error) {
    tab?.close();
    toast.error('Couldn’t open the source', { description: error.message });
  }
}

export function CitationChip({ position, source }) {
  const chip = (
    <button
      type="button"
      onClick={() => source && openSourceInNewTab(source)}
      disabled={!source}
      aria-label={source ? `Source ${position}: ${source.title}` : `Source ${position}`}
      className="mx-0.5 inline-flex h-[1.3rem] min-w-[1.3rem] -translate-y-px items-center justify-center rounded-md bg-accent px-1 align-middle text-[0.7rem] font-semibold text-accent-foreground tabular-nums transition-colors outline-none hover:bg-primary hover:text-primary-foreground focus-visible:ring-2 focus-visible:ring-ring/50 disabled:opacity-60"
    >
      {position}
    </button>
  );
  if (!source) return chip;
  return (
    <Tooltip>
      <TooltipTrigger asChild>{chip}</TooltipTrigger>
      <TooltipContent className="max-w-xs">
        <p className="font-semibold">{source.title}</p>
        {sourceLocation(source) ? <p className="mt-0.5 font-normal opacity-80">{sourceLocation(source)}</p> : null}
      </TooltipContent>
    </Tooltip>
  );
}

function hostOf(url) {
  try {
    return new URL(url).hostname.replace(/^www\./, '');
  } catch {
    return '';
  }
}

/** One source as a compact link pill; details are in its tooltip. */
function SourceLink({ source }) {
  const web = source.url && isWebUrl(source.url);
  const Icon = web ? Globe : FileText;
  const details = [
    web ? hostOf(source.url) : null,
    sourceLocation(source) || null,
    source.academic_year || null,
    formatSourceDate(source.effective_date) || null,
  ].filter(Boolean);
  const className =
    // Fills with the brand colour on hover or keyboard focus; its parts turn white with it.
    'group/source inline-flex h-7 max-w-full items-center gap-1.5 rounded-full border bg-card px-2.5 text-xs text-foreground/85 shadow-xs transition-[background-color,border-color,color,box-shadow] duration-200 outline-none hover:border-primary hover:bg-primary hover:text-primary-foreground hover:shadow-soft focus-visible:border-primary focus-visible:bg-primary focus-visible:text-primary-foreground focus-visible:ring-2 focus-visible:ring-ring/50';
  const content = (
    <>
      <span className="text-[0.7rem] font-semibold text-primary tabular-nums transition-colors duration-200 group-hover/source:text-primary-foreground group-focus-visible/source:text-primary-foreground dark:text-accent-foreground dark:group-hover/source:text-primary-foreground dark:group-focus-visible/source:text-primary-foreground">
        {source.position}
      </span>
      <Icon
        className="size-3 shrink-0 text-muted-foreground transition-colors duration-200 group-hover/source:text-primary-foreground group-focus-visible/source:text-primary-foreground"
        aria-hidden="true"
      />
      <span className="max-w-[14rem] truncate">{source.title}</span>
      {source.is_current === false ? (
        <span className="shrink-0 font-medium text-warning group-hover/source:text-primary-foreground group-focus-visible/source:text-primary-foreground">· Not current</span>
      ) : null}
    </>
  );
  const link = web ? (
    <a href={source.url} target="_blank" rel="noopener noreferrer" className={className}>
      {content}
    </a>
  ) : (
    <button type="button" onClick={() => openSourceInNewTab(source)} className={className}>
      {content}
    </button>
  );
  return (
    <li className="max-w-full">
      <Tooltip>
        <TooltipTrigger asChild>{link}</TooltipTrigger>
        <TooltipContent className="max-w-xs">
          <p className="font-semibold">{source.title}</p>
          {details.length ? <p className="mt-0.5 font-normal opacity-80">{details.join(' · ')}</p> : null}
        </TooltipContent>
      </Tooltip>
    </li>
  );
}

const VISIBLE_SOURCES = 4;

export function SourceList({ sources }) {
  const [expanded, setExpanded] = useState(false);
  if (!sources?.length) return null;

  // Sources the answer actually cited come first; the rest were read but not used.
  const cited = sources.filter((source) => source.cited);
  const all = cited.length ? cited : sources;
  const shown = expanded ? all : all.slice(0, VISIBLE_SOURCES);
  const hidden = all.length - shown.length;

  return (
    <ul aria-label="Sources" className="mt-3 flex animate-fade-in flex-wrap items-center gap-1.5">
      {shown.map((source) => (
        <SourceLink key={source.source_id || source.position} source={source} />
      ))}
      {hidden > 0 ? (
        <li>
          <button
            type="button"
            onClick={() => setExpanded(true)}
            className="inline-flex h-7 items-center rounded-full px-2 text-xs font-medium text-muted-foreground transition-colors outline-none hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring/50"
          >
            +{hidden} more
          </button>
        </li>
      ) : null}
    </ul>
  );
}
