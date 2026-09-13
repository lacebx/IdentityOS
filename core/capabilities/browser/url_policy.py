"""Network boundary for autonomous browser navigation."""

from __future__ import annotations

import ipaddress
import socket
from functools import lru_cache
from urllib.parse import urlsplit


class UnsafeBrowserURL(ValueError):
    """Raised when a URL crosses the browser capability's safety boundary."""


def validate_navigation_url(
    url: str,
    *,
    allow_private_network: bool = False,
) -> str:
    """Allow HTTP(S) navigation while blocking local-file and SSRF targets."""
    candidate = (url or "").strip()
    parsed = urlsplit(candidate)
    if parsed.scheme.lower() not in {"http", "https"}:
        raise UnsafeBrowserURL("browser navigation only supports http:// and https:// URLs")
    if not parsed.hostname:
        raise UnsafeBrowserURL("browser navigation requires a hostname")
    if parsed.username is not None or parsed.password is not None:
        raise UnsafeBrowserURL("credentials embedded in browser URLs are not allowed")
    if not allow_private_network:
        _require_public_host(parsed.hostname)
    return candidate


def allow_browser_request(url: str, *, allow_private_network: bool = False) -> bool:
    """Validate network requests while allowing browser-internal resource URLs."""
    scheme = urlsplit(url).scheme.lower()
    if scheme in {"about", "blob", "data"}:
        return True
    try:
        validate_navigation_url(url, allow_private_network=allow_private_network)
    except UnsafeBrowserURL:
        return False
    return True


@lru_cache(maxsize=512)
def _resolved_addresses(hostname: str) -> tuple[str, ...]:
    try:
        records = socket.getaddrinfo(hostname, None, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise UnsafeBrowserURL(f"browser hostname could not be resolved: {hostname}") from exc
    return tuple(sorted({record[4][0] for record in records}))


def _require_public_host(hostname: str) -> None:
    normalized = hostname.rstrip(".").lower()
    if normalized == "localhost" or normalized.endswith(".localhost"):
        raise UnsafeBrowserURL("browser access to localhost is disabled")

    try:
        direct = ipaddress.ip_address(normalized)
        addresses = (direct,)
    except ValueError:
        addresses = tuple(ipaddress.ip_address(value) for value in _resolved_addresses(normalized))

    if not addresses or any(not address.is_global for address in addresses):
        raise UnsafeBrowserURL("browser access to private or non-global networks is disabled")

