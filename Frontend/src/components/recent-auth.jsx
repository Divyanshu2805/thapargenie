import { EmailAuthProvider, reauthenticateWithCredential, reauthenticateWithPopup } from 'firebase/auth';
import { ShieldCheck } from 'lucide-react';
import { createContext, useCallback, useContext, useRef, useState } from 'react';

import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { firebaseAuth, googleAuthProvider } from '@/config/firebase';
import { authErrorMessage } from '@/utils/auth';

// Destructive actions (admin deletes, a student's delete-all, sign-out-everywhere) need a
// sign-in from the last few minutes (the API answers
// `recent_auth_required`). `withRecentAuth(action)` runs the action, asks the admin to
// confirm their identity if the API demands it, then runs it once more.

const RecentAuthContext = createContext(null);

function isRecentAuthError(error) {
  return error?.code === 'recent_auth_required';
}

function usesGoogle(user) {
  return user?.providerData?.some((provider) => provider.providerId === 'google.com');
}

export function RecentAuthProvider({ children }) {
  const [open, setOpen] = useState(false);
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const pending = useRef(null);

  const withRecentAuth = useCallback(async (action) => {
    try {
      return await action();
    } catch (caught) {
      if (!isRecentAuthError(caught)) throw caught;
      await new Promise((resolve, reject) => {
        pending.current = { resolve, reject };
        setPassword('');
        setError('');
        setOpen(true);
      });
      return action();
    }
  }, []);

  const confirm = async (event) => {
    event?.preventDefault();
    const user = firebaseAuth?.currentUser;
    if (!user) return;
    setBusy(true);
    setError('');
    try {
      if (usesGoogle(user)) await reauthenticateWithPopup(user, googleAuthProvider);
      else await reauthenticateWithCredential(user, EmailAuthProvider.credential(user.email, password));
      await user.getIdToken(true);
      setOpen(false);
      pending.current?.resolve();
    } catch (caught) {
      setError(authErrorMessage(caught));
    } finally {
      setBusy(false);
    }
  };

  const cancel = (next) => {
    if (next) return;
    setOpen(false);
    const cancelled = new Error('Confirmation was cancelled.');
    cancelled.code = 'request_cancelled';
    pending.current?.reject(cancelled);
  };

  const google = usesGoogle(firebaseAuth?.currentUser);

  return (
    <RecentAuthContext.Provider value={withRecentAuth}>
      {children}
      <Dialog open={open} onOpenChange={cancel}>
        <DialogContent>
          <form onSubmit={confirm} className="grid gap-4">
            <DialogHeader>
              <span className="icon-nudge mb-1 flex size-10 items-center justify-center rounded-xl bg-accent text-accent-foreground">
                <ShieldCheck className="size-5" aria-hidden="true" />
              </span>
              <DialogTitle>Confirm it’s you</DialogTitle>
              <DialogDescription>
                This action needs a recent sign-in. {google ? 'Continue with your Google account.' : 'Enter your password to continue.'}
              </DialogDescription>
            </DialogHeader>
            {!google ? (
              <div className="grid content-start gap-2">
                <Label htmlFor="reauth-password">Password</Label>
                <Input
                  id="reauth-password"
                  type="password"
                  autoComplete="current-password"
                  autoFocus
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                />
              </div>
            ) : null}
            {error ? (
              <p role="alert" className="text-sm text-destructive">
                {error}
              </p>
            ) : null}
            <DialogFooter>
              <Button variant="outline" onClick={() => cancel(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={busy || (!google && !password)}>
                {busy ? 'Confirming…' : google ? 'Continue with Google' : 'Confirm'}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </RecentAuthContext.Provider>
  );
}

export function useRecentAuth() {
  const context = useContext(RecentAuthContext);
  if (!context) throw new Error('useRecentAuth must be used inside RecentAuthProvider.');
  return context;
}
