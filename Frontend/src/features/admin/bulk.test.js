import { describe, expect, it, vi } from 'vitest';

import { bulkChanges, bulkSummary, chunks, reprocesses, runInBatches, validateBulkChanges } from './bulk';

describe('runInBatches', () => {
  const ids = Array.from({ length: 250 }, (_, index) => `d${index}`);

  it('sends batches of 100 in order and adds up the results', async () => {
    const send = vi.fn(async (batch) => ({ succeeded: batch.slice(1), failed: [{ id: batch[0], message: 'No.' }] }));
    const progress = vi.fn();
    const result = await runInBatches(ids, send, { onProgress: progress });
    expect(send.mock.calls.map(([batch]) => batch.length)).toEqual([100, 100, 50]);
    expect(result.succeeded).toHaveLength(247);
    expect(result.failed.map((item) => item.id)).toEqual(['d0', 'd100', 'd200']);
    expect(result.skipped).toEqual([]);
    expect(progress.mock.calls).toEqual([
      [100, 250],
      [200, 250],
      [250, 250],
    ]);
  });

  it('stops between batches and reports what was not sent', async () => {
    let stop = false;
    const send = vi.fn(async (batch) => {
      stop = true;
      return { succeeded: batch, failed: [] };
    });
    const result = await runInBatches(ids, send, { shouldStop: () => stop });
    expect(send).toHaveBeenCalledTimes(1);
    expect(result.succeeded).toHaveLength(100);
    expect(result.skipped).toHaveLength(150);
    expect(result.skipped[0]).toBe('d100');
  });

  it('splits into chunks', () => {
    expect(chunks([1, 2, 3], 2)).toEqual([[1, 2], [3]]);
    expect(chunks([], 2)).toEqual([]);
  });
});

const field = (apply, value) => ({ apply, value });

describe('bulkChanges', () => {
  it('keeps only ticked fields, trims text and turns empty dates into null', () => {
    expect(
      bulkChanges({
        category: field(false, 'faq'),
        academic_year: field(true, ' 2026-27 '),
        department: field(true, ''),
        effective_date: field(false, ''),
        valid_until: field(true, ''),
        is_current: field(true, false),
      }),
    ).toEqual({ academic_year: '2026-27', department: '', valid_until: null, is_current: false });
  });
});

describe('validateBulkChanges', () => {
  it('needs at least one field', () => {
    expect(validateBulkChanges({})).toEqual({ form: 'Tick at least one field to change.' });
  });

  it('checks the academic year and the date order', () => {
    expect(validateBulkChanges({ academic_year: '2026', effective_date: '2026-08-01', valid_until: '2026-07-01' })).toEqual({
      academic_year: 'Use the form 2026-27.',
      valid_until: '“Valid until” can’t be before the effective date.',
    });
    expect(validateBulkChanges({ academic_year: '' })).toEqual({});
  });
});

describe('reprocesses', () => {
  it('is true for fields that are part of the search text', () => {
    expect(reprocesses({ department: 'CSED' })).toBe(true);
    expect(reprocesses({ is_current: false, valid_until: null })).toBe(false);
  });
});

describe('bulkSummary', () => {
  it('reports success, partial failure and total failure', () => {
    expect(bulkSummary('update', { succeeded: ['a'], failed: [] })).toEqual({ ok: true, title: 'Updated 1 document', description: null });
    expect(bulkSummary('delete', { succeeded: ['a', 'b'], failed: [{ id: 'c', message: 'Gone.' }] })).toEqual({
      ok: false,
      title: 'Deleted 2 documents; 1 failed',
      description: 'Gone.',
    });
    expect(bulkSummary('reprocess', { succeeded: [], failed: [{ id: 'c', message: 'Busy.' }] }).title).toBe('1 document failed');
    expect(bulkSummary('update', { succeeded: ['a'], failed: [], skipped: ['b', 'c'] })).toEqual({
      ok: false,
      title: 'Updated 1 document',
      description: 'Stopped: 2 documents not processed.',
    });
  });
});
