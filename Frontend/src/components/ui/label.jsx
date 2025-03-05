import { Label as LabelPrimitive } from 'radix-ui';

import { cn } from '@/lib/utils';

function Label({ className, ...props }) {
  return (
    <LabelPrimitive.Root
      data-slot="label"
      className={cn('text-[13px] leading-none font-medium text-foreground/85 select-none peer-disabled:opacity-50', className)}
      {...props}
    />
  );
}

export { Label };
