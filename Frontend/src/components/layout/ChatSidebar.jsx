import { useInfiniteQuery } from '@tanstack/react-query';
import { MessageSquare, Pin, SquarePen } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';

import { SidebarHeader, SidebarItem, useSidebar } from '@/components/layout/SidebarLayout';
import UserMenu from '@/components/layout/UserMenu';
import { MarqueeText } from '@/components/marquee-text';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { Kbd, MOD, SHIFT } from '@/components/ui/kbd';
import ConversationMenu, { InlineRename } from '@/features/chat/ConversationMenu';
import { chatKeys, listConversations } from '@/lib/api/chat';
import { cursorFrom } from '@/lib/pagination';
import { cn } from '@/lib/utils';

export function groupByRecency(conversations, now = new Date()) {
  const startOfToday = new Date(now);
  startOfToday.setHours(0, 0, 0, 0);
  const day = 86_400_000;
  const groups = [
    { label: 'Pinned', items: [] },
    { label: 'Today', items: [] },
    { label: 'Previous 7 days', items: [] },
    { label: 'Earlier', items: [] },
  ];
  for (const conversation of conversations) {
    const at = new Date(conversation.last_message_at || conversation.created_at).getTime();
    if (conversation.is_pinned) groups[0].items.push(conversation);
    else if (at >= startOfToday.getTime()) groups[1].items.push(conversation);
    else if (at >= startOfToday.getTime() - 7 * day) groups[2].items.push(conversation);
    else groups[3].items.push(conversation);
  }
  return groups.filter((group) => group.items.length > 0);
}

function LoadMore({ onVisible, loading }) {
  const ref = useRef(null);
  useEffect(() => {
    const node = ref.current;
    if (!node || typeof IntersectionObserver === 'undefined') return undefined;
    const observer = new IntersectionObserver((entries) => entries[0]?.isIntersecting && onVisible(), {
      rootMargin: '120px',
    });
    observer.observe(node);
    return () => observer.disconnect();
  }, [onVisible]);
  return (
    <div ref={ref} className="px-3 py-2">
      {loading ? (
        <Skeleton className="h-7 w-3/4" />
      ) : (
        <Button variant="ghost" size="sm" className="w-full text-muted-foreground" onClick={onVisible}>
          Load more
        </Button>
      )}
    </div>
  );
}

function ConversationRow({ conversation, onNavigate }) {
  const title = conversation.title || 'New conversation';
  const [renaming, setRenaming] = useState(false);
  if (renaming) {
    return (
      <li className="px-0.5 py-0.5">
        <InlineRename conversation={conversation} onDone={() => setRenaming(false)} />
      </li>
    );
  }
  return (
    <li className="group/row relative">
      <NavLink
        to={`/chat/${conversation.id}`}
        onClick={onNavigate}
        onDoubleClick={(event) => {
          event.preventDefault();
          setRenaming(true);
        }}
        title={`${title} (double-click to rename)`}
        className={({ isActive }) =>
          cn(
            'group/marquee flex items-center gap-2 rounded-lg py-2 pr-9 pl-2.5 text-sm text-sidebar-foreground/85 transition-colors duration-150 outline-none hover:bg-sidebar-accent hover:text-sidebar-foreground focus-visible:ring-2 focus-visible:ring-ring/50',
            // Same raised card as the current page in the admin nav (SidebarLayout itemClass).
            isActive && 'bg-card font-medium text-sidebar-foreground shadow-soft ring-1 ring-sidebar-border hover:bg-card',
          )
        }
      >
        {conversation.is_pinned ? <Pin className="size-3.5 shrink-0 text-gold" aria-label="Pinned" /> : null}
        <MarqueeText>{title}</MarqueeText>
      </NavLink>
      <ConversationMenu
        conversation={conversation}
        align="start"
        className="absolute top-1/2 right-1 -translate-y-1/2 opacity-100 focus-visible:opacity-100 data-[state=open]:opacity-100 md:opacity-0 md:group-hover/row:opacity-100"
      />
    </li>
  );
}

function ConversationList({ archived, onNavigate }) {
  const filters = { archived: archived || undefined };
  const { data, isPending, isError, refetch, hasNextPage, fetchNextPage, isFetchingNextPage } = useInfiniteQuery({
    queryKey: chatKeys.conversations(filters),
    queryFn: ({ pageParam, signal }) => listConversations({ ...filters, cursor: pageParam }, { signal }),
    initialPageParam: undefined,
    getNextPageParam: (page) => cursorFrom(page.next),
  });

  if (isPending) {
    return (
      <div className="space-y-2 px-3 py-2" aria-hidden="true">
        {[72, 88, 64, 80, 56].map((width) => (
          <Skeleton key={width} className="h-7" style={{ width: `${width}%` }} />
        ))}
      </div>
    );
  }

  if (isError) {
    return (
      <div className="px-4 py-6 text-center text-sm text-muted-foreground">
        <p>Couldn’t load your chats.</p>
        <Button variant="link" size="sm" onClick={() => refetch()}>
          Try again
        </Button>
      </div>
    );
  }

  const conversations = data.pages.flatMap((page) => page.results || []);
  // Archived chats are one flat list; recency groups are for browsing.
  const groups = archived ? [{ label: 'Archived', items: conversations }] : groupByRecency(conversations);

  if (conversations.length === 0) {
    return (
      <div className="flex flex-col items-center gap-2 px-6 py-10 text-center">
        <span className="flex size-10 items-center justify-center rounded-full bg-sidebar-accent">
          <MessageSquare className="size-4 text-muted-foreground" />
        </span>
        <p className="text-sm text-muted-foreground">
          {archived ? 'No archived chats.' : 'Your conversations will appear here.'}
        </p>
      </div>
    );
  }

  return (
    <nav aria-label={archived ? 'Archived conversations' : 'Conversations'} className="space-y-5 px-2 pb-4">
      {groups.map((group) => (
        <div key={group.label}>
          <h3 className="px-2.5 pb-1.5 text-[11px] font-semibold tracking-wider text-muted-foreground uppercase">{group.label}</h3>
          <ul className="space-y-0.5">
            {group.items.map((conversation) => (
              <ConversationRow key={conversation.id} conversation={conversation} onNavigate={onNavigate} />
            ))}
          </ul>
        </div>
      ))}
      {hasNextPage ? <LoadMore loading={isFetchingNextPage} onVisible={() => !isFetchingNextPage && fetchNextPage()} /> : null}
    </nav>
  );
}

export default function ChatSidebar({ onNavigate: onNavigateProp }) {
  const sidebar = useSidebar();
  const onNavigate = onNavigateProp || sidebar.onNavigate;
  const rail = sidebar.collapsed && !sidebar.inDrawer;
  const navigate = useNavigate();

  const startNewChat = () => {
    onNavigate?.();
    navigate('/chat/');
  };

  // One tree for the open sidebar and the rail (see SidebarLayout): icons keep their place,
  // labels and the chat list fade, and nothing re-mounts while the width animates.
  return (
    <div className="flex h-full w-[var(--sidebar-width)] max-w-full flex-col bg-sidebar text-sidebar-foreground">
      <SidebarHeader to="/chat/" />

      <nav aria-label="Chat" className="flex flex-col gap-1.5 px-3 pb-3">
        <SidebarItem
          icon={SquarePen}
          label={`New chat (${MOD}+${SHIFT}+O)`}
          onClick={startNewChat}
          className="bg-primary font-medium text-primary-foreground shadow-soft hover:bg-primary/90 hover:text-primary-foreground"
          trailing={<Kbd keys={[MOD, SHIFT, 'O']} className="sidebar-label opacity-80" />}
        >
          New chat
        </SidebarItem>
      </nav>

      <div inert={rail} className={cn('sidebar-label scrollbar-thin min-h-0 flex-1', rail ? 'overflow-hidden' : 'overflow-y-auto')}>
        <ConversationList onNavigate={onNavigate} />
      </div>

      <div className="flex flex-col gap-0.5 border-t border-sidebar-border px-3 py-2">
        <UserMenu compact={rail} />
      </div>
    </div>
  );
}
