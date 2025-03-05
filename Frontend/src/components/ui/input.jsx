import { cn } from '@/lib/utils';

function Input({ className, type, ...props }) {
  return (
    <input
      type={type}
      data-slot="input"
      className={cn(
        'flex h-10 w-full min-w-0 rounded-lg border border-transparent bg-field px-3 py-2 text-sm transition-[border-color,box-shadow,background-color] duration-150 outline-none placeholder:text-muted-foreground/80 hover:border-primary/40 hover:ring-4 hover:ring-primary/[0.07] focus-visible:border-ring focus-visible:bg-card focus-visible:ring-4 focus-visible:ring-ring/15 focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-50 aria-invalid:border-destructive aria-invalid:ring-destructive/15 [&[type=date]]:tabular-nums',
        className,
      )}
      {...props}
    />
  );
}

export { Input };
