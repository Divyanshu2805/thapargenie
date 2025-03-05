import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { API_BASE_URL } from '../utils/constants';
import { _resetForTests, buildReport, isChunkLoadError, reloadForNewVersion, reportError, shouldReport } from './error-reporting';

describe('error reporting', () => {
  beforeEach(() => {
    _resetForTests();
    globalThis.fetch = vi.fn().mockResolvedValue({ ok: true });
    window.history.replaceState(null, '', '/chat/abc?q=private#frag');
  });
  afterEach(() => window.sessionStorage.clear());

  it('sends the path without the query string, and no token', () => {
    reportError(new TypeError('x is undefined'), 'render');
    const [url, init] = fetch.mock.calls[0];
    expect(String(url)).toBe(new URL('client-errors/', API_BASE_URL).toString());
    expect(init.headers).toEqual({ 'Content-Type': 'application/json' });
    const body = JSON.parse(init.body);
    expect(body).toMatchObject({ message: 'x is undefined', kind: 'render', path: '/chat/abc' });
    expect(init.body).not.toContain('private');
  });

  it('sends each distinct error once and caps reports per page', () => {
    reportError(new Error('same'));
    reportError(new Error('same'));
    for (let i = 0; i < 20; i += 1) reportError(new Error(`e${i}`));
    expect(fetch).toHaveBeenCalledTimes(10);
  });

  it('skips expected and foreign errors', () => {
    expect(shouldReport(Object.assign(new Error('Limit reached'), { name: 'ApiError' }))).toBe(false);
    expect(shouldReport(new Error('ResizeObserver loop limit exceeded'))).toBe(false);
    expect(shouldReport(Object.assign(new Error('x'), { stack: 'at chrome-extension://abc/x.js' }))).toBe(false);
    expect(shouldReport(new Error('real bug'))).toBe(true);
  });

  it('truncates long messages and stacks', () => {
    const report = buildReport(Object.assign(new Error('m'.repeat(900)), { stack: 's'.repeat(9000) }));
    expect(report.message).toHaveLength(500);
    expect(report.stack).toHaveLength(4000);
  });

  it('recognises stale-chunk errors and reloads only once per session', () => {
    const error = new TypeError('Failed to fetch dynamically imported module: /assets/Page-abc.js');
    expect(isChunkLoadError(error)).toBe(true);
    const reload = vi.fn();
    Object.defineProperty(window, 'location', { value: { ...window.location, reload, pathname: '/chat/' }, configurable: true });
    expect(reloadForNewVersion(error)).toBe(true);
    expect(reloadForNewVersion(error)).toBe(false);
    expect(reload).toHaveBeenCalledTimes(1);
    expect(fetch).toHaveBeenCalledTimes(1);
  });
});
