import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const api = vi.hoisted(() => ({
  chatKeys: { appConfig: ['app-config'], coverage: ['coverage'] },
  getAppConfig: vi.fn(),
  getCoverage: vi.fn(),
  createConversation: vi.fn(),
}));
vi.mock('@/lib/api/chat', () => api);
vi.mock('@/auth/AuthContext', () => ({ useAuth: () => ({ user: { displayName: 'Asha Rao' } }) }));

import ChatHome from '@/features/chat/ChatHome';

import HelpPage from './HelpPage';

function StateProbe() {
  return <output data-testid="history-state">{JSON.stringify(useLocation().state)}</output>;
}

function renderAt(path) {
  return render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemoryRouter initialEntries={[path]}>
        <StateProbe />
        <Routes>
          <Route path="/help" element={<HelpPage />} />
          <Route path="/chat/" element={<ChatHome />} />
          <Route path="/privacy" element={<h1>Privacy</h1>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('HelpPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.getAppConfig.mockResolvedValue({ starter_questions: [], remaining_today: 7 });
    api.getCoverage.mockResolvedValue({
      total_documents: 1341,
      categories: [
        { category: 'fees_scholarships', label: 'Fees & scholarships', documents: 42, updated_at: '2026-09-20T10:00:00Z' },
        { category: 'new_topic', label: 'New topic', documents: 1, updated_at: null },
      ],
    });
  });

  it('lists covered topics with counts, limits and what it can’t answer', async () => {
    renderAt('/help');

    expect(await screen.findByRole('heading', { name: 'Fees & scholarships' })).toBeInTheDocument();
    expect(screen.getByText(/42 documents · updated/)).toBeInTheDocument();
    // An unknown category still shows, with a generic icon and no examples.
    expect(screen.getByRole('heading', { name: 'New topic' })).toBeInTheDocument();
    expect(screen.getByText('1 document')).toBeInTheDocument();
    expect(screen.getByText(/From 1,341 official documents/)).toBeInTheDocument();
    expect(screen.getByText('Your personal records')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Open Webkiosk/ })).toHaveAttribute('rel', 'noopener noreferrer');
    expect(await screen.findByText(/You have 7 questions left today/)).toBeInTheDocument();
  });

  it('puts a picked example in the new-chat box without sending it', async () => {
    renderAt('/help');

    fireEvent.click(await screen.findByRole('button', { name: 'What is the BE fee for 2026-27?' }));

    await waitFor(() => expect(screen.getByRole('textbox')).toHaveValue('What is the BE fee for 2026-27?'));
    expect(api.createConversation).not.toHaveBeenCalled();
    // The handed-over question is dropped from history, so a reload starts empty.
    await waitFor(() => expect(screen.getByTestId('history-state')).toHaveTextContent('null'));
    expect(screen.getByRole('textbox')).toHaveValue('What is the BE fee for 2026-27?');
  });

  it('shows a maintenance card on the chat home instead of the question box', async () => {
    api.getAppConfig.mockResolvedValue({ maintenance: true, maintenance_message: 'Back by 6 pm.', starter_questions: [] });
    renderAt('/chat/');

    expect(await screen.findByRole('heading', { name: 'We’re improving ThaparGenie' })).toBeInTheDocument();
    expect(screen.getByText('Back by 6 pm.')).toBeInTheDocument();
    expect(screen.queryByRole('textbox')).not.toBeInTheDocument();
  });

  it('still offers the rest of the page when topics fail to load', async () => {
    api.getCoverage.mockRejectedValue(new Error('offline'));
    renderAt('/help');

    expect(await screen.findByText(/topic list couldn’t be loaded/)).toBeInTheDocument();
    expect(screen.getByText('Tips for better answers')).toBeInTheDocument();
  });
});
