import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const api = vi.hoisted(() => ({
  noticeKeys: { list: () => ['notices', 'all'], official: ['notices', 'official'] },
  listNotices: vi.fn(),
  listOfficialNotices: vi.fn(),
  openOfficialNotice: vi.fn(),
}));
vi.mock('@/lib/api/notices', () => api);
vi.mock('@/hooks/use-app-config', () => ({
  useAppConfig: () => ({ data: { latest_notice_at: '2026-09-25T10:00:00Z' } }),
}));
vi.mock('sonner', () => ({ toast: Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn() }) }));

import NoticesPage, { sortNotices } from './NoticesPage';
import { SEEN_KEY, hasUnread } from './seen';

const notice = (fields) => ({
  body: '',
  category: 'notices',
  importance: 'normal',
  is_pinned: false,
  expires_at: null,
  link_url: '',
  publish_at: '2026-09-20T10:00:00Z',
  ...fields,
});

function renderPage() {
  return render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemoryRouter>
        <NoticesPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('sortNotices', () => {
  it('puts pinned, then important, then newest first', () => {
    const sorted = sortNotices([
      notice({ id: 'old', publish_at: '2026-09-01T00:00:00Z' }),
      notice({ id: 'new', publish_at: '2026-09-24T00:00:00Z' }),
      notice({ id: 'important', importance: 'important', publish_at: '2026-09-02T00:00:00Z' }),
      notice({ id: 'pinned', is_pinned: true, publish_at: '2026-08-01T00:00:00Z' }),
    ]);
    expect(sorted.map((item) => item.id)).toEqual(['pinned', 'important', 'new', 'old']);
  });
});

describe('hasUnread', () => {
  it('is true only when something is newer than the last visit', () => {
    expect(hasUnread(null, null)).toBe(false);
    expect(hasUnread('2026-09-25T10:00:00Z', null)).toBe(true);
    expect(hasUnread('2026-09-25T10:00:00Z', '2026-09-25T10:00:00Z')).toBe(false);
    expect(hasUnread('2026-09-25T10:00:01Z', '2026-09-25T10:00:00Z')).toBe(true);
    expect(hasUnread('2026-09-25T10:00:00Z', 'garbage')).toBe(true);
  });
});

describe('NoticesPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.localStorage.clear();
    api.listNotices.mockResolvedValue({
      results: [
        notice({ id: 'n1', title: 'Hostel fee deadline', category: 'fees_scholarships', link_url: 'https://www.thapar.edu/n1' }),
        notice({ id: 'n2', title: 'Exams moved', importance: 'important', category: 'academic_calendar', body: 'Now on **3 Oct**.' }),
      ],
    });
    api.listOfficialNotices.mockResolvedValue({
      results: [{ id: 'd1', title: 'Scholarship circular', processed_at: '2026-09-24T10:00:00Z', source_url: '' }],
    });
  });

  it('shows notices with their topic, the official link and new documents', async () => {
    renderPage();
    const exams = (await screen.findByText('Exams moved')).closest('li');
    expect(within(exams).getByText('Important')).toBeInTheDocument();
    expect(within(exams).getByText('3 Oct')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Read the official notice/ })).toHaveAttribute('href', 'https://www.thapar.edu/n1');
    expect(await screen.findByText('Scholarship circular')).toBeInTheDocument();
  });

  it('filters by topic', async () => {
    renderPage();
    await screen.findByText('Exams moved');
    fireEvent.click(screen.getByRole('radio', { name: 'Fees & scholarships' }));
    expect(screen.queryByText('Exams moved')).not.toBeInTheDocument();
    expect(screen.getByText('Hostel fee deadline')).toBeInTheDocument();
  });

  it('records the visit so the sidebar dot clears', async () => {
    renderPage();
    await screen.findByText('Exams moved');
    expect(window.localStorage.getItem(SEEN_KEY)).toBe('2026-09-25T10:00:00Z');
  });
});
