import { cn } from '@/lib/utils';

export const IS_MAC = typeof navigator !== 'undefined' && /Mac|iPhone|iPad/.test(navigator.platform);

/** The platform's name for a modifier: ⌘ / ⇧ on Apple devices, Ctrl / Shift elsewhere. */
export const MOD = IS_MAC ? '⌘' : 'Ctrl';
export const SHIFT = IS_MAC ? '⇧' : 'Shift';

/** A keyboard shortcut shown on a button. Hidden on touch screens, where it means nothing. */
export function Kbd({ keys, className }) {
  return (
    <kbd
      aria-hidden="true"
      className={cn(
        'pointer-events-none ml-auto hidden items-center gap-0.5 font-sans text-[11px] font-medium opacity-70 [@media(pointer:fine)]:inline-flex',
        className,
      )}
    >
      {keys.map((key) => (
        <span key={key} className="min-w-[1.25rem] rounded border border-current/25 px-1 py-px text-center leading-tight">
          {key}
        </span>
      ))}
    </kbd>
  );
}
