import { useEffect } from 'react';
import { useLocation } from 'react-router-dom';

// The tab title, canonical link and indexing hint for each page. Only the landing page
// and the privacy notice are meant for search engines; everything else needs a sign-in
// or is a private link, and is marked noindex (robots.txt keeps crawlers out as well).

export const SITE_URL = 'https://thapargenie.divyanshuagrahari.dev';
const NAME = 'ThaparGenie';

const PUBLIC_PAGES = {
  '/': { title: `${NAME} · Answers about Thapar, straight from the source`, canonical: '/' },
  '/privacy': { title: `Privacy notice · ${NAME}`, canonical: '/privacy' },
};

const TITLES = [
  ['/login', `Sign in · ${NAME}`],
  ['/register', `Create account · ${NAME}`],
  ['/forgot-password', `Reset password · ${NAME}`],
  ['/admin', `Admin · ${NAME}`],
  ['/s/', `Shared answer · ${NAME}`],
];

/** {title, canonical (absolute URL or null), index} for a path. */
export function pageMeta(pathname) {
  const path = pathname.length > 1 ? pathname.replace(/\/+$/, '') : pathname;
  const page = PUBLIC_PAGES[path];
  if (page) return { title: page.title, canonical: `${SITE_URL}${page.canonical}`, index: true };
  const match = TITLES.find(([prefix]) => pathname.startsWith(prefix));
  return { title: match ? match[1] : NAME, canonical: null, index: false };
}

function setTag(selector, create, apply) {
  let element = document.head.querySelector(selector);
  if (!apply) {
    element?.remove();
    return;
  }
  if (!element) {
    element = create();
    document.head.appendChild(element);
  }
  apply(element);
}

/** Keeps <title>, the canonical link and the robots hint in step with the route. */
export function PageMeta() {
  const { pathname } = useLocation();
  useEffect(() => {
    const meta = pageMeta(pathname);
    document.title = meta.title;
    setTag(
      'link[rel="canonical"]',
      () => Object.assign(document.createElement('link'), { rel: 'canonical' }),
      meta.canonical ? (link) => link.setAttribute('href', meta.canonical) : null,
    );
    setTag(
      'meta[name="robots"]',
      () => Object.assign(document.createElement('meta'), { name: 'robots' }),
      meta.index ? null : (tag) => tag.setAttribute('content', 'noindex'),
    );
  }, [pathname]);
  return null;
}
