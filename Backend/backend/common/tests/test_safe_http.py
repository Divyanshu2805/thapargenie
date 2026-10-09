import httpx
from django.test import SimpleTestCase

from common.safe_http import FetchError, UnsafeURLError, fetch, host_allowed, validate_url

ALLOW = ('thapar.edu', '*.thapar.edu')


def public(_host):
    return {'8.8.8.10'}


def private(_host):
    return {'10.0.0.5'}


class HostAllowlistTests(SimpleTestCase):
    def test_exact_and_wildcard(self):
        self.assertTrue(host_allowed('thapar.edu', ALLOW))
        self.assertTrue(host_allowed('admission.thapar.edu', ALLOW))
        self.assertTrue(host_allowed('ADMISSION.THAPAR.EDU.', ALLOW))

    def test_lookalikes_rejected(self):
        self.assertFalse(host_allowed('thapar.edu.evil.com', ALLOW))
        self.assertFalse(host_allowed('evilthapar.edu', ALLOW))
        self.assertFalse(host_allowed('thapar.edu', ('*.thapar.edu',)))


class ValidateURLTests(SimpleTestCase):
    def test_accepts_public_allowlisted_https(self):
        url = 'https://www.thapar.edu/fees'
        self.assertEqual(validate_url(url, ALLOW, public), url)

    def test_rejections(self):
        cases = [
            'http://www.thapar.edu/',
            'https://user:pw@www.thapar.edu/',
            'https://www.thapar.edu:8443/',
            'https://169.254.169.254/latest/meta-data',
            'https://127.0.0.1/',
            'https://localhost/',
            'https://example.com/',
            'file:///etc/passwd',
        ]
        for url in cases:
            with self.subTest(url=url), self.assertRaises(UnsafeURLError):
                validate_url(url, ALLOW, public)

    def test_private_resolution_rejected(self):
        with self.assertRaises(UnsafeURLError):
            validate_url('https://intranet.thapar.edu/', ALLOW, private)


class FetchTests(SimpleTestCase):
    def run_fetch(self, handler, url='https://www.thapar.edu/a', max_bytes=1000):
        return fetch(
            url,
            max_bytes=max_bytes,
            allowlist=ALLOW,
            resolver=public,
            transport=httpx.MockTransport(handler),
        )

    def test_returns_body(self):
        html = httpx.Response(200, text='<h1>Fees</h1>', headers={'content-type': 'text/html'})
        result = self.run_fetch(lambda request: html)
        self.assertEqual(result.content, b'<h1>Fees</h1>')
        self.assertEqual(result.content_type, 'text/html')

    def test_follows_allowed_redirect(self):
        def handler(request):
            if request.url.path == '/a':
                return httpx.Response(302, headers={'location': '/b'})
            return httpx.Response(200, text='ok')

        self.assertEqual(self.run_fetch(handler).url, 'https://www.thapar.edu/b')

    def test_blocks_redirect_off_allowlist(self):
        handler = lambda request: httpx.Response(  # noqa: E731
            302, headers={'location': 'https://169.254.169.254/'}
        )
        with self.assertRaises(UnsafeURLError):
            self.run_fetch(handler)

    def test_connects_to_the_checked_address(self):
        # The name is resolved once: a second lookup at connect time could be answered
        # with an internal address (DNS rebinding).
        seen = []

        def handler(request):
            seen.append((request.url.host, request.headers['host'], request.extensions))
            return httpx.Response(200, text='ok')

        result = self.run_fetch(handler, url='https://www.thapar.edu/a?b=1')
        host, header, extensions = seen[0]
        self.assertEqual(host, '8.8.8.10')
        self.assertEqual(header, 'www.thapar.edu')
        self.assertEqual(extensions['sni_hostname'], 'www.thapar.edu')
        self.assertEqual(result.url, 'https://www.thapar.edu/a?b=1')

    def test_resolves_once_per_hop(self):
        calls = []

        def resolver(host):
            calls.append(host)
            return {'8.8.8.10'}

        fetch(
            'https://www.thapar.edu/a',
            max_bytes=1000,
            allowlist=ALLOW,
            resolver=resolver,
            transport=httpx.MockTransport(lambda request: httpx.Response(200, text='ok')),
        )
        self.assertEqual(calls, ['www.thapar.edu'])

    def test_prefers_ipv4_and_brackets_ipv6(self):
        seen = []

        def handler(request):
            seen.append(request.url.host)
            return httpx.Response(200, text='ok')

        for addresses in ({'2001:4860:4860::8888', '8.8.8.10'}, {'2001:4860:4860::8888'}):
            fetch(
                'https://www.thapar.edu/a',
                max_bytes=1000,
                allowlist=ALLOW,
                resolver=lambda _host, addresses=addresses: addresses,
                transport=httpx.MockTransport(handler),
            )
        self.assertEqual(seen, ['8.8.8.10', '2001:4860:4860::8888'])

    def test_unresolvable_host_rejected(self):
        with self.assertRaises(UnsafeURLError):
            validate_url('https://www.thapar.edu/', ALLOW, lambda _host: set())

    def test_caps_body_size(self):
        with self.assertRaises(FetchError):
            self.run_fetch(lambda request: httpx.Response(200, content=b'x' * 2000))

    def test_non_200_is_error(self):
        with self.assertRaises(FetchError):
            self.run_fetch(lambda request: httpx.Response(404))
