import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const api = vi.hoisted(() => ({
  chatKeys: { shared: (token) => ['shared', token], share: (id) => ['share', id] },
  getSharedAnswer: vi.fn(),
  getShare: vi.fn(),
  createShare: vi.fn(),
  revokeShare: vi.fn(),
}));
vi.mock('@/lib/api/chat', () => api);
vi.mock('sonner', () => ({ toast: Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn() }) }));

import ShareDialog, { shareUrl } from '@/features/chat/ShareDialog';

import SharedAnswerPage from './SharedAnswerPage';

const client = () => new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });

function renderPage(token = 'a'.repeat(32)) {
  return render(
    <QueryClientProvider client={client()}>
      <MemoryRouter initialEntries={[`/s/${token}`]}>
        <Routes>
          <Route path="/s/:token" element={<SharedAnswerPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('SharedAnswerPage', () => {
  beforeEach(() => vi.clearAllMocks());

  it('shows the shared question, answer and cited sources, and is not indexed', async () => {
    api.getSharedAnswer.mockResolvedValue({
      question: 'What is the hostel fee?',
      answer: 'It is **Rs 1,20,000** a year.',
      sources: [
        { position: 1, title: 'Fee notice', url: 'https://www.thapar.edu/fees', cited: true },
        { position: 2, title: 'Stored scan', url: '', cited: true },
        { position: 3, title: 'Not cited', url: '', cited: false },
      ],
      created_at: '2026-09-26T10:00:00Z',
      expires_at: '2026-10-03T10:00:00Z',
    });
    renderPage();
    expect(await screen.findByText('What is the hostel fee?')).toBeInTheDocument();
    expect(screen.getByText('Rs 1,20,000').tagName).toBe('STRONG');
    expect(screen.getByRole('link', { name: /Fee notice/ })).toHaveAttribute('href', 'https://www.thapar.edu/fees');
    expect(screen.getByText('Stored scan')).toBeInTheDocument();
    expect(screen.queryByText('Not cited')).not.toBeInTheDocument();
    expect(document.head.querySelector('meta[name="robots"]').content).toBe('noindex, nofollow');
  });

  it('explains an expired or turned-off link', async () => {
    api.getSharedAnswer.mockResolvedValue(null);
    renderPage();
    expect(await screen.findByText('This link has expired or was turned off')).toBeInTheDocument();
  });
});

describe('ShareDialog', () => {
  beforeEach(() => vi.clearAllMocks());

  it('creates a link, then can turn it off', async () => {
    api.getShare.mockResolvedValue({ share: null });
    api.createShare.mockResolvedValue({ token: 'b'.repeat(32), expires_at: '2026-10-03T10:00:00Z' });
    api.revokeShare.mockResolvedValue(null);
    render(
      <QueryClientProvider client={client()}>
        <ShareDialog open onOpenChange={vi.fn()} message={{ id: 'm1', content: 'It is Rs 1,20,000.' }} question="Hostel fee?" />
      </QueryClientProvider>,
    );
    const createButton = await screen.findByRole('button', { name: /Create link/ });
    await waitFor(() => expect(createButton).toBeEnabled());
    fireEvent.click(createButton);
    await waitFor(() => expect(screen.getByLabelText('Link')).toHaveValue(shareUrl('b'.repeat(32))));
    expect(api.createShare).toHaveBeenCalledWith('m1');

    fireEvent.click(screen.getByRole('button', { name: /Stop sharing/ }));
    await waitFor(() => expect(api.revokeShare).toHaveBeenCalledWith('m1'));
    expect(await screen.findByRole('button', { name: /Create link/ })).toBeInTheDocument();
  });
});
