import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { MessagesSquare } from 'lucide-react';
import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom';
import { toast } from 'sonner';

import { usePageTopbar } from '@/components/layout/SidebarLayout';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { composerBlock } from '@/features/chat/ChatHome';
import Composer from '@/features/chat/Composer';
import ConversationMenu, { ConversationToolbar } from '@/features/chat/ConversationMenu';
import { AssistantMessage, UserMessage } from '@/features/chat/Message';
import { buildThread, hasStreamingMessage } from '@/features/chat/thread';
import { useAskStream } from '@/features/chat/use-ask-stream';
import { useAppConfig } from '@/hooks/use-app-config';
import { chatKeys, clearFeedback, getMessages, setFeedback } from '@/lib/api/chat';

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const NEAR_BOTTOM_PX = 120;

function NotFound() {
  return (
    <div className="flex min-h-full flex-col items-center justify-center px-6 py-16 text-center">
      <span className="flex size-14 items-center justify-center rounded-2xl bg-accent text-accent-foreground">
        <MessagesSquare className="size-6" aria-hidden="true" />
      </span>
      <h1 className="mt-5 text-title">Conversation not found</h1>
      <p className="mt-2 max-w-sm text-sm text-muted-foreground">It may have been deleted, or the link is incorrect.</p>
      <Button asChild className="mt-6">
        <Link to="/chat/">Start a new chat</Link>
      </Button>
    </div>
  );
}

function ThreadSkeleton() {
  return (
    <div className="chat-column space-y-8 py-10" aria-busy="true" aria-label="Loading conversation">
      <Skeleton className="ml-auto h-11 w-1/2 rounded-2xl" />
      <div className="flex gap-4">
        <Skeleton className="size-7 rounded-lg" />
        <div className="flex-1 space-y-2.5">
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-11/12" />
          <Skeleton className="h-4 w-3/5" />
        </div>
      </div>
    </div>
  );
}

function ConversationView({ conversationId }) {
  const queryClient = useQueryClient();
  const location = useLocation();
  const navigate = useNavigate();
  const { data: config } = useAppConfig();
  const [draft, setDraft] = useState('');
  const scrollRef = useRef(null);
  const stickToBottom = useRef(true);
  const inputRef = useRef(null);

  const messagesKey = chatKeys.messages(conversationId);

  const refreshAfterTurn = useCallback(async () => {
    await queryClient.invalidateQueries({ queryKey: messagesKey });
    queryClient.invalidateQueries({ queryKey: ['conversations'] });
    // The generated title arrives some seconds after the first answer (how long depends on
    // the model), so look again a few times; the header follows the list (below).
    for (const delay of [2500, 6000, 12000, 20000]) {
      window.setTimeout(() => queryClient.invalidateQueries({ queryKey: ['conversations'] }), delay);
    }
  }, [queryClient, messagesKey]);

  // One title everywhere: whenever the sidebar list brings a newer title for this chat,
  // copy it into this page's data so the header matches the sidebar.
  useEffect(
    () =>
      queryClient.getQueryCache().subscribe((event) => {
        if (event.type !== 'updated' || event.query.queryKey[0] !== 'conversations') return;
        const listed = event.query.state.data?.pages
          ?.flatMap((page) => page.results || [])
          .find((item) => item.id === conversationId);
        if (!listed) return;
        queueMicrotask(() =>
          queryClient.setQueryData(chatKeys.messages(conversationId), (current) =>
            current?.conversation && current.conversation.title !== listed.title
              ? { ...current, conversation: { ...current.conversation, title: listed.title } }
              : current,
          ),
        );
      }),
    [queryClient, conversationId],
  );

  const stream = useAskStream({
    onEvent: (event, data) => {
      if ((event === 'meta' || event === 'done') && typeof data.remaining_today === 'number') {
        queryClient.setQueryData(chatKeys.appConfig, (current) =>
          current ? { ...current, remaining_today: data.remaining_today } : current,
        );
      }
    },
    onSettled: async ({ accepted }) => {
      if (!accepted) return; // Nothing was saved; keep the error and the question on screen.
      await refreshAfterTurn();
      stream.reset();
    },
  });
  const streaming = stream.state.phase === 'streaming';

  const { data, isPending, isError } = useQuery({
    queryKey: messagesKey,
    queryFn: ({ signal }) => getMessages(conversationId, { signal }),
    // Another tab (or a just-stopped stream) may still be finishing an answer.
    refetchInterval: (query) => (!streaming && hasStreamingMessage(query.state.data?.messages) ? 2000 : false),
  });

  // A question handed over from the home page streams once, then leaves the history entry.
  const handedOff = useRef(false);
  useEffect(() => {
    const question = location.state?.ask;
    if (!question || handedOff.current) return;
    handedOff.current = true;
    navigate(location.pathname, { replace: true, state: null });
    stream.ask(conversationId, question);
  }, [location.state, location.pathname, navigate, conversationId, stream]);

  const feedback = useMutation({
    mutationFn: ({ messageId, value }) => (value ? setFeedback(messageId, value) : clearFeedback(messageId)),
    onMutate: async ({ messageId, value }) => {
      await queryClient.cancelQueries({ queryKey: messagesKey });
      const previous = queryClient.getQueryData(messagesKey);
      queryClient.setQueryData(messagesKey, (current) =>
        current && {
          ...current,
          messages: current.messages.map((message) =>
            message.id === messageId ? { ...message, feedback: value ? { reason: null, comment: '', ...value } : null } : message,
          ),
        },
      );
      return { previous };
    },
    onSuccess: (_result, { value }) => {
      if (value?.rating === -1) toast.success('Thanks — your feedback was sent');
    },
    onError: (error, _variables, context) => {
      queryClient.setQueryData(messagesKey, context?.previous);
      toast.error('Couldn’t save feedback', { description: error.message });
    },
  });

  const handleStop = () => {
    stream.stop();
    // The server saves the partial answer as "stopped"; the refetch interval picks it up.
    window.setTimeout(async () => {
      await queryClient.invalidateQueries({ queryKey: messagesKey });
      stream.reset();
    }, 700);
  };

  const thread = buildThread(data?.messages, stream.state);

  // Follow the answer while it streams, unless the reader has scrolled up.
  const onScroll = () => {
    const node = scrollRef.current;
    if (node) stickToBottom.current = node.scrollHeight - node.scrollTop - node.clientHeight < NEAR_BOTTOM_PX;
  };
  const lastContent = thread.at(-1)?.content?.length ?? 0;
  useLayoutEffect(() => {
    const node = scrollRef.current;
    if (node && stickToBottom.current) node.scrollTop = node.scrollHeight;
  }, [thread.length, lastContent, stream.state.stage]);

  // The answer keeps growing after its text arrives (the typing reveal, sources, actions),
  // so follow the thread's height itself, not just incoming data.
  const threadRef = useRef(null);
  useEffect(() => {
    const node = scrollRef.current;
    const content = threadRef.current;
    if (!node || !content || typeof ResizeObserver === 'undefined') return undefined;
    const observer = new ResizeObserver(() => {
      if (stickToBottom.current) node.scrollTop = node.scrollHeight;
    });
    observer.observe(content);
    return () => observer.disconnect();
  }, [isPending]);

  const topbarConversation = data?.conversation;
  const topbarActions = useMemo(
    () => (topbarConversation ? <ConversationMenu conversation={topbarConversation} /> : null),
    [topbarConversation],
  );
  usePageTopbar(topbarConversation ? topbarConversation.title || 'New conversation' : '', topbarActions);

  if (isError) return <NotFound />;

  const conversation = data?.conversation;
  const blocked = composerBlock(config);
  const busy = streaming;
  const lastIndex = thread.length - 1;

  const submit = () => {
    const content = draft.trim();
    if (!content) return;
    setDraft('');
    stickToBottom.current = true;
    stream.ask(conversationId, content);
  };

  return (
    <div className="flex h-full flex-col print:block print:h-auto">
      <div className="hidden h-16 shrink-0 items-center gap-2 border-b px-6 md:flex print:hidden">
        <h1 className="min-w-0 truncate text-base font-semibold tracking-tight">
          {conversation ? conversation.title || 'New conversation' : <Skeleton className="h-4 w-48" />}
        </h1>
        {conversation ? <ConversationToolbar conversation={conversation} group="start" /> : null}
        <div className="flex-1" />
        {conversation ? <ConversationToolbar conversation={conversation} group="end" /> : null}
      </div>

      <div ref={scrollRef} onScroll={onScroll} className="scrollbar-thin min-h-0 flex-1 overflow-y-auto print:overflow-visible">
        {isPending && !thread.length ? (
          <ThreadSkeleton />
        ) : (
          <div ref={threadRef} className="chat-column space-y-8 pt-6 pb-10 sm:pt-8">
            {thread.map((message, index) =>
              message.role === 'user' ? (
                <UserMessage
                  key={message.key || message.id}
                  message={message}
                  busy={busy}
                />
              ) : (
                <AssistantMessage
                  key={message.key || message.id}
                  message={message}
                  question={thread[index - 1]?.role === 'user' ? thread[index - 1].content : ''}
                  busy={busy}
                  isLast={index === lastIndex}
                  onFeedback={(messageId, value) => feedback.mutate({ messageId, value })}
                  onRetry={stream.retry}
                />
              ),
            )}
          </div>
        )}
      </div>

      <div className="shrink-0 bg-gradient-to-t from-background via-background to-transparent pb-3 print:hidden">
        <div className="chat-column">
          <Composer
            value={draft}
            onChange={setDraft}
            onSubmit={submit}
            onStop={handleStop}
            streaming={streaming}
            inputRef={inputRef}
            disabled={Boolean(blocked)}
            disabledReason={blocked}
            remaining={config?.remaining_today}
            placeholder="Ask a follow-up…"
            autoFocus
          />
          <p className="mt-2 text-center text-xs text-muted-foreground">ThaparGenie can make mistakes. Check the linked source.</p>
        </div>
      </div>
    </div>
  );
}

export default function ConversationPage() {
  const { conversationId } = useParams();
  if (!UUID.test(conversationId || '')) return <NotFound />;
  // A fresh view per conversation, so a stream never leaks into another chat.
  return <ConversationView key={conversationId} conversationId={conversationId} />;
}
