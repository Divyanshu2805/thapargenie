import {
  ChevronsUpDown,
  FileLock2,
  LogOut,
  Monitor,
  Moon,
  Settings,
  ShieldCheck,
  Sun,
} from 'lucide-react';
import { Link } from 'react-router-dom';

import { useAuth } from '@/auth/AuthContext';
import { useTheme } from '@/components/theme-provider';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { onSignInPage, useSlideClick } from '@/lib/page-slide';
import { cn, initialsOf } from '@/lib/utils';

const THEMES = [
  { value: 'light', label: 'Light theme', short: 'Light', icon: Sun },
  { value: 'dark', label: 'Dark theme', short: 'Dark', icon: Moon },
  { value: 'system', label: 'Match system', short: 'System', icon: Monitor },
];

export function UserAvatar({ className }) {
  const { user, profile } = useAuth();
  const label = user?.displayName || user?.email || profile?.email;
  return (
    <Avatar className={className}>
      {user?.photoURL ? <AvatarImage src={user.photoURL} alt="" referrerPolicy="no-referrer" /> : null}
      <AvatarFallback>{initialsOf(label)}</AvatarFallback>
    </Avatar>
  );
}

export default function UserMenu({ side = 'top', align = 'start', compact = false }) {
  const { user, profile } = useAuth();
  // Signing out slides to the sign-in page once it is showing.
  const signOutClick = useSlideClick({ ready: onSignInPage, back: true });
  const { theme, setTheme } = useTheme();
  const name = user?.displayName || (user?.email || profile?.email || '').split('@')[0];

  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          {/* One button in both states (the sidebar animates between them): the avatar stays put, the rest fades. */}
          <button
            type="button"
            className={cn(
              'sidebar-row flex h-11 shrink-0 items-center gap-2.5 overflow-hidden rounded-lg px-1 text-left outline-none hover:bg-sidebar-accent focus-visible:ring-2 focus-visible:ring-ring/50 data-[state=open]:bg-sidebar-accent',
              compact ? 'w-10' : 'w-full',
            )}
          >
            <UserAvatar className="size-8 shrink-0" />
            <span className="sidebar-label flex min-w-0 flex-1 flex-col">
              <span className="truncate text-sm font-medium">{name || 'Account'}</span>
              <span className="truncate text-xs text-muted-foreground">{profile?.is_staff ? 'Administrator' : 'Student'}</span>
            </span>
            <ChevronsUpDown className="sidebar-label size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
            <span className="sr-only">Open account menu</span>
          </button>
        </DropdownMenuTrigger>
        <DropdownMenuContent side={compact ? 'right' : side} align={compact ? 'end' : align} className="w-64">
          {/* Theme first, centred across the menu. */}
          <div role="group" aria-label="Theme" className="mb-1.5 grid w-full grid-cols-3 gap-0.5 rounded-lg bg-muted p-0.5">
            {THEMES.map(({ value, label, short, icon: Icon }) => (
              <DropdownMenuItem
                key={value}
                onSelect={(event) => {
                  event.preventDefault();
                  setTheme(value);
                }}
                aria-pressed={theme === value}
                aria-label={label}
                title={label}
                className={cn(
                  'h-8 justify-center gap-1.5 rounded-md px-2 py-0 text-xs font-medium text-muted-foreground transition-colors duration-150 data-[highlighted]:bg-foreground/10 data-[highlighted]:text-foreground',
                  theme === value && 'bg-card text-foreground shadow-sm data-[highlighted]:bg-card [&_svg:not([class*=text-])]:text-foreground',
                )}
              >
                <Icon className="size-3.5" />
                {short}
              </DropdownMenuItem>
            ))}
          </div>
          <DropdownMenuSeparator />
          <DropdownMenuItem asChild>
            <Link to="/settings/">
              <Settings /> Settings
            </Link>
          </DropdownMenuItem>
          {profile?.is_staff ? (
            <DropdownMenuItem asChild>
              <Link to="/admin/">
                <ShieldCheck /> Admin dashboard
              </Link>
            </DropdownMenuItem>
          ) : null}
          <DropdownMenuSeparator />
          <DropdownMenuItem asChild>
            <Link to="/privacy">
              <FileLock2 /> Privacy notice
            </Link>
          </DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuItem asChild variant="destructive">
            <Link to="/logout/" onClick={signOutClick}>
              <LogOut /> Sign out
            </Link>
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </>
  );
}
