import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Check, Copy, Link2, Link2Off } from 'lucide-react';
import { useState } from 'react';
import { toast } from 'sonner';

import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import { chatKeys, createShare, getShare, revokeShare } from '@/lib/api/chat';
import { formatDate } from '@/lib/format';

export function shareUrl(token, origin = window.location.origin) {
  return `${origin}/s/${token}`;
}

/** A 7-day public link to one answer. */
export default function ShareDialog({ message, question, open, onOpenChange }) {
  const queryClient = useQueryClient();
  const [copied, setCopied] = useState(false);
  const key = chatKeys.share(message.id);
  const state = useQuery({ queryKey: key, queryFn: ({ signal }) => getShare(message.id, { signal }), enabled: open });
  const shared = state.data?.share;

  const create = useMutation({
    mutationFn: () => createShare(message.id),
    onSuccess: (share) => queryClient.setQueryData(key, { share }),
    onError: (error) => toast.error('Couldn’t create the link', { description: error.message }),
  });
  const revoke = useMutation({
    mutationFn: () => revokeShare(message.id),
    onSuccess: () => {
      queryClient.setQueryData(key, { share: null });
      toast.success('Link turned off');
    },
    onError: (error) => toast.error('Couldn’t turn the link off', { description: error.message }),
  });

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(shareUrl(shared.token));
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      toast.error('Couldn’t copy. Select the link and copy it instead.');
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Share this answer</DialogTitle>
          <DialogDescription>
            Anyone with the link can see this question and answer, with its sources, for 7 days. Nothing else from your chat is shared, and
            your name isn’t shown.
          </DialogDescription>
        </DialogHeader>

        <div className="rounded-xl border bg-muted/40 p-3 text-sm">
          {question ? <p className="line-clamp-2 font-medium">{question}</p> : null}
          <p className="mt-1 line-clamp-3 text-muted-foreground">{message.content}</p>
        </div>

        {state.isPending ? (
          <Skeleton className="h-10 w-full" />
        ) : shared ? (
          <div className="grid gap-2">
            <div className="flex gap-2">
              <label htmlFor="share-link" className="sr-only">
                Link
              </label>
              <Input id="share-link" readOnly value={shareUrl(shared.token)} onFocus={(event) => event.target.select()} />
              <Button onClick={copy} className="shrink-0">
                {copied ? <Check /> : <Copy />} {copied ? 'Copied' : 'Copy'}
              </Button>
            </div>
            <p className="text-xs text-muted-foreground">Works until {formatDate(shared.expires_at, { day: 'numeric', month: 'long' })}.</p>
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">Check the question doesn’t include anything personal before you share it.</p>
        )}

        <DialogFooter>
          {shared ? (
            <Button variant="outline" onClick={() => revoke.mutate()} disabled={revoke.isPending}>
              <Link2Off /> {revoke.isPending ? 'Turning off…' : 'Stop sharing'}
            </Button>
          ) : (
            <Button onClick={() => create.mutate()} disabled={create.isPending || state.isPending}>
              <Link2 /> {create.isPending ? 'Creating…' : 'Create link'}
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
