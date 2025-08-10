import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const api = vi.hoisted(() => ({ createNotice: vi.fn(), updateNotice: vi.fn() }));
vi.mock('@/lib/api/admin', () => api);
vi.mock('sonner', () => ({ toast: Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn() }) }));

import NoticeDialog from './NoticeDialog';

function renderDialog(props = {}) {
  const onOpenChange = vi.fn();
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { mutations: { retry: false } } })}>
      <MemoryRouter>
        <NoticeDialog open onOpenChange={onOpenChange} {...props} />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return { onOpenChange };
}

describe('NoticeDialog', () => {
  beforeEach(() => vi.clearAllMocks());

  it('asks for a title before saving', () => {
    renderDialog();
    fireEvent.click(screen.getByRole('button', { name: 'Publish' }));
    expect(screen.getByText('Give the notice a title.')).toBeInTheDocument();
    expect(api.createNotice).not.toHaveBeenCalled();
  });

  it('publishes a new notice, answerable by default', async () => {
    api.createNotice.mockResolvedValue({ id: 'n1', state: 'published' });
    const { onOpenChange } = renderDialog();
    fireEvent.change(screen.getByLabelText('Title'), { target: { value: 'Hostel fee deadline' } });
    fireEvent.change(screen.getByLabelText('Details'), { target: { value: 'Pay by **15 October**.' } });
    fireEvent.click(screen.getByRole('switch', { name: /Important/ }));
    fireEvent.click(screen.getByRole('button', { name: 'Publish' }));

    await waitFor(() => expect(api.createNotice).toHaveBeenCalledTimes(1));
    expect(api.createNotice.mock.calls[0][0]).toMatchObject({
      title: 'Hostel fee deadline',
      body: 'Pay by **15 October**.',
      importance: 'important',
      is_draft: false,
      answerable: true,
    });
    await waitFor(() => expect(onOpenChange).toHaveBeenCalledWith(false));
  });

  it('saves a draft', async () => {
    api.createNotice.mockResolvedValue({ id: 'n1', state: 'draft' });
    renderDialog();
    fireEvent.change(screen.getByLabelText('Title'), { target: { value: 'Draft notice' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save draft' }));
    await waitFor(() => expect(api.createNotice.mock.calls[0][0].is_draft).toBe(true));
  });

  it('previews the Markdown', () => {
    renderDialog();
    fireEvent.change(screen.getByLabelText('Details'), { target: { value: 'Pay by **Friday**.' } });
    fireEvent.mouseDown(screen.getByRole('tab', { name: /Preview/ }));
    fireEvent.click(screen.getByRole('tab', { name: /Preview/ }));
    expect(screen.getByText('Friday').tagName).toBe('STRONG');
  });

  it('edits only what the notice form sends', async () => {
    api.updateNotice.mockResolvedValue({ id: 'n1', state: 'published' });
    const notice = {
      id: 'n1', title: 'Old title', body: '', category: 'notices', importance: 'normal', is_pinned: false,
      state: 'published', publish_at: '2026-09-20T04:00:00Z', expires_at: null, link_url: '', answerable: true,
    };
    renderDialog({ notice });
    fireEvent.change(screen.getByLabelText('Title'), { target: { value: 'New title' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));
    await waitFor(() => expect(api.updateNotice).toHaveBeenCalledTimes(1));
    const [id, body] = api.updateNotice.mock.calls[0];
    expect(id).toBe('n1');
    expect(body.title).toBe('New title');
    expect('publish_at' in body).toBe(false);
    expect('expires_at' in body).toBe(false);
  });
});
