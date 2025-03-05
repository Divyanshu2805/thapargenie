import { cn } from '@/lib/utils';

function Textarea({ className, ...props }) {
  return (
    <textarea
      data-slot="textarea"
      className={cn(
        'flex field-sizing-content min-h-16 w-full rounded-lg border border-transparent bg-field px-3 py-2.5 text-sm leading-relaxed transition-[border-color,box-shadow,background-color] duration-150 outline-none placeholder:text-muted-foreground/80 hover:border-primary/40 hover:ring-4 hover:ring-primary/[0.07] focus-visible:border-ring focus-visible:bg-card focus-visible:ring-4 focus-visible:ring-ring/15 focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-50 aria-invalid:border-destructive',
        className,
      )}
      {...props}
    />
  );
}

export { Textarea };
