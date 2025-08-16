import { describe, expect, it } from 'vitest';

import { buildCsp } from './csp.config.js';

const parse = (csp) => Object.fromEntries(csp.split('; ').map((part) => {
  const [name, ...values] = part.split(' ');
  return [name, values];
}));

describe('buildCsp', () => {
  const csp = parse(
    buildCsp({ apiBaseUrl: 'https://api.thapargpt.in/api/v1/', firebaseAuthDomain: 'thapargpt.firebaseapp.com' }),
  );

  it('allows the API origin (not its path) and Firebase Auth endpoints', () => {
    expect(csp['connect-src']).toContain('https://api.thapargpt.in');
    expect(csp['connect-src']).toContain('https://identitytoolkit.googleapis.com');
    expect(csp['frame-src']).toEqual(['https://thapargpt.firebaseapp.com', 'https://accounts.google.com']);
  });

  it('never allows inline or evaluated scripts, plugins or foreign form posts', () => {
    expect(csp['script-src']).toEqual(["'self'", 'https://apis.google.com']);
    expect(csp['script-src'].join(' ')).not.toMatch(/unsafe/);
    expect(csp['object-src']).toEqual(["'none'"]);
    expect(csp['form-action']).toEqual(["'self'"]);
    expect(csp['base-uri']).toEqual(["'self'"]);
  });

  it('upgrades insecure requests only for an https API', () => {
    expect(csp).toHaveProperty('upgrade-insecure-requests');
    const local = parse(buildCsp({ apiBaseUrl: 'http://127.0.0.1:8000/api/v1/' }));
    expect(local).not.toHaveProperty('upgrade-insecure-requests');
    expect(local['frame-src']).toEqual(['https://accounts.google.com']);
  });

  it('allows the Auth emulator only in a local end-to-end build', () => {
    expect(csp['connect-src'].join(' ')).not.toMatch(/9099/);
    const e2e = parse(buildCsp({ apiBaseUrl: 'http://127.0.0.1:8020/api/v1/', authEmulatorUrl: 'http://127.0.0.1:9099' }));
    expect(e2e['connect-src']).toContain('http://127.0.0.1:9099');
    expect(() =>
      buildCsp({ apiBaseUrl: 'https://api.thapargpt.in/api/v1/', authEmulatorUrl: 'http://127.0.0.1:9099' }),
    ).toThrow(/local end-to-end builds only/);
  });

  it('refuses to build without an absolute API URL', () => {
    expect(() => buildCsp({ apiBaseUrl: '/api/v1/' })).toThrow(/absolute URL/);
  });
});
