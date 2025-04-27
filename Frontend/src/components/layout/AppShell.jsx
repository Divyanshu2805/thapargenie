import { Info, SquarePen } from 'lucide-react';
import { Suspense, useEffect } from 'react';
import { Link, Outlet, useLocation, useNavigate } from 'react-router-dom';

import { Ambient } from '@/components/ambient';
import { Brand } from '@/components/brand/Brand';
import { ErrorBoundary } from '@/components/error-boundary';
import ChatSidebar from '@/components/layout/ChatSidebar';
import SidebarLayout from '@/components/layout/SidebarLayout';
import { Button } from '@/components/ui/button';
import { useAppConfig } from '@/hooks/use-app-config';
import { cn } from '@/lib/utils';

function Notice({ tone, icon: Icon, children }) {
  const tones = {
    info: 'border-gold/25 bg-gold-soft text-foreground',
    warning: 'border-warning/30 bg-warning/10 text-foreground',
  };
  return (
    <div role="status" className={cn('flex animate-fade-in items-center justify-center gap-2 border-b px-4 py-2 text-center text-sm', tones[tone])}>
      <Icon className="size-4 shrink-0" aria-hidden="true" />
      <span>{children}</span>
    </div>
  );
}

export default function AppShell() {
  const { data: config } = useAppConfig();
  const navigate = useNavigate();
  const location = useLocation();

  // Ctrl/Cmd + Shift + O starts a new chat from anywhere.
  useEffect(() => {
    const onKeyDown = (event) => {
      if ((event.ctrlKey || event.metaKey) && event.shiftKey && event.key.toLowerCase() === 'o') {
        event.preventDefault();
        navigate('/chat/');
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [navigate]);

  // Maintenance is shown by the chat screens themselves (features/chat/Maintenance.jsx);
  // the strip is only for the admin's announcement banner.
  const notice = config?.banner && !config?.maintenance ? (
    <Notice tone="info" icon={Info}>
      {config.banner}
    </Notice>
  ) : null;

  return (
    <SidebarLayout
      renderSidebar={() => <ChatSidebar />}
      title={
        <Link to="/chat/" className="inline-flex rounded-lg outline-none focus-visible:ring-2 focus-visible:ring-ring/50">
          <Brand markClassName="size-8" />
        </Link>
      }
      topbarActions={
        <>
          <Button asChild variant="ghost" size="icon" aria-label="New chat">
            <Link to="/chat/">
              <SquarePen className="size-5" />
            </Link>
          </Button>
        </>
      }
      notice={notice}
      backdrop={<Ambient />}
    >
      {/* Keyed by path: moving to another page clears an error screen and replays the page entrance. */}
      <ErrorBoundary key={location.pathname}>
        <Suspense fallback={null}>
          <div className="h-full animate-page-in">
            <Outlet />
          </div>
        </Suspense>
      </ErrorBoundary>
    </SidebarLayout>
  );
}
