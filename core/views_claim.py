from urllib.parse import urlencode

from django.conf import settings
from django.db import connection
from django.http import Http404, HttpResponseRedirect, JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .auth_utils import get_current_user
from .forms import ClaimProfileForm, OTPStartForm
from .models import QRClaim, VoucherType
from .services import (
    enqueue_onchain,
    finish_qr_claim,
    get_or_create_user,
    issue_voucher,
    log_claim_request,
    rate_limit_ok,
    mint_erc1155_now,
    can_user_claim,
)


def _process_claim(request, qr, *, user):
    email = (user.email or "").lower() or None
    phone = user.phone or None
    consent = True
    client_ip = request.META.get("REMOTE_ADDR")
    ua = request.META.get("HTTP_USER_AGENT")

    # Handle both QRClaim and VoucherType objects
    code = getattr(qr, 'code', None) or getattr(qr, 'slug', '')
    
    # For VoucherType objects, skip QR-specific validations
    if hasattr(qr, 'voucher_type'):
        # qr is QRClaim object - do full validation
        if not rate_limit_ok(email=email, ip=client_ip):
            log_claim_request(qr, client_ip, ua, email, phone, consent, "rate_limited")
            return render(
                request,
                "claim_start.html",
                {
                    "code": code,
                    "error": "Bạn thao tác quá nhanh, thử lại sau vài phút.",
                },
                status=429,
            )

        if qr.active != True:
            log_claim_request(qr, client_ip, ua, email, phone, consent, "used")
            return render(
                request,
                "claim_start.html",
                {
                    "code": code,
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
                    "code": code,
                    "error": "QR đã hết hạn.",
                },
                status=410,
            )
    else:
        # qr is VoucherType object - skip QR validations
        pass

    # Get voucher_type - handle both QRClaim and VoucherType objects
    if hasattr(qr, 'voucher_type'):
        voucher_type = qr.voucher_type
    else:
        voucher_type = qr
    
    # Enforce per-user limit
    ok, claimed, limit = can_user_claim(user, voucher_type, amount=1)
    if not ok:
        if hasattr(qr, 'voucher_type'):
            log_claim_request(qr, client_ip, ua, email, phone, consent, "limit_reached")
        return render(
            request,
            "claim_start.html",
            {
                "code": code,
                "error": f"Bạn đã đạt giới hạn claim ({claimed}/{limit}).",
            },
            status=403,
        )

    # Issue voucher and mint immediately
    from django.db import transaction
    
    try:
        with transaction.atomic():
            wallet = issue_voucher(user, voucher_type, amount=1)
            
            # Mint immediately instead of queuing
            tx_hash = mint_erc1155_now(wallet, voucher_type, amount=1, wait=True)
            
            # Only finish QR claim if it's a QRClaim object
            if hasattr(qr, 'voucher_type'):
                finish_qr_claim(qr, user)
                log_claim_request(qr, client_ip, ua, email, phone, consent, "ok")
            
            # Store transaction hash in session for success page
            request.session['last_claim_tx_hash'] = tx_hash
            
    except Exception as exc:
        if hasattr(qr, 'voucher_type'):
            log_claim_request(qr, client_ip, ua, email, phone, consent, f"mint_failed: {str(exc)}")
        return render(
            request,
            "claim_start.html",
            {
                "code": code,
                "error": f"Không thể mint voucher: {str(exc)}",
            },
            status=500,
        )

    return HttpResponseRedirect(reverse("claim_done", args=[code]))

def _voucher_display(qr):
    # Handle both QRClaim and VoucherType objects
    if hasattr(qr, 'voucher_type'):
        # qr is QRClaim object
        voucher = qr.voucher_type
    else:
        # qr is VoucherType object
        voucher = qr
    
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


def _render_email_form(request, qr, form: OTPStartForm, *, message: str | None = None):
    meta = _voucher_display(qr)
    # Handle both QRClaim and VoucherType objects
    code = getattr(qr, 'code', None) or getattr(qr, 'slug', '')
    return render(
        request,
        "claim_guest_email.html",
        {
            "code": code,
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
    qr,
    form: ClaimProfileForm,
    *,
    status_code: int = 200,
    message: str | None = None,
    user_email: str | None = None,
):
    meta = _voucher_display(qr)
    # Handle both QRClaim and VoucherType objects
    code = getattr(qr, 'code', None) or getattr(qr, 'slug', '')
    return render(
        request,
        "claim_guest_form.html",
        {
            "code": code,
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
def claim_start(request, slug: str):
    try:
        qr = VoucherType.objects.get(slug=slug)
    except VoucherType.DoesNotExist:
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
def claim_submit(request, slug: str):
    try:
        qr = VoucherType.objects.get(slug=slug)
    except VoucherType.DoesNotExist:
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

@require_http_methods(["POST"])  # JSON API: claim by slug and mint now
def claim_mint_now(request, slug: str):
    user = get_current_user(request)
    if not user:
        return JsonResponse({"ok": False, "error": "AUTH_REQUIRED"}, status=401)

    try:
        voucher = VoucherType.objects.get(slug=slug, active=True)
    except VoucherType.DoesNotExist:
        return JsonResponse({"ok": False, "error": "VOUCHER_NOT_FOUND"}, status=404)

    ok, claimed, limit = can_user_claim(user, voucher, amount=1)
    if not ok:
        return JsonResponse({"ok": False, "error": "LIMIT_REACHED", "claimed": claimed, "limit": limit}, status=403)

    # Issue off-chain balance and mint on-chain in one flow
    from django.db import transaction
    
    # Validate config before attempting mint
    if not settings.ST_RPC_URL or not settings.ST_ERC1155_SIGNER or not settings.ST_DEFAULT_CONTRACT:
        return JsonResponse({"ok": False, "error": "CONFIG_INVALID", "detail": "Blockchain configuration incomplete"}, status=500)
    
    try:
        with transaction.atomic():
            wallet = issue_voucher(user, voucher, amount=1)
            
            # Debug info
            contract_addr = voucher.erc1155_contract or settings.ST_DEFAULT_CONTRACT
            token_id = int(voucher.token_id)
            wallet_addr = wallet.address_hex
            
            print(f"DEBUG: contract={contract_addr}, token_id={token_id}, wallet={wallet_addr}")
            print(f"DEBUG: signer_key starts with: {settings.ST_ERC1155_SIGNER[:10]}...")
            
            tx_hash = mint_erc1155_now(wallet, voucher, amount=1, wait=True)
    except Exception as exc:
        import traceback
        print(f"DEBUG: Full error: {exc}")
        print(f"DEBUG: Traceback: {traceback.format_exc()}")
        return JsonResponse({"ok": False, "error": "MINT_FAILED", "detail": str(exc)}, status=500)

    return JsonResponse({
        "ok": True,
        "wallet_address": wallet.address_hex,
        "tx_hash": tx_hash,
        "explorer": (settings.ST_EXPLORER_TX_PREFIX + tx_hash) if settings.ST_EXPLORER_TX_PREFIX else None,
    })


def claim_done(request, slug: str):
    try:
        qr = VoucherType.objects.get(slug=slug)
    except VoucherType.DoesNotExist:
        raise Http404
    user = qr.used_by_user
    wallet = None
    if user:
        from .models import Wallet
        wallet = Wallet.objects.filter(user=user, chain_id=settings.ST_CHAIN_ID).first()
    
    # Get transaction hash from session
    tx_hash = request.session.pop('last_claim_tx_hash', None)
    explorer_url = None
    if tx_hash and settings.ST_EXPLORER_TX_PREFIX:
        explorer_url = settings.ST_EXPLORER_TX_PREFIX + tx_hash
    
    # Tạo URL QR ví để hiển thị trong template claim_success.html
    wallet_addr = wallet.address_hex if wallet else ""
    qr_png_url = reverse("qr_wallet_png", kwargs={"addr": wallet_addr[2:]}) if wallet_addr else ""
    
    return render(request, "claim_success.html", {
        "wallet_address": wallet_addr,
        "qr_png_url": qr_png_url,
        "tx_hash": tx_hash,
        "explorer_url": explorer_url,
        "voucher_name": qr.voucher_type.name if qr.voucher_type else "StayToken voucher"
    })
