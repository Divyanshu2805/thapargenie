import { render } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, describe, expect, it } from 'vitest';

import { PageMeta, pageMeta, SITE_URL } from './page-meta';

describe('pageMeta', () => {
  it('lets search engines index only the landing page and the privacy notice', () => {
    expect(pageMeta('/')).toMatchObject({ canonical: `${SITE_URL}/`, index: true });
    expect(pageMeta('/privacy')).toMatchObject({ canonical: `${SITE_URL}/privacy`, index: true });
    expect(pageMeta('/privacy/').index).toBe(true);
    for (const path of ['/chat/', '/chat/abc', '/admin/users', '/s/token', '/login/', '/settings/']) {
      expect(pageMeta(path)).toMatchObject({ canonical: null, index: false });
    }
  });

  it('names each page in the tab', () => {
    expect(pageMeta('/').title).toContain('Answers about Thapar');
    expect(pageMeta('/login/').title).toBe('Sign in · ThaparGenie');
    expect(pageMeta('/admin/gaps').title).toBe('Admin · ThaparGenie');
    expect(pageMeta('/chat/').title).toBe('ThaparGenie');
  });
});

describe('PageMeta', () => {
  afterEach(() => {
    document.head.querySelectorAll('link[rel="canonical"], meta[name="robots"]').forEach((element) => element.remove());
  });

  const show = (path) =>
    render(
      <MemoryRouter initialEntries={[path]}>
        <PageMeta />
      </MemoryRouter>,
    );

  it('sets the title and canonical link on a public page and no robots hint', () => {
    show('/privacy');
    expect(document.title).toBe('Privacy notice · ThaparGenie');
    expect(document.head.querySelector('link[rel="canonical"]').getAttribute('href')).toBe(`${SITE_URL}/privacy`);
    expect(document.head.querySelector('meta[name="robots"]')).toBeNull();
  });

  it('marks a signed-in page noindex and drops the canonical link', () => {
    show('/privacy').unmount();
    show('/chat/');
    expect(document.title).toBe('ThaparGenie');
    expect(document.head.querySelector('link[rel="canonical"]')).toBeNull();
    expect(document.head.querySelector('meta[name="robots"]').getAttribute('content')).toBe('noindex');
  });
});
