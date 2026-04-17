"""
Camera discovery via WS-Discovery (ONVIF) and RTSP credential probing.

Sends a UDP multicast probe per the WS-Discovery spec, collects responding
device IPs, then probes each for RTSP stream URLs using known manufacturer
patterns (Reolink, Hikvision, Dahua) before falling back to generic ONVIF.
"""

import asyncio
import ipaddress
import re
import socket
import uuid
from dataclasses import dataclass
from typing import Optional

import defusedxml.ElementTree as ET  # safe against XXE / billion-laughs

MULTICAST_ADDR = "239.255.255.250"
DISCOVERY_PORT = 3702
PROBE_TIMEOUT = 5.0  # seconds to listen for responses

# RTSP URL patterns ordered by sub/main stream.
# {username} and {password} are substituted via urllib.parse.quote, not .format().
KNOWN_RTSP_PATTERNS: list[dict] = [
    {
        "name": "Reolink",
        "sub":  "rtsp://{creds}@{ip}:554/h264Preview_01_sub",
        "main": "rtsp://{creds}@{ip}:554/h264Preview_01_main",
    },
    {
        "name": "Hikvision",
        "sub":  "rtsp://{creds}@{ip}:554/Streaming/Channels/102",
        "main": "rtsp://{creds}@{ip}:554/Streaming/Channels/101",
    },
    {
        "name": "Dahua",
        "sub":  "rtsp://{creds}@{ip}:554/cam/realmonitor?channel=1&subtype=1",
        "main": "rtsp://{creds}@{ip}:554/cam/realmonitor?channel=1&subtype=0",
    },
    {
        "name": "Generic ONVIF",
        "sub":  "rtsp://{creds}@{ip}:554/stream2",
        "main": "rtsp://{creds}@{ip}:554/stream1",
    },
]

WS_DISCOVERY_PROBE = """\
<?xml version="1.0" encoding="utf-8"?>
<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope"
            xmlns:a="http://schemas.xmlsoap.org/ws/2004/08/addressing"
            xmlns:d="http://schemas.xmlsoap.org/ws/2005/04/discovery"
            xmlns:dn="http://www.onvif.org/ver10/network/wsdl">
  <s:Header>
    <a:MessageID>uuid:{message_id}</a:MessageID>
    <a:To>urn:schemas-xmlsoap-org:ws:2005:04:discovery</a:To>
    <a:Action>http://schemas.xmlsoap.org/ws/2005/04/discovery/Probe</a:Action>
  </s:Header>
  <s:Body>
    <d:Probe>
      <d:Types>dn:NetworkVideoTransmitter</d:Types>
    </d:Probe>
  </s:Body>
</s:Envelope>"""


@dataclass
class DiscoveredDevice:
    ip: str
    onvif_url: str = ""
    manufacturer: str = "Unknown"
    model: str = ""
    # Populated after credential probe
    username: str = "admin"
    password: str = ""
    rtsp_sub: str = ""
    rtsp_main: str = ""
    authenticated: bool = False


def is_routable_camera_ip(ip_str: str) -> bool:
    """
    Return True only for IPs that could plausibly be a camera.
    Rejects loopback, link-local, multicast, and public internet addresses —
    both to prevent SSRF and to avoid scanning hosts that aren't cameras.
    """
    try:
        addr = ipaddress.ip_address(ip_str)
    except ValueError:
        return False
    if addr.is_loopback or addr.is_link_local or addr.is_multicast:
        return False
    if addr.is_unspecified or addr.is_reserved:
        return False
    # Only allow RFC-1918 private ranges (camera networks)
    private_ranges = [
        ipaddress.ip_network("10.0.0.0/8"),
        ipaddress.ip_network("172.16.0.0/12"),
        ipaddress.ip_network("192.168.0.0/16"),
    ]
    return any(addr in net for net in private_ranges)


def _encode_credentials(username: str, password: str) -> str:
    """URL-encode username:password for embedding in an RTSP URL."""
    from urllib.parse import quote
    return f"{quote(username, safe='')}:{quote(password, safe='')}"


async def scan_network() -> list[DiscoveredDevice]:
    """Send a WS-Discovery probe and return responding ONVIF devices."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _ws_discovery_probe)


def _ws_discovery_probe() -> list[DiscoveredDevice]:
    probe = WS_DISCOVERY_PROBE.format(message_id=str(uuid.uuid4())).encode()

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
    sock.settimeout(PROBE_TIMEOUT)

    sock.sendto(probe, (MULTICAST_ADDR, DISCOVERY_PORT))

    devices: dict[str, DiscoveredDevice] = {}
    try:
        while True:
            data, addr = sock.recvfrom(4096)
            ip = addr[0]
            if ip in devices:
                continue
            if not is_routable_camera_ip(ip):
                continue
            device = _parse_probe_match(data, ip)
            if device:
                devices[ip] = device
    except socket.timeout:
        pass
    finally:
        sock.close()

    return list(devices.values())


def _parse_probe_match(data: bytes, ip: str) -> Optional[DiscoveredDevice]:
    try:
        root = ET.fromstring(data.decode(errors="replace"))
        ns = {
            "s": "http://www.w3.org/2003/05/soap-envelope",
            "d": "http://schemas.xmlsoap.org/ws/2005/04/discovery",
            "dn": "http://www.onvif.org/ver10/network/wsdl",
        }
        xaddrs_el = root.find(".//d:XAddrs", ns)
        onvif_url = (
            xaddrs_el.text.split()[0]
            if xaddrs_el is not None and xaddrs_el.text
            else f"http://{ip}:80/onvif/device_service"
        )
        return DiscoveredDevice(ip=ip, onvif_url=onvif_url)
    except Exception:
        return DiscoveredDevice(ip=ip)


async def probe_credentials(
    device: DiscoveredDevice, username: str, password: str
) -> DiscoveredDevice:
    """Try credentials against a device; populate RTSP URLs on success."""
    device.username = username
    device.password = password

    # Single reachability check before trying all URL patterns
    loop = asyncio.get_running_loop()
    reachable = await loop.run_in_executor(None, _test_rtsp_connect, device.ip)
    if not reachable:
        return device

    creds = _encode_credentials(username, password)
    for pattern in KNOWN_RTSP_PATTERNS:
        sub_url = pattern["sub"].format(creds=creds, ip=device.ip)
        main_url = pattern["main"].format(creds=creds, ip=device.ip)

        ok = await _probe_rtsp(sub_url)
        if ok:
            device.rtsp_sub = sub_url
            device.rtsp_main = main_url
            device.manufacturer = pattern["name"]
            device.authenticated = True
            return device

    return device


def _test_rtsp_connect(ip: str, port: int = 554, timeout: float = 2.0) -> bool:
    """Quick TCP connect check to RTSP port before spending time on stream probe."""
    try:
        with socket.create_connection((ip, port), timeout=timeout):
            return True
    except OSError:
        return False


async def _probe_rtsp(url: str, timeout: float = 6.0) -> bool:
    """Use ffprobe to verify an RTSP URL is reachable with the given credentials."""
    proc = await asyncio.create_subprocess_exec(
        "ffprobe",
        "-v", "quiet",
        "-rtsp_transport", "tcp",
        "-i", url,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    try:
        await asyncio.wait_for(proc.communicate(), timeout=timeout)
        return proc.returncode == 0
    except asyncio.TimeoutError:
        proc.kill()
        return False


def slugify(name: str) -> str:
    """Turn a display name into a Frigate camera ID slug."""
    slug = name.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "_", slug)
    return slug.strip("_") or "camera"
