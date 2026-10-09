import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Copy, Download, KeyRound, ShieldCheck } from 'lucide-react';
import qrcode from 'qrcode-generator';
import { useEffect, useMemo, useState } from 'react';
import { toast } from 'sonner';

import { useRecentAuth } from '@/components/recent-auth';
import { SectionRow, SplitSection } from '@/components/split-section';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Skeleton } from '@/components/ui/skeleton';
import { ErrorState } from '@/features/admin/components';
import {
  adminKeys,
  confirmTwoFactor,
  getTwoFactorStatus,
  newRecoveryCodes,
  setUpTwoFactor,
  verifyTwoFactor,
} from '@/lib/api/admin';
import { downloadBlob } from '@/lib/download';

// The admin dashboard's second sign-in step. Staff add ThaparGenie to an authenticator
// app once, then enter a code after each sign-in (the API refuses admin requests until
// they do). Everything under /admin renders inside <TwoFactorGate>.

/** Any admin request can find the check has expired; these codes send the gate back to it. */
export function isTwoFactorError(error) {
  return error?.code === 'second_factor_required' || error?.code === 'second_factor_setup_required';
}

/** Which screen the gate shows for a status from the API. */
export function gateStep(status) {
  if (!status?.required || status.verified) return 'open';
  return status.enrolled ? 'verify' : 'enrol';
}

/** "ABCD EFGH IJKL …": the key in groups of four, easier to type into an app. */
export function groupKey(secret) {
  return (secret || '').replace(/(.{4})/g, '$1 ').trim();
}

function QrCode({ value }) {
  const { size, path } = useMemo(() => {
    const code = qrcode(0, 'M');
    code.addData(value);
    code.make();
    const count = code.getModuleCount();
    let d = '';
    for (let row = 0; row < count; row += 1) {
      for (let column = 0; column < count; column += 1) {
        if (code.isDark(row, column)) d += `M${column} ${row}h1v1h-1z`;
      }
    }
    return { size: count, path: d };
  }, [value]);
  // Always dark on white with a quiet border, whatever the theme: cameras need the contrast.
  return (
    <svg
      role="img"
      aria-label="QR code to scan with your authenticator app"
      viewBox={`-4 -4 ${size + 8} ${size + 8}`}
      className="size-44 shrink-0 rounded-xl bg-white"
      shapeRendering="crispEdges"
    >
      <path d={path} fill="#000" />
    </svg>
  );
}

function Shell({ icon: Icon = ShieldCheck, title, children }) {
  return (
    <div className="mx-auto w-full max-w-lg px-4 py-10 sm:py-16">
      <div className="rounded-2xl border bg-card p-6 text-center shadow-soft sm:p-8">
        <span className="mx-auto flex size-10 items-center justify-center rounded-xl bg-accent text-accent-foreground">
          <Icon className="size-[18px]" aria-hidden="true" />
        </span>
        <h1 className="mt-4 text-heading">{title}</h1>
        {children}
      </div>
    </div>
  );
}

function CodeField({ id, label, value, onChange, error, recovery, autoFocus = true }) {
  return (
    <div className="grid gap-2">
      <Label htmlFor={id} className="justify-center">
        {label}
      </Label>
      <Input
        id={id}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        autoFocus={autoFocus}
        autoComplete="one-time-code"
        inputMode={recovery ? 'text' : 'numeric'}
        maxLength={recovery ? 12 : 9}
        placeholder={recovery ? 'ABCD-EFGH' : '123456'}
        aria-invalid={Boolean(error)}
        aria-describedby={error ? `${id}-error` : undefined}
        className="text-center font-mono text-base tracking-widest"
      />
      {error ? (
        <p id={`${id}-error`} role="alert" className="text-xs text-destructive">
          {error}
        </p>
      ) : null}
    </div>
  );
}

function BackupCodes({ codes, onDone }) {
  const text = `ThaparGenie backup codes\nEach code works once.\n\n${codes.join('\n')}\n`;
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(codes.join('\n'));
      toast.success('Backup codes copied');
    } catch {
      toast.error('Couldn’t copy. Select the codes and copy them by hand.');
    }
  };
  return (
    <Shell icon={KeyRound} title="Save your backup codes">
      <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
        If you lose your phone, one of these gets you in. Each works once. They are shown only now, so keep them somewhere safe, away from your
        password.
      </p>
      <ul aria-label="Backup codes" className="mt-5 grid grid-cols-2 gap-2 rounded-xl bg-muted p-4 font-mono text-sm">
        {codes.map((code) => (
          <li key={code}>{code}</li>
        ))}
      </ul>
      <div className="mt-4 flex flex-wrap justify-center gap-2">
        <Button type="button" variant="outline" size="sm" onClick={copy}>
          <Copy /> Copy
        </Button>
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={() => downloadBlob(new Blob([text], { type: 'text/plain;charset=utf-8' }), 'thapargenie-backup-codes.txt')}
        >
          <Download /> Download
        </Button>
      </div>
      <Button type="button" className="mt-6 w-full" onClick={onDone}>
        I’ve saved them
      </Button>
    </Shell>
  );
}

function Enrol({ onEnrolled }) {
  const [code, setCode] = useState('');
  const setup = useMutation({ mutationFn: setUpTwoFactor });
  const { mutate: start } = setup;
  useEffect(() => {
    start();
  }, [start]);

  const confirm = useMutation({
    mutationFn: () => confirmTwoFactor(code),
    onSuccess: (data) => onEnrolled(data),
  });

  if (setup.isError) {
    return (
      <Shell title="Set up two-factor sign-in">
        <ErrorState error={setup.error} onRetry={() => setup.mutate()} />
      </Shell>
    );
  }

  return (
    <Shell title="Set up two-factor sign-in">
      <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
        The admin dashboard needs a second step after your password. You set it up once, then enter a 6-digit code from your phone when you sign
        in.
      </p>
      <ol className="mt-6 space-y-6 text-sm">
        <li>
          <p className="font-semibold">1. Open an authenticator app</p>
          <p className="mt-1 text-muted-foreground">Google Authenticator, Microsoft Authenticator, Authy or a password manager all work.</p>
        </li>
        <li>
          <p className="font-semibold">2. Scan this code, or type the key</p>
          {setup.data ? (
            <div className="mt-3 flex flex-col items-center gap-4">
              <QrCode value={setup.data.otpauth_uri} />
              <div className="min-w-0">
                <p className="text-xs text-muted-foreground">Key</p>
                <p className="mt-1 font-mono text-sm break-words select-all">{groupKey(setup.data.secret)}</p>
              </div>
            </div>
          ) : (
            <Skeleton className="mx-auto mt-3 size-44 rounded-xl" aria-label="Loading the QR code" />
          )}
        </li>
        <li>
          <p className="font-semibold">3. Enter the code the app shows</p>
          <form
            className="mt-3 grid gap-3"
            onSubmit={(event) => {
              event.preventDefault();
              if (code.trim()) confirm.mutate();
            }}
          >
            <CodeField
              id="two-factor-setup-code"
              label="6-digit code"
              value={code}
              onChange={setCode}
              error={confirm.error?.message}
              autoFocus={false}
            />
            <Button type="submit" disabled={!setup.data || !code.trim() || confirm.isPending}>
              {confirm.isPending ? 'Checking…' : 'Turn on two-factor'}
            </Button>
          </form>
        </li>
      </ol>
    </Shell>
  );
}

function Verify({ status, onVerified }) {
  const [code, setCode] = useState('');
  const [recovery, setRecovery] = useState(false);
  const verify = useMutation({
    mutationFn: () => verifyTwoFactor(recovery ? { recovery_code: code.trim() } : { code: code.trim() }),
    onSuccess: onVerified,
  });
  const { reset } = verify;
  const switchMode = () => {
    setRecovery((value) => !value);
    setCode('');
    reset();
  };

  return (
    <Shell title="Enter your code">
      <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
        {recovery
          ? 'Enter one of the backup codes you saved when you set this up. It works once.'
          : 'Open your authenticator app and enter the 6-digit code for ThaparGenie.'}
      </p>
      <form
        className="mt-6 grid gap-3"
        onSubmit={(event) => {
          event.preventDefault();
          if (code.trim()) verify.mutate();
        }}
      >
        <CodeField
          key={recovery ? 'recovery' : 'code'}
          id="two-factor-code"
          label={recovery ? 'Backup code' : '6-digit code'}
          value={code}
          onChange={setCode}
          error={verify.error?.message}
          recovery={recovery}
        />
        <Button type="submit" disabled={!code.trim() || verify.isPending}>
          {verify.isPending ? 'Checking…' : 'Continue'}
        </Button>
      </form>
      <button
        type="button"
        onClick={switchMode}
        className="mt-4 rounded text-sm text-muted-foreground underline-offset-4 outline-none hover:text-foreground hover:underline focus-visible:ring-2 focus-visible:ring-ring/50"
      >
        {recovery ? 'Use the authenticator app instead' : 'Lost your phone? Use a backup code'}
      </button>
      {recovery ? (
        <p className="mt-3 text-xs leading-relaxed text-muted-foreground">
          {status.recovery_codes_left} backup {status.recovery_codes_left === 1 ? 'code is' : 'codes are'} left. With none left, ask the owner to
          reset two-factor for your account.
        </p>
      ) : null}
    </Shell>
  );
}

export default function TwoFactorGate({ children }) {
  const queryClient = useQueryClient();
  const status = useQuery({ queryKey: adminKeys.twoFactor, queryFn: getTwoFactorStatus, staleTime: 60_000 });
  // Backup codes are shown once, right after enrolling, before the dashboard opens.
  const [codes, setCodes] = useState(null);

  // The check lasts some hours. When it runs out mid-visit, the next admin request is
  // refused with a two-factor code: ask again instead of leaving a page of errors.
  useEffect(() => {
    const recheck = (event) => {
      const error = event?.query?.state?.error || event?.mutation?.state?.error;
      if (isTwoFactorError(error)) queryClient.invalidateQueries({ queryKey: adminKeys.twoFactor });
    };
    const offQueries = queryClient.getQueryCache().subscribe(recheck);
    const offMutations = queryClient.getMutationCache().subscribe(recheck);
    return () => {
      offQueries();
      offMutations();
    };
  }, [queryClient]);

  const accept = (next) => {
    queryClient.setQueryData(adminKeys.twoFactor, next);
    // Whatever was refused while the gate was closed loads now.
    queryClient.invalidateQueries({ queryKey: ['admin'], predicate: (query) => query.queryKey[1] !== 'two-factor' });
  };

  if (status.isPending) {
    return (
      <div className="page-wide space-y-4" aria-busy="true" aria-label="Loading">
        <Skeleton className="h-8 w-56" />
        <Skeleton className="h-4 w-80" />
      </div>
    );
  }
  if (status.isError) return <ErrorState error={status.error} onRetry={() => status.refetch()} />;
  if (codes) return <BackupCodes codes={codes} onDone={() => setCodes(null)} />;

  const step = gateStep(status.data);
  if (step === 'enrol') {
    return (
      <Enrol
        onEnrolled={(data) => {
          setCodes(data.recovery_codes);
          accept(data.status);
        }}
      />
    );
  }
  if (step === 'verify') return <Verify status={status.data} onVerified={accept} />;
  return children;
}

/** On the admin Settings page: how many backup codes are left, and a way to get new ones. */
export function TwoFactorSettings() {
  const queryClient = useQueryClient();
  const withRecentAuth = useRecentAuth();
  const status = useQuery({ queryKey: adminKeys.twoFactor, queryFn: getTwoFactorStatus, staleTime: 60_000 });
  const [codes, setCodes] = useState(null);
  const renew = useMutation({
    mutationFn: () => withRecentAuth(newRecoveryCodes),
    onSuccess: (data) => {
      setCodes(data.recovery_codes);
      queryClient.setQueryData(adminKeys.twoFactor, data.status);
    },
    onError: (error) => toast.error('Couldn’t make new backup codes', { description: error.message }),
  });

  if (!status.data?.enrolled) return null;
  const left = status.data.recovery_codes_left;
  return (
    <SplitSection icon={ShieldCheck} title="Your two-factor sign-in" description="The code from your authenticator app, asked after you sign in.">
      <SectionRow
        title={`On · asked again after ${status.data.session_hours} hours`}
        description={`${left} backup ${left === 1 ? 'code' : 'codes'} left. New codes replace the old ones.`}
      >
        <Button type="button" variant="outline" size="sm" disabled={renew.isPending} onClick={() => renew.mutate()}>
          <KeyRound /> New backup codes
        </Button>
      </SectionRow>
      {codes ? (
        <div className="px-5 py-4 sm:px-6">
          <p className="text-[13px] leading-relaxed text-muted-foreground">Save these now. They are not shown again.</p>
          <ul aria-label="Backup codes" className="mt-3 grid grid-cols-2 gap-2 rounded-xl bg-muted p-4 font-mono text-sm sm:grid-cols-5">
            {codes.map((code) => (
              <li key={code}>{code}</li>
            ))}
          </ul>
          <Button type="button" variant="ghost" size="sm" className="mt-3" onClick={() => setCodes(null)}>
            I’ve saved them
          </Button>
        </div>
      ) : null}
    </SplitSection>
  );
}
