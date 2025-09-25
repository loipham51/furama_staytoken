from django.shortcuts import render
from django.http import JsonResponse
from django.conf import settings
from django.db import connection
from .auth_utils import login_required, get_current_user

@login_required
def me(request):
    """My Profile - thông tin cá nhân + wallet"""
    user = get_current_user(request)
    
    # Lấy wallet theo chain + số dư các voucher
    with connection.cursor() as cur:
        cur.execute("""
            SELECT w.id, '0x' || encode(w.address,'hex') AS address_hex, w.created_at
            FROM wallet w
            WHERE w.user_id=%s AND w.chain_id=%s
            ORDER BY w.created_at DESC
            LIMIT 1
        """, [str(user.id), settings.ST_CHAIN_ID])
        row = cur.fetchone()
    wallet = {"id": row[0], "address_hex": row[1], "created_at": row[2]} if row else None

    balances = []
    if wallet:
        with connection.cursor() as cur:
            cur.execute("""
                SELECT vt.slug, vt.name, vb.balance
                FROM voucher_balance vb
                JOIN voucher_type vt ON vt.id = vb.voucher_type_id
                WHERE vb.wallet_id=%s
                ORDER BY vt.slug
            """, [str(wallet["id"])])
            for slug, name, bal in cur.fetchall():
                balances.append({"slug": slug, "name": name, "balance": int(bal)})

    # Serve JSON for clients that request it
    wants_json = 'application/json' in request.headers.get('Accept', '') or request.GET.get('format') == 'json'
    if wants_json:
        # Tính per-user limit và đã claim bao nhiêu từ QRClaim
        limits = []
        with connection.cursor() as cur:
            cur.execute(
                """
                SELECT vt.slug,
                       COALESCE(vt.per_user_limit, 0) AS limit,
                       COALESCE(COUNT(qc.id), 0) AS claimed
                FROM voucher_type vt
                LEFT JOIN qr_claim qc ON qc.voucher_type_id = vt.id AND qc.used_by_user = %s
                WHERE vt.active = TRUE
                GROUP BY vt.slug, vt.per_user_limit
                ORDER BY vt.slug
                """,
                [str(user.id)],
            )
            for slug, limit_val, claimed_val in cur.fetchall():
                limit_int = int(limit_val or 0)
                claimed_int = int(claimed_val or 0)
                can_claim = True if limit_int <= 0 else (claimed_int < limit_int)
                limits.append({
                    "slug": slug,
                    "limit": limit_int,
                    "claimed": claimed_int,
                    "can_claim": can_claim,
                })

        addr = wallet["address_hex"] if wallet else None
        voucher_total = sum(item["balance"] for item in balances) if balances else 0
        def addr_no0x(a):
            return a[2:] if a and a.startswith('0x') else (a or '')
        vouchers = []
        if addr:
            # Get QRClaim codes for each voucher
            from .models import QRClaim
            for it in balances:
                # Get the latest QRClaim for this user and voucher
                qr_claim = QRClaim.objects.filter(
                    used_by_user=user,
                    voucher_type__slug=it["slug"]
                ).order_by('-created_at').first()
                
                qr_code = qr_claim.code if qr_claim else None
                
                vouchers.append({
                    "slug": it["slug"],
                    "name": it["name"],
                    "balance": it["balance"],
                    "qr_png": f"/qr/voucher/{it['slug']}/{addr_no0x(addr)}.png",
                    "qr_claim_code": qr_code  # Add QRClaim code for POS scanner
                })
        return JsonResponse({
            "wallet_address": addr,
            "voucher_total": voucher_total,
            "vouchers": vouchers,
            "limits": limits,
            "wallet_qr_png": f"/qr/wallet/{addr_no0x(addr)}.png" if addr else None
        })

    return render(request, "me_profile.html", {"user": user, "wallet": wallet, "balances": balances})


@login_required
def my_wallet(request):
    """My Wallet - thông tin wallet và vouchers"""
    user = get_current_user(request)
    
    # Lấy wallet theo chain + số dư các voucher
    with connection.cursor() as cur:
        cur.execute("""
            SELECT w.id, '0x' || encode(w.address,'hex') AS address_hex, w.created_at
            FROM wallet w
            WHERE w.user_id=%s AND w.chain_id=%s
            ORDER BY w.created_at DESC
            LIMIT 1
        """, [str(user.id), settings.ST_CHAIN_ID])
        row = cur.fetchone()
    wallet = {"id": row[0], "address_hex": row[1], "created_at": row[2]} if row else None

    balances = []
    if wallet:
        with connection.cursor() as cur:
            cur.execute("""
                SELECT vt.slug, vt.name, vb.balance
                FROM voucher_balance vb
                JOIN voucher_type vt ON vt.id = vb.voucher_type_id
                WHERE vb.wallet_id=%s
                ORDER BY vt.slug
            """, [str(wallet["id"])])
            for slug, name, bal in cur.fetchall():
                balances.append({"slug": slug, "name": name, "balance": int(bal)})

    return render(request, "me_wallet.html", {"wallet": wallet, "balances": balances})


@login_required
def my_vouchers(request):
    """My Vouchers - chỉ hiển thị vouchers"""
    user = get_current_user(request)
    
    # Lấy wallet theo chain + số dư các voucher
    with connection.cursor() as cur:
        cur.execute("""
            SELECT w.id, '0x' || encode(w.address,'hex') AS address_hex, w.created_at
            FROM wallet w
            WHERE w.user_id=%s AND w.chain_id=%s
            ORDER BY w.created_at DESC
            LIMIT 1
        """, [str(user.id), settings.ST_CHAIN_ID])
        row = cur.fetchone()
    wallet = {"id": row[0], "address_hex": row[1], "created_at": row[2]} if row else None

    balances = []
    if wallet:
        # Get QRClaim codes for each voucher
        from .models import QRClaim
        with connection.cursor() as cur:
            cur.execute("""
                SELECT vt.slug, vt.name, vb.balance
                FROM voucher_balance vb
                JOIN voucher_type vt ON vt.id = vb.voucher_type_id
                WHERE vb.wallet_id=%s
                ORDER BY vt.slug
            """, [str(wallet["id"])])
            for slug, name, bal in cur.fetchall():
                # Get the latest QRClaim for this user and voucher
                qr_claim = QRClaim.objects.filter(
                    used_by_user=user,
                    voucher_type__slug=slug
                ).order_by('-created_at').first()
                
                qr_claim_code = qr_claim.code if qr_claim else None
                
                balances.append({
                    "slug": slug, 
                    "name": name, 
                    "balance": int(bal),
                    "qr_claim_code": qr_claim_code
                })

    return render(request, "me_vouchers.html", {"wallet": wallet, "balances": balances})
