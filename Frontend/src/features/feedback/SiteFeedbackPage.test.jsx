import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const api = vi.hoisted(() => ({
  chatKeys: { siteFeedback: ['site-feedback'] },
  listSiteFeedback: vi.fn(),
  sendSiteFeedback: vi.fn(),
}));
vi.mock('@/lib/api/chat', () => api);
vi.mock('sonner', () => ({ toast: Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn() }) }));

import SiteFeedbackPage from './SiteFeedbackPage';

function renderPage(from = '/chat/2b8f0c9e-1111-4a5b-9c1d-000000000000') {
  return render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemoryRouter initialEntries={[{ pathname: '/feedback', state: { from } }]}>
        <Routes>
          <Route path="/feedback" element={<SiteFeedbackPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('SiteFeedbackPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.listSiteFeedback.mockResolvedValue({
      results: [
        { id: 'f1', kind: 'problem', rating: 2, message: 'The sidebar flickers.', review_status: 'resolved', created_at: '2026-09-20T10:00:00Z' },
      ],
    });
    api.sendSiteFeedback.mockResolvedValue({ id: 'f2' });
  });

  it('lists what the student sent, with a student-facing status', async () => {
    renderPage();
    expect(await screen.findByText('The sidebar flickers.')).toBeInTheDocument();
    expect(screen.getByText('Resolved')).toBeInTheDocument();
  });

  it('sends the chosen kind, rating and message, with only the section it came from', async () => {
    renderPage();
    fireEvent.click(screen.getByRole('radio', { name: /Answer quality/ }));
    fireEvent.click(screen.getByRole('radio', { name: /^4 of 5/ }));
    fireEvent.change(screen.getByLabelText('Your feedback'), { target: { value: '  Fee answers were out of date.  ' } });
    fireEvent.click(screen.getByRole('button', { name: 'Send feedback' }));

    await waitFor(() =>
      expect(api.sendSiteFeedback).toHaveBeenCalledWith({
        kind: 'answers',
        rating: 4,
        message: 'Fee answers were out of date.',
        page: '/chat/',
        contactOk: false,
      }),
    );
  });

  it('asks for a longer message instead of sending a very short one', () => {
    renderPage();
    fireEvent.change(screen.getByLabelText('Your feedback'), { target: { value: 'meh' } });
    fireEvent.click(screen.getByRole('button', { name: 'Send feedback' }));
    expect(screen.getByText(/Write at least 10 characters/)).toBeInTheDocument();
    expect(api.sendSiteFeedback).not.toHaveBeenCalled();
  });
});
