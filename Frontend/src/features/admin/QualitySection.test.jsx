import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import QualitySection, { scoreChange } from './QualitySection';

const run = (fields) => ({
  id: 1,
  created_at: '2026-09-26T20:30:00Z',
  trigger: 'nightly',
  cases: 21,
  recall_at_5: 0.95,
  recall_at_10: 1,
  mrr: 0.93,
  errors: 0,
  misses: [],
  important_misses: [],
  ...fields,
});

describe('scoreChange', () => {
  it('describes the move since the previous run', () => {
    expect(scoreChange(0.95, 0.9)).toEqual({ text: '+0.05', tone: 'up' });
    expect(scoreChange(0.8, 0.9)).toEqual({ text: '−0.10', tone: 'down' });
    expect(scoreChange(0.9, 0.9)).toEqual({ text: 'no change', tone: 'same' });
    expect(scoreChange(0.9, undefined)).toBeNull();
  });
});

describe('QualitySection', () => {
  it('shows scores, changes, warnings and misses', () => {
    render(
      <QualitySection
        quality={{
          latest: run({ recall_at_5: 0.86, misses: ['fees-hostel'] }),
          previous: run({ recall_at_5: 0.95 }),
          warnings: [{ code: 'below_target', message: 'Recall@5 is 0.86, below the 0.90 target.' }],
        }}
      />,
    );
    expect(screen.getByText('0.86')).toHaveClass('text-destructive');
    expect(screen.getByText('−0.09')).toBeInTheDocument();
    expect(screen.getByText('Recall@5 is 0.86, below the 0.90 target.')).toBeInTheDocument();
    expect(screen.getByText('Not in the top 5: fees-hostel')).toBeInTheDocument();
  });

  it('explains how to get the first run', () => {
    render(<QualitySection quality={{ latest: null, previous: null, warnings: [] }} />);
    expect(screen.getByText('No checks yet')).toBeInTheDocument();
  });
});
