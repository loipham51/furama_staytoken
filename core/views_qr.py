import re
from pathlib import Path

from django.http import FileResponse, Http404

from .qrcode_utils import get_or_make_cached_png


def _normalize_addr(addr: str) -> str:
    candidate = (addr or "").strip().lower()
    if candidate.startswith("0x"):
        candidate = candidate[2:]
    if not re.fullmatch(r"[0-9a-f]{40}", candidate):
        raise Http404("Invalid wallet address")
    return candidate


# QR cho ví (POS sẽ nhận ra dạng wallet:<addr_hex>)
def wallet_qr_png(request, addr: str):
    normalized = _normalize_addr(addr)
    data = f"wallet:0x{normalized}"
    path = Path(get_or_make_cached_png(f"wallet_{normalized}.png", data))
    return FileResponse(path.open("rb"), content_type="image/png")

# QR cho voucher cụ thể (voucher:<slug>:<addr_hex>)
def voucher_qr_png(request, slug: str, addr: str):
    if not re.fullmatch(r"[A-Za-z0-9_-]+", slug or ""):
        raise Http404("Invalid voucher slug")
    normalized = _normalize_addr(addr)
    data = f"voucher:{slug}:0x{normalized}"
    path = Path(get_or_make_cached_png(f"voucher_{slug}_{normalized}.png", data))
    return FileResponse(path.open("rb"), content_type="image/png")

# QR cho QRClaim code (để POS scanner redeem)
def qr_claim_png(request, code: str):
    if not re.fullmatch(r"[A-Za-z0-9_-]+", code or ""):
        raise Http404("Invalid QR claim code")
    data = code  # QRClaim code is the data itself
    path = Path(get_or_make_cached_png(f"qr_claim_{code}.png", data))
    return FileResponse(path.open("rb"), content_type="image/png")

# QR cho voucher (admin export)
def voucher_qr_png_admin(request, slug: str):
    if not re.fullmatch(r"[A-Za-z0-9_-]+", slug or ""):
        raise Http404("Invalid voucher slug")
    data = f"voucher:{slug}:claim"
    path = Path(get_or_make_cached_png(f"voucher_{slug}.png", data))
    return FileResponse(path.open("rb"), content_type="image/png")