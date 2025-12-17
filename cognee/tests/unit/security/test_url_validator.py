"""Tests for URL validator SSRF protection."""

import os
import pytest
from unittest.mock import patch, MagicMock

from cognee.shared.security.url_validator import (
    validate_url_for_ssrf,
    validate_urls_for_ssrf,
    is_private_ip,
    resolve_hostname,
    SSRFError,
    ALLOWED_SCHEMES,
    BLOCKED_SCHEMES,
)


class TestIsPrivateIP:
    """Tests for is_private_ip function."""

    def test_loopback_ipv4_is_private(self):
        """127.x.x.x addresses should be private."""
        assert is_private_ip("127.0.0.1") is True
        assert is_private_ip("127.0.0.2") is True
        assert is_private_ip("127.255.255.255") is True

    def test_loopback_ipv6_is_private(self):
        """::1 should be private."""
        assert is_private_ip("::1") is True

    def test_class_a_private_is_private(self):
        """10.x.x.x addresses should be private."""
        assert is_private_ip("10.0.0.1") is True
        assert is_private_ip("10.255.255.255") is True

    def test_class_b_private_is_private(self):
        """172.16.x.x - 172.31.x.x addresses should be private."""
        assert is_private_ip("172.16.0.1") is True
        assert is_private_ip("172.31.255.255") is True
        # 172.32.x.x is NOT private
        assert is_private_ip("172.32.0.1") is False

    def test_class_c_private_is_private(self):
        """192.168.x.x addresses should be private."""
        assert is_private_ip("192.168.0.1") is True
        assert is_private_ip("192.168.255.255") is True

    def test_link_local_is_private(self):
        """169.254.x.x addresses should be private."""
        assert is_private_ip("169.254.0.1") is True
        assert is_private_ip("169.254.169.254") is True  # AWS metadata

    def test_public_ip_is_not_private(self):
        """Public IPs should not be private."""
        assert is_private_ip("8.8.8.8") is False
        assert is_private_ip("1.1.1.1") is False
        assert is_private_ip("93.184.216.34") is False  # example.com

    def test_multicast_is_private(self):
        """Multicast addresses should be private."""
        assert is_private_ip("224.0.0.1") is True
        assert is_private_ip("239.255.255.255") is True

    def test_broadcast_is_private(self):
        """Broadcast address should be private."""
        assert is_private_ip("255.255.255.255") is True

    def test_invalid_ip_returns_true(self):
        """Invalid IP formats should be treated as private (blocked)."""
        assert is_private_ip("not-an-ip") is True
        assert is_private_ip("") is True
        assert is_private_ip("256.256.256.256") is True


class TestResolveHostname:
    """Tests for resolve_hostname function."""

    def test_resolves_valid_hostname(self):
        """Should resolve valid hostnames."""
        with patch("socket.gethostbyname") as mock_resolve:
            mock_resolve.return_value = "93.184.216.34"
            result = resolve_hostname("example.com")
            assert result == "93.184.216.34"

    def test_returns_none_for_invalid_hostname(self):
        """Should return None for unresolvable hostnames."""
        with patch("socket.gethostbyname") as mock_resolve:
            import socket
            mock_resolve.side_effect = socket.gaierror("DNS resolution failed")
            result = resolve_hostname("invalid.nonexistent.tld")
            assert result is None

    def test_respects_timeout(self):
        """Should use timeout for DNS resolution."""
        with patch("socket.setdefaulttimeout") as mock_timeout:
            with patch("socket.gethostbyname") as mock_resolve:
                mock_resolve.return_value = "1.2.3.4"
                resolve_hostname("example.com", timeout=2.0)
                mock_timeout.assert_called()


class TestValidateUrlForSsrf:
    """Tests for validate_url_for_ssrf function."""

    def test_allows_valid_https_url(self):
        """Valid HTTPS URLs should pass."""
        with patch("cognee.shared.security.url_validator.resolve_hostname") as mock_resolve:
            mock_resolve.return_value = "93.184.216.34"
            result = validate_url_for_ssrf("https://example.com/path")
            assert result == "https://example.com/path"

    def test_allows_valid_http_url(self):
        """Valid HTTP URLs should pass."""
        with patch("cognee.shared.security.url_validator.resolve_hostname") as mock_resolve:
            mock_resolve.return_value = "93.184.216.34"
            result = validate_url_for_ssrf("http://example.com/path")
            assert result == "http://example.com/path"

    def test_blocks_file_scheme(self):
        """File scheme should be blocked."""
        with pytest.raises(SSRFError) as exc_info:
            validate_url_for_ssrf("file:///etc/passwd")
        assert "blocked" in str(exc_info.value).lower()

    def test_blocks_gopher_scheme(self):
        """Gopher scheme should be blocked."""
        with pytest.raises(SSRFError) as exc_info:
            validate_url_for_ssrf("gopher://localhost:25")
        assert "blocked" in str(exc_info.value).lower()

    def test_blocks_ftp_scheme(self):
        """FTP scheme should be blocked."""
        with pytest.raises(SSRFError) as exc_info:
            validate_url_for_ssrf("ftp://ftp.example.com/file")
        assert "blocked" in str(exc_info.value).lower()

    def test_blocks_data_scheme(self):
        """Data scheme should be blocked."""
        with pytest.raises(SSRFError) as exc_info:
            validate_url_for_ssrf("data:text/html,<script>alert(1)</script>")
        assert "blocked" in str(exc_info.value).lower()

    def test_blocks_javascript_scheme(self):
        """JavaScript scheme should be blocked."""
        with pytest.raises(SSRFError) as exc_info:
            validate_url_for_ssrf("javascript:alert(1)")
        assert "blocked" in str(exc_info.value).lower()

    def test_blocks_localhost(self):
        """Localhost should be blocked."""
        with pytest.raises(SSRFError) as exc_info:
            validate_url_for_ssrf("http://localhost/admin")
        assert "not allowed" in str(exc_info.value).lower()

    def test_blocks_127_0_0_1(self):
        """127.0.0.1 should be blocked."""
        with pytest.raises(SSRFError) as exc_info:
            validate_url_for_ssrf("http://127.0.0.1/admin")
        assert "not allowed" in str(exc_info.value).lower()

    def test_blocks_ipv6_loopback(self):
        """::1 should be blocked."""
        with pytest.raises(SSRFError) as exc_info:
            validate_url_for_ssrf("http://[::1]/admin")
        assert "not allowed" in str(exc_info.value).lower()

    def test_blocks_private_ip_resolution(self):
        """URLs resolving to private IPs should be blocked."""
        with patch("cognee.shared.security.url_validator.resolve_hostname") as mock_resolve:
            mock_resolve.return_value = "192.168.1.1"
            with pytest.raises(SSRFError) as exc_info:
                validate_url_for_ssrf("http://internal.company.com")
            assert "private" in str(exc_info.value).lower()

    def test_blocks_aws_metadata_endpoint(self):
        """AWS metadata endpoint should be blocked."""
        with patch("cognee.shared.security.url_validator.resolve_hostname") as mock_resolve:
            mock_resolve.return_value = "169.254.169.254"
            with pytest.raises(SSRFError) as exc_info:
                validate_url_for_ssrf("http://169.254.169.254/latest/meta-data/")
            assert "private" in str(exc_info.value).lower()

    def test_blocks_url_without_hostname(self):
        """URLs without hostname should be blocked."""
        with pytest.raises(SSRFError) as exc_info:
            validate_url_for_ssrf("http:///path")
        assert "hostname" in str(exc_info.value).lower()

    def test_blocks_unresolvable_hostname(self):
        """Unresolvable hostnames should be blocked."""
        with patch("cognee.shared.security.url_validator.resolve_hostname") as mock_resolve:
            mock_resolve.return_value = None
            with pytest.raises(SSRFError) as exc_info:
                validate_url_for_ssrf("http://nonexistent.invalid.tld/")
            assert "resolve" in str(exc_info.value).lower()

    def test_allows_private_when_flag_set(self):
        """Private IPs should be allowed when allow_private=True."""
        with patch("cognee.shared.security.url_validator.resolve_hostname") as mock_resolve:
            mock_resolve.return_value = "192.168.1.1"
            result = validate_url_for_ssrf(
                "http://internal.company.com",
                allow_private=True
            )
            assert result == "http://internal.company.com"

    def test_respects_ssrf_protection_disabled_env(self):
        """Should skip validation when SSRF_PROTECTION_ENABLED=false."""
        with patch.dict(os.environ, {"SSRF_PROTECTION_ENABLED": "false"}):
            # Need to reload the module to pick up the env var
            with patch("cognee.shared.security.url_validator.SSRF_PROTECTION_ENABLED", False):
                result = validate_url_for_ssrf("http://localhost/admin")
                assert result == "http://localhost/admin"


class TestValidateUrlsForSsrf:
    """Tests for validate_urls_for_ssrf function."""

    def test_validates_multiple_urls(self):
        """Should validate all URLs in a list."""
        with patch("cognee.shared.security.url_validator.resolve_hostname") as mock_resolve:
            mock_resolve.return_value = "93.184.216.34"
            urls = [
                "https://example.com/page1",
                "https://example.org/page2",
            ]
            result = validate_urls_for_ssrf(urls)
            assert result == urls

    def test_raises_on_first_invalid_url(self):
        """Should raise SSRFError if any URL is invalid."""
        with patch("cognee.shared.security.url_validator.resolve_hostname") as mock_resolve:
            mock_resolve.return_value = "93.184.216.34"
            urls = [
                "https://example.com/page1",
                "http://localhost/admin",  # Invalid
                "https://example.org/page2",
            ]
            with pytest.raises(SSRFError):
                validate_urls_for_ssrf(urls)

    def test_empty_list_returns_empty(self):
        """Empty list should return empty list."""
        result = validate_urls_for_ssrf([])
        assert result == []


class TestSchemeConstants:
    """Tests for scheme constants."""

    def test_blocked_schemes_are_dangerous(self):
        """Blocked schemes should include known dangerous schemes."""
        assert "file" in BLOCKED_SCHEMES
        assert "gopher" in BLOCKED_SCHEMES
        assert "ftp" in BLOCKED_SCHEMES
        assert "data" in BLOCKED_SCHEMES
        assert "javascript" in BLOCKED_SCHEMES

    def test_allowed_schemes_are_safe(self):
        """Allowed schemes should be HTTP/HTTPS only."""
        assert "http" in ALLOWED_SCHEMES
        assert "https" in ALLOWED_SCHEMES
        assert len(ALLOWED_SCHEMES) == 2
