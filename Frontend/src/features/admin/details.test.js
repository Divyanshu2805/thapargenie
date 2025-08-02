import { describe, expect, it } from 'vitest';

import { MAX_AI_DOCUMENTS, acceptedChanges, mergeAi, rowsNeedingAi, toRows, validateRows } from './details';

const result = (overrides) => ({
  id: 'd1',
  title: 'Notice',
  current_academic_year: '',
  current_effective_date: null,
  academic_year: '',
  effective_date: null,
  source: '',
  evidence: '',
  ...overrides,
});

describe('suggested details', () => {
  it('ticks rows only when a suggestion would change something', () => {
    const rows = toRows([
      result({ id: 'a', academic_year: '2026-27', source: 'text' }),
      result({ id: 'b', academic_year: '2026-27', current_academic_year: '2026-27', source: 'title' }),
      result({ id: 'c' }),
    ]);
    expect(rows.map((row) => row.accept)).toEqual([true, false, false]);
    expect(rows[2].effective_date).toBe('');
  });

  it('sends only ticked rows and only the fields that change', () => {
    const rows = toRows([
      result({ id: 'a', academic_year: '2026-27', effective_date: '2026-08-01', source: 'ai' }),
      result({ id: 'b', academic_year: '2025-26', current_effective_date: '2026-01-01', effective_date: '2026-01-01', source: 'text' }),
      result({ id: 'c', academic_year: '2024-25', source: 'text' }),
    ]);
    rows[2].accept = false;
    expect(acceptedChanges(rows)).toEqual({
      a: { academic_year: '2026-27', effective_date: '2026-08-01' },
      b: { academic_year: '2025-26' },
    });
  });

  it('fills only the rows the rules left empty with AI answers', () => {
    const rows = toRows([result({ id: 'a', academic_year: '2026-27', source: 'text' }), result({ id: 'b' }), result({ id: 'c' })]);
    const merged = mergeAi(rows, [
      result({ id: 'a', academic_year: '2099-00', source: 'ai' }),
      result({ id: 'b', effective_date: '2026-08-20', source: 'ai', evidence: 'Dated: August 20, 2026' }),
      result({ id: 'c' }),
    ]);
    expect(merged.map((row) => [row.id, row.academic_year, row.effective_date, row.source, row.accept])).toEqual([
      ['a', '2026-27', '', 'text', true],
      ['b', '', '2026-08-20', 'ai', true],
      ['c', '', '', '', false],
    ]);
  });

  it('asks the AI about at most 20 rows without a suggestion', () => {
    const rows = toRows(Array.from({ length: 25 }, (_, index) => result({ id: String(index) })));
    expect(rowsNeedingAi(rows)).toHaveLength(MAX_AI_DOCUMENTS);
  });

  it('checks the session format of ticked rows', () => {
    const rows = toRows([result({ id: 'a', academic_year: '2026', source: 'text' })]);
    expect(validateRows(rows)).toEqual({ a: 'Use the form 2026-27.' });
    expect(validateRows([{ ...rows[0], accept: false }])).toEqual({});
  });
});
