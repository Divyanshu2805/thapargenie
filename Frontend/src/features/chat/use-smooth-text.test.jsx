import { render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { ThinkingIndicator } from './thinking';
import { useSmoothText } from './use-smooth-text';

function Reveal({ text, live }) {
  const smooth = useSmoothText(text, live);
  return <p data-testid="text" data-revealing={smooth.revealing}>{smooth.text}</p>;
}

describe('useSmoothText', () => {
  it('shows an answer from history whole', () => {
    render(<Reveal text="The hostel fee is Rs 1,20,000." live={false} />);
    expect(screen.getByTestId('text')).toHaveTextContent('The hostel fee is Rs 1,20,000.');
  });

  it('types out a live answer, then settles on the full text', async () => {
    const text = 'The hostel fee is Rs 1,20,000 per year.';
    const { rerender } = render(<Reveal text="" live />);
    rerender(<Reveal text={text} live />);
    expect(screen.getByTestId('text').textContent.length).toBeLessThan(text.length);
    rerender(<Reveal text={text} live={false} />);
    await waitFor(() => expect(screen.getByTestId('text')).toHaveTextContent(text));
    expect(screen.getByTestId('text')).toHaveAttribute('data-revealing', 'false');
  });
});

describe('ThinkingIndicator', () => {
  it('names the stage for screen readers', () => {
    render(<ThinkingIndicator stage="reading" detail="Reading 3 sources" />);
    expect(screen.getByRole('status')).toHaveTextContent('Reading the sources');
  });
});
