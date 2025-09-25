from django.conf import settings
from django.shortcuts import render
from django.contrib.auth.decorators import login_required  # Nếu cần check login
from .models import VoucherType


def home(request):
    "Home landing page showing available vouchers for claim."
    # Load active voucher types from DB
    vouchers_qs = (
        VoucherType.objects
        .filter(active=True)
        .order_by('-created_at')
    )

    # Map to template-friendly dicts
    available_vouchers = []
    for vt in vouchers_qs:
        available_vouchers.append({
            "slug": vt.slug,
            "name": vt.name,
            "description": vt.description or "StayToken reward",
            # Model không có giá trị danh nghĩa -> để UI format mặc định
            "value_vnd": None,
            "expiry": "",
            "displayValue": "—",
        })

    return render(request, "home.html", {
        "demo_mode": settings.ST_DEMO_MODE,
        "available_vouchers": available_vouchers,
    })


def qr_scanner(request):
    "QR Scanner page for claiming vouchers via QR codes."
    return render(request, "qr_scanner.html", {
        "demo_mode": settings.ST_DEMO_MODE,
    })