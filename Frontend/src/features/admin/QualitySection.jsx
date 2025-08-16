import { AlertTriangle, FlaskConical } from 'lucide-react';

import { SplitSection } from '@/components/split-section';
import { EmptyState } from '@/features/admin/components';
import { formatDateTime, formatRelative } from '@/lib/format';
import { cn } from '@/lib/utils';

/** "+0.05", "−0.10" or "no change" between two scores (null without a previous run). */
export function scoreChange(latest, previous) {
  if (latest === null || latest === undefined || previous === null || previous === undefined) return null;
  const delta = Math.round((latest - previous) * 100) / 100;
  if (delta === 0) return { text: 'no change', tone: 'same' };
  return { text: `${delta > 0 ? '+' : '−'}${Math.abs(delta).toFixed(2)}`, tone: delta > 0 ? 'up' : 'down' };
}

function Score({ label, value, previous, target }) {
  const change = scoreChange(value, previous);
  return (
    <div className="min-w-0">
      <dt className="text-sm text-muted-foreground">{label}</dt>
      <dd className="mt-1 flex items-baseline gap-2">
        <span className={cn('text-metric tabular-nums', target !== undefined && value < target && 'text-destructive')}>{value.toFixed(2)}</span>
        {change ? (
          <span
            className={cn(
              'text-xs font-medium tabular-nums',
              change.tone === 'up' && 'text-success',
              change.tone === 'down' && 'text-destructive',
              change.tone === 'same' && 'text-muted-foreground',
            )}
          >
            {change.text}
          </span>
        ) : null}
      </dd>
    </div>
  );
}

/** The nightly search-quality check. */
export default function QualitySection({ quality }) {
  const latest = quality?.latest;
  const previous = quality?.previous;
  const warnings = quality?.warnings || [];
  return (
    <SplitSection
      icon={FlaskConical}
      title="Answer quality"
      description="A nightly check that the right official passage is found for 21 test questions. Target: recall@5 of 0.90 or more."
      flush
    >
      {latest ? (
        <>
          <dl className="grid grid-cols-2 gap-6 px-5 py-5 sm:px-6 lg:grid-cols-4">
            <Score label="Recall@5" value={latest.recall_at_5} previous={previous?.recall_at_5} target={0.9} />
            <Score label="Recall@10" value={latest.recall_at_10} previous={previous?.recall_at_10} />
            <Score label="MRR" value={latest.mrr} previous={previous?.mrr} />
            <div className="min-w-0">
              <dt className="text-sm text-muted-foreground">Last run</dt>
              <dd className="mt-1 text-base font-semibold" title={formatDateTime(latest.created_at)}>
                {formatRelative(latest.created_at)}
              </dd>
              <dd className="text-xs text-muted-foreground">
                {latest.cases} questions · {latest.trigger === 'nightly' ? 'nightly' : 'run by hand'}
              </dd>
            </div>
          </dl>
          {warnings.length ? (
            <ul className="space-y-2 border-t px-5 py-4 sm:px-6" aria-label="Quality warnings">
              {warnings.map((warning) => (
                <li key={warning.code} className="flex items-start gap-2 text-sm">
                  <AlertTriangle className="mt-0.5 size-4 shrink-0 text-warning" aria-hidden="true" />
                  {warning.message}
                </li>
              ))}
            </ul>
          ) : null}
          {latest.misses?.length ? (
            <p className="border-t px-5 py-3 text-xs text-muted-foreground sm:px-6">
              Not in the top 5: {latest.misses.join(', ')}
            </p>
          ) : null}
        </>
      ) : (
        <EmptyState icon={FlaskConical} title="No checks yet">
          The first nightly run appears here. Run it by hand with <code className="font-mono text-xs">manage.py eval_rag --record manual</code>.
        </EmptyState>
      )}
    </SplitSection>
  );
}
