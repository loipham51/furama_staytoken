import uuid
from decimal import Decimal
from django.db import models


# =========================
# Reusable Choices
# =========================
class ExportStatus(models.TextChoices):
    NOT_ALLOWED = "not_allowed", "Not allowed"
    ALLOWED = "allowed", "Allowed"
    REQUESTED = "requested", "Requested"
    DONE = "done", "Done"
    DENIED = "denied", "Denied"


class PosRedeemStatus(models.TextChoices):
    RESERVED = "reserved", "Reserved"
    COMMITTED = "committed", "Committed"
    CANCELLED = "cancelled", "Cancelled"


class OnchainKind(models.TextChoices):
    MINT1155 = "mint1155", "Mint ERC-1155"
    SAFE_TRANSFER_1155 = "safeTransfer1155", "Safe Transfer ERC-1155"


class OnchainStatus(models.TextChoices):
    QUEUED = "queued", "Queued"
    SENT = "sent", "Sent"
    CONFIRMED = "confirmed", "Confirmed"
    FAILED = "failed", "Failed"


# =========================
# Core user/wallet/voucher
# =========================
class AppUser(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # DB là CITEXT; map bằng CharField
    email = models.CharField(max_length=320, unique=True, null=True, blank=True)
    phone = models.CharField(max_length=32, null=True, blank=True)
    full_name = models.CharField(max_length=120, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "app_user"
        managed = False
        indexes = [
            models.Index(fields=["phone"], name="idx_user_phone_py"),
        ]

    def __str__(self):
        return self.full_name or self.email or str(self.id)

    @property
    def masked_email(self):
        if not self.email:
            return ""
        try:
            name, dom = self.email.split("@", 1)
            if len(name) <= 2:
                name_mask = name[0] + "*"
            else:
                name_mask = name[0] + "*" * (len(name) - 2) + name[-1]
            return f"{name_mask}@{dom}"
        except Exception:
            return self.email

    @property
    def masked_phone(self):
        if not self.phone:
            return ""
        p = self.phone
        if len(p) <= 4:
            return "*" * len(p)
        return p[:2] + "*" * (len(p) - 4) + p[-2:]


class Wallet(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey("AppUser", on_delete=models.CASCADE, db_column="user_id", related_name="wallets")
    provider = models.CharField(max_length=40)              # 'privy' | 'fireblocks' | 'self'
    provider_ref = models.CharField(max_length=128)
    chain_id = models.IntegerField()
    address = models.BinaryField()                           # 20 bytes (BYTEA)
    exportable = models.BooleanField(default=False)
    export_status = models.CharField(max_length=20, choices=ExportStatus.choices, default=ExportStatus.NOT_ALLOWED)
    created_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "wallet"
        managed = False
        unique_together = (("provider", "provider_ref"), ("chain_id", "address"))
        indexes = [
            models.Index(fields=["user"], name="idx_wallet_user_py"),
            models.Index(fields=["chain_id"], name="idx_wallet_chain_py"),
        ]

    def __str__(self):
        return f"{self.user_id} @ {self.address_hex or '0x?'}"

    @property
    def address_hex(self) -> str:
        if self.address:
            return "0x" + self.address.hex()
        return None

    @property
    def short_address(self) -> str:
        h = self.address_hex
        return (h[:8] + "…" + h[-6:]) if h else ""


class VoucherType(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    slug = models.CharField(max_length=64, unique=True)
    name = models.CharField(max_length=120)
    description = models.TextField(null=True, blank=True)
    erc1155_contract = models.CharField(max_length=64)
    token_id = models.DecimalField(max_digits=78, decimal_places=0)  # matches NUMERIC(78,0)
    max_supply = models.BigIntegerField(null=True, blank=True)
    per_user_limit = models.IntegerField(null=True, blank=True, default=1)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "voucher_type"
        managed = False
        indexes = [
            models.Index(fields=["active"], name="idx_vtype_active_py"),
        ]

    def __str__(self):
        return f"{self.slug} (#{self.token_id})"


class VoucherBalance(models.Model):
    wallet = models.ForeignKey("Wallet", on_delete=models.CASCADE, db_column="wallet_id", related_name="voucher_balances")
    voucher_type = models.ForeignKey("VoucherType", on_delete=models.CASCADE, db_column="voucher_type_id", related_name="balances")
    balance = models.BigIntegerField(default=0)
    updated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "voucher_balance"
        managed = False
        unique_together = (("wallet", "voucher_type"),)
        indexes = [
            models.Index(fields=["wallet"], name="idx_vbal_wallet_py"),
            models.Index(fields=["voucher_type"], name="idx_vbal_vtype_py"),
        ]

    def __str__(self):
        return f"{self.wallet_id} / {self.voucher_type_id} = {self.balance}"


class VoucherTransferLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    from_wallet = models.ForeignKey("Wallet", null=True, on_delete=models.SET_NULL, db_column="from_wallet_id", related_name="+")
    to_wallet = models.ForeignKey("Wallet", null=True, on_delete=models.SET_NULL, db_column="to_wallet_id", related_name="+")
    voucher_type = models.ForeignKey("VoucherType", on_delete=models.CASCADE, db_column="voucher_type_id")
    amount = models.BigIntegerField()
    reason = models.CharField(max_length=40)                 # 'claim' | 'pos' | 'export' | ...
    pos_ref = models.CharField(max_length=64, null=True, blank=True)
    created_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "voucher_transfer_log"
        managed = False
        indexes = [
            models.Index(fields=["voucher_type"], name="idx_vtlog_vtype_py"),
            models.Index(fields=["created_at"], name="idx_vtlog_time_py"),
        ]

    def __str__(self):
        return f"{self.reason} {self.amount} {self.voucher_type_id}"


class QRClaim(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=64, unique=True)
    voucher_type = models.ForeignKey("VoucherType", on_delete=models.CASCADE, db_column="voucher_type_id")
    event_label = models.CharField(max_length=64, null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    used_by_user = models.ForeignKey("AppUser", null=True, on_delete=models.SET_NULL, db_column="used_by_user")
    used_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=16, default="new")  # new|used|expired
    created_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "qr_claim"
        managed = False
        indexes = [
            models.Index(fields=["code"], name="idx_qr_code_py"),
            models.Index(fields=["status"], name="idx_qr_status_py"),
            models.Index(fields=["voucher_type"], name="idx_qr_vtype_py"),
        ]

    def __str__(self):
        return f"{self.code} ({self.status})"


class ClaimRequest(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    qr_claim = models.ForeignKey("QRClaim", on_delete=models.CASCADE, db_column="qr_claim_id")
    ip_hash = models.CharField(max_length=64, null=True, blank=True)
    device_fp = models.CharField(max_length=128, null=True, blank=True)
    user_agent = models.CharField(max_length=200, null=True, blank=True)
    email = models.CharField(max_length=320, null=True, blank=True)
    phone = models.CharField(max_length=32, null=True, blank=True)
    consent = models.BooleanField()
    result = models.CharField(max_length=16)                 # ok|used|expired|rate_limited|...
    created_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "claim_request"
        managed = False
        indexes = [
            models.Index(fields=["created_at"], name="idx_creq_time_py"),
            models.Index(fields=["result"], name="idx_creq_result_py"),
            models.Index(fields=["email"], name="idx_creq_email_py"),
            models.Index(fields=["phone"], name="idx_creq_phone_py"),
        ]

    def __str__(self):
        return f"{self.qr_claim_id} / {self.result}"


class POSRedemption(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    voucher_type = models.ForeignKey("VoucherType", on_delete=models.CASCADE, db_column="voucher_type_id")
    wallet = models.ForeignKey("Wallet", on_delete=models.CASCADE, db_column="wallet_id")
    amount = models.BigIntegerField(default=1)
    status = models.CharField(max_length=16, choices=PosRedeemStatus.choices, default=PosRedeemStatus.RESERVED)
    pos_terminal = models.CharField(max_length=64, null=True, blank=True)  # lưu code hoặc id
    reserved_at = models.DateTimeField(null=True, blank=True)
    committed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "pos_redemption"
        managed = False
        indexes = [
            models.Index(fields=["wallet"], name="idx_posr_wallet_py"),
            models.Index(fields=["voucher_type"], name="idx_posr_vtype_py"),
            models.Index(fields=["status", "reserved_at"], name="idx_posr_status_time_py"),
            models.Index(fields=["pos_terminal"], name="idx_posr_terminal_py"),
            models.Index(fields=["committed_at"], name="idx_posr_committed_py"),
        ]

    def __str__(self):
        return f"{self.status} {self.amount} of {self.voucher_type_id} by {self.wallet_id}"


class OnchainTx(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    kind = models.CharField(max_length=20, choices=OnchainKind.choices)  # mint1155 | safeTransfer1155
    voucher_type = models.ForeignKey("VoucherType", null=True, on_delete=models.SET_NULL, db_column="voucher_type_id")
    to_wallet = models.ForeignKey("Wallet", null=True, on_delete=models.SET_NULL, db_column="to_wallet_id")
    amount = models.BigIntegerField()
    nonce = models.BigIntegerField(null=True, blank=True)
    gas_price = models.DecimalField(max_digits=38, decimal_places=18, null=True, blank=True)
    status = models.CharField(max_length=16, choices=OnchainStatus.choices, default=OnchainStatus.QUEUED)
    tx_hash = models.CharField(max_length=80, null=True, blank=True)
    last_error = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "onchain_tx"
        managed = False
        indexes = [
            models.Index(fields=["status"], name="idx_otx_status_py"),
            models.Index(fields=["created_at"], name="idx_otx_created_py"),
            models.Index(fields=["voucher_type"], name="idx_otx_vtype_py"),
        ]

    def __str__(self):
        return f"{self.kind}/{self.status} {self.amount} -> {self.to_wallet_id or '—'}"


class ConsentLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey("AppUser", on_delete=models.CASCADE, db_column="user_id")
    scope = models.CharField(max_length=64)                  # 'marketing' | 'tos' | ...
    granted = models.BooleanField()
    created_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "consent_log"
        managed = False
        indexes = [
            models.Index(fields=["user"], name="idx_consent_user_py"),
            models.Index(fields=["scope"], name="idx_consent_scope_py"),
        ]

    def __str__(self):
        return f"{self.user_id} / {self.scope} = {self.granted}"


class Policy(models.Model):
    key = models.CharField(max_length=64, primary_key=True)
    value = models.JSONField()
    updated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "policy"
        managed = False

    def __str__(self):
        return self.key


# =========================
# POS / Merchant (bổ sung)
# =========================
class Merchant(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=120, unique=True)
    category = models.CharField(max_length=40, null=True, blank=True)  # 'spa' | 'restaurant' | ...
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "merchant"
        managed = False

    def __str__(self):
        return self.name


class POSTerminal(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    merchant = models.ForeignKey("Merchant", on_delete=models.CASCADE, db_column="merchant_id", related_name="terminals")
    code = models.CharField(max_length=64, unique=True)      # SPA01, REST01...
    api_key = models.CharField(max_length=128, unique=True)  # prod: cân nhắc hash
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "pos_terminal"
        managed = False
        indexes = [
            models.Index(fields=["merchant"], name="idx_term_merchant_py"),
            models.Index(fields=["active"], name="idx_term_active_py"),
        ]

    def __str__(self):
        return f"{self.code} ({self.merchant.name})"


class POSTerminalVoucher(models.Model):
    terminal = models.ForeignKey("POSTerminal", on_delete=models.CASCADE, db_column="terminal_id", related_name="allowed_vouchers")
    voucher_type = models.ForeignKey("VoucherType", on_delete=models.CASCADE, db_column="voucher_type_id", related_name="allowed_terminals")

    class Meta:
        db_table = "pos_terminal_voucher"
        managed = False
        unique_together = (("terminal", "voucher_type"),)
        indexes = [
            models.Index(fields=["terminal"], name="idx_ptv_terminal_py"),
            models.Index(fields=["voucher_type"], name="idx_ptv_vtype_py"),
        ]

    def __str__(self):
        return f"{self.terminal_id} ↔ {self.voucher_type_id}"
