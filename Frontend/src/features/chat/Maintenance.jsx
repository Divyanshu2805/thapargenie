import { MessagesSquare, Wrench } from 'lucide-react';

const FALLBACK = 'Asking is paused for a short while. Please check back soon.';

function Progress({ className }) {
  return (
    <div className={`maintenance-progress h-1 overflow-hidden rounded-full bg-gold/15 ${className}`} aria-hidden="true">
      <span className="block h-full w-1/3 rounded-full bg-gold" />
    </div>
  );
}

/** The chat home, while an admin has paused asking: shown where the question box would be. */
export function MaintenanceCard({ message }) {
  return (
    <section
      aria-labelledby="maintenance-title"
      className="relative overflow-hidden rounded-3xl border border-gold/30 bg-card p-6 text-center shadow-lift sm:p-8"
    >
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 bg-[radial-gradient(70%_60%_at_50%_0%,color-mix(in_oklab,var(--color-gold)_14%,transparent),transparent)]"
      />
      <div className="relative">
        <span className="maintenance-icon mx-auto flex size-14 items-center justify-center rounded-2xl bg-gold-soft text-gold ring-1 ring-gold/30">
          <Wrench className="size-6" aria-hidden="true" />
        </span>
        <h2 id="maintenance-title" className="mt-4 text-heading">
          We’re improving ThaparGenie
        </h2>
        <p className="mx-auto mt-2 max-w-md text-sm leading-relaxed text-muted-foreground">{message || FALLBACK}</p>
        <Progress className="mx-auto mt-5 w-40" />
        <p className="mt-5 inline-flex items-center gap-1.5 text-xs text-muted-foreground">
          <MessagesSquare className="size-3.5" aria-hidden="true" />
          Your past chats are still here in the sidebar.
        </p>
      </div>
    </section>
  );
}

/** An open chat, while asking is paused: takes the question box's place under the thread. */
export function MaintenanceBar({ message }) {
  return (
    <section
      role="status"
      aria-label="Maintenance"
      className="relative flex items-center gap-4 overflow-hidden rounded-2xl border border-gold/30 bg-card px-4 py-3.5 shadow-lift sm:px-5"
    >
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 bg-[radial-gradient(60%_120%_at_0%_50%,color-mix(in_oklab,var(--color-gold)_12%,transparent),transparent)]"
      />
      <span className="maintenance-icon relative flex size-10 shrink-0 items-center justify-center rounded-xl bg-gold-soft text-gold ring-1 ring-gold/30">
        <Wrench className="size-[18px]" aria-hidden="true" />
      </span>
      <div className="relative min-w-0 flex-1">
        <p className="text-sm font-semibold">We’re improving ThaparGenie</p>
        <p className="truncate text-sm text-muted-foreground" title={message || FALLBACK}>
          {message || FALLBACK} You can still read this chat.
        </p>
      </div>
      <Progress className="relative hidden w-24 shrink-0 sm:block" />
    </section>
  );
}
