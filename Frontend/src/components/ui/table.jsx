import { cn } from '@/lib/utils';

function Table({ className, ...props }) {
  return (
    <div data-slot="table-container" className="scrollbar-thin @container relative w-full overflow-x-auto">
      <table data-slot="table" className={cn('w-full caption-bottom text-sm', className)} {...props} />
    </div>
  );
}

function TableHeader({ className, ...props }) {
  return <thead data-slot="table-header" className={cn('[&_tr]:border-b', className)} {...props} />;
}

function TableBody({ className, ...props }) {
  return <tbody data-slot="table-body" className={cn('[&_tr:last-child]:border-0', className)} {...props} />;
}

function TableRow({ className, ...props }) {
  return (
    <tr
      data-slot="table-row"
      className={cn('border-b transition-colors hover:bg-hover data-[state=selected]:bg-muted', className)}
      {...props}
    />
  );
}

function TableHead({ className, ...props }) {
  return (
    <th
      data-slot="table-head"
      className={cn(
        'h-10 px-3 text-left align-middle text-xs font-medium whitespace-nowrap text-muted-foreground first:pl-4 last:pr-4',
        className,
      )}
      {...props}
    />
  );
}

function TableCell({ className, ...props }) {
  return <td data-slot="table-cell" className={cn('px-3 py-3 align-middle first:pl-4 last:pr-4', className)} {...props} />;
}

export { Table, TableBody, TableCell, TableHead, TableHeader, TableRow };
