import {
  ArrowLeft,
  FileText,
} from 'lucide-react';
import { Suspense } from 'react';
import { Outlet, useLocation } from 'react-router-dom';

import { Ambient } from '@/components/ambient';
import { Brand } from '@/components/brand/Brand';
import { ErrorBoundary } from '@/components/error-boundary';
import SidebarLayout, { SidebarGroupLabel, SidebarHeader, SidebarItem, useRail } from '@/components/layout/SidebarLayout';
import UserMenu from '@/components/layout/UserMenu';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';

const ADMIN_SECTIONS = [
  { group: 'Knowledge', to: '/admin/documents', label: 'Documents', icon: FileText },
];

function AdminNav() {
  const rail = useRail();
  const groups = [...new Set(ADMIN_SECTIONS.map((section) => section.group))];
  // Same tree open or collapsed (see SidebarLayout), so the rail animates without jumps.
  return (
    <div className="flex h-full w-[var(--sidebar-width)] max-w-full flex-col bg-sidebar text-sidebar-foreground">
      {/* The logo and name lead back to the student chat home; Overview is in the nav. */}
      <SidebarHeader to="/chat/" />
      <p className="sidebar-label -mt-2 px-3 pb-2 text-[11px] font-semibold tracking-wider whitespace-nowrap text-primary uppercase dark:text-accent-foreground">
        Admin
      </p>
      <nav aria-label="Admin" className={cn('scrollbar-thin min-h-0 flex-1 px-3 py-1', rail ? 'overflow-hidden' : 'overflow-y-auto')}>
        {groups.map((group) => (
          <div key={group} className="flex flex-col gap-0.5 pb-3">
            <SidebarGroupLabel>{group}</SidebarGroupLabel>
            {ADMIN_SECTIONS.filter((section) => section.group === group).map(({ to, end, label, icon }) => (
              <SidebarItem key={to} to={to} end={end} icon={icon} label={label} />
            ))}
          </div>
        ))}
      </nav>
      <div className="flex flex-col gap-0.5 border-t border-sidebar-border px-3 py-2">
        <SidebarItem to="/chat/" icon={ArrowLeft} label="Back to chat" />
        <UserMenu compact={rail} />
      </div>
    </div>
  );
}

function PageFallback() {
  return (
    <div className="page-wide space-y-4" aria-busy="true" aria-label="Loading">
      <Skeleton className="h-8 w-56" />
      <Skeleton className="h-4 w-80" />
      <div className="grid grid-cols-2 gap-4 pt-4 xl:grid-cols-4">
        {[0, 1, 2, 3].map((item) => (
          <Skeleton key={item} className="h-28 rounded-xl" />
        ))}
      </div>
    </div>
  );
}

export default function AdminLayout() {
  const location = useLocation();
  return (
    <SidebarLayout
      renderSidebar={() => <AdminNav />}
      title={
        <span className="flex items-center gap-2">
          <Brand markClassName="size-8" />
          <Badge variant="brand">Admin</Badge>
        </span>
      }
      drawerTitle="Admin navigation"
      backdrop={<Ambient />}
    >
      <ErrorBoundary key={location.pathname}>
        <Suspense fallback={<PageFallback />}>
          <div className="animate-page-in">
            <Outlet />
          </div>
        </Suspense>
      </ErrorBoundary>
    </SidebarLayout>
  );
}
