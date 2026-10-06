import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const api = vi.hoisted(() => ({
  adminKeys: {
    gaps: (range) => ['admin', 'gaps', range],
    complaints: (range) => ['admin', 'complaints', range],
  },
  listGaps: vi.fn(),
  listComplaints: vi.fn(),
  exportGapsCsv: vi.fn(),
}));
vi.mock('@/lib/api/admin', () => api);

import GapsPage from './GapsPage';

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <GapsPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('GapsPage follow-ups', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.listGaps.mockResolvedValue({ range_days: 30, results: [] });
  });

  it('lists what students said about an earlier answer next to the question it followed', async () => {
    api.listComplaints.mockResolvedValue({
      range_days: 30,
      results: [
        {
          remark: 'why didnt you give this before?',
          question: 'list all boys hostels',
          answer: 'Agira, Prithvi.',
          created_at: new Date().toISOString(),
          reporter: 'abc123def456',
        },
      ],
    });

    renderPage();

    expect(await screen.findByText('why didnt you give this before?')).toBeInTheDocument();
    expect(screen.getByText('list all boys hostels')).toBeInTheDocument();
    expect(screen.getByText('Agira, Prithvi.')).toBeInTheDocument();
    expect(api.listComplaints).toHaveBeenCalledWith('30d');
  });

  it('says so when there are none', async () => {
    api.listComplaints.mockResolvedValue({ range_days: 30, results: [] });

    renderPage();

    expect(await screen.findByText('No follow-ups in this period')).toBeInTheDocument();
  });
});
