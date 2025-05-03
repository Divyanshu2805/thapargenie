import { Switch } from '@/components/ui/switch';
import { cn } from '@/lib/utils';

// The split layout used by the settings pages, the help page and every admin page:
// each section has its icon, title, description and actions on the
// left, and its content on a card on the right. On narrow screens the two stack.

export function SplitSection({ icon: Icon, title, description, actions, tone, flush, bare, children }) {
  return (
    <section className="grid items-start gap-4 border-b border-border/70 py-8 first:pt-2 last:border-0 lg:grid-cols-[16rem_minmax(0,1fr)] lg:gap-10">
      <div className="flex gap-3 lg:flex-col lg:gap-3">
        {Icon ? (
          <span
            className={cn(
              'icon-nudge flex size-10 shrink-0 items-center justify-center rounded-xl',
              tone === 'danger' ? 'bg-destructive/10 text-destructive' : 'bg-accent text-accent-foreground',
            )}
          >
            <Icon className="size-[18px]" aria-hidden="true" />
          </span>
        ) : null}
        <div>
          <h2 className="text-heading">{title}</h2>
          {description ? <p className="mt-1 text-sm leading-relaxed text-muted-foreground">{description}</p> : null}
          {actions ? <div className="mt-4 flex flex-wrap gap-2">{actions}</div> : null}
        </div>
      </div>
      {bare ? (
        // `bare` content brings its own cards (grids of tiles).
        <div className="min-w-0">{children}</div>
      ) : (
        <div
          className={cn(
            'min-w-0 overflow-hidden rounded-2xl border bg-card shadow-soft',
            // `flush` content (tables, charts) manages its own inner spacing and dividers.
            !flush && 'divide-y',
            tone === 'danger' && 'border-destructive/25',
          )}
        >
          {children}
        </div>
      )}
    </section>
  );
}

/** One line in a section card: a label and description, with its control on the right. */
export function SectionRow({ title, description, htmlFor, children, className }) {
  const Label = htmlFor ? 'label' : 'div';
  return (
    <div className={cn('flex flex-col gap-3 px-5 py-4 sm:flex-row sm:items-center sm:justify-between sm:gap-6 sm:px-6', className)}>
      <Label htmlFor={htmlFor} className="min-w-0">
        <span className="block text-sm font-semibold">{title}</span>
        {description ? <span className="mt-0.5 block text-[13px] leading-relaxed text-muted-foreground">{description}</span> : null}
      </Label>
      {children ? <div className="flex shrink-0 flex-wrap items-center gap-2">{children}</div> : null}
    </div>
  );
}

/** A switch row; clicking anywhere on the text toggles it. */
export function SectionToggle({ id, title, description, checked, onChange }) {
  return (
    <label
      htmlFor={id}
      className="relative flex cursor-pointer items-center justify-between gap-6 px-5 py-4 transition-colors duration-150 hover:bg-hover sm:px-6"
    >
      <span className="min-w-0">
        <span className="block text-sm font-semibold">{title}</span>
        {description ? <span className="mt-0.5 block text-[13px] leading-relaxed text-muted-foreground">{description}</span> : null}
      </span>
      <Switch id={id} checked={checked} onCheckedChange={onChange} />
    </label>
  );
}

/** Form fields inside a section card. */
export function SectionFields({ className, children }) {
  return <div className={cn('grid gap-5 px-5 py-5 sm:px-6', className)}>{children}</div>;
}
