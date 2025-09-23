from django.shortcuts import render
from django.http import JsonResponse
from django.conf import settings
from django.db import connection
from .auth_utils import login_required, get_current_user

@login_required
def me(request):
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
        addr = wallet["address_hex"] if wallet else None
        voucher_total = sum(item["balance"] for item in balances) if balances else 0
        def addr_no0x(a):
            return a[2:] if a and a.startswith('0x') else (a or '')
        vouchers = []
        if addr:
            for it in balances:
                vouchers.append({
                    "slug": it["slug"],
                    "name": it["name"],
                    "balance": it["balance"],
                    "qr_png": f"/qr/voucher/{it['slug']}/{addr_no0x(addr)}.png"
                })
        return JsonResponse({
            "wallet_address": addr,
            "voucher_total": voucher_total,
            "vouchers": vouchers,
            "wallet_qr_png": f"/qr/wallet/{addr_no0x(addr)}.png" if addr else None
        })

    return render(request, "me.html", {"wallet": wallet, "balances": balances})
