import { useMutation, useQueryClient } from '@tanstack/react-query';
import {
  BadgeCheck,
  Check,
  Database,
  Download,
  GraduationCap,
  LogOut,
  Monitor,
  MonitorSmartphone,
  Moon,
  Palette,
  ShieldCheck,
  Sun,
  Trash2,
} from 'lucide-react';
import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { toast } from 'sonner';

import { useAuth } from '@/auth/AuthContext';
import { PageHeader } from '@/components/layout/PageHeader';
import { UserAvatar } from '@/components/layout/UserMenu';
import { useTheme } from '@/components/theme-provider';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { ConfirmDialog } from '@/components/confirm-dialog';
import { useRecentAuth } from '@/components/recent-auth';
import { SectionFields, SectionRow, SplitSection } from '@/components/split-section';
import { deleteAllConversations, exportMyData, revokeAllSessions, updatePreferences } from '@/lib/api/chat';
import { downloadBlob } from '@/lib/download';
import { logout } from '@/utils/auth';
import { cn } from '@/lib/utils';

const THEME_OPTIONS = [
  { value: 'light', label: 'Light', icon: Sun },
  { value: 'dark', label: 'Dark', icon: Moon },
  { value: 'system', label: 'System', icon: Monitor },
];

function ProfileCard() {
  const { user, profile } = useAuth();
  const email = user?.email || profile?.email || 'Unavailable';
  const approved = profile?.onboarding_status === 'ready';
  return (
    <section className="relative overflow-hidden rounded-2xl border bg-card shadow-soft">
      <div
        aria-hidden="true"
        className="h-20 bg-[radial-gradient(80%_120%_at_0%_0%,color-mix(in_oklab,var(--color-primary)_28%,transparent),transparent),radial-gradient(60%_120%_at_100%_100%,color-mix(in_oklab,var(--color-gold)_22%,transparent),transparent)] sm:h-24"
      />
      <div className="flex flex-col gap-4 px-5 pb-5 sm:flex-row sm:items-end sm:px-6 sm:pb-6">
        <UserAvatar className="-mt-10 size-20 border-4 border-card text-lg shadow-soft" />
        <div className="min-w-0 flex-1">
          <p className="truncate text-lg font-semibold">{user?.displayName || email.split('@')[0]}</p>
          <p className="truncate text-sm text-muted-foreground">{email}</p>
          <div className="mt-2 flex flex-wrap gap-2">
            <Badge variant={approved ? 'brand' : 'secondary'}>
              <BadgeCheck /> {approved ? 'Approved' : 'Pending'}
            </Badge>
            {profile?.is_staff ? (
              <Badge variant="gold">
                <ShieldCheck /> Administrator
              </Badge>
            ) : null}
          </div>
        </div>
        <Button asChild variant="outline">
          <Link to="/logout/">
            <LogOut /> Sign out
          </Link>
        </Button>
      </div>
    </section>
  );
}

function PreferencesCard() {
  const { profile, reloadProfile } = useAuth();
  const initial = profile?.preferences || {};
  const [form, setForm] = useState({
    campus: initial.campus || '',
    program: initial.program || '',
    academic_year: initial.academic_year ? String(initial.academic_year) : '',
  });

  const mutation = useMutation({
    mutationFn: () =>
      updatePreferences({
        campus: form.campus.trim(),
        program: form.program.trim(),
        academic_year: form.academic_year ? Number(form.academic_year) : null,
      }),
    onSuccess: async () => {
      toast.success('Preferences saved');
      await reloadProfile().catch(() => {});
    },
    onError: (error) => toast.error('Couldn’t save preferences', { description: error.message }),
  });

  const field = (name) => ({
    id: `pref-${name}`,
    value: form[name],
    onChange: (event) => setForm((current) => ({ ...current, [name]: event.target.value })),
  });

  return (
    <SplitSection
      icon={GraduationCap}
      title="Personalisation"
      description="Optional. Tailors answers such as “my fee” or “my timetable”. Never sent to the AI provider as your identity."
    >
      <form
        onSubmit={(event) => {
          event.preventDefault();
          mutation.mutate();
        }}
      >
        <SectionFields className="sm:grid-cols-3">
          <div className="grid content-start gap-2">
            <Label htmlFor="pref-campus">Campus</Label>
            <Input placeholder="Patiala" maxLength={100} {...field('campus')} />
          </div>
          <div className="grid content-start gap-2">
            <Label htmlFor="pref-program">Programme</Label>
            <Input placeholder="BE Computer Engineering" maxLength={120} {...field('program')} />
          </div>
          <div className="grid content-start gap-2">
            <Label htmlFor="pref-academic_year">Year of study</Label>
            <Input type="number" min={1} max={12} inputMode="numeric" placeholder="2" {...field('academic_year')} />
          </div>
        </SectionFields>
        <div className="flex justify-end border-t bg-muted/30 px-5 py-3 sm:px-6">
          <Button type="submit" disabled={mutation.isPending}>
            {mutation.isPending ? 'Saving…' : 'Save preferences'}
          </Button>
        </div>
      </form>
    </SplitSection>
  );
}

/** A tiny picture of the app in a theme: sidebar, a question and an answer. */
function ThemePreview({ variant }) {
  const pane = (dark) => (
    <div className={cn('flex h-full', dark ? 'bg-[#141011]' : 'bg-[#faf8f6]')}>
      <div className={cn('w-1/4 space-y-1 p-1.5', dark ? 'bg-[#110d0e]' : 'bg-[#f4f0ed]')}>
        <div className="h-1.5 rounded-sm bg-[#8c1c2b]" />
        <div className={cn('h-1 rounded-sm', dark ? 'bg-white/15' : 'bg-black/10')} />
        <div className={cn('h-1 rounded-sm', dark ? 'bg-white/15' : 'bg-black/10')} />
      </div>
      <div className="flex-1 space-y-1.5 p-2">
        <div className={cn('ml-auto h-2 w-1/2 rounded-full', dark ? 'bg-white/15' : 'bg-black/10')} />
        <div className={cn('h-1 w-5/6 rounded-sm', dark ? 'bg-white/25' : 'bg-black/20')} />
        <div className={cn('h-1 w-2/3 rounded-sm', dark ? 'bg-white/25' : 'bg-black/20')} />
        <div className={cn('mt-2 h-2.5 rounded-md border', dark ? 'border-white/15 bg-white/5' : 'border-black/10 bg-white')} />
      </div>
    </div>
  );
  if (variant === 'system') {
    return (
      <div className="relative h-full">
        {pane(false)}
        <div className="absolute inset-0 [clip-path:polygon(100%_0,100%_100%,0_100%)]">{pane(true)}</div>
      </div>
    );
  }
  return pane(variant === 'dark');
}

function AppearanceCard() {
  const { theme, setTheme } = useTheme();
  return (
    <SplitSection icon={Palette} title="Appearance" description="How ThaparGenie looks on this device.">
      <div role="radiogroup" aria-label="Theme" className="grid grid-cols-3 gap-3 p-5 sm:gap-4 sm:p-6">
        {THEME_OPTIONS.map(({ value, label, icon: Icon }) => {
          const selected = theme === value;
          return (
            <button
              key={value}
              type="button"
              role="radio"
              aria-checked={selected}
              onClick={() => setTheme(value)}
              className="group/theme flex flex-col gap-2.5 text-left outline-none"
            >
              <span
                className={cn(
                  'block aspect-[4/3] overflow-hidden rounded-xl border-2 transition-[border-color,box-shadow,translate] duration-200 group-hover/theme:-translate-y-0.5 group-focus-visible/theme:ring-[3px] group-focus-visible/theme:ring-ring/30',
                  selected ? 'border-primary shadow-lift dark:border-accent-foreground' : 'border-border group-hover/theme:border-primary/40',
                )}
              >
                <ThemePreview variant={value} />
              </span>
              <span className="flex items-center gap-1.5 text-sm font-medium">
                <Icon className={cn('size-4', selected ? 'text-primary dark:text-accent-foreground' : 'text-muted-foreground')} aria-hidden="true" />
                {label}
                {selected ? <Check className="ml-auto size-4 text-primary dark:text-accent-foreground" aria-hidden="true" /> : null}
              </span>
            </button>
          );
        })}
      </div>
    </SplitSection>
  );
}

function DataCard() {
  const queryClient = useQueryClient();
  const withRecentAuth = useRecentAuth();
  const [confirming, setConfirming] = useState(false);

  const exportData = useMutation({
    mutationFn: exportMyData,
    onSuccess: ({ blob }) => downloadBlob(blob, `thapargenie-export-${new Date().toISOString().slice(0, 10)}.json`),
    onError: (error) => toast.error('Couldn’t export your chats', { description: error.message }),
  });

  const deleteAll = useMutation({
    // Irreversible, so the API asks for a recent sign-in first.
    mutationFn: () => withRecentAuth(deleteAllConversations),
    onSuccess: () => {
      queryClient.removeQueries({ queryKey: ['conversation'] });
      queryClient.invalidateQueries({ queryKey: ['conversations'] });
      setConfirming(false);
      toast.success('All chats deleted');
    },
    onError: (error) => {
      setConfirming(false);
      if (error.code !== 'request_cancelled') toast.error('Couldn’t delete your chats', { description: error.message });
    },
  });

  return (
    <SplitSection icon={Database} title="Your data" description="Chats with no activity for 180 days are deleted automatically.">
      <SectionRow title="Export your chats" description="Download every conversation as a JSON file.">
        <Button variant="outline" onClick={() => exportData.mutate()} disabled={exportData.isPending}>
          <Download /> {exportData.isPending ? 'Preparing…' : 'Export'}
        </Button>
      </SectionRow>
      <SectionRow title="Delete all chats" description="Removes every conversation and your feedback. This can’t be undone.">
        <Button
          variant="outline"
          className="border-destructive/30 text-destructive hover:bg-destructive/10 hover:text-destructive"
          onClick={() => setConfirming(true)}
        >
          <Trash2 /> Delete all
        </Button>
      </SectionRow>
      <ConfirmDialog
        open={confirming}
        onOpenChange={setConfirming}
        title="Delete all chats?"
        description="Every conversation, answer and piece of feedback you’ve given will be permanently deleted. This can’t be undone."
        confirmLabel="Delete everything"
        pendingLabel="Deleting…"
        pending={deleteAll.isPending}
        onConfirm={() => deleteAll.mutate()}
      />
    </SplitSection>
  );
}

function SessionsCard() {
  const withRecentAuth = useRecentAuth();
  const navigate = useNavigate();
  const [confirming, setConfirming] = useState(false);
  const revoke = useMutation({
    mutationFn: () => withRecentAuth(revokeAllSessions),
    onSuccess: async () => {
      toast.success('Signed out on every device');
      await logout().catch(() => {});
      navigate('/login/', { replace: true });
    },
    onError: (error) => {
      setConfirming(false);
      if (error.code !== 'request_cancelled') toast.error('Couldn’t sign out everywhere', { description: error.message });
    },
  });

  return (
    <SplitSection icon={ShieldCheck} title="Security" description="Lost a phone or used a shared computer? End every session at once.">
      <SectionRow title="Sign out on all devices" description="Every device, including this one, will need to sign in again.">
        <Button variant="outline" onClick={() => setConfirming(true)}>
          <MonitorSmartphone /> Sign out everywhere
        </Button>
      </SectionRow>
      <ConfirmDialog
        open={confirming}
        onOpenChange={setConfirming}
        title="Sign out on all devices?"
        description="Every device, including this one, will need to sign in again."
        confirmLabel="Sign out everywhere"
        pendingLabel="Signing out…"
        pending={revoke.isPending}
        onConfirm={() => revoke.mutate()}
      />
    </SplitSection>
  );
}

export default function SettingsPage() {
  return (
    <div className="page-wide space-y-6">
      <PageHeader title="Settings" description="Your account, preferences and data." />
      <ProfileCard />
      <div>
        <PreferencesCard />
        <AppearanceCard />
        <DataCard />
        <SessionsCard />
      </div>
    </div>
  );
}
