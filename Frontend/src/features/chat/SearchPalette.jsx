import { useQuery } from '@tanstack/react-query';
import { CircleHelp, CornerDownLeft, MessageSquare, Search, Settings, SquarePen } from 'lucide-react';
import { createContext, useContext, useDeferredValue, useEffect, useId, useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { Dialog, DialogContent, DialogTitle } from '@/components/ui/dialog';
import { MOD } from '@/components/ui/kbd';
import { chatKeys, listConversations } from '@/lib/api/chat';
import { cn } from '@/lib/utils';

// Chat search as a command palette in the middle of the screen:
// Ctrl/⌘ K anywhere in the app, arrow keys and Enter, quick actions when empty.

// The server searches from 2 characters (chat/views.py MIN_SEARCH_CHARS).
const MIN_SEARCH_CHARS = 2;

/** Split `text` into [{text, match}] parts around case-insensitive occurrences of `query`. */
export function highlightParts(text, query) {
  if (!query) return [{ text, match: false }];
  const escaped = query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  return text
    .split(new RegExp(`(${escaped})`, 'gi'))
    .filter(Boolean)
    .map((part) => ({ text: part, match: part.toLowerCase() === query.toLowerCase() }));
}

function Highlighted({ text, query }) {
  return highlightParts(text, query).map((part, index) =>
    part.match ? (
      <mark key={index} className="rounded-sm bg-gold/30 px-0.5 text-inherit">
        {part.text}
      </mark>
    ) : (
      <span key={index}>{part.text}</span>
    ),
  );
}

const ACTIONS = [
  { key: 'new', label: 'New chat', icon: SquarePen, to: '/chat/' },
  { key: 'help', label: 'What can I ask?', icon: CircleHelp, to: '/help' },
  { key: 'settings', label: 'Settings', icon: Settings, to: '/settings/' },
];

function SearchPalette({ open, onOpenChange }) {
  const navigate = useNavigate();
  const listId = useId();
  const [query, setQuery] = useState('');
  const [active, setActive] = useState(0);
  const search = useDeferredValue(query.trim());
  const searching = search.length >= MIN_SEARCH_CHARS;

  const filters = { q: searching ? search : undefined, pageSize: 8 };
  const { data, isFetching } = useQuery({
    queryKey: chatKeys.conversations({ ...filters, palette: true }),
    queryFn: ({ signal }) => listConversations(filters, { signal }),
    enabled: open,
    placeholderData: (previous) => previous,
  });
  const chats = data?.results || [];

  const items = [
    ...(searching ? [] : ACTIONS.map((action) => ({ ...action, kind: 'action' }))),
    ...chats.map((chat) => ({ key: chat.id, kind: 'chat', chat, to: `/chat/${chat.id}` })),
  ];
  const current = Math.min(active, Math.max(0, items.length - 1));

  const close = () => {
    onOpenChange(false);
    setQuery('');
    setActive(0);
  };

  const run = (item) => {
    if (!item) return;
    close();
    navigate(item.to);
  };

  const onKeyDown = (event) => {
    if (event.key === 'ArrowDown') {
      event.preventDefault();
      setActive((index) => (items.length ? (Math.min(index, items.length - 1) + 1) % items.length : 0));
    } else if (event.key === 'ArrowUp') {
      event.preventDefault();
      setActive((index) => (items.length ? (Math.min(index, items.length - 1) - 1 + items.length) % items.length : 0));
    } else if (event.key === 'Enter') {
      event.preventDefault();
      run(items[current]);
    }
  };

  const optionId = (index) => `${listId}-option-${index}`;

  return (
    <Dialog open={open} onOpenChange={(next) => (next ? onOpenChange(true) : close())}>
      <DialogContent showCloseButton={false} className="max-w-xl gap-0 overflow-hidden p-0 sm:p-0" aria-describedby={undefined}>
        <DialogTitle className="sr-only">Search chats</DialogTitle>
        <div className="flex items-center gap-3 border-b px-4">
          <Search className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
          <input
            autoFocus
            role="combobox"
            aria-expanded="true"
            aria-controls={listId}
            aria-activedescendant={items.length ? optionId(current) : undefined}
            aria-label="Search chats"
            value={query}
            onChange={(event) => {
              setQuery(event.target.value);
              setActive(0);
            }}
            onKeyDown={onKeyDown}
            placeholder="Search your chats…"
            className="h-14 min-w-0 flex-1 bg-transparent text-[15px] outline-none placeholder:text-muted-foreground"
          />
          {isFetching ? <span className="size-3.5 animate-spin rounded-full border-2 border-muted-foreground/30 border-t-muted-foreground" /> : null}
          <kbd className="hidden rounded border px-1.5 py-0.5 font-sans text-[11px] text-muted-foreground [@media(pointer:fine)]:inline">Esc</kbd>
        </div>

        <div className="h-[min(22rem,60dvh)] overflow-y-auto p-2">
          <ul id={listId} role="listbox" aria-label={searching ? 'Results' : 'Suggestions'}>
            {items.map((item, index) => {
              const selected = index === current;
              const showGroup = index === 0 || items[index - 1].kind !== item.kind;
              const Icon = item.kind === 'action' ? item.icon : MessageSquare;
              const match = item.chat?.match;
              return (
                <li key={item.key} role="presentation">
                  {showGroup ? (
                    <p className="px-2.5 pt-2 pb-1 text-[11px] font-semibold tracking-wider text-muted-foreground uppercase" aria-hidden="true">
                      {item.kind === 'action' ? 'Quick actions' : searching ? 'Chats' : 'Recent chats'}
                    </p>
                  ) : null}
                  <div
                    id={optionId(index)}
                    role="option"
                    aria-selected={selected}
                    onMouseMove={() => setActive(index)}
                    onClick={() => run(item)}
                    className={cn(
                      'flex cursor-pointer items-start gap-3 rounded-lg px-2.5 py-2 text-sm transition-colors',
                      selected ? 'bg-primary/10 text-foreground' : 'text-foreground/85',
                    )}
                  >
                    <Icon
                      className={cn('mt-0.5 size-4 shrink-0', selected ? 'text-primary dark:text-accent-foreground' : 'text-muted-foreground')}
                      aria-hidden="true"
                    />
                    <span className="min-w-0 flex-1">
                      <span className="block truncate font-medium">
                        {item.kind === 'action' ? (
                          item.label
                        ) : (
                          <Highlighted text={item.chat.title || 'New conversation'} query={searching ? search : ''} />
                        )}
                      </span>
                      {match ? (
                        <span className="mt-0.5 line-clamp-2 text-xs text-muted-foreground">
                          {match.role === 'user' ? 'You' : 'ThaparGenie'}: <Highlighted text={match.snippet} query={search} />
                        </span>
                      ) : null}
                    </span>
                    {selected ? <CornerDownLeft className="mt-0.5 size-3.5 shrink-0 text-muted-foreground" aria-hidden="true" /> : null}
                  </div>
                </li>
              );
            })}
          </ul>
          {searching && !isFetching && !chats.length ? (
            <p className="px-3 py-10 text-center text-sm text-muted-foreground">No chats mention that.</p>
          ) : null}
        </div>

        <div className="hidden items-center gap-4 border-t px-4 py-2.5 text-xs text-muted-foreground [@media(pointer:fine)]:flex">
          <span>↑ ↓ to move</span>
          <span>Enter to open</span>
          <span className="ml-auto">{MOD} K to toggle</span>
        </div>
      </DialogContent>
    </Dialog>
  );
}

const OpenSearchContext = createContext(() => {});

/** Opens the search palette (sidebar button, rail icon, top bar). */
export const useOpenSearch = () => useContext(OpenSearchContext);

export function SearchPaletteProvider({ children }) {
  const [open, setOpen] = useState(false);

  // Ctrl/⌘ K opens (or closes) search from anywhere in the app.
  useEffect(() => {
    const onKeyDown = (event) => {
      if ((event.ctrlKey || event.metaKey) && !event.shiftKey && !event.altKey && event.key.toLowerCase() === 'k') {
        event.preventDefault();
        setOpen((value) => !value);
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, []);

  return (
    <OpenSearchContext.Provider value={() => setOpen(true)}>
      {children}
      <SearchPalette open={open} onOpenChange={setOpen} />
    </OpenSearchContext.Provider>
  );
}

