"""Outbound HTTP for admin-supplied URLs, guarded against SSRF.

Controls, in order: https only, no credentials in the URL, default port, host must be
on the allowlist, every resolved address must be public, redirects are re-validated
hop by hop, and the body is capped while streaming. The host allowlist is the primary
control; the address check is defence in depth against internal DNS entries.
"""

import ipaddress
import socket
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit

import httpx
from django.conf import settings

MAX_REDIRECTS = 5
USER_AGENT = 'ThaparGenie-Ingest/1.0 (+https://thapar.edu)'


class UnsafeURLError(ValueError):
    pass


class FetchError(Exception):
    pass


@dataclass(frozen=True)
class FetchResult:
    url: str
    content_type: str
    content: bytes


def host_allowed(host, allowlist):
    host = host.lower().rstrip('.')
    for entry in allowlist:
        entry = entry.lower().strip()
        if entry.startswith('*.'):
            if host.endswith(entry[1:]) and host != entry[2:]:
                return True
        elif host == entry:
            return True
    return False


def _resolve(host):
    try:
        infos = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise UnsafeURLError(f'Cannot resolve host {host!r}.') from exc
    return {info[4][0] for info in infos}


def validate_url(url, allowlist=None, resolver=_resolve):
    allowlist = settings.INGEST_URL_ALLOWLIST if allowlist is None else allowlist
    parts = urlsplit(url)
    if parts.scheme != 'https':
        raise UnsafeURLError('Only https URLs are allowed.')
    if parts.username or parts.password:
        raise UnsafeURLError('URLs with credentials are not allowed.')
    if parts.port not in (None, 443):
        raise UnsafeURLError('Only the default https port is allowed.')
    host = parts.hostname or ''
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise UnsafeURLError('IP address URLs are not allowed.')
    if not host_allowed(host, allowlist):
        raise UnsafeURLError(f'Host {host!r} is not on the allowlist.')
    for address in resolver(host):
        if not ipaddress.ip_address(address).is_global:
            raise UnsafeURLError(f'Host {host!r} resolves to a non-public address.')
    return url


def fetch(url, *, max_bytes, timeout=15.0, allowlist=None, resolver=_resolve, transport=None):
    """GET a URL within the ingestion allowlist, following safe redirects."""
    with httpx.Client(
        follow_redirects=False,
        timeout=timeout,
        headers={'User-Agent': USER_AGENT},
        transport=transport,
    ) as client:
        for _ in range(MAX_REDIRECTS + 1):
            validate_url(url, allowlist, resolver)
            with client.stream('GET', url) as response:
                if response.is_redirect:
                    location = response.headers.get('location', '')
                    url = urljoin(url, location)
                    continue
                if response.status_code != 200:
                    raise FetchError(f'Upstream returned HTTP {response.status_code}.')
                declared = response.headers.get('content-length')
                if declared and declared.isdigit() and int(declared) > max_bytes:
                    raise FetchError('Response is larger than the allowed size.')
                body = bytearray()
                for chunk in response.iter_bytes():
                    body.extend(chunk)
                    if len(body) > max_bytes:
                        raise FetchError('Response is larger than the allowed size.')
                return FetchResult(
                    url=str(response.url),
                    content_type=response.headers.get('content-type', ''),
                    content=bytes(body),
                )
    raise FetchError('Too many redirects.')
