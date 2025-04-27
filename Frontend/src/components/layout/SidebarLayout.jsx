import { Menu, PanelLeftClose, PanelLeftOpen } from 'lucide-react';
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { Link, useMatch, useResolvedPath } from 'react-router-dom';

import { LogoMark, Wordmark } from '@/components/brand/Brand';
import { Button } from '@/components/ui/button';
import { Sheet, SheetContent } from '@/components/ui/sheet';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { cn } from '@/lib/utils';

// One layout for the student app and the admin dashboard: a 272 px
// sidebar that collapses to a 64 px icon rail from 768 px, and a drawer below that.
// Sidebars render their contents at the full --sidebar-width in both states.

const STORAGE_KEY = 'thapargpt:sidebar';
const SHORTCUT = typeof navigator !== 'undefined' && /Mac|iPhone|iPad/.test(navigator.platform) ? '⌘B' : 'Ctrl+B';

function initialCollapsed() {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved === 'collapsed' || saved === 'expanded') return saved === 'collapsed';
  } catch {
    // Storage can be unavailable (private mode); fall back to the screen width.
  }
  return typeof window !== 'undefined' && window.innerWidth < 1024;
}

const SidebarContext = createContext({ collapsed: false, inDrawer: false, toggle: () => {}, onNavigate: undefined });

export const useSidebar = () => useContext(SidebarContext);

// Pages can put their own title and actions in the phone top bar (one bar, not two).
const TopbarContext = createContext(() => {});

export function usePageTopbar(title, actions) {
  const setPageTopbar = useContext(TopbarContext);
  useEffect(() => {
    setPageTopbar({ title, actions });
    return () => setPageTopbar(null);
  }, [setPageTopbar, title, actions]);
}

/** True when this copy of the sidebar is the collapsed icon rail. */
export function useRail() {
  const { collapsed, inDrawer } = useSidebar();
  return collapsed && !inDrawer;
}

// The sidebar keeps one layout whether open or collapsed: its contents stay at the full
// width and the <aside> clips them, every icon sits 24 px from the left edge (the centre
// of the 64 px rail), and only labels fade (.sidebar-label in index.css). Nothing is
// swapped or re-mounted, so nothing jumps while the width animates.

/** Tooltip that only opens on the rail. Always rendered so its child never re-mounts. */
function RailTooltip({ label, children }) {
  const rail = useRail();
  const [open, setOpen] = useState(false);
  // Hovers on the open sidebar must not be remembered: Radix never sends the matching
  // "close" while we hold the tooltip shut, so collapsing would pop every hovered one up.
  const [wasRail, setWasRail] = useState(rail);
  if (wasRail !== rail) {
    setWasRail(rail);
    setOpen(false);
  }
  return (
    <Tooltip open={rail && open} onOpenChange={(next) => setOpen(rail && next)}>
      <TooltipTrigger asChild>{children}</TooltipTrigger>
      <TooltipContent side="right">{label}</TooltipContent>
    </Tooltip>
  );
}

/** Row shape shared by sidebar items: full width when open, a 40 px square on the rail. */
const sidebarRowClass = (rail) =>
  cn(
    'sidebar-row icon-nudge relative flex h-9 shrink-0 items-center gap-3 overflow-hidden rounded-lg px-3 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring/50 [&_svg]:size-4 [&_svg]:shrink-0',
    rail ? 'w-10' : 'w-full',
  );

const itemClass = (rail, active) =>
  cn(
    sidebarRowClass(rail),
    'text-sidebar-foreground/80 hover:bg-sidebar-accent hover:text-sidebar-foreground',
    active && 'bg-card font-medium text-sidebar-foreground shadow-soft ring-1 ring-sidebar-border [&_svg]:text-primary dark:[&_svg]:text-accent-foreground',
  );

/** A navigation link or action; icon-only with a tooltip on the rail. */
export function SidebarItem({ icon: Icon, label, to, end, onClick, active, pressed, className, trailing, children }) {
  const { onNavigate } = useSidebar();
  const rail = useRail();
  // Computed here rather than through NavLink's function props: the tooltip trigger
  // merges props and would stringify a className function.
  const resolved = useResolvedPath(to || '.');
  const match = useMatch({ path: resolved.pathname, end: Boolean(end) });
  const isActive = to ? Boolean(match) : Boolean(active);
  const content = (
    <>
      <Icon aria-hidden="true" className={cn(!isActive && !className && 'text-muted-foreground')} />
      <span className="sidebar-label whitespace-nowrap">{children || label}</span>
      {trailing}
    </>
  );
  return (
    <RailTooltip label={label}>
      {to ? (
        <Link to={to} onClick={onNavigate} aria-current={isActive ? 'page' : undefined} className={cn(itemClass(rail, isActive), className)}>
          {content}
        </Link>
      ) : (
        <button type="button" onClick={onClick} aria-pressed={pressed} className={cn(itemClass(rail, isActive), className)}>
          {content}
        </button>
      )}
    </RailTooltip>
  );
}

/** Group label; on the rail it cross-fades into a thin divider of the same height. */
export function SidebarGroupLabel({ children }) {
  return (
    <div className="relative flex h-7 shrink-0 items-center px-3">
      <h3 className="sidebar-label text-[11px] font-semibold tracking-wider whitespace-nowrap text-muted-foreground uppercase">{children}</h3>
      <span className="sidebar-rail-only absolute top-1/2 left-2 h-px w-6 bg-sidebar-border" aria-hidden="true" />
    </div>
  );
}

/** Logo, wordmark and collapse button. On the rail the logo itself expands the sidebar. */
export function SidebarHeader({ to, badge }) {
  const { inDrawer, toggle, onNavigate } = useSidebar();
  const rail = useRail();
  return (
    <div className="flex h-16 shrink-0 items-center gap-2.5 px-3">
      {/* The mark never re-mounts (its draw-in animation would replay); only the control over it changes. */}
      <div className="group/logo relative flex size-10 shrink-0 items-center justify-center">
        <LogoMark
          motion="loop"
          className="pointer-events-none transition-opacity duration-150 group-has-[button:hover]/logo:opacity-0 group-has-[button:focus-visible]/logo:opacity-0"
        />
        {rail ? (
          <Tooltip>
            <TooltipTrigger asChild>
              <button
                type="button"
                onClick={toggle}
                className="icon-nudge absolute inset-0 flex items-center justify-center rounded-xl text-muted-foreground opacity-0 transition-opacity duration-150 outline-none hover:opacity-100 focus-visible:opacity-100 focus-visible:ring-2 focus-visible:ring-ring/50"
                aria-label="Expand sidebar"
              >
                <PanelLeftOpen className="size-5" />
              </button>
            </TooltipTrigger>
            <TooltipContent side="right">Expand sidebar ({SHORTCUT})</TooltipContent>
          </Tooltip>
        ) : (
          <Link to={to} onClick={onNavigate} className="absolute inset-0 rounded-xl outline-none focus-visible:ring-2 focus-visible:ring-ring/50">
            <span className="sr-only">Home</span>
          </Link>
        )}
      </div>
      <Link to={to} onClick={onNavigate} tabIndex={-1} aria-hidden="true" className="sidebar-label min-w-0">
        <Wordmark />
      </Link>
      {badge}
      {inDrawer ? null : (
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              variant="ghost"
              size="icon-sm"
              onClick={toggle}
              tabIndex={rail ? -1 : undefined}
              className="sidebar-label icon-nudge ml-auto shrink-0 text-muted-foreground"
              aria-label="Collapse sidebar"
            >
              <PanelLeftClose />
            </Button>
          </TooltipTrigger>
          <TooltipContent side="right">Collapse sidebar ({SHORTCUT})</TooltipContent>
        </Tooltip>
      )}
    </div>
  );
}

export default function SidebarLayout({ renderSidebar, title, topbarActions, notice, backdrop, drawerTitle = 'Navigation', children }) {
  const [collapsed, setCollapsed] = useState(initialCollapsed);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [pageTopbar, setPageTopbar] = useState(null);

  const toggle = useCallback(() => {
    setCollapsed((value) => {
      try {
        localStorage.setItem(STORAGE_KEY, value ? 'expanded' : 'collapsed');
      } catch {
        // Not remembered, but still toggled.
      }
      return !value;
    });
  }, []);

  // Ctrl/Cmd + B toggles the sidebar, as in most editors.
  useEffect(() => {
    const onKeyDown = (event) => {
      if ((event.ctrlKey || event.metaKey) && !event.shiftKey && !event.altKey && event.key.toLowerCase() === 'b') {
        event.preventDefault();
        toggle();
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [toggle]);

  // Lets toasts centre over the main area (index.css) instead of the whole window.
  useEffect(() => {
    const root = document.documentElement;
    root.style.setProperty('--app-sidebar-width', collapsed ? 'var(--sidebar-rail)' : 'var(--sidebar-width)');
    return () => root.style.removeProperty('--app-sidebar-width');
  }, [collapsed]);

  const closeDrawer = useCallback(() => setDrawerOpen(false), []);
  const rail = useMemo(() => ({ collapsed, inDrawer: false, toggle, onNavigate: undefined }), [collapsed, toggle]);
  const drawer = useMemo(() => ({ collapsed: false, inDrawer: true, toggle, onNavigate: closeDrawer }), [toggle, closeDrawer]);

  return (
    <div className="flex h-dvh overflow-hidden bg-background">
      <a
        href="#main"
        className="sr-only z-50 rounded-md bg-primary px-3 py-2 text-primary-foreground focus:not-sr-only focus:absolute focus:top-3 focus:left-3"
      >
        Skip to content
      </a>

      <aside
        data-collapsed={collapsed || undefined}
        className={cn(
          'sidebar-aside hidden shrink-0 overflow-hidden border-r border-sidebar-border bg-sidebar md:block',
          collapsed ? 'w-[var(--sidebar-rail)]' : 'w-[var(--sidebar-width)]',
        )}
      >
        <SidebarContext.Provider value={rail}>{renderSidebar()}</SidebarContext.Provider>
      </aside>

      <Sheet open={drawerOpen} onOpenChange={setDrawerOpen}>
        <SheetContent side="left" title={drawerTitle} className="p-0">
          <SidebarContext.Provider value={drawer}>{renderSidebar()}</SidebarContext.Provider>
        </SheetContent>
      </Sheet>

      <div className="relative isolate flex min-w-0 flex-1 flex-col">
        {backdrop}
        <header className="flex h-[var(--topbar-height)] shrink-0 items-center gap-1 border-b bg-background/85 px-2 backdrop-blur md:hidden">
          <Button variant="ghost" size="icon" onClick={() => setDrawerOpen(true)} aria-label="Open navigation">
            <Menu className="size-5" />
          </Button>
          <div className="min-w-0 flex-1 truncate px-1 text-sm font-semibold">{pageTopbar?.title ?? title}</div>
          {pageTopbar?.actions}
          {topbarActions}
        </header>
        {notice}
        <main id="main" className="min-h-0 flex-1 overflow-y-auto">
          <TopbarContext.Provider value={setPageTopbar}>{children}</TopbarContext.Provider>
        </main>
      </div>
    </div>
  );
}
