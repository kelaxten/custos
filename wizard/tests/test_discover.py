"""Tests for camera discovery utilities."""

import pytest
from discover import (
    _encode_credentials,
    _parse_probe_match,
    is_routable_camera_ip,
    slugify,
)


# ─── slugify ──────────────────────────────────────────────────────────────────

class TestSlugify:
    def test_simple_name(self):
        assert slugify("Front Door") == "front_door"

    def test_already_lowercase(self):
        assert slugify("driveway") == "driveway"

    def test_special_characters(self):
        assert slugify("Back Yard (East)") == "back_yard_east"

    def test_leading_trailing_spaces(self):
        assert slugify("  porch  ") == "porch"

    def test_numbers_preserved(self):
        assert slugify("Camera 1") == "camera_1"

    def test_empty_string_returns_camera(self):
        assert slugify("") == "camera"

    def test_only_special_chars_returns_camera(self):
        assert slugify("!!!") == "camera"

    def test_consecutive_separators_collapsed(self):
        assert slugify("front  door") == "front_door"


# ─── is_routable_camera_ip ────────────────────────────────────────────────────

class TestIsRoutableCameraIp:
    # Valid private ranges
    def test_rfc1918_192(self):
        assert is_routable_camera_ip("192.168.1.100") is True

    def test_rfc1918_10(self):
        assert is_routable_camera_ip("10.0.0.50") is True

    def test_rfc1918_172(self):
        assert is_routable_camera_ip("172.16.5.10") is True

    # Rejected addresses
    def test_loopback_rejected(self):
        assert is_routable_camera_ip("127.0.0.1") is False

    def test_link_local_rejected(self):
        assert is_routable_camera_ip("169.254.0.1") is False

    def test_multicast_rejected(self):
        assert is_routable_camera_ip("224.0.0.1") is False

    def test_public_internet_rejected(self):
        assert is_routable_camera_ip("8.8.8.8") is False

    def test_invalid_string_rejected(self):
        assert is_routable_camera_ip("not-an-ip") is False

    def test_empty_string_rejected(self):
        assert is_routable_camera_ip("") is False

    def test_aws_metadata_rejected(self):
        # SSRF guard: cloud metadata endpoint
        assert is_routable_camera_ip("169.254.169.254") is False


# ─── _encode_credentials ──────────────────────────────────────────────────────

class TestEncodeCredentials:
    def test_plain_credentials(self):
        assert _encode_credentials("admin", "secret") == "admin:secret"

    def test_password_with_at_sign(self):
        # '@' in a password would break a raw RTSP URL
        result = _encode_credentials("admin", "p@ssword")
        assert "@" not in result.split(":")[1]
        assert "p%40ssword" in result

    def test_password_with_colon(self):
        result = _encode_credentials("admin", "pass:word")
        assert result == "admin:pass%3Aword"

    def test_password_with_spaces(self):
        result = _encode_credentials("admin", "my password")
        assert " " not in result


# ─── _parse_probe_match ───────────────────────────────────────────────────────

class TestParseProbeMatch:
    _VALID_RESPONSE = b"""\
<?xml version="1.0" encoding="utf-8"?>
<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope"
            xmlns:d="http://schemas.xmlsoap.org/ws/2005/04/discovery">
  <s:Body>
    <d:ProbeMatches>
      <d:ProbeMatch>
        <d:XAddrs>http://192.168.1.101/onvif/device_service</d:XAddrs>
      </d:ProbeMatch>
    </d:ProbeMatches>
  </s:Body>
</s:Envelope>"""

    def test_parses_xaddrs(self):
        device = _parse_probe_match(self._VALID_RESPONSE, "192.168.1.101")
        assert device is not None
        assert device.ip == "192.168.1.101"
        assert "192.168.1.101" in device.onvif_url

    def test_falls_back_on_missing_xaddrs(self):
        minimal = b"<s:Envelope xmlns:s='http://www.w3.org/2003/05/soap-envelope'><s:Body/></s:Envelope>"
        device = _parse_probe_match(minimal, "192.168.1.50")
        assert device is not None
        assert device.ip == "192.168.1.50"
        assert "192.168.1.50" in device.onvif_url

    def test_returns_device_on_malformed_xml(self):
        device = _parse_probe_match(b"not xml at all <<<", "192.168.1.99")
        assert device is not None
        assert device.ip == "192.168.1.99"

    def test_xxe_payload_is_harmless(self):
        # defusedxml should neutralise external entity expansion
        xxe = b"""\
<?xml version="1.0"?>
<!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>
<root>&xxe;</root>"""
        # Should not raise; should return a device with fallback URL
        device = _parse_probe_match(xxe, "192.168.1.77")
        assert device is not None
