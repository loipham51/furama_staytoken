import io
import os
import re
from pathlib import Path

import qrcode
from django.conf import settings
from django.http import HttpResponse

def render_qr_png(data: str) -> bytes:
    img = qrcode.make(data)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

def qr_response(data: str) -> HttpResponse:
    png = render_qr_png(data)
    return HttpResponse(png, content_type="image/png")

def get_or_make_cached_png(filename: str, data: str) -> str:
    """Lưu file PNG QR vào ST_QR_CACHE_DIR, trả path filesystem."""
    cache_dir = Path(settings.ST_QR_CACHE_DIR)
    cache_dir.mkdir(parents=True, exist_ok=True)

    if not re.fullmatch(r"[A-Za-z0-9_.-]+", filename):
        raise ValueError("Invalid QR cache filename")

    path = cache_dir / filename
    if not path.exists():
        png = render_qr_png(data)
        path.write_bytes(png)
    return str(path)
