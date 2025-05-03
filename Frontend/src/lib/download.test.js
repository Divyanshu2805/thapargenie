import { describe, expect, it } from 'vitest';

import { filenameFrom } from './download';

describe('filenameFrom', () => {
  it('reads the server’s file name, or falls back', () => {
    expect(filenameFrom('attachment; filename="thapargenie-gaps-2026-09-26.csv"', 'x.csv')).toBe('thapargenie-gaps-2026-09-26.csv');
    expect(filenameFrom('attachment; filename=stats.csv', 'x.csv')).toBe('stats.csv');
    expect(filenameFrom('', 'x.csv')).toBe('x.csv');
  });
});
