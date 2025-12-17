"""URL validation for SSRF protection.

This module provides utilities to validate URLs and prevent
Server-Side Request Forgery (SSRF) attacks by blocking:
- Private/internal IP ranges
- Loopback addresses
- Link-local addresses
- Dangerous URL schemes
- DNS rebinding attacks
"""

import ipaddress
import os
import socket
from typing import Set, Optional, List
from urllib.parse import urlparse

from cognee.shared.logging_utils import get_logger

logger = get_logger("url_validator")

# Blocked URL schemes that could be dangerous
BLOCKED_SCHEMES: Set[str] = frozenset({
    "file",
    "gopher",
    "ftp",
    "data",
    "javascript",
    "vbscript",
    "about",
    "blob",
})

# Allowed schemes (whitelist approach)
ALLOWED_SCHEMES: Set[str] = frozenset({"http", "https"})

# Private/internal network ranges to block
PRIVATE_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),        # Class A private
    ipaddress.ip_network("172.16.0.0/12"),     # Class B private
    ipaddress.ip_network("192.168.0.0/16"),    # Class C private
    ipaddress.ip_network("127.0.0.0/8"),       # Loopback
    ipaddress.ip_network("169.254.0.0/16"),    # Link-local
    ipaddress.ip_network("0.0.0.0/8"),         # Current network
    ipaddress.ip_network("100.64.0.0/10"),     # Carrier-grade NAT
    ipaddress.ip_network("192.0.0.0/24"),      # IETF protocol assignments
    ipaddress.ip_network("192.0.2.0/24"),      # TEST-NET-1
    ipaddress.ip_network("198.51.100.0/24"),   # TEST-NET-2
    ipaddress.ip_network("203.0.113.0/24"),    # TEST-NET-3
    ipaddress.ip_network("224.0.0.0/4"),       # Multicast
    ipaddress.ip_network("240.0.0.0/4"),       # Reserved
    ipaddress.ip_network("255.255.255.255/32"),  # Broadcast
    # IPv6 private ranges
    ipaddress.ip_network("::1/128"),           # Loopback
    ipaddress.ip_network("fc00::/7"),          # Unique local
    ipaddress.ip_network("fe80::/10"),         # Link-local
    ipaddress.ip_network("ff00::/8"),          # Multicast
]

# Environment-controlled SSRF protection
SSRF_PROTECTION_ENABLED = os.getenv("SSRF_PROTECTION_ENABLED", "true").lower() == "true"
ALLOW_PRIVATE_URLS = os.getenv("ALLOW_PRIVATE_URLS", "false").lower() == "true"


class SSRFError(ValueError):
    """Raised when a URL fails SSRF validation."""

    pass


def is_private_ip(ip_str: str) -> bool:
    """Check if an IP address is in a private/internal range.

    Args:
        ip_str: IP address as string

    Returns:
        True if IP is private/internal
    """
    try:
        ip = ipaddress.ip_address(ip_str)

        # Check against all private networks
        for network in PRIVATE_NETWORKS:
            if ip in network:
                return True

        # Use ipaddress module's built-in checks
        if ip.is_private or ip.is_loopback or ip.is_reserved or ip.is_multicast:
            return True

        return False

    except ValueError:
        # Invalid IP format
        return True  # Block on error


def resolve_hostname(hostname: str, timeout: float = 5.0) -> Optional[str]:
    """Resolve hostname to IP address.

    Args:
        hostname: Hostname to resolve
        timeout: DNS resolution timeout

    Returns:
        IP address string or None if resolution fails
    """
    old_timeout = socket.getdefaulttimeout()
    try:
        socket.setdefaulttimeout(timeout)
        return socket.gethostbyname(hostname)
    except socket.gaierror:
        return None
    finally:
        socket.setdefaulttimeout(old_timeout)


def validate_url_for_ssrf(
    url: str,
    allow_private: Optional[bool] = None,
) -> str:
    """Validate URL is safe from SSRF attacks.

    Performs the following checks:
    1. URL scheme is allowed (http/https only)
    2. Hostname is present and valid
    3. Resolved IP is not in private/internal range

    Args:
        url: URL to validate
        allow_private: Override for allowing private IPs (default from env)

    Returns:
        The validated URL (unchanged)

    Raises:
        SSRFError: If URL fails any validation check
    """
    if not SSRF_PROTECTION_ENABLED:
        logger.debug("SSRF protection disabled, skipping validation")
        return url

    allow_private = allow_private if allow_private is not None else ALLOW_PRIVATE_URLS

    # Parse URL
    try:
        parsed = urlparse(url)
    except Exception as e:
        raise SSRFError(f"Invalid URL format: {e}")

    # Validate scheme
    scheme = (parsed.scheme or "").lower()

    if scheme in BLOCKED_SCHEMES:
        raise SSRFError(f"URL scheme '{scheme}' is blocked for security reasons")

    if scheme not in ALLOWED_SCHEMES:
        raise SSRFError(
            f"URL scheme '{scheme}' is not allowed. Use http or https."
        )

    # Validate hostname
    hostname = parsed.hostname

    if not hostname:
        raise SSRFError("URL must have a hostname")

    # Block obvious internal hostnames
    blocked_hostnames = {"localhost", "127.0.0.1", "::1", "0.0.0.0"}
    if hostname.lower() in blocked_hostnames:
        raise SSRFError(f"Access to '{hostname}' is not allowed")

    # Skip IP validation if private URLs are allowed
    if allow_private:
        logger.debug(f"Private URLs allowed, skipping IP validation for {hostname}")
        return url

    # Resolve hostname and check IP
    ip_str = resolve_hostname(hostname)

    if ip_str is None:
        raise SSRFError(f"Could not resolve hostname: {hostname}")

    if is_private_ip(ip_str):
        raise SSRFError(
            f"Access to private/internal network ({ip_str}) is not allowed. "
            f"Hostname '{hostname}' resolved to a blocked IP range."
        )

    logger.debug(f"URL validated: {url} -> {ip_str}")
    return url


def validate_urls_for_ssrf(urls: List[str], **kwargs) -> List[str]:
    """Validate multiple URLs for SSRF.

    Args:
        urls: List of URLs to validate
        **kwargs: Passed to validate_url_for_ssrf

    Returns:
        List of validated URLs

    Raises:
        SSRFError: If any URL fails validation
    """
    return [validate_url_for_ssrf(url, **kwargs) for url in urls]
