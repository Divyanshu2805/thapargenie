import { describe, expect, it } from 'vitest';

import { currentSession, describeFreshness } from './freshness';

const SEPT_2026 = new Date(2026, 8, 25);

function source(overrides = {}) {
  return { cited: true, academic_year: '', effective_date: null, is_current: true, ...overrides };
}

describe('currentSession', () => {
  it('starts a new session in July', () => {
    expect(currentSession(new Date(2026, 5, 30))).toBe('2025-26');
    expect(currentSession(new Date(2026, 6, 1))).toBe('2026-27');
    expect(currentSession(new Date(2099, 11, 31))).toBe('2099-00');
  });
});

describe('describeFreshness', () => {
  it('summarises the session and date of the cited sources', () => {
    const result = describeFreshness([source({ academic_year: '2026-27', effective_date: '2026-08-12' })], SEPT_2026);
    expect(result).toEqual({ summary: 'Based on session 2026-27 sources · dated 12 Aug 2026', warning: null });
  });

  it('lists several sessions and uses the latest date', () => {
    const result = describeFreshness(
      [
        source({ academic_year: '2026-27', effective_date: '2026-08-12' }),
        source({ academic_year: '2025-26', effective_date: '2025-07-01' }),
        source({ academic_year: '2026-27' }),
      ],
      SEPT_2026,
    );
    expect(result.summary).toBe('Based on sessions 2025-26, 2026-27 sources · latest dated 12 Aug 2026');
  });

  it('shows a date alone when no session is known', () => {
    expect(describeFreshness([source({ effective_date: '2026-03-05' })], SEPT_2026).summary).toBe(
      'Sources dated 5 Mar 2026',
    );
  });

  it('ignores sources the answer did not cite', () => {
    expect(describeFreshness([source({ cited: false, academic_year: '2026-27' })], SEPT_2026)).toBeNull();
  });

  it('says nothing when the cited sources carry no year or date', () => {
    expect(describeFreshness([source()], SEPT_2026)).toBeNull();
    expect(describeFreshness([], SEPT_2026)).toBeNull();
    expect(describeFreshness(undefined, SEPT_2026)).toBeNull();
  });

  it('warns when the newest session is older than the current one', () => {
    const result = describeFreshness([source({ academic_year: '2025-26' })], SEPT_2026);
    expect(result.warning).toBe('The newest source is from session 2025-26. Details for 2026-27 may differ; check the official site.');
  });

  it('does not warn when any cited source is from the current session', () => {
    const result = describeFreshness([source({ academic_year: '2025-26' }), source({ academic_year: '2026-27' })], SEPT_2026);
    expect(result.warning).toBeNull();
  });

  it('warns about a not-current document first, even without a year or date', () => {
    const result = describeFreshness([source({ is_current: false, academic_year: '2024-25' })], SEPT_2026);
    expect(result.warning).toMatch(/marked as no longer current/);
    expect(describeFreshness([source({ is_current: false })], SEPT_2026)).toEqual({
      summary: null,
      warning: expect.stringMatching(/no longer current/),
    });
  });

  it('leaves out dates after today (placeholders, not issue dates)', () => {
    const result = describeFreshness(
      [source({ effective_date: '2027-12-31' }), source({ effective_date: '2026-09-01' })],
      SEPT_2026,
    );
    expect(result.summary).toBe('Sources dated 1 Sept 2026');
    expect(describeFreshness([source({ effective_date: '2027-12-31' })], SEPT_2026)).toBeNull();
  });

  it('treats a deleted document (is_current null) as unknown, not outdated', () => {
    expect(describeFreshness([source({ is_current: null, academic_year: '2026-27' })], SEPT_2026).warning).toBeNull();
  });

  it('ignores malformed years and dates', () => {
    expect(describeFreshness([source({ academic_year: '2026', effective_date: '12/08/2026' })], SEPT_2026)).toBeNull();
  });
});
