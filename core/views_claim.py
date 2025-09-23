from urllib.parse import urlencode

from django.conf import settings
from django.db import connection
from django.http import Http404, HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .auth_utils import get_current_user
from .forms import ClaimProfileForm, OTPStartForm
from .models import QRClaim
from .services import (
    enqueue_onchain,
    finish_qr_claim,
    get_or_create_user,
    issue_voucher,
    log_claim_request,
    rate_limit_ok,
)


def _process_claim(request, qr: QRClaim, *, user):
    email = (user.email or "").lower() or None
    phone = user.phone or None
    consent = True
    client_ip = request.META.get("REMOTE_ADDR")
    ua = request.META.get("HTTP_USER_AGENT")

    if not rate_limit_ok(email=email, ip=client_ip):
        log_claim_request(qr, client_ip, ua, email, phone, consent, "rate_limited")
        return render(
            request,
            "claim_start.html",
            {
                "code": qr.code,
                "error": "Bạn thao tác quá nhanh, thử lại sau vài phút.",
            },
            status=429,
        )

    if qr.status != "new":
        log_claim_request(qr, client_ip, ua, email, phone, consent, "used")
        return render(
            request,
            "claim_start.html",
            {
                "code": qr.code,
                "error": "QR đã được sử dụng hoặc không còn hiệu lực.",
            },
            status=409,
        )

    if qr.expires_at and qr.expires_at < timezone.now():
        log_claim_request(qr, client_ip, ua, email, phone, consent, "expired")
        return render(
            request,
            "claim_start.html",
            {
                "code": qr.code,
                "error": "QR đã hết hạn.",
            },
            status=410,
        )

    wallet = issue_voucher(user, qr.voucher_type, amount=1)
    enqueue_onchain(kind="mint1155", voucher=qr.voucher_type, to_wallet=wallet, amount=1)

    finish_qr_claim(qr, user)
    log_claim_request(qr, client_ip, ua, email, phone, consent, "ok")

    return HttpResponseRedirect(reverse("claim_done", args=[qr.code]))

def _voucher_display(qr: QRClaim):
    voucher = qr.voucher_type
    if not voucher:
        return {
            "title": "StayToken voucher",
            "subtitle": "Bring this QR to Furama staff to redeem your benefit.",
            "value": "",
        }
    subtitle = (voucher.description or "").splitlines()[0].strip() if voucher.description else "Enjoy exclusive perks at Furama Resort"
    return {
        "title": voucher.name or voucher.slug,
        "subtitle": subtitle,
        "value": getattr(voucher, "face_value_display", None)
        or getattr(voucher, "face_value", None)
        or getattr(voucher, "value_text", None)
        or "",
    }


def _render_email_form(request, qr: QRClaim, form: OTPStartForm, *, message: str | None = None):
    meta = _voucher_display(qr)
    return render(
        request,
        "claim_guest_email.html",
        {
            "code": qr.code,
            "form": form,
            "voucher_title": meta["title"],
            "voucher_subtitle": meta["subtitle"],
            "voucher_value": meta["value"],
            "error": message,
        },
    )


def _needs_profile(user) -> bool:
    if not user:
        return False
    name = (user.full_name or "").strip().lower()
    placeholder = name.startswith("khach furama") or name.startswith("guest furama")
    return not name or placeholder or not (user.phone and user.phone.strip())


def _render_profile_form(
    request,
    qr: QRClaim,
    form: ClaimProfileForm,
    *,
    status_code: int = 200,
    message: str | None = None,
    user_email: str | None = None,
):
    meta = _voucher_display(qr)
    return render(
        request,
        "claim_guest_form.html",
        {
            "code": qr.code,
            "form": form,
            "voucher_title": meta["title"],
            "voucher_subtitle": meta["subtitle"],
            "voucher_value": meta["value"],
            "error": message,
            "user_email": user_email,
        },
        status=status_code,
    )


def _refresh_user_profile(user, *, full_name: str | None, email: str | None, phone: str | None):
    updates = []
    params = []

    if full_name and full_name.strip() and (user.full_name or "").strip() != full_name.strip():
        updates.append("full_name = %s")
        params.append(full_name.strip())
        user.full_name = full_name.strip()

    if email and email.strip() and (user.email or "").lower().strip() != email.lower().strip():
        updates.append("email = %s")
        params.append(email.lower().strip())
        user.email = email.lower().strip()

    if phone and phone.strip() and (user.phone or "").strip() != phone.strip():
        updates.append("phone = %s")
        params.append(phone.strip())
        user.phone = phone.strip()

    if not updates:
        return user

    updates.append("updated_at = NOW()")
    params.append(str(user.id))
    sql = "UPDATE app_user SET " + ", ".join(updates) + " WHERE id = %s"
    with connection.cursor() as cur:
        cur.execute(sql, params)
    return user


@require_http_methods(["GET"])
def claim_start(request, code: str):
    try:
        qr = QRClaim.objects.get(code=code)
    except QRClaim.DoesNotExist:
        raise Http404("QR không hợp lệ")

    user = get_current_user(request)
    if user:
        if not _needs_profile(user):
            return _process_claim(request, qr, user=user)
        form = ClaimProfileForm(initial={"full_name": user.full_name or "", "phone": user.phone or ""})
        return _render_profile_form(request, qr, form, user_email=user.email)

    form = OTPStartForm(initial={"next": request.get_full_path()})
    return _render_email_form(request, qr, form)

@require_http_methods(["POST"])
def claim_submit(request, code: str):
    try:
        qr = QRClaim.objects.get(code=code)
    except QRClaim.DoesNotExist:
        raise Http404("QR không hợp lệ")

    user = get_current_user(request)
    if not user:
        login_url = reverse("auth_start")
        next_param = urlencode({"next": request.get_full_path()})
        return HttpResponseRedirect(f"{login_url}?{next_param}")

    if _needs_profile(user):
        form = ClaimProfileForm(request.POST)
        if not form.is_valid():
            return _render_profile_form(request, qr, form, status_code=400, user_email=user.email)

        data = form.cleaned_data
        user = _refresh_user_profile(
            user,
            full_name=data["full_name"],
            email=user.email,
            phone=data.get("phone"),
        )

    return _process_claim(request, qr, user=user)

def claim_done(request, code: str):
    try:
        qr = QRClaim.objects.get(code=code)
    except QRClaim.DoesNotExist:
        raise Http404
    user = qr.used_by_user
    wallet = None
    if user:
        from .models import Wallet
        wallet = Wallet.objects.filter(user=user, chain_id=settings.ST_CHAIN_ID).first()
    # Tạo URL QR ví để hiển thị trong template claim_success.html (bạn đã có template)
    wallet_addr = wallet.address_hex if wallet else ""
    qr_png_url = reverse("qr_wallet_png", kwargs={"addr": wallet_addr[2:]}) if wallet_addr else ""
    return render(request, "claim_success.html", {
        "wallet_address": wallet_addr,
        "qr_png_url": qr_png_url
    })
