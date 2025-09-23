import hashlib
import uuid
from typing import Optional

from django.conf import settings
from django.db import connection, transaction
from django.utils import timezone

from .models import (
    AppUser,
    Wallet,
    VoucherBalance,
    VoucherTransferLog,
    VoucherType,
    OnchainTx,
    QRClaim,
    ClaimRequest,
    Policy,
)
from .adapters.wallet_provider import WalletProviderAdapter


def _ip_hash(ip: str) -> Optional[str]:
    if not ip:
        return None
    seed = settings.SECRET_KEY or "x"
    return hashlib.sha256((ip + seed).encode("utf-8")).hexdigest()


def _normalize_evm_address(address: str) -> str:
    if not address:
        raise ValueError("Address is required")
    normalized = address.strip().lower()
    if normalized.startswith("0x"):
        normalized = normalized[2:]
    if len(normalized) != 40:
        raise ValueError("Address must be 20 bytes (40 hex chars)")
    try:
        bytes.fromhex(normalized)
    except ValueError as exc:
        raise ValueError("Address contains non-hex characters") from exc
    return normalized


def rate_limit_ok(email: Optional[str], ip: Optional[str]) -> bool:
    """Simple rate-limit guard; disabled when ST_RATE_LIMIT_PER_10M <= 0."""
    per_10m = getattr(settings, "ST_RATE_LIMIT_PER_10M", 0)
    if per_10m is None or per_10m <= 0:
        return True
    with connection.cursor() as cur:
        cur.execute(
            """
            SELECT COUNT(*)
            FROM claim_request
            WHERE created_at > NOW() - interval '10 minutes'
              AND (email = %s OR ip_hash = %s)
            """,
            [email, _ip_hash(ip)],
        )
        count = cur.fetchone()[0]
    return count < per_10m


def get_or_create_user(full_name: str, email: Optional[str], phone: Optional[str]) -> AppUser:
    user = None
    if email:
        try:
            user = AppUser.objects.get(email=email)
        except AppUser.DoesNotExist:
            user = None
    if not user and phone:
        user = AppUser.objects.filter(phone=phone).first()
    if user:
        return user

    new_id = uuid.uuid4()
    now = timezone.now()
    with connection.cursor() as cur:
        cur.execute(
            """
            INSERT INTO app_user (id, email, phone, full_name, is_active, created_at, updated_at)
            VALUES (%s, %s, %s, %s, TRUE, NOW(), NOW())
            """,
            [str(new_id), email, phone, full_name],
        )
    return AppUser.objects.get(id=new_id)


def get_or_create_wallet(user: AppUser, chain_id: int) -> Wallet:
    wallet = Wallet.objects.filter(user=user, chain_id=chain_id).first()
    if wallet:
        return wallet

    adapter = WalletProviderAdapter(settings.ST_PROVIDER, chain_id)
    meta = adapter.create_wallet(user_external_id=str(user.id))

    new_id = uuid.uuid4()
    with connection.cursor() as cur:
        cur.execute(
            """
            INSERT INTO wallet (id, user_id, provider, provider_ref, chain_id, address, exportable, export_status, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
            """,
            [
                str(new_id),
                str(user.id),
                settings.ST_PROVIDER,
                meta["provider_ref"],
                chain_id,
                meta["address_bytes"],
                meta["exportable"],
                "not_allowed",
            ],
        )
    return Wallet.objects.get(id=new_id)


def get_or_create_external_wallet(user: AppUser, chain_id: int, address_hex: str) -> Wallet:
    normalized = _normalize_evm_address(address_hex)
    address_bytes = bytes.fromhex(normalized)
    wallet = Wallet.objects.filter(chain_id=chain_id, address=address_bytes).first()
    if wallet:
        owner_id = getattr(wallet, "user_id", None)
        if owner_id and str(owner_id) != str(user.id):
            raise PermissionError("Address already registered to another user")
        return wallet

    provider_ref = f"external:{normalized}"[:128]
    new_id = uuid.uuid4()
    with connection.cursor() as cur:
        cur.execute(
            """
            INSERT INTO wallet (id, user_id, provider, provider_ref, chain_id, address, exportable, export_status, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, FALSE, 'not_allowed', NOW())
            """,
            [str(new_id), str(user.id), "external", provider_ref, chain_id, address_bytes],
        )
    return Wallet.objects.get(id=new_id)


@transaction.atomic
def issue_voucher(user: AppUser, voucher: VoucherType, amount: int = 1) -> Wallet:
    wallet = get_or_create_wallet(user, chain_id=settings.ST_CHAIN_ID)

    with connection.cursor() as cur:
        cur.execute(
            """
            SELECT balance FROM voucher_balance
            WHERE wallet_id=%s AND voucher_type_id=%s
            FOR UPDATE
            """,
            [str(wallet.id), str(voucher.id)],
        )
        row = cur.fetchone()
        if not row:
            cur.execute(
                """
                INSERT INTO voucher_balance (wallet_id, voucher_type_id, balance, updated_at)
                VALUES (%s, %s, %s, NOW())
                """,
                [str(wallet.id), str(voucher.id), amount],
            )
        else:
            cur.execute(
                """
                UPDATE voucher_balance
                SET balance = balance + %s, updated_at = NOW()
                WHERE wallet_id = %s AND voucher_type_id = %s
                """,
                [amount, str(wallet.id), str(voucher.id)],
            )
        cur.execute(
            """
            INSERT INTO voucher_transfer_log (id, from_wallet_id, to_wallet_id, voucher_type_id, amount, reason, pos_ref, created_at)
            VALUES (%s, NULL, %s, %s, %s, 'claim', NULL, NOW())
            """,
            [str(uuid.uuid4()), str(wallet.id), str(voucher.id), amount],
        )
    return wallet


@transaction.atomic
def debit_voucher(
    wallet: Wallet,
    voucher: VoucherType,
    amount: int,
    *,
    reason: str,
    to_wallet: Optional[Wallet] = None,
    pos_ref: Optional[str] = None,
) -> uuid.UUID:
    if amount <= 0:
        raise ValueError("Amount must be positive")

    with connection.cursor() as cur:
        cur.execute(
            """
            SELECT balance FROM voucher_balance
            WHERE wallet_id=%s AND voucher_type_id=%s
            FOR UPDATE
            """,
            [str(wallet.id), str(voucher.id)],
        )
        row = cur.fetchone()
        if not row or row[0] < amount:
            raise ValueError("Insufficient balance")

        cur.execute(
            """
            UPDATE voucher_balance
            SET balance = balance - %s, updated_at = NOW()
            WHERE wallet_id = %s AND voucher_type_id = %s
            """,
            [amount, str(wallet.id), str(voucher.id)],
        )

        transfer_id = uuid.uuid4()
        cur.execute(
            """
            INSERT INTO voucher_transfer_log (id, from_wallet_id, to_wallet_id, voucher_type_id, amount, reason, pos_ref, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
            """,
            [
                str(transfer_id),
                str(wallet.id),
                str(to_wallet.id) if to_wallet else None,
                str(voucher.id),
                amount,
                reason,
                pos_ref,
            ],
        )
    return transfer_id


def enqueue_onchain(kind: str, voucher: VoucherType, to_wallet: Wallet, amount: int = 1) -> OnchainTx:
    new_id = uuid.uuid4()
    with connection.cursor() as cur:
        cur.execute(
            """
            INSERT INTO onchain_tx (id, kind, voucher_type_id, to_wallet_id, amount, status, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, 'queued', NOW(), NOW())
            """,
            [
                str(new_id),
                kind,
                str(voucher.id) if voucher else None,
                str(to_wallet.id) if to_wallet else None,
                amount,
            ],
        )
    return OnchainTx.objects.get(id=new_id)


def log_claim_request(qr: QRClaim, ip: Optional[str], ua: Optional[str], email: Optional[str], phone: Optional[str], consent: bool, result: str):
    request_id = uuid.uuid4()
    with connection.cursor() as cur:
        cur.execute(
            """
            INSERT INTO claim_request (id, qr_claim_id, ip_hash, device_fp, user_agent, email, phone, consent, result, created_at)
            VALUES (%s, %s, %s, NULL, %s, %s, %s, %s, %s, NOW())
            """,
            [
                str(request_id),
                str(qr.id),
                _ip_hash(ip),
                ua[:200] if ua else None,
                email,
                phone,
                consent,
                result,
            ],
        )


def finish_qr_claim(qr: QRClaim, user: AppUser):
    with connection.cursor() as cur:
        cur.execute(
            """
            UPDATE qr_claim
            SET status='claimed', used_by_user=%s, used_at=NOW()
            WHERE id=%s
            """,
            [str(user.id), str(qr.id)],
        )
