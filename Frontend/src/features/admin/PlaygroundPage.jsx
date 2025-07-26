import { useMutation } from '@tanstack/react-query';
import {
  BookOpen,
  Brain,
  ChevronDown,
  FlaskConical,
  ListOrdered,
  Loader2,
  MessageSquareText,
  Play,
  ShieldAlert,
  ShieldCheck,
  Timer,
} from 'lucide-react';
import { useState } from 'react';
import { Link, useLocation } from 'react-router-dom';

import { PageHeader } from '@/components/layout/PageHeader';
import { SplitSection } from '@/components/split-section';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Textarea } from '@/components/ui/textarea';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { EmptyState, ErrorState } from '@/features/admin/components';
import { ANSWER_TYPES } from '@/features/admin/constants';
import Markdown from '@/features/chat/Markdown';
import { runPlayground } from '@/lib/api/admin';
import { formatMs, formatNumber } from '@/lib/format';
import { cn } from '@/lib/utils';

// Stage names from rag/pipeline.py (`timer.lap`).
const TIMING_LABELS = {
  cache: 'Cache lookup',
  analysis: 'Understanding',
  embedding: 'Embedding',
  retrieval: 'Search',
  rerank: 'Rerank',
  generation: 'Writing',
};

function Timings({ timings }) {
  const total = timings.total || Object.values(timings).reduce((sum, value) => sum + value, 0);
  const parts = Object.entries(timings).filter(([name]) => name !== 'total');
  return (
    <div className="space-y-3">
      <div className="flex h-2.5 overflow-hidden rounded-full bg-muted" aria-hidden="true">
        {parts.map(([name, value], index) => (
          <span
            key={name}
            className="h-full bg-chart-1 first:rounded-l-full last:rounded-r-full"
            style={{ width: `${(value / total) * 100}%`, opacity: 1 - index * 0.14, marginRight: index < parts.length - 1 ? 2 : 0 }}
          />
        ))}
      </div>
      <dl className="grid grid-cols-2 gap-x-4 gap-y-1.5 text-sm sm:grid-cols-3">
        {parts.map(([name, value]) => (
          <div key={name} className="flex justify-between gap-2">
            <dt className="text-muted-foreground">{TIMING_LABELS[name] || name}</dt>
            <dd className="font-medium tabular-nums">{formatMs(value)}</dd>
          </div>
        ))}
        <div className="flex justify-between gap-2">
          <dt className="font-medium">Total</dt>
          <dd className="font-semibold tabular-nums">{formatMs(total)}</dd>
        </div>
      </dl>
    </div>
  );
}

function Analysis({ analysis }) {
  const rows = [
    ['Intent', analysis.intent],
    ['Standalone question', analysis.standalone_query],
    ['Other phrasings', analysis.alternate_queries?.join(' · ')],
    ['Keywords', analysis.keywords?.join(', ')],
    ['Categories', analysis.categories?.join(', ')],
    ['Academic year', analysis.academic_year],
    ['Needs current info', analysis.needs_current === undefined ? null : analysis.needs_current ? 'Yes' : 'No'],
    ['Language', analysis.language],
  ].filter(([, value]) => value);
  return (
    <dl className="divide-y text-sm">
      {rows.map(([label, value]) => (
        <div key={label} className="grid gap-1 px-5 py-2.5 sm:grid-cols-[10rem_1fr]">
          <dt className="text-muted-foreground">{label}</dt>
          <dd className="break-words">{value}</dd>
        </div>
      ))}
      {analysis.fallback ? (
        <p className="px-5 py-2.5 text-xs text-warning">Analysis fell back to the raw question (the model call failed).</p>
      ) : null}
    </dl>
  );
}

function SourceRow({ source }) {
  const [open, setOpen] = useState(false);
  return (
    <li className="px-5 py-3">
      <button type="button" onClick={() => setOpen((value) => !value)} aria-expanded={open} className="flex w-full items-start gap-3 text-left outline-none">
        <span
          className={cn(
            'mt-0.5 flex size-6 shrink-0 items-center justify-center rounded-md text-[11px] font-semibold tabular-nums',
            source.cited ? 'bg-primary text-primary-foreground' : 'bg-muted text-muted-foreground',
          )}
        >
          {source.position}
        </span>
        <span className="min-w-0 flex-1">
          <span className="block text-sm font-medium">{source.title}</span>
          <span className="mt-0.5 block text-xs text-muted-foreground">
            {[source.heading_path, source.academic_year, `score ${source.score.toFixed(3)}`, source.cited ? 'cited' : 'not cited', source.is_current ? null : 'superseded']
              .filter(Boolean)
              .join(' · ')}
          </span>
        </span>
        <ChevronDown className={cn('mt-1 size-4 shrink-0 text-muted-foreground transition-transform', open && 'rotate-180')} aria-hidden="true" />
      </button>
      {open ? (
        <div className="mt-3 ml-9 space-y-2">
          <p className="max-h-72 overflow-y-auto rounded-lg bg-muted p-3 text-[13px] leading-relaxed whitespace-pre-wrap">{source.content}</p>
          <Link to={`/admin/documents/${source.document_id}`} className="text-xs font-medium text-primary hover:underline dark:text-accent-foreground">
            Open document
          </Link>
        </div>
      ) : null}
    </li>
  );
}

function Candidates({ retrieval }) {
  const lists = retrieval?.lists || {};
  const candidates = retrieval?.candidates || [];
  const listNames = Object.keys(lists);
  return (
    <>
      <p className="border-b px-5 py-3 text-xs text-muted-foreground">
        {listNames.map((name) => `${name}: ${formatNumber(lists[name])}`).join(' · ') || 'No ranked lists'}
      </p>
      <Table>
        <TableHeader>
          <TableRow className="hover:bg-transparent">
            <TableHead>#</TableHead>
            <TableHead>Passage</TableHead>
            <TableHead className="text-right">Ranks</TableHead>
            <TableHead className="text-right">Fused</TableHead>
            <TableHead className="text-right">Boost</TableHead>
            <TableHead className="text-right">Rerank</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {candidates.map((candidate, index) => (
            <TableRow key={candidate.chunk_id}>
              <TableCell className="text-muted-foreground tabular-nums">{index + 1}</TableCell>
              <TableCell className="max-w-[20rem]">
                <p className="truncate font-medium">{candidate.title}</p>
                {candidate.heading_path ? <p className="truncate text-xs text-muted-foreground">{candidate.heading_path}</p> : null}
              </TableCell>
              <TableCell className="text-right text-xs whitespace-nowrap text-muted-foreground tabular-nums">
                {Object.entries(candidate.ranks || {})
                  .map(([name, rank]) => `${name} ${rank}`)
                  .join(' · ') || '—'}
              </TableCell>
              <TableCell className="text-right tabular-nums">{candidate.fused?.toFixed(4)}</TableCell>
              <TableCell className="text-right tabular-nums">{candidate.boost ? candidate.boost.toFixed(4) : '—'}</TableCell>
              <TableCell className="text-right tabular-nums">{candidate.rerank ?? '—'}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </>
  );
}

export default function PlaygroundPage() {
  const location = useLocation();
  // The gaps page can hand over a question to test.
  const [query, setQuery] = useState(location.state?.query || '');
  const [rerank, setRerank] = useState('default');
  const run = useMutation({
    mutationFn: () =>
      runPlayground({ query: query.trim(), ...(rerank === 'default' ? {} : { rerank: rerank === 'on' }) }),
  });
  const result = run.data;

  return (
    <div className="page-wide space-y-6">
      <PageHeader
        title="Playground"
        description="See every step of an answer. Nothing is saved; AI calls count toward the daily budget."
      />

      <SplitSection
        icon={FlaskConical}
        title="Question"
        description="Runs the full answer pipeline. Nothing is saved; AI calls count toward the daily budget."
        flush
      >
        <form
          className="grid gap-4 p-5 sm:p-6"
          onSubmit={(event) => {
            event.preventDefault();
            if (query.trim()) run.mutate();
          }}
        >
          <div className="grid content-start gap-2">
            <Label htmlFor="playground-query">Question</Label>
            <Textarea
              id="playground-query"
              className="min-h-20"
              maxLength={2000}
              placeholder="What is the hostel fee for first-year girls?"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Enter' && (event.ctrlKey || event.metaKey) && query.trim()) run.mutate();
              }}
            />
          </div>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <span className="text-sm text-muted-foreground" id="rerank-label">
                Rerank
              </span>
              <Tabs value={rerank} onValueChange={setRerank}>
                <TabsList aria-labelledby="rerank-label">
                  <TabsTrigger value="default">Setting</TabsTrigger>
                  <TabsTrigger value="on">On</TabsTrigger>
                  <TabsTrigger value="off">Off</TabsTrigger>
                </TabsList>
              </Tabs>
            </div>
            <Tooltip>
              <TooltipTrigger asChild>
                <Button type="submit" disabled={!query.trim() || run.isPending}>
                  <Play /> {run.isPending ? 'Running…' : 'Run'}
                </Button>
              </TooltipTrigger>
              <TooltipContent>Ctrl+Enter</TooltipContent>
            </Tooltip>
          </div>
        </form>
      </SplitSection>

      {run.isError ? <ErrorState error={run.error} onRetry={() => run.mutate()} /> : null}

      {run.isPending ? (
        <SplitSection icon={Loader2} title="Running" description="Searching, reading and writing." flush>
          <div className="flex items-center gap-3 px-5 py-10 text-sm text-muted-foreground" role="status">
            <span className="relative flex size-2.5">
              <span className="absolute inline-flex size-full animate-ping rounded-full bg-primary/50" />
              <span className="relative inline-flex size-2.5 rounded-full bg-primary" />
            </span>
            Running the pipeline. This usually takes 5–15 seconds.
          </div>
        </SplitSection>
      ) : null}

      {!result && !run.isPending && !run.isError ? (
        <SplitSection icon={MessageSquareText} title="Answer" description="The answer, its timings and every search step appear here." flush>
          <EmptyState icon={FlaskConical} title="Try a question">
            Use it to see why an answer went wrong: what was searched, which passages ranked, and what the model wrote.
          </EmptyState>
        </SplitSection>
      ) : null}

      {result && !run.isPending ? (
        <div>
          <SplitSection
            icon={MessageSquareText}
            title="Answer"
            description="What the student would see, and whether every claim was found in the sources."
            actions={
              <>
                <Badge variant="secondary">{ANSWER_TYPES[result.answer_type] || result.answer_type}</Badge>
                {result.grounded === true ? (
                  <Badge variant="outline">
                    <ShieldCheck className="text-success" /> Grounded
                  </Badge>
                ) : result.grounded === false ? (
                  <Badge variant="outline">
                    <ShieldAlert className="text-warning" /> Not grounded
                  </Badge>
                ) : null}
              </>
            }
            flush
          >
            <div className="p-5 sm:p-6">
              <Markdown content={result.answer || '_No answer text._'} />
              {result.unsupported?.length ? (
                <div className="mt-4 rounded-lg border border-warning/30 bg-warning/10 p-3 text-sm">
                  <p className="font-medium">Claims the sources didn’t support</p>
                  <ul className="mt-1 list-disc pl-5 text-muted-foreground">
                    {result.unsupported.map((item) => (
                      <li key={item}>{item}</li>
                    ))}
                  </ul>
                </div>
              ) : null}
            </div>
          </SplitSection>

          <SplitSection
            icon={Timer}
            title="Timing"
            description={`${result.model || 'no model'} · ${formatNumber(result.usage.llm_calls)} AI calls · ${result.reranked ? 'reranked' : 'no rerank'}`}
            flush
          >
            <div className="p-5 sm:p-6">
              <Timings timings={result.timings} />
            </div>
          </SplitSection>

          <SplitSection icon={Brain} title="Understanding" description="How the question was read and rewritten for search." flush>
            <Analysis analysis={result.analysis} />
          </SplitSection>

          <SplitSection icon={BookOpen} title="Sources given to the model" description="Filled numbers were cited in the answer." flush>
            {result.sources.length ? (
              <ul className="divide-y">
                {result.sources.map((source) => (
                  <SourceRow key={source.position} source={source} />
                ))}
              </ul>
            ) : (
              <p className="px-5 py-6 text-sm text-muted-foreground">No sources were used.</p>
            )}
          </SplitSection>

          <SplitSection icon={ListOrdered} title="Search candidates" description="Every passage the hybrid search considered, in fused order." flush>
            <Candidates retrieval={result.retrieval} />
          </SplitSection>
        </div>
      ) : null}
    </div>
  );
}
