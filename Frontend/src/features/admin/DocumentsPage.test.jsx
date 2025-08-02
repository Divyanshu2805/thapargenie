import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const api = vi.hoisted(() => ({
  adminKeys: { documents: (filters) => ['admin', 'documents', filters] },
  listDocuments: vi.fn(),
  bulkDocuments: vi.fn(),
  suggestDetails: vi.fn(),
  listMatchingDocumentIds: vi.fn(),
}));
const recentAuth = vi.hoisted(() => vi.fn((action) => action()));
vi.mock('@/lib/api/admin', () => api);
vi.mock('@/components/recent-auth', () => ({ useRecentAuth: () => recentAuth }));
vi.mock('sonner', () => ({ toast: Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn() }) }));

import { toast } from 'sonner';

import { EXPIRY_WARNING_DAYS } from './constants';
import DocumentsPage from './DocumentsPage';

const today = new Date();
const inDays = (offset) => {
  const date = new Date(today.getFullYear(), today.getMonth(), today.getDate() + offset);
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
};

function renderAt(url) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[url]}>
        <DocumentsPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('DocumentsPage validity', () => {
  beforeEach(() => vi.clearAllMocks());

  it('applies ?validity=expiring from the Overview link and tags expiring rows', async () => {
    api.listDocuments.mockResolvedValue({
      results: [
        { id: 'd1', title: 'Fee notice', source_type: 'pdf', category: 'fees_scholarships', status: 'ready', is_current: true, chunk_count: 3, valid_until: inDays(5), updated_at: today.toISOString() },
      ],
      next: null,
    });

    renderAt('/admin/documents?validity=expiring');

    await waitFor(() => expect(api.listDocuments).toHaveBeenCalledWith(expect.objectContaining({ validity: 'expiring' })));
    expect(screen.getByRole('combobox', { name: 'Valid until' })).toHaveTextContent(`Expiring in ${EXPIRY_WARNING_DAYS} days`);
    expect(await screen.findByText(/^Expires /)).toBeInTheDocument();
  });

  it('ignores an unknown validity value', async () => {
    api.listDocuments.mockResolvedValue({ results: [], next: null });

    renderAt('/admin/documents?validity=nope');

    await waitFor(() => expect(api.listDocuments).toHaveBeenCalledWith(expect.objectContaining({ validity: '' })));
  });
});

const row = (id, title) => ({
  id, title, source_type: 'pdf', category: 'fees_scholarships', status: 'ready', is_current: true, chunk_count: 1, valid_until: null, updated_at: today.toISOString(),
});

describe('DocumentsPage bulk actions', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.listDocuments.mockResolvedValue({ results: [row('d1', 'Fees 2025-26'), row('d2', 'Hostel 2025-26'), row('d3', 'Calendar')], next: null });
  });

  async function selectTwo() {
    renderAt('/admin/documents');
    fireEvent.click(await screen.findByRole('checkbox', { name: 'Select Fees 2025-26' }));
    fireEvent.click(screen.getByRole('checkbox', { name: 'Select Hostel 2025-26' }));
    return screen.getByRole('region', { name: 'Bulk actions' });
  }

  it('disables the selected documents and keeps failures selected', async () => {
    api.bulkDocuments.mockResolvedValue({ succeeded: ['d1'], failed: [{ id: 'd2', code: 'invalid_transition', message: 'Only ready documents can be disabled.' }] });
    const bar = await selectTwo();
    expect(within(bar).getByText('2 selected')).toBeInTheDocument();

    fireEvent.click(within(bar).getByRole('button', { name: /Disable/ }));

    await waitFor(() => expect(api.bulkDocuments).toHaveBeenCalledWith({ action: 'disable', ids: ['d1', 'd2'], changes: undefined }));
    await waitFor(() => expect(toast.error).toHaveBeenCalledWith('Disabled 1 document; 1 failed', { description: 'Only ready documents can be disabled.' }));
    expect(screen.getByRole('checkbox', { name: 'Select Hostel 2025-26' })).toBeChecked();
    expect(screen.getByRole('checkbox', { name: 'Select Fees 2025-26' })).not.toBeChecked();
  });

  it('sends only the ticked fields from the edit dialog', async () => {
    api.bulkDocuments.mockResolvedValue({ succeeded: ['d1', 'd2'], failed: [] });
    const bar = await selectTwo();
    fireEvent.click(within(bar).getByRole('button', { name: /Edit details/ }));

    const dialog = await screen.findByRole('dialog');
    fireEvent.click(within(dialog).getByRole('button', { name: 'Apply changes' }));
    expect(within(dialog).getByRole('alert')).toHaveTextContent('Tick at least one field');

    fireEvent.change(within(dialog).getByLabelText('Academic year'), { target: { value: '2026-27' } });
    expect(within(dialog).getByRole('checkbox', { name: 'Change academic year' })).toBeChecked();
    fireEvent.click(within(dialog).getByRole('checkbox', { name: 'Change valid until' }));
    expect(within(dialog).getByText(/re-processes each ready document/)).toBeInTheDocument();
    fireEvent.click(within(dialog).getByRole('button', { name: 'Apply changes' }));

    await waitFor(() =>
      expect(api.bulkDocuments).toHaveBeenCalledWith({ action: 'update', ids: ['d1', 'd2'], changes: { academic_year: '2026-27', valid_until: null } }),
    );
    await waitFor(() => expect(toast.success).toHaveBeenCalledWith('Updated 2 documents', undefined));
  });

  it('confirms a delete and runs it behind the recent sign-in check', async () => {
    api.bulkDocuments.mockResolvedValue({ succeeded: ['d1', 'd2'], failed: [] });
    const bar = await selectTwo();
    fireEvent.click(within(bar).getByRole('button', { name: /Delete/ }));

    const dialog = await screen.findByRole('dialog');
    expect(dialog).toHaveTextContent('Delete 2 documents?');
    expect(api.bulkDocuments).not.toHaveBeenCalled();
    fireEvent.click(within(dialog).getByRole('button', { name: 'Delete' }));

    await waitFor(() => expect(api.bulkDocuments).toHaveBeenCalledWith({ action: 'delete', ids: ['d1', 'd2'], changes: undefined }));
    expect(recentAuth).toHaveBeenCalled();
  });

  it('suggests details, asks the AI on request and applies the reviewed values', async () => {
    const found = { title: '', current_academic_year: '', current_effective_date: null, effective_date: null, evidence: '' };
    api.suggestDetails
      .mockResolvedValueOnce({
        results: [
          { ...found, id: 'd1', title: 'Fees 2025-26', academic_year: '2026-27', source: 'text', evidence: 'Fees for 2026-27' },
          { ...found, id: 'd2', title: 'Hostel 2025-26', academic_year: '', source: '' },
        ],
      })
      .mockResolvedValueOnce({
        results: [{ ...found, id: 'd2', title: 'Hostel 2025-26', academic_year: '', effective_date: '2026-08-20', source: 'ai', evidence: 'Dated: August 20, 2026' }],
      });
    api.bulkDocuments.mockResolvedValue({ succeeded: ['d1', 'd2'], failed: [] });
    const bar = await selectTwo();
    fireEvent.click(within(bar).getByRole('button', { name: /Suggest details/ }));

    const dialog = await screen.findByRole('dialog');
    expect(api.suggestDetails).toHaveBeenCalledWith({ ids: ['d1', 'd2'] });
    expect(await within(dialog).findByText('Fees for 2026-27')).toBeInTheDocument();
    expect(within(dialog).getByRole('checkbox', { name: 'Apply to Fees 2025-26' })).toBeChecked();
    expect(within(dialog).getByRole('checkbox', { name: 'Apply to Hostel 2025-26' })).not.toBeChecked();

    fireEvent.click(within(dialog).getByRole('button', { name: /Ask AI for the rest \(1\)/ }));
    await waitFor(() => expect(api.suggestDetails).toHaveBeenLastCalledWith({ ids: ['d2'], ai: true }));
    expect(await within(dialog).findByText('Dated: August 20, 2026')).toBeInTheDocument();

    fireEvent.click(within(dialog).getByRole('button', { name: 'Apply to 2 documents' }));
    await waitFor(() =>
      expect(api.bulkDocuments).toHaveBeenCalledWith({
        action: 'update',
        ids: ['d1', 'd2'],
        changes: undefined,
        changesById: { d1: { academic_year: '2026-27' }, d2: { effective_date: '2026-08-20' } },
      }),
    );
  });

  it('selects everything matching the filter and runs the action in batches', async () => {
    api.listDocuments.mockResolvedValue({
      results: [row('d1', 'Fees 2025-26'), row('d2', 'Hostel 2025-26'), row('d3', 'Calendar')],
      next: 'http://127.0.0.1:8020/api/v1/admin/documents/?cursor=page2',
    });
    const matching = Array.from({ length: 250 }, (_, index) => `m${index}`);
    api.listMatchingDocumentIds.mockResolvedValue({ count: 250, ids: matching, truncated: false });
    api.bulkDocuments.mockImplementation(async ({ ids }) => ({ succeeded: ids, failed: [] }));
    renderAt('/admin/documents?details=missing_session');

    fireEvent.click(await screen.findByRole('checkbox', { name: 'Select all shown documents' }));
    fireEvent.click(screen.getByRole('button', { name: 'Select all matching this filter' }));
    await waitFor(() => expect(api.listMatchingDocumentIds).toHaveBeenCalledWith(expect.objectContaining({ details: 'missing_session' })));
    expect(await screen.findByText(/All 250 matching documents are selected/)).toBeInTheDocument();
    const bar = screen.getByRole('region', { name: 'Bulk actions' });
    expect(bar).toHaveTextContent('250 selected (all matching)');

    fireEvent.click(within(bar).getByRole('button', { name: /Disable/ }));
    await waitFor(() => expect(toast.success).toHaveBeenCalledWith('Disabled 250 documents', undefined));
    expect(api.bulkDocuments.mock.calls.map(([body]) => body.ids.length)).toEqual([100, 100, 50]);
    expect(api.bulkDocuments.mock.calls[0][0].ids[0]).toBe('m0');
  });

  it('selects every shown document from the header', async () => {
    renderAt('/admin/documents');
    fireEvent.click(await screen.findByRole('checkbox', { name: 'Select all shown documents' }));
    expect(screen.getByText('3 selected')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('checkbox', { name: 'Select all shown documents' }));
    expect(screen.queryByRole('region', { name: 'Bulk actions' })).not.toBeInTheDocument();
  });
});
