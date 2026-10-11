import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { TooltipProvider } from '@/components/ui/tooltip';

const api = vi.hoisted(() => ({ runPlayground: vi.fn() }));
vi.mock('@/lib/api/admin', () => api);

import PlaygroundPage from './PlaygroundPage';

// The shape `admin_services.playground` returns: `keywords` is one string, not a list.
const RESULT = {
  analysis: {
    intent: 'college',
    standalone_query: 'What is the hostel fee for first-year students?',
    alternate_queries: ['first year hostel charges', 'hostel fee 2026-27'],
    keywords: 'hostel fee first-year',
    categories: ['fees_scholarships'],
    academic_year: '2026-27',
    needs_current: true,
    wants_complete_list: false,
    language: 'english',
    fallback: false,
  },
  stages: [],
  retrieval: {
    lists: { vector: 12, text: 4 },
    candidates: [
      { chunk_id: 'c1', title: 'Hostel fee structure', heading_path: 'Fees', ranks: { vector: 1, text: 2 }, fused: 0.0325, boost: 0, rerank: null },
    ],
  },
  reranked: false,
  sources: [
    {
      position: 1,
      title: 'Hostel fee structure',
      heading_path: 'Fees',
      academic_year: '2026-27',
      document_id: 'd1',
      chunk_ids: ['c1'],
      score: 0.0325,
      is_current: true,
      content: 'The hostel fee is paid in two instalments.',
      cited: true,
    },
  ],
  answer: 'The hostel fee is paid in two instalments [1].',
  answer_type: 'answered',
  grounded: true,
  unsupported: [],
  model: 'chat-model',
  timings: { analysis: 400, retrieval: 30, generation: 900, total: 1330 },
  usage: { llm_calls: 3, prompt_tokens: 1200, completion_tokens: 40 },
};

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <TooltipProvider>
        <MemoryRouter>
          <PlaygroundPage />
        </MemoryRouter>
      </TooltipProvider>
    </QueryClientProvider>,
  );
}

describe('PlaygroundPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.runPlayground.mockResolvedValue(RESULT);
  });

  it('runs a question and shows the answer and how the question was understood', async () => {
    renderPage();
    fireEvent.change(screen.getByLabelText('Question'), { target: { value: 'What is the hostel fee?' } });
    fireEvent.click(screen.getByRole('button', { name: /run/i }));

    expect(await screen.findByText('Grounded')).toBeInTheDocument();
    expect(api.runPlayground).toHaveBeenCalledWith({ query: 'What is the hostel fee?' });
    expect(screen.getByText('hostel fee first-year')).toBeInTheDocument();
    expect(screen.getByText('first year hostel charges · hostel fee 2026-27')).toBeInTheDocument();
    expect(screen.getByText('fees_scholarships')).toBeInTheDocument();
    expect(screen.getByText('vector: 12 · text: 4')).toBeInTheDocument();
  });
});
