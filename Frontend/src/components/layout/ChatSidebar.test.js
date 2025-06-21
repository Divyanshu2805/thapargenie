import { describe, expect, it, vi } from 'vitest';

vi.mock('@/lib/api/chat', () => ({ chatKeys: {}, listConversations: vi.fn() }));
vi.mock('@/features/chat/ConversationMenu', () => ({ default: () => null }));
vi.mock('@/components/layout/UserMenu', () => ({ default: () => null }));

import { cursorFrom } from '@/lib/pagination';

import { highlightParts } from '@/features/chat/SearchPalette';

import { groupByRecency } from './ChatSidebar';

describe('highlightParts', () => {
  it('marks every case-insensitive occurrence', () => {
    expect(highlightParts('Hostel fee and HOSTEL rules', 'hostel')).toEqual([
      { text: 'Hostel', match: true },
      { text: ' fee and ', match: false },
      { text: 'HOSTEL', match: true },
      { text: ' rules', match: false },
    ]);
  });

  it('treats the query as text, not a pattern', () => {
    expect(highlightParts('Fee (Rs 1,20,000) per year', '(rs 1,20,000)')).toEqual([
      { text: 'Fee ', match: false },
      { text: '(Rs 1,20,000)', match: true },
      { text: ' per year', match: false },
    ]);
    expect(highlightParts('a.b', '.')).toEqual([
      { text: 'a', match: false },
      { text: '.', match: true },
      { text: 'b', match: false },
    ]);
  });

  it('returns the text unchanged without a query', () => {
    expect(highlightParts('Mess fee', '')).toEqual([{ text: 'Mess fee', match: false }]);
  });
});

describe('groupByRecency', () => {
  it('puts pinned first, then today, the last week and earlier', () => {
    const now = new Date('2026-09-25T15:00:00');
    const groups = groupByRecency(
      [
        { id: 'old-pinned', is_pinned: true, created_at: '2026-01-01T00:00:00' },
        { id: 'today', last_message_at: '2026-09-25T09:00:00' },
        { id: 'week', last_message_at: '2026-09-21T09:00:00' },
        { id: 'old', last_message_at: '2026-08-01T09:00:00' },
      ],
      now,
    );
    expect(groups.map((group) => [group.label, group.items.map((item) => item.id)])).toEqual([
      ['Pinned', ['old-pinned']],
      ['Today', ['today']],
      ['Previous 7 days', ['week']],
      ['Earlier', ['old']],
    ]);
  });
});

describe('cursorFrom', () => {
  it('extracts the cursor from the next-page URL', () => {
    expect(cursorFrom('http://127.0.0.1:8010/api/v1/conversations/?cursor=cD0yMDI2&q=fee')).toBe('cD0yMDI2');
    expect(cursorFrom(null)).toBeUndefined();
    expect(cursorFrom('not a url')).toBeUndefined();
  });
});
