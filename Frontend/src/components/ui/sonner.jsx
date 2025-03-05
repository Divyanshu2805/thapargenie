import { Toaster as Sonner } from 'sonner';

import { useTheme } from '@/components/theme-provider';

function Toaster(props) {
  const { resolvedTheme } = useTheme();
  return (
    <Sonner
      theme={resolvedTheme}
      position="top-center"
      toastOptions={{
        classNames: {
          toast: '!rounded-xl !border-border !bg-popover !text-popover-foreground !shadow-lift',
          description: '!text-muted-foreground',
        },
      }}
      {...props}
    />
  );
}

export { Toaster };
