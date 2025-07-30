import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const api = vi.hoisted(() => ({
  uploadDocuments: vi.fn(),
  addDocumentFromUrl: vi.fn(),
  addDocumentFromText: vi.fn(),
}));
vi.mock('@/lib/api/admin', () => api);
vi.mock('sonner', () => ({ toast: Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn() }) }));

import AddKnowledgeDialog from './AddKnowledgeDialog';

function renderDialog(props = {}) {
  const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
  const onOpenChange = vi.fn();
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <AddKnowledgeDialog open onOpenChange={onOpenChange} {...props} />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return { onOpenChange };
}

describe('AddKnowledgeDialog', () => {
  beforeEach(() => vi.clearAllMocks());

  it('uploads chosen files with shared metadata', async () => {
    api.uploadDocuments.mockResolvedValue({ created: [{ id: 'd1' }], rejected: [] });
    const { onOpenChange } = renderDialog();

    const file = new File(['%PDF-1.7'], 'fees-2026.pdf', { type: 'application/pdf' });
    fireEvent.change(screen.getByLabelText('Choose files'), { target: { files: [file] } });
    expect(screen.getByText('fees-2026.pdf')).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('Academic year'), { target: { value: '2026-27' } });
    fireEvent.keyDown(screen.getByLabelText('Category'), { key: 'Enter' });
    fireEvent.click(await screen.findByRole('option', { name: 'Fees & scholarships' }));
    fireEvent.click(screen.getByRole('button', { name: 'Add to knowledge base' }));

    await waitFor(() => expect(api.uploadDocuments).toHaveBeenCalled());
    const [files, meta] = api.uploadDocuments.mock.calls[0];
    expect(files).toEqual([file]);
    expect(meta).toEqual({ category: 'fees_scholarships', academic_year: '2026-27', is_current: true, parser: 'auto' });
    await waitFor(() => expect(onOpenChange).toHaveBeenCalledWith(false));
  });

  it('blocks an invalid academic year before calling the API', () => {
    renderDialog({ initial: { tab: 'text', title: 'Refunds', text: 'Q: …\nA: …' } });
    fireEvent.change(screen.getByLabelText('Academic year'), { target: { value: '26-27' } });
    fireEvent.click(screen.getByRole('button', { name: 'Add to knowledge base' }));

    expect(screen.getByText('Use the form 2026-27.')).toBeInTheDocument();
    expect(api.addDocumentFromText).not.toHaveBeenCalled();
  });

  it('submits a prefilled FAQ and reports it created', async () => {
    api.addDocumentFromText.mockResolvedValue({ id: 'd2' });
    const onCreated = vi.fn();
    renderDialog({ initial: { tab: 'text', title: 'Hostel fee?', text: 'Q: Hostel fee?\nA: ₹1L', meta: { category: 'faq' } }, onCreated });

    fireEvent.click(screen.getByRole('button', { name: 'Add to knowledge base' }));

    await waitFor(() =>
      expect(api.addDocumentFromText).toHaveBeenCalledWith({ category: 'faq', is_current: true, title: 'Hostel fee?', text: 'Q: Hostel fee?\nA: ₹1L' }),
    );
    await waitFor(() => expect(onCreated).toHaveBeenCalledWith([{ id: 'd2' }]));
  });

  it('shows a link to the existing document on a duplicate upload', async () => {
    api.uploadDocuments.mockRejectedValue(Object.assign(new Error('Already uploaded.'), { code: 'duplicate_document', existingId: 'd9' }));
    renderDialog();
    fireEvent.change(screen.getByLabelText('Choose files'), { target: { files: [new File(['x'], 'a.pdf')] } });
    fireEvent.click(screen.getByRole('button', { name: 'Add to knowledge base' }));

    expect(await screen.findByRole('link', { name: 'Open the existing document' })).toHaveAttribute('href', '/admin/documents/d9');
  });
});
