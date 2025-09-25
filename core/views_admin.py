import csv
import datetime
import io
import os
from io import BytesIO

from django.conf import settings
from django.core import management
from django.db import connection
from django.http import HttpResponse, HttpResponseBadRequest, JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
import json
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT

from .auth_utils import admin_required
from .models import (
    AppUser,
    VoucherType,
    VoucherBalance,
    POSRedemption,
    Wallet,
    POSTerminal,
    Merchant,
    OnchainTx,
    OnchainStatus,
)
from .forms import VoucherTypeForm, MerchantForm, POSTerminalForm
from django.core.paginator import Paginator
from django.db import models
from django.db.models import Count, Sum, Q, Max


@admin_required
def admin_dashboard(request):
    msg = request.session.pop("console_msg", None)
    pending_qs = (
        OnchainTx.objects
        .select_related('voucher_type', 'to_wallet', 'to_wallet__user')
        .filter(status__in=[OnchainStatus.QUEUED, OnchainStatus.SENT])
        .order_by('created_at')[:25]
    )

    recent_qs = (
        OnchainTx.objects
        .select_related('voucher_type', 'to_wallet', 'to_wallet__user')
        .filter(status__in=[OnchainStatus.CONFIRMED, OnchainStatus.FAILED])
        .order_by('-created_at')[:25]
    )

    # Note: VoucherTransferLog removed - using QRClaim for tracking instead
    claims_qs = []  # Empty for now, can be replaced with QRClaim.objects if needed

    # Recent POS redemptions (both reserved and committed)
    recent_redeem_qs = (
        POSRedemption.objects
        .select_related('voucher_type', 'wallet', 'wallet__user')
        .order_by('-reserved_at')[:20]
    )

    def wallet_info(wallet: Wallet | None) -> dict:
        if not wallet:
            return {"address": None, "short_address": None, "guest_name": None}
        address = wallet.address_hex or None
        short = f"{address[:10]}...{address[-6:]}" if address and len(address) > 16 else address
        guest = None
        if getattr(wallet, "user", None):
            guest = wallet.user.full_name or wallet.user.email or str(wallet.user_id)
        return {"address": address, "short_address": short, "guest_name": guest}

    def tx_payload(tx: OnchainTx) -> dict:
        wallet = wallet_info(getattr(tx, "to_wallet", None))
        voucher = None
        if tx.voucher_type:
            voucher = tx.voucher_type.name or tx.voucher_type.slug
        return {
            "created_at": tx.created_at,
            "updated_at": tx.updated_at,
            "voucher": voucher or "—",
            "amount": tx.amount,
            "status": tx.get_status_display(),
            "status_code": tx.status,
            "tx_hash": tx.tx_hash,
            "wallet": wallet,
        }

    # Note: claim_payload function removed - VoucherTransferLog no longer exists

    def redeem_payload(rec: POSRedemption) -> dict:
        wallet = wallet_info(getattr(rec, "wallet", None))
        voucher = getattr(rec, "voucher_type", None)
        voucher_label = voucher.name if voucher and voucher.name else getattr(voucher, "slug", "—")
        return {
            "reserved_at": rec.reserved_at,
            "committed_at": rec.committed_at,
            "status": rec.status,
            "amount": rec.amount,
            "voucher": voucher_label,
            "wallet": wallet,
            "terminal": rec.pos_terminal or "—",
        }

    context = {
        "console_msg": msg,
        "pending_txs": [tx_payload(tx) for tx in pending_qs],
        "recent_txs": [tx_payload(tx) for tx in recent_qs],
        "claim_logs": [claim_payload(log) for log in claims_qs],
        "recent_redeems": [redeem_payload(r) for r in recent_redeem_qs],
        "contract_address": settings.ST_DEFAULT_CONTRACT,
        "rpc_url": settings.ST_RPC_URL,
        "provider": settings.ST_PROVIDER,
        "chain_id": settings.ST_CHAIN_ID,
        "explorer_tx_prefix": getattr(settings, "ST_EXPLORER_TX_PREFIX", ""),
        "explorer_addr_prefix": getattr(settings, "ST_EXPLORER_ADDR_PREFIX", ""),
    }
    return render(request, "admin_console.html", context)


@admin_required
def admin_stats_page(request):
    msg = request.session.pop("console_msg", None)
    return render(request, "admin_stats.html", {"console_msg": msg})


@admin_required
def admin_scan(request):
    return render(request, "admin_scan.html")


@admin_required
def admin_stat_detail_page(request, key: str):
    return render(request, "admin_stat_detail.html", {"key": key})


@admin_required
def admin_users_page(request):
    q = (request.GET.get('q') or '').strip()
    qs = AppUser.objects.all().order_by('-created_at')
    if q == 'has_wallet':
        qs = qs.filter(wallets__isnull=False).distinct()
    elif q:
        qs = qs.filter(
            models.Q(full_name__icontains=q) |
            models.Q(email__icontains=q) |
            models.Q(phone__icontains=q)
        )
    paginator = Paginator(qs, 20)
    page_obj = paginator.get_page(request.GET.get('page'))

    now = timezone.now()
    last_7 = now - datetime.timedelta(days=7)
    wallet_user_count = Wallet.objects.values('user_id').distinct().count()
    stats = {
        'total_users': AppUser.objects.count(),
        'active_users': AppUser.objects.filter(is_active=True).count(),
        'users_with_wallet': wallet_user_count,
        'new_last_7d': AppUser.objects.filter(created_at__gte=last_7).count(),
    }

    return render(request, 'admin_users.html', {
        'page_obj': page_obj,
        'q': q,
        'stats': stats,
    })


@admin_required
def admin_vouchers_page(request):
    q = (request.GET.get('q') or '').strip()
    qs = VoucherType.objects.all().order_by('-created_at')
    if q:
        qs = qs.filter(models.Q(slug__icontains=q) | models.Q(name__icontains=q))
    
    # Add voucher code statistics
    from .models import QRClaim
    qs = qs.annotate(
        total_codes=Count('qrclaim', distinct=True),
        used_codes=Count('qrclaim', filter=Q(qrclaim__status='used'), distinct=True)
    )
    
    paginator = Paginator(qs, 20)
    page_obj = paginator.get_page(request.GET.get('page'))

    totals = VoucherType.objects.aggregate(
        total=Count('id'),
        active=Count('id', filter=Q(active=True)),
    )
    redemption_stats = POSRedemption.objects.aggregate(
        committed_amount=Sum('amount', filter=Q(status='committed')),
        reserved_amount=Sum('amount', filter=Q(status='reserved')),
    )
    balance_stats = VoucherBalance.objects.aggregate(
        circulating=Sum('balance'),
    )
    top_vouchers = (
        POSRedemption.objects.filter(status='committed')
        .values('voucher_type__slug', 'voucher_type__name')
        .annotate(total_amount=Sum('amount'), last_redeemed=Max('committed_at'))
        .order_by('-total_amount')[:5]
    )

    return render(request, 'admin_vouchers.html', {
        'page_obj': page_obj,
        'q': q,
        'stats': {
            'total_campaigns': totals.get('total') or 0,
            'active_campaigns': totals.get('active') or 0,
            'committed_amount': redemption_stats.get('committed_amount') or 0,
            'reserved_amount': redemption_stats.get('reserved_amount') or 0,
            'circulating_balance': balance_stats.get('circulating') or 0,
        },
        'top_vouchers': top_vouchers,
    })


@admin_required
def admin_voucher_new(request):
    if request.method == 'POST':
        form = VoucherTypeForm(request.POST)
        if form.is_valid():
            voucher = form.save(commit=False)
            # Auto-generate slug from name
            import re
            from django.utils.text import slugify
            from django.utils import timezone
            
            name = voucher.name
            base_slug = slugify(name)
            # Ensure uniqueness
            counter = 1
            slug = base_slug
            while VoucherType.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            voucher.slug = slug
            
            # Auto-set contract and token_id from settings
            voucher.erc1155_contract = settings.ST_DEFAULT_CONTRACT
            # Generate token_id based on existing vouchers
            last_voucher = VoucherType.objects.order_by('-token_id').first()
            voucher.token_id = (last_voucher.token_id + 1) if last_voucher else 1
            
            # Set timestamps
            now = timezone.now()
            voucher.created_at = now
            voucher.updated_at = now
            
            voucher.save()
            request.session['console_msg'] = 'Voucher created.'
            return redirect('/adv1/admin/vouchers')
    else:
        form = VoucherTypeForm()
    return render(request, 'admin_voucher_form.html', {'form': form, 'mode': 'create'})


@admin_required
def admin_voucher_edit(request, slug: str):
    try:
        obj = VoucherType.objects.get(slug=slug)
    except VoucherType.DoesNotExist:
        return redirect('/adv1/admin/vouchers')
    if request.method == 'POST':
        form = VoucherTypeForm(request.POST, instance=obj)
        if form.is_valid():
            voucher = form.save(commit=False)
            # Update timestamp
            from django.utils import timezone
            voucher.updated_at = timezone.now()
            voucher.save()
            request.session['console_msg'] = 'Voucher updated.'
            return redirect('/adv1/admin/vouchers')
    else:
        form = VoucherTypeForm(instance=obj)
    return render(request, 'admin_voucher_form.html', {'form': form, 'mode': 'edit', 'obj': obj})


@admin_required
@require_http_methods(["POST"]) 
def admin_voucher_delete(request, slug: str):
    try:
        obj = VoucherType.objects.get(slug=slug)
        obj.delete()
        request.session['console_msg'] = 'Voucher deleted.'
    except VoucherType.DoesNotExist:
        pass
    return redirect('/adv1/admin/vouchers')


@admin_required
@require_http_methods(["POST"])
def admin_voucher_export_qr_pdf(request):
    """Export voucher QR codes as PDF for printing."""
    voucher_slugs = request.POST.getlist('vouchers')
    if not voucher_slugs:
        return HttpResponseBadRequest("No vouchers selected")
    
    # Get voucher types
    vouchers = VoucherType.objects.filter(slug__in=voucher_slugs, active=True)
    if not vouchers.exists():
        return HttpResponseBadRequest("No active vouchers found")
    
    # Create PDF response
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="voucher_qr_codes_{timezone.now().strftime("%Y%m%d_%H%M%S")}.pdf"'
    
    # Create PDF document
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=0.5*inch, bottomMargin=0.5*inch)
    
    # Styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        spaceAfter=30,
        alignment=TA_CENTER,
        textColor=colors.darkgreen
    )
    
    voucher_style = ParagraphStyle(
        'VoucherTitle',
        parent=styles['Heading2'],
        fontSize=14,
        spaceAfter=10,
        alignment=TA_CENTER,
        textColor=colors.darkblue
    )
    
    # Build content
    story = []
    
    # Title
    story.append(Paragraph("Furama Resort - Voucher QR Codes", title_style))
    story.append(Spacer(1, 20))
    
    # Generate QR codes for each voucher
    from .qrcode_utils import render_qr_png
    from .models import QRClaim
    
    for voucher in vouchers:
        # Create a sample QR claim for this voucher
        # In a real implementation, you might want to generate multiple QR codes per voucher
        qr_data = f"voucher:{voucher.slug}:claim"
        
        # Generate QR code image
        qr_png = render_qr_png(qr_data)
        
        # Use BytesIO instead of temporary file to avoid Windows path issues
        qr_image_buffer = BytesIO(qr_png)
        
        try:
            # Add voucher title
            story.append(Paragraph(f"{voucher.name}", voucher_style))
            story.append(Spacer(1, 10))
            
            # Add QR code image using BytesIO
            qr_image = Image(qr_image_buffer, width=2*inch, height=2*inch)
            qr_image.hAlign = 'CENTER'
            story.append(qr_image)
            story.append(Spacer(1, 10))
            
            # Add voucher details
            details = [
                ['Voucher Code:', voucher.slug],
                ['Description:', voucher.description or 'StayToken reward'],
                ['Token ID:', str(voucher.token_id)],
                ['Status:', 'Active' if voucher.active else 'Inactive'],
            ]
            
            details_table = Table(details, colWidths=[1.5*inch, 3*inch])
            details_table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
            ]))
            
            story.append(details_table)
            story.append(Spacer(1, 20))
            
        finally:
            # Close the BytesIO buffer
            qr_image_buffer.close()
    
    # Build PDF
    doc.build(story)
    
    # Get PDF content
    pdf_content = buffer.getvalue()
    buffer.close()
    
    response.write(pdf_content)
    return response


@admin_required
def admin_merchants_page(request):
    merchants = Merchant.objects.all().order_by('-created_at')
    return render(request, 'admin_merchants.html', {'merchants': merchants})


@admin_required
def admin_merchant_new(request):
    if request.method == 'POST':
        form = MerchantForm(request.POST)
        if form.is_valid():
            merchant = form.save(commit=False)
            from django.utils import timezone
            merchant.created_at = timezone.now()
            merchant.save()
            request.session['console_msg'] = 'Merchant created successfully.'
            return redirect('/adv1/admin/merchants')
    else:
        form = MerchantForm()
    return render(request, 'admin_merchant_form.html', {'form': form, 'mode': 'create'})


@admin_required
def admin_merchant_edit(request, pk: str):
    try:
        obj = Merchant.objects.get(id=pk)
    except Merchant.DoesNotExist:
        return redirect('/adv1/admin/merchants')
    
    if request.method == 'POST':
        form = MerchantForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            request.session['console_msg'] = 'Merchant updated successfully.'
            return redirect('/adv1/admin/merchants')
    else:
        form = MerchantForm(instance=obj)
    return render(request, 'admin_merchant_form.html', {'form': form, 'mode': 'edit', 'obj': obj})


@admin_required
def admin_merchant_delete(request, pk: str):
    try:
        obj = Merchant.objects.get(id=pk)
        obj.delete()
        request.session['console_msg'] = 'Merchant deleted successfully.'
    except Merchant.DoesNotExist:
        pass
    return redirect('/adv1/admin/merchants')


@admin_required
def admin_terminals_page(request):
    terminals = POSTerminal.objects.select_related('merchant').all().order_by('-created_at')
    return render(request, 'admin_terminals.html', {'terminals': terminals})


@admin_required
def admin_terminal_new(request):
    if request.method == 'POST':
        form = POSTerminalForm(request.POST)
        if form.is_valid():
            terminal = form.save(commit=False)
            from django.utils import timezone
            import secrets
            import string
            
            # Auto-generate API key
            alphabet = string.ascii_letters + string.digits
            api_key = ''.join(secrets.choice(alphabet) for _ in range(32))
            terminal.api_key = api_key
            terminal.created_at = timezone.now()
            terminal.save()
            request.session['console_msg'] = 'Terminal created successfully.'
            return redirect('/adv1/admin/terminals')
    else:
        form = POSTerminalForm()
    return render(request, 'admin_terminal_form.html', {'form': form, 'mode': 'create'})


@admin_required
def admin_terminal_edit(request, pk: str):
    try:
        obj = POSTerminal.objects.get(id=pk)
    except POSTerminal.DoesNotExist:
        return redirect('/adv1/admin/terminals')
    
    if request.method == 'POST':
        form = POSTerminalForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            request.session['console_msg'] = 'Terminal updated successfully.'
            return redirect('/adv1/admin/terminals')
    else:
        form = POSTerminalForm(instance=obj)
    return render(request, 'admin_terminal_form.html', {'form': form, 'mode': 'edit', 'obj': obj})


@admin_required
def admin_terminal_delete(request, pk: str):
    try:
        obj = POSTerminal.objects.get(id=pk)
        obj.delete()
        request.session['console_msg'] = 'Terminal deleted successfully.'
    except POSTerminal.DoesNotExist:
        pass
    return redirect('/adv1/admin/terminals')


@admin_required
def admin_pos_redemptions_page(request):
    status = (request.GET.get('status') or '').strip()
    days = int(request.GET.get('days') or 7)
    since = timezone.now() - datetime.timedelta(days=days)
    qs = POSRedemption.objects.filter(reserved_at__gte=since).order_by('-reserved_at')
    if status:
        qs = qs.filter(status=status)
    paginator = Paginator(qs, 25)
    page_obj = paginator.get_page(request.GET.get('page'))

    summary = POSRedemption.objects.filter(reserved_at__gte=since).aggregate(
        total_count=Count('id'),
        committed_count=Count('id', filter=Q(status='committed')),
        committed_amount=Sum('amount', filter=Q(status='committed')),
        cancelled_count=Count('id', filter=Q(status='cancelled')),
    )

    terminal_map = POSTerminal.objects.select_related('merchant').in_bulk(field_name='code')
    # Attach terminal and merchant metadata to each row for easy rendering
    page_items = list(page_obj.object_list)
    for entry in page_items:
        terminal = terminal_map.get(entry.pos_terminal)
        entry.display_terminal = entry.pos_terminal or 'Unknown'
        entry.display_merchant = terminal.merchant.name if terminal and terminal.merchant_id else 'Unknown'
    page_obj.object_list = page_items
    top_merchants_raw = (
        POSRedemption.objects.filter(reserved_at__gte=since, pos_terminal__isnull=False)
        .values('pos_terminal')
        .annotate(
            total_amount=Sum('amount'),
            committed_amount=Sum('amount', filter=Q(status='committed')),
            redemption_count=Count('id'),
        )
        .order_by('-committed_amount')[:5]
    )
    top_merchants = []
    for item in top_merchants_raw:
        terminal = terminal_map.get(item['pos_terminal'])
        merchant_name = terminal.merchant.name if terminal and terminal.merchant_id else 'Unknown merchant'
        top_merchants.append({
            'terminal': item['pos_terminal'],
            'merchant': merchant_name,
            'committed_amount': item['committed_amount'] or 0,
            'total_amount': item['total_amount'] or 0,
            'redemption_count': item['redemption_count'],
        })

    return render(request, 'admin_merchants.html', {
        'page_obj': page_obj,
        'status': status,
        'days': days,
        'summary': summary,
        'top_merchants': top_merchants,
        'terminal_map': terminal_map,
    })


@admin_required
def admin_stats_json(request):
    with connection.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM app_user")
        users = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM voucher_type")
        voucher_campaigns = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM wallet")
        wallets = cur.fetchone()[0]

        cur.execute(
            """
            SELECT status, COUNT(*)
            FROM onchain_tx
            WHERE created_at::date = CURRENT_DATE
            GROUP BY status
            """
        )
        rows = cur.fetchall()

    tx_today_total = sum(r[1] for r in rows)
    tx_failed = sum(r[1] for r in rows if r[0] == "failed")

    stats = [
        {
            "key": "users_total",
            "title": "Total users",
            "value": f"{users:,}",
            "change": "+12.5%",
            "changeType": "positive",
            "tag": "users",
        },
        {
            "key": "voucher_campaigns",
            "title": "Voucher campaigns",
            "value": f"{voucher_campaigns:,}",
            "change": "+4.1%",
            "changeType": "positive",
            "tag": "vouchers",
        },
        {
            "key": "wallet_active",
            "title": "Active custodial wallets",
            "value": f"{wallets:,}",
            "change": "+3.1%",
            "changeType": "positive",
            "tag": "wallets",
        },
        {
            "key": "tx_today",
            "title": "On-chain transactions today",
            "value": f"{tx_today_total:,}",
            "change": f"{tx_failed} failed" if tx_failed else "Stable",
            "changeType": "negative" if tx_failed else "neutral",
            "tag": "on-chain",
        },
    ]
    return JsonResponse({"ok": True, "stats": stats})


@admin_required
def admin_stat_detail_json(request, key: str):
    detail = {
        "title": "Metric detail",
        "subtitle": "",
        "breakdown": [],
        "chart": [],
    }

    today = timezone.now().date()
    last7 = [today - datetime.timedelta(days=i) for i in range(6, -1, -1)]

    with connection.cursor() as cur:
        if key == "users_total":
            detail["title"] = "Platform users"
            detail["subtitle"] = "Total accounts and new sign-ups"

            cur.execute(
                "SELECT COUNT(*) FROM app_user WHERE created_at::date = %s",
                [today],
            )
            today_new = cur.fetchone()[0]

            cur.execute(
                """
                SELECT created_at::date, COUNT(*)
                FROM app_user
                WHERE created_at::date >= %s
                GROUP BY created_at::date
                """,
                [last7[0]],
            )
            daily = {row[0]: row[1] for row in cur.fetchall() if row[0]}
            detail["breakdown"] = [
                {"label": "Sign-ups today", "value": today_new},
                {"label": "Sign-ups (last 7 days)", "value": sum(daily.values())},
            ]
            detail["chart"] = [
                {"label": d.strftime("%d/%m"), "value": daily.get(d, 0)} for d in last7
            ]

        elif key == "voucher_campaigns":
            detail["title"] = "Voucher campaigns"
            detail["subtitle"] = "Active versus paused campaigns"

            cur.execute(
                "SELECT active, COUNT(*) FROM voucher_type GROUP BY active"
            )
            rows = cur.fetchall()
            active = sum(r[1] for r in rows if r[0])
            inactive = sum(r[1] for r in rows if not r[0])
            detail["breakdown"] = [
                {"label": "Active", "value": active},
                {"label": "Inactive", "value": inactive},
            ]

            cur.execute(
                """
                SELECT created_at::date, COUNT(*)
                FROM voucher_type
                WHERE created_at >= %s
                GROUP BY created_at::date
                """,
                [last7[0]],
            )
            rows = cur.fetchall()
            chart_lookup = {row[0]: row[1] for row in rows if row[0]}
            detail["chart"] = [
                {"label": d.strftime("%d/%m"), "value": chart_lookup.get(d, 0)} for d in last7
            ]

        elif key == "wallet_active":
            detail['title'] = 'Custodial wallets'
            detail["subtitle"] = "Wallet creation trend and totals"

            cur.execute(
                "SELECT COUNT(*) FROM wallet WHERE created_at::date = %s",
                [today],
            )
            wallet_new_today = cur.fetchone()[0]

            cur.execute(
                """
                SELECT created_at::date, COUNT(*)
                FROM wallet
                WHERE created_at::date >= %s
                GROUP BY created_at::date
                """,
                [last7[0]],
            )
            rows = cur.fetchall()
            chart_lookup = {row[0]: row[1] for row in rows if row[0]}
            detail["breakdown"] = [
                {"label": "Wallets created today", "value": wallet_new_today},
                {"label": "Wallets created (last 7 days)", "value": sum(chart_lookup.values())},
            ]
            detail["chart"] = [
                {"label": d.strftime("%d/%m"), "value": chart_lookup.get(d, 0)} for d in last7
            ]

        elif key == "tx_today":
            detail["title"] = "On-chain transactions"
            detail["subtitle"] = "Status distribution today"

            cur.execute(
                """
                SELECT status, COUNT(*)
                FROM onchain_tx
                WHERE created_at::date = %s
                GROUP BY status
                """,
                [today],
            )
            rows = cur.fetchall()
            status_map = {row[0] or 'unknown': row[1] for row in rows}
            detail["breakdown"] = [
                {"label": "Sent", "value": status_map.get('sent', 0)},
                {"label": "Confirmed", "value": status_map.get('confirmed', 0)},
                {"label": "Queued", "value": status_map.get('queued', 0)},
                {"label": "Failed", "value": status_map.get('failed', 0)},
            ]

            cur.execute(
                """
                SELECT created_at::date, COUNT(*)
                FROM onchain_tx
                WHERE created_at::date >= %s
                GROUP BY created_at::date
                """,
                [last7[0]],
            )
            rows = cur.fetchall()
            chart_lookup = {row[0]: row[1] for row in rows if row[0]}
            detail["chart"] = [
                {"label": d.strftime("%d/%m"), "value": chart_lookup.get(d, 0)} for d in last7
            ]
        else:
            return JsonResponse({"ok": False, "error": "unknown_key"}, status=404)

    return JsonResponse({"ok": True, "detail": detail})


@admin_required
@require_http_methods(["POST"])
def quick_gen_qr(request):
    slug = (request.POST.get("slug") or "").strip()
    count = int(request.POST.get("count") or 0)
    if not slug or count <= 0:
        return HttpResponseBadRequest("slug/count invalid")
    out = io.StringIO()
    management.call_command("gen_claim_qr", slug=slug, count=count, stdout=out)
    request.session['console_msg'] = f'Generated {count} QR codes for {slug}.'
    return redirect("/adv1/console")


@admin_required
@require_http_methods(["POST"])
def quick_export_csv(request):
    days = int(request.POST.get("days") or 30)
    start = timezone.now() - datetime.timedelta(days=days)

    with connection.cursor() as cur:
        cur.execute(
            """
            SELECT pr.id, vt.slug, pr.amount, pr.status, pr.pos_terminal, pr.reserved_at, pr.committed_at
            FROM pos_redemption pr
            JOIN voucher_type vt ON vt.id = pr.voucher_type_id
            WHERE pr.reserved_at >= %s
            ORDER BY pr.reserved_at DESC
            """,
            [start],
        )
        rows = cur.fetchall()

    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["reservation_id", "voucher_slug", "amount", "status", "terminal", "reserved_at", "committed_at"])
    for r in rows:
        writer.writerow(r)

    resp = HttpResponse(out.getvalue(), content_type="text/csv")
    resp["Content-Disposition"] = f'attachment; filename="redemptions_{days}d.csv"'
    return resp


@admin_required
def recent_activity_json(request):
    items = []
    with connection.cursor() as cur:
        cur.execute(
            """
            SELECT cr.created_at, COALESCE(cr.email, cr.phone, 'unknown') AS who, cr.result
            FROM claim_request cr
            ORDER BY cr.created_at DESC LIMIT 10
            """
        )
        for ts, who, result in cur.fetchall():
            status = "success" if result == "ok" else "warning"
            items.append({
                "type": "user_register",
                "user": who,
                "action": f"Claim voucher ({result})",
                "timestamp": ts,
                "status": status,
            })

        cur.execute(
            """
            SELECT pr.reserved_at, vt.slug, pr.status
            FROM pos_redemption pr
            JOIN voucher_type vt ON vt.id = pr.voucher_type_id
            ORDER BY pr.reserved_at DESC LIMIT 10
            """
        )
        for ts, slug, status in cur.fetchall():
            items.append({
                "type": "voucher_redeem",
                "user": slug,
                "action": f"POS redeem ({status})",
                "timestamp": ts,
                "status": "success" if status == "committed" else "warning",
            })

        cur.execute(
            """
            SELECT created_at, kind, status
            FROM onchain_tx
            ORDER BY created_at DESC LIMIT 10
            """
        )
        for ts, kind, status in cur.fetchall():
            items.append({
                "type": "onchain",
                "user": kind,
                "action": f"On-chain tx ({status})",
                "timestamp": ts,
                "status": "success" if status in ("sent", "confirmed") else "warning",
            })

    items.sort(key=lambda x: x["timestamp"], reverse=True)
    out = []
    for idx, it in enumerate(items[:15], start=1):
        out.append({
            "id": idx,
            "type": it["type"],
            "user": it["user"],
            "action": it["action"],
            "timestamp": it["timestamp"].isoformat() if hasattr(it["timestamp"], "isoformat") else str(it["timestamp"]),
            "status": it["status"],
        })
    return JsonResponse({"ok": True, "activities": out})


@admin_required
def admin_pos_scanner(request):
    """POS Scanner page for admin to scan and validate vouchers."""
    return render(request, "admin_pos_scanner.html")


@admin_required
@require_http_methods(["POST"])
def admin_pos_validate_voucher(request):
    """Validate a voucher from QRClaim code scan."""
    try:
        data = json.loads(request.body)
        qr_code = data.get('qr_code')
        
        if not qr_code:
            return JsonResponse({
                "success": False,
                "message": "Missing QR code"
            }, status=400)
        
        # Get QRClaim by code
        from .models import QRClaim, VoucherBalance
        try:
            qr_claim = QRClaim.objects.select_related('voucher_type', 'used_by_user').get(code=qr_code)
        except QRClaim.DoesNotExist:
            return JsonResponse({
                "success": False,
                "message": "QR code not found"
            })
        
        # Check if already used
        if qr_claim.status == 'used':
            return JsonResponse({
                "success": False,
                "message": "This voucher has already been used"
            })
        
        # Get user's wallet and balance
        wallet = qr_claim.used_by_user.wallets.first()
        if not wallet:
            return JsonResponse({
                "success": False,
                "message": "User has no wallet"
            })
        
        try:
            balance = VoucherBalance.objects.get(wallet=wallet, voucher_type=qr_claim.voucher_type)
            balance_amount = balance.balance
        except VoucherBalance.DoesNotExist:
            balance_amount = 0
        
        # Check if user has sufficient balance
        is_valid = balance_amount > 0
        
        if is_valid:
            message = f"✅ Valid voucher. Balance: {balance_amount} tokens"
        else:
            message = "❌ No voucher balance found"
            
        return JsonResponse({
            "success": True,
            "qr_code": qr_code,
            "voucher_name": qr_claim.voucher_type.name,
            "voucher_slug": qr_claim.voucher_type.slug,
            "balance": balance_amount,
            "is_valid": is_valid,
            "message": message,
            "wallet_address": wallet.address_hex,
            "user_name": qr_claim.used_by_user.full_name or qr_claim.used_by_user.email or "Unknown",
            "created_at": qr_claim.created_at.isoformat()
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            "success": False,
            "message": "Invalid JSON data"
        }, status=400)
    except Exception as e:
        return JsonResponse({
            "success": False,
            "message": f"Validation error: {str(e)}"
        }, status=500)


@admin_required
@require_http_methods(["POST"])
def admin_pos_confirm_redemption(request):
    """Confirm voucher redemption and update balances."""
    from django.db import transaction
    
    try:
        data = json.loads(request.body)
        qr_code = data.get('qr_code')
        
        print(f"Confirm redemption request for QR code: {qr_code}")
        
        if not qr_code:
            return JsonResponse({
                "success": False,
                "message": "Missing QR code"
            }, status=400)
        
        # Get QRClaim
        from .models import QRClaim, VoucherBalance, POSRedemption
        try:
            qr_claim = QRClaim.objects.select_related('voucher_type', 'used_by_user').get(code=qr_code)
            print(f"Found QRClaim: {qr_claim.id}, status: {qr_claim.status}")
        except QRClaim.DoesNotExist:
            print(f"QRClaim not found for code: {qr_code}")
            return JsonResponse({
                "success": False,
                "message": "QR code not found"
            })
        
        # Check if already used
        if qr_claim.status == 'used':
            return JsonResponse({
                "success": False,
                "message": "This voucher has already been used"
            })
        
        with transaction.atomic():
            # Get user's wallet and balance
            wallet = qr_claim.used_by_user.wallets.first()
            if not wallet:
                return JsonResponse({
                    "success": False,
                    "message": "User has no wallet"
                })
            
            try:
                balance = VoucherBalance.objects.get(wallet=wallet, voucher_type=qr_claim.voucher_type)
                if balance.balance <= 0:
                    return JsonResponse({
                        "success": False,
                        "message": "Insufficient voucher balance"
                    })
            except VoucherBalance.DoesNotExist:
                return JsonResponse({
                    "success": False,
                    "message": "No voucher balance found"
                })
            
            # Perform redemption (decrease balance by 1)
            from django.db import connection
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE voucher_balance SET balance = balance - 1, updated_at = NOW() WHERE wallet_id = %s AND voucher_type_id = %s",
                    [wallet.id, qr_claim.voucher_type.id]
                )
            
            # Update QRClaim status to used
            qr_claim.status = 'used'
            qr_claim.used_at = timezone.now()
            qr_claim.save()
            
            # Create POS redemption record
            try:
                pos_redemption = POSRedemption.objects.create(
                    voucher_type=qr_claim.voucher_type,
                    wallet=wallet,
                    amount=1,
                    status='committed',
                    pos_terminal='pos_scanner',
                    reserved_at=timezone.now(),
                    committed_at=timezone.now()
                )
                print(f"Created POSRedemption: {pos_redemption.id}")
            except Exception as e:
                print(f"Error creating POSRedemption: {e}")
                # Continue anyway, don't fail the redemption
        
        # Get updated balance for response
        updated_balance = VoucherBalance.objects.get(wallet=wallet, voucher_type=qr_claim.voucher_type)
        
        response_message = f"Voucher redeemed successfully. Remaining balance: {updated_balance.balance}"
        print(f"Returning success response: {response_message}")
        
        return JsonResponse({
            "success": True,
            "message": response_message
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            "success": False,
            "message": "Invalid JSON data"
        }, status=400)
    except Exception as e:
        return JsonResponse({
            "success": False,
            "message": f"Redemption error: {str(e)}"
        }, status=500)


@admin_required
def admin_voucher_codes(request, slug: str):
    """View voucher codes for a specific voucher type."""
    try:
        voucher = VoucherType.objects.get(slug=slug)
    except VoucherType.DoesNotExist:
        raise Http404("Voucher not found")
    
    # Get search parameters
    q = (request.GET.get('q') or '').strip()
    status = request.GET.get('status', '')
    
    # Build queryset
    from .models import QRClaim
    qs = QRClaim.objects.filter(voucher_type=voucher)
    
    if q:
        qs = qs.filter(code__icontains=q)
    if status:
        qs = qs.filter(status=status)
    
    # Order by created_at desc
    qs = qs.order_by('-created_at')
    
    # Paginate
    paginator = Paginator(qs, 50)
    page_obj = paginator.get_page(request.GET.get('page'))
    
    # Calculate statistics
    total_codes = QRClaim.objects.filter(voucher_type=voucher).count()
    used_codes = QRClaim.objects.filter(voucher_type=voucher, status='used').count()
    available_codes = total_codes - used_codes
    usage_rate = round((used_codes / total_codes * 100) if total_codes > 0 else 0, 1)
    
    return render(request, 'admin_voucher_codes.html', {
        'voucher': voucher,
        'page_obj': page_obj,
        'q': q,
        'status': status,
        'stats': {
            'total_codes': total_codes,
            'used_codes': used_codes,
            'available_codes': available_codes,
            'usage_rate': usage_rate
        }
    })


@admin_required
@require_http_methods(["POST"])
def admin_voucher_generate_codes(request, slug: str):
    """Generate new voucher codes for a voucher type."""
    try:
        voucher = VoucherType.objects.get(slug=slug)
    except VoucherType.DoesNotExist:
        return JsonResponse({"success": False, "message": "Voucher not found"}, status=404)
    
    try:
        data = json.loads(request.body)
        count = data.get('count', 10)
        prefix = data.get('prefix', slug.upper())
        expiry_days = data.get('expiry_days')
        
        if count < 1 or count > 1000:
            return JsonResponse({"success": False, "message": "Count must be between 1 and 1000"}, status=400)
        
        # Generate codes
        from .models import QRClaim
        from django.utils import timezone
        from datetime import timedelta
        import random
        import string
        
        codes_created = []
        expires_at = None
        if expiry_days:
            expires_at = timezone.now() + timedelta(days=expiry_days)
        
        for i in range(count):
            # Generate unique code
            while True:
                suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
                code = f"{prefix}_{suffix}"
                if not QRClaim.objects.filter(code=code).exists():
                    break
            
            # Create QRClaim
            qr_claim = QRClaim.objects.create(
                code=code,
                voucher_type=voucher,
                status='new',
                expires_at=expires_at,
                created_at=timezone.now()
            )
            codes_created.append(code)
        
        return JsonResponse({
            "success": True,
            "message": f"Generated {len(codes_created)} voucher codes",
            "codes": codes_created[:10]  # Return first 10 for preview
        })
        
    except json.JSONDecodeError:
        return JsonResponse({"success": False, "message": "Invalid JSON data"}, status=400)
    except Exception as e:
        return JsonResponse({"success": False, "message": f"Error generating codes: {str(e)}"}, status=500)


@admin_required
@require_http_methods(["POST"])
def admin_voucher_expire_code(request, slug: str):
    """Expire a specific voucher code."""
    try:
        voucher = VoucherType.objects.get(slug=slug)
    except VoucherType.DoesNotExist:
        return JsonResponse({"success": False, "message": "Voucher not found"}, status=404)
    
    try:
        data = json.loads(request.body)
        code = data.get('code')
        
        if not code:
            return JsonResponse({"success": False, "message": "Code is required"}, status=400)
        
        from .models import QRClaim
        try:
            qr_claim = QRClaim.objects.get(code=code, voucher_type=voucher)
            if qr_claim.status == 'used':
                return JsonResponse({"success": False, "message": "Code is already used"}, status=400)
            
            qr_claim.status = 'expired'
            qr_claim.save()
            
            return JsonResponse({"success": True, "message": "Code expired successfully"})
            
        except QRClaim.DoesNotExist:
            return JsonResponse({"success": False, "message": "Code not found"}, status=404)
        
    except json.JSONDecodeError:
        return JsonResponse({"success": False, "message": "Invalid JSON data"}, status=400)
    except Exception as e:
        return JsonResponse({"success": False, "message": f"Error expiring code: {str(e)}"}, status=500)


@admin_required
def admin_voucher_export_codes(request, slug: str):
    """Export voucher codes as CSV."""
    try:
        voucher = VoucherType.objects.get(slug=slug)
    except VoucherType.DoesNotExist:
        raise Http404("Voucher not found")
    
    # Get search parameters
    q = (request.GET.get('q') or '').strip()
    status = request.GET.get('status', '')
    
    # Build queryset
    from .models import QRClaim
    qs = QRClaim.objects.filter(voucher_type=voucher)
    
    if q:
        qs = qs.filter(code__icontains=q)
    if status:
        qs = qs.filter(status=status)
    
    # Order by created_at desc
    qs = qs.order_by('-created_at')
    
    # Create CSV response
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{slug}_voucher_codes_{timezone.now().strftime("%Y%m%d_%H%M%S")}.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Code', 'Status', 'Used By', 'Used At', 'Expires At', 'Created At'])
    
    for code in qs:
        writer.writerow([
            code.code,
            code.status,
            code.used_by_user.email if code.used_by_user else '',
            code.used_at.strftime('%Y-%m-%d %H:%M:%S') if code.used_at else '',
            code.expires_at.strftime('%Y-%m-%d %H:%M:%S') if code.expires_at else '',
            code.created_at.strftime('%Y-%m-%d %H:%M:%S') if code.created_at else ''
        ])
    
    return response
