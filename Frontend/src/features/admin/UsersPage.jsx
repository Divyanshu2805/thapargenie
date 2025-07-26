import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Ban, CheckCircle2, MailPlus, MoreHorizontal, Search, ShieldCheck, Trash2, UserX, Users } from 'lucide-react';
import { useDeferredValue, useState } from 'react';
import { Link } from 'react-router-dom';
import { toast } from 'sonner';

import { useAuth } from '@/auth/AuthContext';
import { PageHeader } from '@/components/layout/PageHeader';
import { SplitSection } from '@/components/split-section';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select } from '@/components/ui/select';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { EmptyState, ErrorState, LoadMoreButton, StatusBadge, TableSkeleton, useCursorList } from '@/features/admin/components';
import { ELIGIBILITY_STATES } from '@/features/admin/constants';
import { useRecentAuth } from '@/components/recent-auth';
import { ConfirmDialog } from '@/components/confirm-dialog';
import { adminKeys, createInvitation, getSettings, listInvitations, listUsers, revokeInvitation, updateUser } from '@/lib/api/admin';
import { formatDate, formatRelative } from '@/lib/format';

const ACTIONS = {
  approved: { label: 'Approve', icon: CheckCircle2, verb: 'approved' },
  suspended: { label: 'Suspend', icon: Ban, verb: 'suspended' },
  denied: { label: 'Deny', icon: UserX, verb: 'denied' },
};

function SearchBox({ id, value, onChange, placeholder }) {
  return (
    <div className="relative flex-1">
      <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden="true" />
      <label htmlFor={id} className="sr-only">
        {placeholder}
      </label>
      <Input id={id} type="search" className="pl-9" placeholder={placeholder} value={value} onChange={(event) => onChange(event.target.value)} />
    </div>
  );
}

function EligibilityDialog({ target, onClose }) {
  const queryClient = useQueryClient();
  const [reason, setReason] = useState('');
  const action = ACTIONS[target.state];
  const mutation = useMutation({
    mutationFn: () => updateUser(target.user.id, { eligibility_state: target.state, ...(reason.trim() ? { reason: reason.trim() } : {}) }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'users'] });
      toast.success(`${target.user.email} ${action.verb}`);
      onClose();
    },
    onError: (error) => toast.error('Couldn’t change access', { description: error.message }),
  });

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent>
        <form
          className="grid gap-4"
          onSubmit={(event) => {
            event.preventDefault();
            mutation.mutate();
          }}
        >
          <DialogHeader>
            <DialogTitle>
              {action.label} {target.user.email}?
            </DialogTitle>
            <DialogDescription>
              {target.state === 'approved'
                ? 'They will be able to use ThaparGenie right away.'
                : 'They will lose access on their next request. Their chats are kept.'}
            </DialogDescription>
          </DialogHeader>
          <div className="grid content-start gap-2">
            <Label htmlFor="eligibility-reason">Reason (recorded in the audit log)</Label>
            <Input id="eligibility-reason" maxLength={200} value={reason} onChange={(event) => setReason(event.target.value)} />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" variant={target.state === 'approved' ? 'default' : 'destructive'} disabled={mutation.isPending}>
              {mutation.isPending ? 'Saving…' : action.label}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function UsersTab() {
  const { profile } = useAuth();
  const [search, setSearch] = useState('');
  const [state, setState] = useState('');
  const [target, setTarget] = useState(null);
  const q = useDeferredValue(search.trim());
  const filters = { q, eligibilityState: state };
  const list = useCursorList({ queryKey: adminKeys.users(filters), fetchPage: (cursor) => listUsers({ ...filters, cursor }) });

  return (
    <>
      <div className="flex flex-col gap-3 border-b p-4 sm:flex-row">
        <SearchBox id="user-search" value={search} onChange={setSearch} placeholder="Search by email or name" />
        <Select
          aria-label="Access"
          className="sm:w-44"
          value={state}
          onChange={(event) => setState(event.target.value)}
          placeholder="Any access"
          options={Object.entries(ELIGIBILITY_STATES).map(([value, label]) => ({ value, label }))}
        />
      </div>
      {list.isPending ? (
        <TableSkeleton />
      ) : list.isError ? (
        <ErrorState error={list.error} onRetry={() => list.refetch()} />
      ) : list.rows.length === 0 ? (
        <EmptyState icon={Users} title="No users found">
          Students appear here after their first sign-in.
        </EmptyState>
      ) : (
        <>
          <Table>
            <TableHeader>
              <TableRow className="hover:bg-transparent">
                <TableHead>User</TableHead>
                <TableHead>Access</TableHead>
                <TableHead className="hidden @2xl:table-cell">Joined</TableHead>
                <TableHead>
                  <span className="sr-only">Actions</span>
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {list.rows.map((user) => {
                const name = [user.first_name, user.last_name].filter(Boolean).join(' ');
                const isSelf = user.email === profile?.email;
                return (
                  <TableRow key={user.id}>
                    <TableCell>
                      <p className="font-medium">{name || user.email}</p>
                      {name ? <p className="text-xs text-muted-foreground">{user.email}</p> : null}
                    </TableCell>
                    <TableCell>
                      <div className="flex flex-wrap items-center gap-1.5">
                        <StatusBadge status={user.eligibility_state} />
                        {user.is_staff ? (
                          <Badge variant="gold">
                            <ShieldCheck /> Admin
                          </Badge>
                        ) : null}
                        {!user.is_active ? <Badge variant="secondary">Inactive</Badge> : null}
                      </div>
                    </TableCell>
                    <TableCell className="hidden text-muted-foreground @2xl:table-cell">{formatDate(user.date_joined)}</TableCell>
                    <TableCell className="text-right">
                      {isSelf ? (
                        <span className="text-xs text-muted-foreground">You</span>
                      ) : (
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <Button variant="ghost" size="icon-sm" aria-label={`Change access for ${user.email}`}>
                              <MoreHorizontal />
                            </Button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end">
                            {Object.entries(ACTIONS)
                              .filter(([value]) => value !== user.eligibility_state)
                              .map(([value, action]) => (
                                <DropdownMenuItem
                                  key={value}
                                  variant={value === 'approved' ? 'default' : 'destructive'}
                                  onSelect={() => setTarget({ user, state: value })}
                                >
                                  <action.icon /> {action.label}
                                </DropdownMenuItem>
                              ))}
                          </DropdownMenuContent>
                        </DropdownMenu>
                      )}
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
          <LoadMoreButton query={list} />
        </>
      )}
      {target ? <EligibilityDialog target={target} onClose={() => setTarget(null)} /> : null}
    </>
  );
}

function InviteForm() {
  const queryClient = useQueryClient();
  const [email, setEmail] = useState('');
  const [days, setDays] = useState('30');
  const invite = useMutation({
    mutationFn: () => createInvitation({ email: email.trim(), ...(days ? { expires_in_days: Number(days) } : {}) }),
    onSuccess: (created) => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'invitations'] });
      toast.success(`Invited ${created.email}`, { description: 'They are approved as soon as they sign in with this email.' });
      setEmail('');
    },
    onError: (error) => toast.error('Couldn’t invite', { description: error.message }),
  });
  return (
    <form
      className="flex flex-col gap-3 border-b p-4 sm:flex-row sm:items-end"
      onSubmit={(event) => {
        event.preventDefault();
        if (email.trim()) invite.mutate();
      }}
    >
      <div className="grid flex-1 gap-2">
        <Label htmlFor="invite-email">Invite by email</Label>
        <Input id="invite-email" type="email" autoComplete="off" placeholder="student@thapar.edu" value={email} onChange={(event) => setEmail(event.target.value)} />
      </div>
      <div className="grid gap-2 sm:w-40">
        <Label htmlFor="invite-expiry">Expires</Label>
        <Select
          id="invite-expiry"
          value={days}
          onChange={(event) => setDays(event.target.value)}
          options={[
            { value: '7', label: 'In 7 days' },
            { value: '30', label: 'In 30 days' },
            { value: '90', label: 'In 90 days' },
            { value: '365', label: 'In a year' },
            { value: '', label: 'Never' },
          ]}
        />
      </div>
      <Button type="submit" disabled={!email.trim() || invite.isPending}>
        <MailPlus /> {invite.isPending ? 'Inviting…' : 'Invite'}
      </Button>
    </form>
  );
}

function InvitationsTab() {
  const queryClient = useQueryClient();
  const withRecentAuth = useRecentAuth();
  const [search, setSearch] = useState('');
  const [revoking, setRevoking] = useState(null);
  const q = useDeferredValue(search.trim());
  const list = useCursorList({ queryKey: adminKeys.invitations(q), fetchPage: (cursor) => listInvitations({ q, cursor }) });

  const revoke = useMutation({
    mutationFn: (invitation) => withRecentAuth(() => revokeInvitation(invitation.id)),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'invitations'] });
      toast.success('Invitation revoked');
      setRevoking(null);
    },
    onError: (error) => {
      setRevoking(null);
      if (error.code !== 'request_cancelled') toast.error('Couldn’t revoke', { description: error.message });
    },
  });

  return (
    <>
      <InviteForm />
      <div className="border-b p-4">
        <SearchBox id="invite-search" value={search} onChange={setSearch} placeholder="Search invitations" />
      </div>
      {list.isPending ? (
        <TableSkeleton rows={4} />
      ) : list.isError ? (
        <ErrorState error={list.error} onRetry={() => list.refetch()} />
      ) : list.rows.length === 0 ? (
        <EmptyState icon={MailPlus} title="No invitations">
          Invited emails are approved automatically on their first sign-in.
        </EmptyState>
      ) : (
        <>
          <Table>
            <TableHeader>
              <TableRow className="hover:bg-transparent">
                <TableHead>Email</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="hidden @2xl:table-cell">Expires</TableHead>
                <TableHead className="hidden @2xl:table-cell">Created</TableHead>
                <TableHead>
                  <span className="sr-only">Actions</span>
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {list.rows.map((invitation) => (
                <TableRow key={invitation.id}>
                  <TableCell className="font-medium">{invitation.email}</TableCell>
                  <TableCell>
                    <StatusBadge status={invitation.status} />
                  </TableCell>
                  <TableCell className="hidden text-muted-foreground @2xl:table-cell">
                    {invitation.expires_at ? formatDate(invitation.expires_at) : 'Never'}
                  </TableCell>
                  <TableCell className="hidden text-muted-foreground @2xl:table-cell">{formatRelative(invitation.created_at)}</TableCell>
                  <TableCell className="text-right">
                    {invitation.status === 'pending' ? (
                      <Button variant="ghost" size="icon-sm" aria-label={`Revoke invitation for ${invitation.email}`} onClick={() => setRevoking(invitation)}>
                        <Trash2 />
                      </Button>
                    ) : null}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          <LoadMoreButton query={list} />
        </>
      )}
      <ConfirmDialog
        open={Boolean(revoking)}
        onOpenChange={(open) => !open && setRevoking(null)}
        title="Revoke this invitation?"
        description={revoking ? `${revoking.email} will no longer be approved automatically.` : ''}
        confirmLabel="Revoke"
        pendingLabel="Revoking…"
        pending={revoke.isPending}
        onConfirm={() => revoke.mutate(revoking)}
      />
    </>
  );
}

export default function UsersPage() {
  const settings = useQuery({ queryKey: adminKeys.settings, queryFn: getSettings });
  const open = settings.data?.require_approval === false;
  return (
    <div className="page-wide space-y-6">
      <PageHeader
        title="Users & invites"
        description="Approve, suspend or deny accounts. Every change is audited."
      />
      {open ? (
        <p role="status" className="rounded-lg border border-gold/30 bg-gold-soft px-4 py-3 text-sm">
          Open access: new users with a verified email are approved automatically.{' '}
          <Link to="/admin/settings" className="font-medium underline underline-offset-4">
            Change in Settings
          </Link>
        </p>
      ) : null}
      <div>
        <SplitSection
          icon={Users}
          title="Users"
          description="Everyone who has signed in. Approve, suspend or deny access; you can't change your own."
          flush
        >
          <UsersTab />
        </SplitSection>
        <SplitSection
          icon={MailPlus}
          title="Invitations"
          description="An invited email is approved automatically the first time it signs in with a verified address."
          flush
        >
          <InvitationsTab />
        </SplitSection>
      </div>
    </div>
  );
}
