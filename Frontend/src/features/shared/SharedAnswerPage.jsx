import { useQuery } from '@tanstack/react-query';
import { ArrowRight, ExternalLink, Link2Off } from 'lucide-react';
import { useEffect } from 'react';
import { Link, useParams } from 'react-router-dom';

import { Brand, LogoMark } from '@/components/brand/Brand';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import Markdown from '@/features/chat/Markdown';
import { chatKeys, getSharedAnswer } from '@/lib/api/chat';
import { formatDate } from '@/lib/format';

/** Keeps shared links out of search engines (the API also sends X-Robots-Tag). */
function useNoIndex() {
  useEffect(() => {
    const meta = document.createElement('meta');
    meta.name = 'robots';
    meta.content = 'noindex, nofollow';
    document.head.append(meta);
    return () => meta.remove();
  }, []);
}

function Gone() {
  return (
    <div className="flex flex-col items-center gap-3 py-16 text-center">
      <span className="flex size-12 items-center justify-center rounded-2xl bg-muted text-muted-foreground">
        <Link2Off className="size-5" aria-hidden="true" />
      </span>
      <h1 className="text-lg font-semibold">This link has expired or was turned off</h1>
      <p className="max-w-sm text-sm text-muted-foreground">Shared answers work for 7 days. Ask ThaparGenie the question yourself for an up-to-date answer.</p>
    </div>
  );
}

/** Public, read-only view of one shared answer. No sign-in. */
export default function SharedAnswerPage() {
  const { token } = useParams();
  useNoIndex();
  const shared = useQuery({
    queryKey: chatKeys.shared(token),
    queryFn: ({ signal }) => getSharedAnswer(token, { signal }),
    retry: false,
  });
  const data = shared.data;
  const sources = (data?.sources || []).filter((source) => source.cited);

  return (
    <div className="min-h-dvh bg-background">
      <header className="border-b bg-background/80 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-3xl items-center justify-between px-4 sm:px-6">
          <Link to="/chat/" className="rounded-lg outline-none focus-visible:ring-2 focus-visible:ring-ring/50">
            <Brand />
          </Link>
          <Button asChild size="sm">
            <Link to="/login/">
              Ask ThaparGenie yourself <ArrowRight />
            </Link>
          </Button>
        </div>
      </header>

      <main className="mx-auto max-w-3xl px-4 py-8 sm:px-6 sm:py-12">
        {shared.isPending ? (
          <div className="space-y-4" aria-busy="true">
            <Skeleton className="ml-auto h-10 w-2/3 rounded-2xl" />
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-5/6" />
          </div>
        ) : shared.isError ? (
          <div className="py-16 text-center text-sm text-muted-foreground">
            <p>{shared.error.message}</p>
            <Button className="mt-4" variant="outline" onClick={() => shared.refetch()}>
              Try again
            </Button>
          </div>
        ) : !data ? (
          <Gone />
        ) : (
          <article className="space-y-6">
            <p className="text-sm text-muted-foreground">
              A student shared this answer from ThaparGenie on {formatDate(data.created_at, { day: 'numeric', month: 'long', year: 'numeric' })}.
            </p>
            {data.question ? (
              <div className="flex justify-end">
                <p className="max-w-[85%] rounded-2xl rounded-br-md bg-secondary px-4 py-2.5 text-[15px] leading-relaxed break-words whitespace-pre-wrap text-secondary-foreground">
                  {data.question}
                </p>
              </div>
            ) : null}
            <div className="flex gap-3 sm:gap-4">
              <LogoMark className="mt-0.5 size-7 rounded-lg" />
              <div className="min-w-0 flex-1">
                <Markdown content={data.answer} />
                {sources.length ? (
                  <div className="mt-5">
                    <h2 className="text-xs font-semibold tracking-wider text-muted-foreground uppercase">Sources</h2>
                    <ol className="mt-2 space-y-1.5 text-sm">
                      {sources.map((source) => (
                        <li key={source.position} className="flex gap-2">
                          <span className="w-5 shrink-0 text-muted-foreground tabular-nums">{source.position}.</span>
                          {source.url ? (
                            <a
                              href={source.url}
                              target="_blank"
                              rel="noopener noreferrer nofollow"
                              className="inline-flex min-w-0 items-center gap-1 text-primary hover:underline"
                            >
                              <span className="truncate">{source.title}</span>
                              <ExternalLink className="size-3.5 shrink-0" aria-hidden="true" />
                            </a>
                          ) : (
                            <span className="min-w-0 truncate">{source.title}</span>
                          )}
                        </li>
                      ))}
                    </ol>
                  </div>
                ) : null}
              </div>
            </div>
            <p className="border-t pt-4 text-center text-xs text-muted-foreground">
              Answers can be wrong; check the official sources. This link works until{' '}
              {formatDate(data.expires_at, { day: 'numeric', month: 'long' })}.
            </p>
          </article>
        )}
      </main>
    </div>
  );
}
