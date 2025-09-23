import json

from django.conf import settings
from django.http import HttpResponseBadRequest, JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST

from .auth_utils import get_current_user, login_required
from .models import VoucherBalance, VoucherType, Wallet
from .services import (
    debit_voucher,
    enqueue_onchain,
    get_or_create_external_wallet,
)

def export_view(request):
    # Chỉ hiển thị thông báo policy (demo)
    return render(request, "wallet_export.html", {
        "export_allowed": False,
        "note": "Hiện chưa bật xuất private key. Vui lòng dùng tính năng chuyển voucher sang ví cá nhân."
    })

@login_required
@require_POST
def transfer_view(request):
    try:
        payload = json.loads(request.body.decode())
        to_address = (payload.get("to_address") or "").strip()
        slug = (payload.get("voucher") or "").strip()
        amount = int(payload.get("amount", 1))
    except Exception:
        return HttpResponseBadRequest("Bad JSON")

    if not to_address:
        return JsonResponse({"ok": False, "error": "Destination address required"}, status=400)
    if amount <= 0:
        return JsonResponse({"ok": False, "error": "Amount must be positive"}, status=400)

    user = get_current_user(request)
    # Tìm wallet thật của user theo session
    voucher = VoucherType.objects.filter(slug=slug, active=True).first()
    if not voucher:
        return JsonResponse({"ok": False, "error": "Voucher not found"}, status=404)

    wallet = (
        Wallet.objects
        .filter(user=user, chain_id=settings.ST_CHAIN_ID)
        .order_by("-created_at")
        .first()
    )
    if not wallet:
        return JsonResponse({"ok": False, "error": "Wallet not found"}, status=404)

    try:
        external_wallet = get_or_create_external_wallet(user, settings.ST_CHAIN_ID, to_address)
        debit_voucher(wallet, voucher, amount, reason="export", to_wallet=external_wallet)
    except (ValueError, PermissionError) as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=400)

    new_balance = (
        VoucherBalance.objects
        .filter(wallet=wallet, voucher_type=voucher)
        .values_list("balance", flat=True)
        .first()
    )

    tx = enqueue_onchain(
        kind="safeTransfer1155",
        voucher=voucher,
        to_wallet=external_wallet,
        amount=amount,
    )

    return JsonResponse({
        "ok": True,
        "queued_tx_id": str(tx.id),
        "destination": external_wallet.address_hex,
        "remaining_balance": int(new_balance) if new_balance is not None else 0,
    })
