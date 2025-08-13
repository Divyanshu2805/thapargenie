import { fireEvent, render, screen, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

vi.mock('@/lib/api/chat', () => ({ openSource: vi.fn() }));

import { TooltipProvider } from '@/components/ui/tooltip';
import { AssistantMessage, BranchSwitcher } from './Message';

const wrap = (ui) => render(<TooltipProvider>{ui}</TooltipProvider>);

const answer = {
  id: 'a1',
  role: 'assistant',
  status: 'complete',
  answer_type: 'answered',
  grounded: true,
  content: 'The BE fee is ₹2,00,000 per semester [1].',
  sources: [{ position: 1, source_id: 's1', title: 'Fee structure 2026-27', cited: true, url: '' }],
  feedback: null,
  siblings: { index: 0, count: 1, ids: ['a1'] },
};

describe('BranchSwitcher', () => {
  it('moves to the neighbouring version', () => {
    const onSwitch = vi.fn();
    wrap(<BranchSwitcher siblings={{ index: 1, count: 3, ids: ['x', 'y', 'z'] }} onSwitch={onSwitch} />);

    expect(screen.getByText('2 / 3')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Previous version' }));
    fireEvent.click(screen.getByRole('button', { name: 'Next version' }));
    expect(onSwitch.mock.calls).toEqual([['x'], ['z']]);
  });

  it('is hidden with a single version and disables the ends', () => {
    const { container } = wrap(<BranchSwitcher siblings={{ index: 0, count: 1, ids: ['x'] }} onSwitch={vi.fn()} />);
    expect(container).toBeEmptyDOMElement();

    wrap(<BranchSwitcher siblings={{ index: 0, count: 2, ids: ['x', 'y'] }} onSwitch={vi.fn()} />);
    expect(screen.getByRole('button', { name: 'Previous version' })).toBeDisabled();
  });
});

describe('AssistantMessage', () => {
  const handlers = { onRegenerate: vi.fn(), onSwitch: vi.fn(), onFeedback: vi.fn(), onRetry: vi.fn() };

  it('renders citation chips linked to their sources', () => {
    wrap(<AssistantMessage message={answer} isLast {...handlers} />);
    expect(screen.getByRole('button', { name: 'Source 1: Fee structure 2026-27' })).toBeInTheDocument();
    expect(screen.queryByText(/couldn’t be matched/)).not.toBeInTheDocument();
  });

  it('warns when the answer is not grounded', () => {
    wrap(<AssistantMessage message={{ ...answer, grounded: false }} isLast {...handlers} />);
    expect(screen.getByText(/Verify the details with the official source/)).toBeInTheDocument();
  });

  it('shows how current the cited sources are once the answer is complete', () => {
    const dated = { ...answer.sources[0], academic_year: '2099-00', effective_date: '2026-08-12', is_current: true };
    const { rerender } = wrap(<AssistantMessage message={{ ...answer, sources: [dated] }} isLast {...handlers} />);
    expect(screen.getByText('Based on session 2099-00 sources · dated 12 Aug 2026')).toBeInTheDocument();

    rerender(
      <TooltipProvider>
        <AssistantMessage message={{ ...answer, status: 'streaming', sources: [dated] }} isLast {...handlers} />
      </TooltipProvider>,
    );
    expect(screen.queryByText(/Based on session/)).not.toBeInTheDocument();
  });

  it('warns when a cited document is not current, and marks its link', () => {
    const outdated = { ...answer.sources[0], is_current: false };
    wrap(<AssistantMessage message={{ ...answer, sources: [outdated] }} isLast {...handlers} />);
    expect(screen.getByText(/marked as no longer current/)).toBeInTheDocument();
    const link = within(screen.getByRole('list', { name: 'Sources' })).getByRole('button');
    expect(link).toHaveTextContent('Not current');
  });

  describe('follow-up suggestions', () => {
    it('offers a button under the latest answer only, and asks for suggestions on click', () => {
      const onSuggest = vi.fn();
      const { rerender } = wrap(<AssistantMessage message={answer} isLast {...handlers} onSuggest={onSuggest} onAsk={vi.fn()} />);
      fireEvent.click(screen.getByRole('button', { name: 'Suggest follow-ups' }));
      expect(onSuggest).toHaveBeenCalledWith('a1');

      rerender(
        <TooltipProvider>
          <AssistantMessage message={answer} isLast={false} {...handlers} onSuggest={onSuggest} onAsk={vi.fn()} />
        </TooltipProvider>,
      );
      expect(screen.queryByRole('button', { name: 'Suggest follow-ups' })).not.toBeInTheDocument();
    });

    it('is not offered for answers that found nothing, or while streaming', () => {
      const props = { ...handlers, onSuggest: vi.fn(), onAsk: vi.fn(), isLast: true };
      const { rerender } = wrap(<AssistantMessage message={{ ...answer, answer_type: 'no_answer' }} {...props} />);
      expect(screen.queryByRole('button', { name: 'Suggest follow-ups' })).not.toBeInTheDocument();
      rerender(
        <TooltipProvider>
          <AssistantMessage message={{ ...answer, status: 'streaming' }} {...props} />
        </TooltipProvider>,
      );
      expect(screen.queryByRole('button', { name: 'Suggest follow-ups' })).not.toBeInTheDocument();
    });

    it('shows the loading state while suggestions are requested', () => {
      wrap(<AssistantMessage message={answer} isLast {...handlers} onSuggest={vi.fn()} onAsk={vi.fn()} suggesting />);
      expect(screen.getByRole('button', { name: 'Thinking of follow-ups…' })).toBeDisabled();
    });

    it('turns saved suggestions into chips that ask the question', () => {
      const onAsk = vi.fn();
      const withSuggestions = { ...answer, suggestions: ['What is the mess fee?', 'Is AC hostel extra?'] };
      const { rerender } = wrap(<AssistantMessage message={withSuggestions} isLast {...handlers} onSuggest={vi.fn()} onAsk={onAsk} />);
      const group = screen.getByRole('group', { name: 'Suggested follow-ups' });
      fireEvent.click(within(group).getByRole('button', { name: 'Is AC hostel extra?' }));
      expect(onAsk).toHaveBeenCalledWith('Is AC hostel extra?');

      rerender(
        <TooltipProvider>
          <AssistantMessage message={withSuggestions} isLast {...handlers} onSuggest={vi.fn()} onAsk={onAsk} askDisabled />
        </TooltipProvider>,
      );
      expect(screen.getByRole('button', { name: 'What is the mess fee?' })).toBeDisabled();
    });

    it('says so when there were no suggestions', () => {
      wrap(<AssistantMessage message={{ ...answer, suggestionsEmpty: true }} isLast {...handlers} onSuggest={vi.fn()} onAsk={vi.fn()} />);
      expect(screen.getByText('No follow-up suggestions for this answer.')).toBeInTheDocument();
      expect(screen.queryByRole('button', { name: 'Suggest follow-ups' })).not.toBeInTheDocument();
    });
  });

  it('toggles a thumbs up and clears it on a second click', () => {
    const onFeedback = vi.fn();
    const { rerender } = wrap(<AssistantMessage message={answer} isLast {...handlers} onFeedback={onFeedback} />);
    fireEvent.click(screen.getByRole('button', { name: 'Good answer' }));
    expect(onFeedback).toHaveBeenLastCalledWith('a1', { rating: 1 });

    rerender(
      <TooltipProvider>
        <AssistantMessage message={{ ...answer, feedback: { rating: 1 } }} isLast {...handlers} onFeedback={onFeedback} />
      </TooltipProvider>,
    );
    fireEvent.click(screen.getByRole('button', { name: 'Good answer' }));
    expect(onFeedback).toHaveBeenLastCalledWith('a1', null);
  });

  it('asks for a reason before sending a thumbs down', () => {
    const onFeedback = vi.fn();
    wrap(<AssistantMessage message={answer} isLast {...handlers} onFeedback={onFeedback} />);
    fireEvent.click(screen.getByRole('button', { name: 'Bad answer' }));
    fireEvent.click(screen.getByRole('radio', { name: 'Outdated' }));
    fireEvent.click(screen.getByRole('button', { name: 'Send feedback' }));
    expect(onFeedback).toHaveBeenCalledWith('a1', { rating: -1, reason: 'outdated', comment: '' });
  });

  it('shows the live stage while streaming and offers retry on errors', () => {
    const onRetry = vi.fn();
    const { rerender } = wrap(
      <AssistantMessage message={{ id: null, status: 'streaming', content: '', stage: 'searching', sources: [] }} isLast {...handlers} />,
    );
    expect(screen.getByRole('status')).toHaveTextContent('Searching official documents');

    rerender(
      <TooltipProvider>
        <AssistantMessage
          message={{ id: null, status: 'failed', content: '', sources: [], error: { message: 'Busy.', retryable: true } }}
          isLast
          {...handlers}
          onRetry={onRetry}
        />
      </TooltipProvider>,
    );
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
    expect(onRetry).toHaveBeenCalled();
  });
});
