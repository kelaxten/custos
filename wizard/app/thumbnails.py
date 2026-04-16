"""
Capture a single JPEG frame from an RTSP stream using ffmpeg.
Thumbnails are cached under THUMB_DIR and served as static files by the wizard.
"""

import asyncio
import hashlib
import os
from pathlib import Path

THUMB_DIR = Path(os.environ.get("THUMB_DIR", "/tmp/custos-thumbnails"))
THUMB_DIR.mkdir(parents=True, exist_ok=True)

PLACEHOLDER = "/static/camera-placeholder.svg"


async def capture(rtsp_url: str) -> str:
    """
    Returns the URL path to the captured thumbnail (e.g. "/thumbnails/abc123.jpg"),
    or PLACEHOLDER if capture fails.
    """
    key = hashlib.sha256(rtsp_url.encode()).hexdigest()[:16]
    out_path = THUMB_DIR / f"{key}.jpg"

    if out_path.exists():
        return f"/thumbnails/{key}.jpg"

    proc = await asyncio.create_subprocess_exec(
        "ffmpeg", "-y",
        "-rtsp_transport", "tcp",
        "-i", rtsp_url,
        "-vframes", "1",
        "-vf", "scale=320:-1",   # resize to 320px wide for fast loading
        "-q:v", "5",
        str(out_path),
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    try:
        await asyncio.wait_for(proc.communicate(), timeout=12.0)
        if proc.returncode == 0 and out_path.exists():
            return f"/thumbnails/{key}.jpg"
    except asyncio.TimeoutError:
        proc.kill()

    return PLACEHOLDER


def invalidate(rtsp_url: str) -> None:
    """Remove a cached thumbnail so it will be re-captured on next request."""
    key = hashlib.sha256(rtsp_url.encode()).hexdigest()[:16]
    path = THUMB_DIR / f"{key}.jpg"
    path.unlink(missing_ok=True)
