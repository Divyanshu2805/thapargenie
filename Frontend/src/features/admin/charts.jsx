import { useState } from 'react';

import { formatNumber } from '@/lib/format';
import { cn } from '@/lib/utils';

// The smallest "round" axis top (two gridline steps) that fits the value: 18 → 20, 21 → 30, 130 → 200.
export function niceMax(value) {
  if (value <= 4) return 4;
  const magnitude = 10 ** Math.floor(Math.log10(value));
  const step = [0.5, 1, 1.5, 2.5, 5, 10].find((candidate) => candidate * magnitude * 2 >= value) * magnitude;
  return step * 2;
}

/**
 * Single-series column chart: `data` is [{label, value, detail?}]. One hue (the chart token),
 * so the title names the series and no legend is needed. Hover or focus shows the value;
 * a visually hidden table carries the same numbers for screen readers.
 */
export function ColumnChart({ data, title, valueLabel = 'Value', height = 180 }) {
  const [active, setActive] = useState(null);
  const max = niceMax(Math.max(0, ...data.map((item) => item.value)));
  const ticks = [0, max / 2, max];
  const labelEvery = Math.ceil(data.length / 7);

  return (
    <figure className="relative">
      <div className="flex gap-3">
        <div className="flex flex-col justify-between pb-6 text-right text-[11px] text-muted-foreground tabular-nums" style={{ height }} aria-hidden="true">
          {[...ticks].reverse().map((tick) => (
            <span key={tick} className="-translate-y-1/2 first:translate-y-0 last:translate-y-0">
              {formatNumber(tick)}
            </span>
          ))}
        </div>
        <div className="relative min-w-0 flex-1" style={{ height }}>
          <div className="absolute inset-x-0 top-0 bottom-6" aria-hidden="true">
            {ticks.map((tick) => (
              <div
                key={tick}
                className="absolute inset-x-0 border-t border-dashed border-border/80"
                style={{ bottom: `${(tick / max) * 100}%` }}
              />
            ))}
          </div>
          <div className="absolute inset-x-0 top-0 bottom-6 flex items-end gap-[2px]">
            {data.map((item, index) => (
              <button
                key={item.label}
                type="button"
                aria-label={`${item.label}: ${formatNumber(item.value)} ${valueLabel.toLowerCase()}`}
                onMouseEnter={() => setActive(index)}
                onMouseLeave={() => setActive(null)}
                onFocus={() => setActive(index)}
                onBlur={() => setActive(null)}
                className="group relative flex h-full flex-1 items-end outline-none"
              >
                <span
                  className={cn(
                    'w-full rounded-t-[4px] bg-chart-1 transition-opacity group-focus-visible:ring-2 group-focus-visible:ring-ring',
                    active !== null && active !== index && 'opacity-45',
                  )}
                  style={{ height: `${Math.max(item.value ? 2 : 0, (item.value / max) * 100)}%` }}
                />
              </button>
            ))}
          </div>
          <div className="absolute inset-x-0 bottom-0 flex h-5 gap-[2px] text-[11px] text-muted-foreground" aria-hidden="true">
            {data.map((item, index) => (
              <span
                key={item.label}
                // On phones every other label is hidden, so dates never collide.
                className={cn('flex-1 truncate text-center', (data.length - 1 - index) % (2 * labelEvery) !== 0 && 'max-sm:invisible')}
              >
                {index % labelEvery === 0 || index === data.length - 1 ? item.shortLabel ?? item.label : ''}
              </span>
            ))}
          </div>
          {active !== null ? (
            <div
              className="pointer-events-none absolute -top-2 z-10 -translate-x-1/2 -translate-y-full rounded-lg border bg-popover px-2.5 py-1.5 text-xs whitespace-nowrap shadow-lift"
              style={{ left: `${((active + 0.5) / data.length) * 100}%` }}
              role="status"
            >
              <p className="font-medium">{data[active].label}</p>
              <p className="text-muted-foreground">
                {valueLabel}: <span className="font-semibold text-foreground tabular-nums">{formatNumber(data[active].value)}</span>
              </p>
              {data[active].detail ? <p className="text-muted-foreground">{data[active].detail}</p> : null}
            </div>
          ) : null}
        </div>
      </div>
      <table className="sr-only">
        <caption>{title}</caption>
        <thead>
          <tr>
            <th scope="col">Day</th>
            <th scope="col">{valueLabel}</th>
          </tr>
        </thead>
        <tbody>
          {data.map((item) => (
            <tr key={item.label}>
              <th scope="row">{item.label}</th>
              <td>{item.value}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </figure>
  );
}

/** Horizontal magnitude bars with direct labels: `data` is [{label, value}], sorted by the caller. */
export function BarList({ data, total }) {
  const max = Math.max(1, ...data.map((item) => item.value));
  return (
    <ul className="space-y-2.5">
      {data.map((item) => (
        <li key={item.label} className="grid grid-cols-[minmax(0,9rem)_1fr_auto] items-center gap-3 text-sm">
          <span className="truncate text-muted-foreground">{item.label}</span>
          <span className="h-2 overflow-hidden rounded-full bg-muted" aria-hidden="true">
            <span className="block h-full rounded-full bg-chart-1" style={{ width: `${(item.value / max) * 100}%` }} />
          </span>
          <span className="text-right font-medium tabular-nums">
            {formatNumber(item.value)}
            {total ? <span className="ml-1.5 text-xs font-normal text-muted-foreground">{Math.round((item.value / total) * 100)}%</span> : null}
          </span>
        </li>
      ))}
    </ul>
  );
}

/** A value against a limit, e.g. LLM calls against the daily budget. */
export function Meter({ value, max, label }) {
  const ratio = max ? Math.min(1, value / max) : 0;
  const tone = ratio >= 0.9 ? 'bg-destructive' : ratio >= 0.7 ? 'bg-warning' : 'bg-chart-1';
  return (
    <div
      role="meter"
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={max}
      aria-valuenow={value}
      className="h-2 overflow-hidden rounded-full bg-muted"
    >
      <div className={cn('h-full rounded-full transition-[width]', tone)} style={{ width: `${ratio * 100}%` }} />
    </div>
  );
}
