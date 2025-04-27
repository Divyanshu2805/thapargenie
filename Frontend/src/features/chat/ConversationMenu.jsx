import { useMutation, useQueryClient } from '@tanstack/react-query';
import { MoreHorizontal, Pencil, Trash2 } from 'lucide-react';
import { useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { toast } from 'sonner';

import { ConfirmDialog } from '@/components/confirm-dialog';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Input } from '@/components/ui/input';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { chatKeys, deleteConversation, updateConversation } from '@/lib/api/chat';
import { cn } from '@/lib/utils';

function useConversationActions(conversation) {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const { conversationId: openId } = useParams();

  const refresh = (updated) => {
    if (updated) queryClient.setQueryData(chatKeys.conversation(updated.id), updated);
    queryClient.invalidateQueries({ queryKey: ['conversations'] });
    queryClient.invalidateQueries({ queryKey: chatKeys.messages(conversation.id) });
  };

  const update = useMutation({
    mutationFn: (changes) => updateConversation(conversation.id, changes),
    onSuccess: refresh,
    onError: (error) => toast.error('Couldn’t update the chat', { description: error.message }),
  });

  const remove = useMutation({
    mutationFn: () => deleteConversation(conversation.id),
    onSuccess: () => {
      queryClient.removeQueries({ queryKey: chatKeys.conversation(conversation.id) });
      queryClient.invalidateQueries({ queryKey: ['conversations'] });
      if (openId === conversation.id) navigate('/chat/', { replace: true });
      toast.success('Chat deleted');
    },
    onError: (error) => toast.error('Couldn’t delete the chat', { description: error.message }),
  });

  return { update, remove };
}

function RenameDialog({ conversation, open, onOpenChange, onRename }) {
  const [title, setTitle] = useState(conversation.title || '');
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Rename chat</DialogTitle>
        </DialogHeader>
        <form
          className="grid gap-4"
          onSubmit={(event) => {
            event.preventDefault();
            const value = title.trim();
            if (value) onRename(value);
          }}
        >
          <label htmlFor="rename-title" className="sr-only">
            Title
          </label>
          <Input id="rename-title" autoFocus value={title} maxLength={120} onChange={(event) => setTitle(event.target.value)} />
          <DialogFooter>
            <Button variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={!title.trim()}>
              Save
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

export default function ConversationMenu({ conversation, className, align = 'end' }) {
  const { update, remove } = useConversationActions(conversation);
  const [dialog, setDialog] = useState(null);
  const title = conversation.title || 'New conversation';

  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <button
            type="button"
            aria-label={`Options for ${title}`}
            className={cn(
              'icon-nudge flex size-7 shrink-0 items-center justify-center rounded-md text-muted-foreground transition-colors outline-none hover:bg-black/5 hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring/50 data-[state=open]:bg-black/5 dark:hover:bg-white/10 dark:data-[state=open]:bg-white/10',
              className,
            )}
          >
            <MoreHorizontal className="size-4" />
          </button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align={align} className="w-48">
          <DropdownMenuItem onSelect={() => setDialog('rename')}>
            <Pencil /> Rename
          </DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuItem variant="destructive" onSelect={() => setDialog('delete')}>
            <Trash2 /> Delete
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>

      {dialog === 'rename' ? (
        <RenameDialog
          open
          conversation={conversation}
          onOpenChange={(open) => !open && setDialog(null)}
          onRename={(value) => update.mutate({ title: value }, { onSuccess: () => setDialog(null) })}
        />
      ) : null}
      <ConfirmDialog
        open={dialog === 'delete'}
        onOpenChange={(open) => !open && setDialog(null)}
        title="Delete this chat?"
        description={`“${title}” and all its answers will be permanently deleted.`}
        confirmLabel="Delete"
        pendingLabel="Deleting…"
        pending={remove.isPending}
        onConfirm={() => remove.mutate(undefined, { onSettled: () => setDialog(null) })}
      />
    </>
  );
}

function ToolbarButton({ label, onClick, danger, children }) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <button
          type="button"
          aria-label={label}
          onClick={onClick}
          className={cn(
            'icon-nudge flex size-9 items-center justify-center rounded-lg text-muted-foreground transition-[background-color,color,scale] duration-150 outline-none hover:bg-hover hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring/50 active:scale-90 [&_svg]:size-[18px]',
            danger && 'hover:bg-destructive/10 hover:text-destructive',
          )}
        >
          {children}
        </button>
      </TooltipTrigger>
      <TooltipContent side="bottom">{label}</TooltipContent>
    </Tooltip>
  );
}

/**
 * The chat's actions as icons in its header (desktop). `group="start"` holds rename
 * (beside the title); `group="end"` holds delete (right edge).
 */
export function ConversationToolbar({ conversation, group }) {
  const { update, remove } = useConversationActions(conversation);
  const [dialog, setDialog] = useState(null);
  const title = conversation.title || 'New conversation';
  return (
    <div className="flex shrink-0 items-center gap-0.5">
      {group === 'start' ? (
        <>
          <ToolbarButton label="Rename" onClick={() => setDialog('rename')}>
            <Pencil />
          </ToolbarButton>
        </>
      ) : (
        <>
          <ToolbarButton label="Delete" danger onClick={() => setDialog('delete')}>
            <Trash2 />
          </ToolbarButton>
        </>
      )}
      {dialog === 'rename' ? (
        <RenameDialog
          open
          conversation={conversation}
          onOpenChange={(open) => !open && setDialog(null)}
          onRename={(value) => update.mutate({ title: value }, { onSuccess: () => setDialog(null) })}
        />
      ) : null}
      <ConfirmDialog
        open={dialog === 'delete'}
        onOpenChange={(open) => !open && setDialog(null)}
        title="Delete this chat?"
        description={`“${title}” and all its answers will be permanently deleted.`}
        confirmLabel="Delete"
        pendingLabel="Deleting…"
        pending={remove.isPending}
        onConfirm={() => remove.mutate(undefined, { onSettled: () => setDialog(null) })}
      />
    </div>
  );
}

/** Rename a chat in place (double-click its name in the sidebar). */
export function InlineRename({ conversation, onDone }) {
  const { update } = useConversationActions(conversation);
  const [title, setTitle] = useState(conversation.title || '');
  const finish = (save) => {
    const value = title.trim();
    if (save && value && value !== conversation.title) update.mutate({ title: value });
    onDone();
  };
  return (
    <input
      autoFocus
      aria-label="Chat name"
      value={title}
      maxLength={120}
      onChange={(event) => setTitle(event.target.value)}
      onFocus={(event) => event.target.select()}
      onBlur={() => finish(true)}
      onKeyDown={(event) => {
        if (event.key === 'Enter') finish(true);
        if (event.key === 'Escape') finish(false);
      }}
      className="h-9 w-full rounded-lg border border-ring bg-card px-2.5 text-sm ring-4 ring-ring/15 outline-none"
    />
  );
}
