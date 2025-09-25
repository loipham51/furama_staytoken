import json
import uuid

from django.conf import settings
from django.db import connection
from django.http import HttpResponseBadRequest, HttpResponseForbidden, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render
from django.urls import reverse

from .models import VoucherType, VoucherBalance, Wallet
from .auth_utils import login_required, get_current_user
from .pos_utils import get_terminal_by_api_key, terminal_allows_voucher
from .adapters.erc1155_client import ERC1155Client


def _get_terminal(request):
    api_key = request.headers.get("X-API-Key") or request.GET.get("api_key")
    if not api_key:
        return None

    terminal = get_terminal_by_api_key(api_key)
    if terminal:
        terminal.setdefault('is_super', False)
        return terminal

    if api_key == getattr(settings, 'ST_POS_API_KEY', None):
        return {
            'id': None,
            'code': 'GLOBAL',
            'merchant': 'Global',
            'category': None,
            'is_super': True,
        }

    return None


def _terminal_allows(terminal, voucher):
    if not terminal or not voucher:
        return False
    if terminal.get('is_super'):
        return True
    return terminal_allows_voucher(str(terminal['id']), str(voucher.id))




@login_required
def user_portal(request):
    user = get_current_user(request)
    wallet = None
    if user:
        wallet = (
            Wallet.objects
            .filter(user=user)
            .order_by('-created_at')
            .first()
        )

    vouchers = []
    wallet_address = wallet.address_hex if wallet else None
    if wallet and wallet_address:
        balances = (
            VoucherBalance.objects
            .filter(wallet=wallet, balance__gt=0)
            .select_related('voucher_type')
            .order_by('voucher_type__name')
        )
        for bal in balances:
            vt = bal.voucher_type
            if not vt:
                continue
            qr_url = reverse('qr_voucher_png', kwargs={'slug': vt.slug, 'addr': wallet_address[2:]})
            vouchers.append({
                'slug': vt.slug,
                'name': vt.name,
                'description': vt.description or '',
                'balance': int(bal.balance),
                'token_id': str(vt.token_id),
                'qr_url': qr_url,
            })

    context = {
        'wallet_address': wallet_address or '',
        'vouchers': vouchers,
    }
    return render(request, 'pos_user.html', context)


def api_check(request):
    terminal = _get_terminal(request)
    if not terminal:
        return HttpResponseForbidden("Invalid API key")

    addr = request.GET.get("address", "").strip()
    slug = request.GET.get("voucher", "").strip()
    if not addr or not slug:
        return HttpResponseBadRequest("Missing address or voucher")

    voucher = VoucherType.objects.filter(slug=slug, active=True).first()
    if not voucher:
        return JsonResponse({"ok": False, "error": "Voucher not found"})

    if not _terminal_allows(terminal, voucher):
        return JsonResponse({"ok": False, "error": "Voucher not allowed for this POS"})

    try:
        addr_bytes = bytes.fromhex(addr.lower().replace("0x", ""))
    except Exception:
        return JsonResponse({"ok": False, "error": "Invalid address"})

    wallet = Wallet.objects.filter(chain_id=settings.ST_CHAIN_ID, address=addr_bytes).first()
    if not wallet:
        return JsonResponse({"ok": False, "balance": 0, "pos": terminal["code"]})

    vb = VoucherBalance.objects.filter(wallet=wallet, voucher_type=voucher).first()
    offchain_bal = int(vb.balance) if vb else 0

    onchain_bal = None
    if getattr(settings, 'ST_POS_VERIFY_ONCHAIN', False):
        try:
            client = ERC1155Client(
                rpc_url=settings.ST_RPC_URL,
                contract_address=voucher.erc1155_contract or settings.ST_DEFAULT_CONTRACT,
                signer_key=settings.ST_ERC1155_SIGNER,
                chain_id=settings.ST_CHAIN_ID,
            )
            onchain_bal = int(client.balance_of(wallet.address_hex, int(voucher.token_id)))
        except Exception as exc:
            onchain_bal = -1  # indicate error

    return JsonResponse({
        "ok": True,
        "balance": offchain_bal,
        "onchain_balance": onchain_bal,
        "pos": terminal["code"],
    })


@csrf_exempt
def api_reserve(request):
    if request.method != "POST":
        return HttpResponseBadRequest("POST only")

    terminal = _get_terminal(request)
    if not terminal:
        return HttpResponseForbidden("Invalid API key")

    try:
        payload = json.loads(request.body.decode())
        addr = payload["address"].strip()
        slug = payload["voucher"].strip()
        amount = int(payload.get("amount", 1))
    except Exception:
        return HttpResponseBadRequest("Bad JSON")

    voucher = VoucherType.objects.filter(slug=slug, active=True).first()
    if not voucher:
        return JsonResponse({"ok": False, "error": "Voucher not found"})

    if not _terminal_allows(terminal, voucher):
        return JsonResponse({"ok": False, "error": "Voucher not allowed for this POS"})

    try:
        addr_bytes = bytes.fromhex(addr.lower().replace("0x", ""))
    except Exception:
        return JsonResponse({"ok": False, "error": "Invalid address"})

    wallet = Wallet.objects.filter(chain_id=settings.ST_CHAIN_ID, address=addr_bytes).first()
    if not wallet:
        return JsonResponse({"ok": False, "error": "Wallet not found"})

    with connection.cursor() as cur:
        cur.execute(
            """
            SELECT balance FROM voucher_balance
            WHERE wallet_id=%s AND voucher_type_id=%s FOR UPDATE
            """,
            [str(wallet.id), str(voucher.id)],
        )
        row = cur.fetchone()
        if not row:
            return JsonResponse({"ok": False, "error": "No balance"})

        bal = row[0]
        if bal < amount:
            return JsonResponse({"ok": False, "error": "Insufficient balance"})

        cur.execute(
            """
            UPDATE voucher_balance SET balance = balance - %s, updated_at = NOW()
            WHERE wallet_id = %s AND voucher_type_id = %s
            """,
            [amount, str(wallet.id), str(voucher.id)],
        )
        reservation_id = uuid.uuid4()
        cur.execute(
            """
            INSERT INTO pos_redemption (id, voucher_type_id, wallet_id, amount, status, pos_terminal, reserved_at)
            VALUES (%s, %s, %s, %s, 'reserved', %s, NOW())
            """,
            [str(reservation_id), str(voucher.id), str(wallet.id), amount, terminal["code"]],
        )

    return JsonResponse({"ok": True, "reservation_id": str(reservation_id), "pos": terminal["code"]})


@csrf_exempt
def api_commit(request):
    if request.method != "POST":
        return HttpResponseBadRequest("POST only")

    terminal = _get_terminal(request)
    if not terminal:
        return HttpResponseForbidden("Invalid API key")

    try:
        payload = json.loads(request.body.decode())
        reservation_id = payload["reservation_id"]
    except Exception:
        return HttpResponseBadRequest("Bad JSON")

    with connection.cursor() as cur:
        cur.execute(
            """
            SELECT id, voucher_type_id, wallet_id, amount, status, pos_terminal
            FROM pos_redemption
            WHERE id=%s FOR UPDATE
            """,
            [reservation_id],
        )
        row = cur.fetchone()
        if not row:
            return JsonResponse({"ok": False, "error": "Reservation not found"})

        _, _, _, _, status, pos_code = row
        if status != "reserved":
            return JsonResponse({"ok": False, "error": "Already finalized"})
        if pos_code != terminal["code"]:
            return JsonResponse({"ok": False, "error": "Reservation belongs to another terminal"})

        cur.execute(
            """
            UPDATE pos_redemption
            SET status='committed', committed_at=NOW()
            WHERE id=%s
            """,
            [reservation_id],
        )

    return JsonResponse({"ok": True})
