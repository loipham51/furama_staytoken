from django.contrib import admin
from .models import AppUser, Wallet, VoucherType, VoucherBalance, VoucherTransferLog, QRClaim, POSRedemption, OnchainTx, Policy

@admin.register(AppUser)
class AppUserAdmin(admin.ModelAdmin):
    list_display = ("full_name", "email", "phone", "is_active", "created_at")
    search_fields = ("full_name", "email", "phone")

@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ("user", "provider", "chain_id", "address_hex", "export_status", "created_at")
    search_fields = ("provider_ref",)

@admin.register(VoucherType)
class VoucherTypeAdmin(admin.ModelAdmin):
    list_display = ("slug", "name", "active", "token_id", "erc1155_contract", "created_at")
    search_fields = ("slug","name")
    list_filter = ("active",)

@admin.register(VoucherBalance)
class VoucherBalanceAdmin(admin.ModelAdmin):
    list_display = ("wallet", "voucher_type", "balance", "updated_at")
    search_fields = ("voucher_type__slug",)

@admin.register(VoucherTransferLog)
class VoucherTransferLogAdmin(admin.ModelAdmin):
    list_display = ("voucher_type","from_wallet","to_wallet","amount","reason","created_at")
    list_filter = ("reason",)

@admin.register(QRClaim)
class QRClaimAdmin(admin.ModelAdmin):
    list_display = ("code","voucher_type","status","expires_at","used_at","used_by_user")
    search_fields = ("code","event_label")
    list_filter = ("status","voucher_type")

@admin.register(POSRedemption)
class POSRedemptionAdmin(admin.ModelAdmin):
    list_display = ("voucher_type","wallet","amount","status","pos_terminal","reserved_at","committed_at")
    list_filter = ("status",)

@admin.register(OnchainTx)
class OnchainTxAdmin(admin.ModelAdmin):
    list_display = ("kind","voucher_type","to_wallet","amount","status","tx_hash","updated_at")
    list_filter = ("status","kind")

@admin.register(Policy)
class PolicyAdmin(admin.ModelAdmin):
    list_display = ("key","updated_at")
    search_fields = ("key",)
