import { XIcon } from 'lucide-react';
import { Dialog as SheetPrimitive } from 'radix-ui';

import { cn } from '@/lib/utils';

function Sheet(props) {
  return <SheetPrimitive.Root data-slot="sheet" {...props} />;
}

function SheetTrigger(props) {
  return <SheetPrimitive.Trigger data-slot="sheet-trigger" {...props} />;
}

function SheetClose(props) {
  return <SheetPrimitive.Close data-slot="sheet-close" {...props} />;
}

const sides = {
  left: 'inset-y-0 left-0 h-full w-[var(--sidebar-width)] max-w-[85vw] border-r data-[state=open]:animate-[sheet-in-left_0.28s_var(--ease-out)]',
  right: 'inset-y-0 right-0 h-full w-[22rem] max-w-[90vw] border-l data-[state=open]:animate-[sheet-in-right_0.28s_var(--ease-out)]',
};

function SheetContent({ className, children, side = 'left', title, ...props }) {
  return (
    <SheetPrimitive.Portal>
      <SheetPrimitive.Overlay className="fixed inset-0 z-50 animate-fade-in bg-black/45" />
      <SheetPrimitive.Content
        data-slot="sheet-content"
        aria-describedby={undefined}
        className={cn('fixed z-50 flex flex-col bg-sidebar shadow-lift outline-none', sides[side], className)}
        {...props}
      >
        <SheetPrimitive.Title className="sr-only">{title}</SheetPrimitive.Title>
        {children}
        <SheetPrimitive.Close className="absolute top-3.5 right-3 rounded-md p-1.5 text-muted-foreground transition-colors hover:bg-sidebar-accent hover:text-foreground">
          <XIcon className="size-4" />
          <span className="sr-only">Close</span>
        </SheetPrimitive.Close>
      </SheetPrimitive.Content>
    </SheetPrimitive.Portal>
  );
}

export { Sheet, SheetClose, SheetContent, SheetTrigger };
