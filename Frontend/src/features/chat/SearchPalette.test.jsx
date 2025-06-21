import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const api = vi.hoisted(() => ({
  chatKeys: { conversations: (filters) => ['conversations', filters] },
  listConversations: vi.fn(),
}));
vi.mock('@/lib/api/chat', () => api);

import { SearchPaletteProvider } from './SearchPalette';

function renderApp() {
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemoryRouter initialEntries={['/chat/']}>
        <SearchPaletteProvider>
          <Routes>
            <Route path="/chat/" element={<h1>Home</h1>} />
            <Route path="/chat/:id" element={<h1>Opened chat</h1>} />
            <Route path="/help" element={<h1>Help</h1>} />
          </Routes>
        </SearchPaletteProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const openPalette = () => fireEvent.keyDown(window, { key: 'k', ctrlKey: true });

describe('SearchPalette', () => {
  beforeEach(() => {
    api.listConversations.mockReset();
    api.listConversations.mockImplementation(async ({ q }) => ({
      next: null,
      results: q
        ? [
            {
              id: 'c1',
              title: 'Hostel questions',
              match: { role: 'assistant', snippet: '…The boys hostel fee is Rs 1,20,000 per year…' },
            },
          ]
        : [{ id: 'c2', title: 'Fee refund', match: null }],
    }));
  });

  it('opens with Ctrl+K and offers actions and recent chats', async () => {
    renderApp();
    openPalette();
    const listbox = await screen.findByRole('listbox', { name: 'Suggestions' });
    expect(within(listbox).getByRole('option', { name: /New chat/ })).toBeInTheDocument();
    expect(await within(listbox).findByRole('option', { name: /Fee refund/ })).toBeInTheDocument();
  });

  it('searches message text, highlights the words, and opens the chosen chat with Enter', async () => {
    renderApp();
    openPalette();
    const input = await screen.findByRole('combobox', { name: 'Search chats' });
    fireEvent.change(input, { target: { value: 'fee' } });
    await waitFor(() => expect(api.listConversations).toHaveBeenCalledWith(expect.objectContaining({ q: 'fee' }), expect.anything()));

    const hit = await screen.findByRole('option', { name: /Hostel questions/ });
    expect(hit).toHaveTextContent('ThaparGenie: …The boys hostel fee is Rs 1,20,000 per year…');
    expect(within(hit).getByText('fee', { selector: 'mark' })).toBeInTheDocument();

    fireEvent.keyDown(input, { key: 'Enter' });
    expect(await screen.findByRole('heading', { name: 'Opened chat' })).toBeInTheDocument();
  });

  it('moves through options with the arrow keys', async () => {
    renderApp();
    openPalette();
    const input = await screen.findByRole('combobox', { name: 'Search chats' });
    await screen.findByRole('option', { name: /Fee refund/ });
    fireEvent.keyDown(input, { key: 'ArrowDown' });
    fireEvent.keyDown(input, { key: 'Enter' });
    expect(await screen.findByRole('heading', { name: 'Help' })).toBeInTheDocument();
  });
});
