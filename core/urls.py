from django.urls import path
from . import views_admin, views_auth, views_me, views_home, views_claim, views_pos, views_wallet, views_qr

urlpatterns = [
  path("adv1/console", views_admin.admin_dashboard, name="admin_console"),
  path("adv1/console/stats.json", views_admin.admin_stats_json, name="admin_stats_json"),
  path("adv1/console/stats/<str:key>.json", views_admin.admin_stat_detail_json, name="admin_stat_detail_json"),
  path("adv1/console/stats/<str:key>", views_admin.admin_stat_detail_page, name="admin_stat_detail_page"),
  path("adv1/console/stats", views_admin.admin_stats_page, name="admin_stats_page"),
  path("adv1/console/scan", views_admin.admin_scan, name="admin_scan"),
  path("adv1/admin/users", views_admin.admin_users_page, name="admin_users_page"),
  path("adv1/admin/vouchers", views_admin.admin_vouchers_page, name="admin_vouchers_page"),
  path("adv1/admin/vouchers/new", views_admin.admin_voucher_new, name="admin_voucher_new"),
  path("adv1/admin/vouchers/<str:slug>/edit", views_admin.admin_voucher_edit, name="admin_voucher_edit"),
  path("adv1/admin/vouchers/<str:slug>/delete", views_admin.admin_voucher_delete, name="admin_voucher_delete"),
  path("adv1/admin/vouchers/<str:slug>/codes", views_admin.admin_voucher_codes, name="admin_voucher_codes"),
  path("adv1/admin/vouchers/<str:slug>/generate-codes", views_admin.admin_voucher_generate_codes, name="admin_voucher_generate_codes"),
  path("adv1/admin/vouchers/<str:slug>/expire-code", views_admin.admin_voucher_expire_code, name="admin_voucher_expire_code"),
  path("adv1/admin/vouchers/<str:slug>/export-codes", views_admin.admin_voucher_export_codes, name="admin_voucher_export_codes"),
  path("adv1/admin/vouchers/export-qr-pdf", views_admin.admin_voucher_export_qr_pdf, name="admin_voucher_export_qr_pdf"),
  
  # POS Scanner
  path("adv1/admin/pos/scanner", views_admin.admin_pos_scanner, name="admin_pos_scanner"),
  path("adv1/admin/pos/validate-voucher", views_admin.admin_pos_validate_voucher, name="admin_pos_validate_voucher"),
  path("adv1/admin/pos/confirm-redemption", views_admin.admin_pos_confirm_redemption, name="admin_pos_confirm_redemption"),
  
  # Merchant Management
  path("adv1/admin/merchants", views_admin.admin_merchants_page, name="admin_merchants"),
  path("adv1/admin/merchants/new", views_admin.admin_merchant_new, name="admin_merchant_new"),
  path("adv1/admin/merchants/<uuid:pk>", views_admin.admin_merchant_edit, name="admin_merchant_edit"),
  path("adv1/admin/merchants/<uuid:pk>/delete", views_admin.admin_merchant_delete, name="admin_merchant_delete"),
  
  # Terminal Management
  path("adv1/admin/terminals", views_admin.admin_terminals_page, name="admin_terminals"),
  path("adv1/admin/terminals/new", views_admin.admin_terminal_new, name="admin_terminal_new"),
  path("adv1/admin/terminals/<uuid:pk>", views_admin.admin_terminal_edit, name="admin_terminal_edit"),
  path("adv1/admin/terminals/<uuid:pk>/delete", views_admin.admin_terminal_delete, name="admin_terminal_delete"),
  path("adv1/admin/merchants", views_admin.admin_merchants_page, name="admin_merchants_page"),
  path("adv1/console/quick/gen-qr", views_admin.quick_gen_qr, name="console_gen_qr"),
  path("adv1/console/quick/export-csv", views_admin.quick_export_csv, name="console_export_csv"),
  path("adv1/console/recent.json", views_admin.recent_activity_json, name="admin_recent_json"),

  path("auth/start", views_auth.auth_start, name="auth_start"),
  path("auth/verify", views_auth.auth_verify, name="auth_verify"),
  path("auth/profile", views_auth.auth_profile, name="auth_profile"),
  path("logout", views_auth.logout, name="logout"),
  path("me", views_me.me, name="me"),
  path("my-wallet", views_me.my_wallet, name="my_wallet"),
  path("my-vouchers", views_me.my_vouchers, name="my_vouchers"),

  path("", views_home.home, name="home"),
  path("qr-scanner", views_home.qr_scanner, name="qr_scanner"),
  path('claim/<str:slug>/', views_claim.claim_start, name='claim_start'),
  path('claim/<str:slug>/submit', views_claim.claim_submit, name='claim_submit'),
  path('claim/<str:code>/done', views_claim.claim_done, name='claim_done'),
  path('api/claim-mint/<str:slug>', views_claim.claim_mint_now, name='claim_mint_now'),
  path('wallet/export', views_wallet.export_view, name='wallet_export'),
  path('wallet/transfer', views_wallet.transfer_view, name='wallet_transfer'),
  # path('pos/check', views_pos.user_portal, name='pos_user_portal'),  # Removed - duplicate of my-vouchers
  path('pos/api/check', views_pos.api_check, name='pos_check_api'),
  path('pos/reserve', views_pos.api_reserve, name='pos_reserve'),
  path('pos/api/reserve', views_pos.api_reserve, name='pos_reserve_api'),
  path('pos/commit', views_pos.api_commit, name='pos_commit'),
  path('pos/api/commit', views_pos.api_commit, name='pos_commit_api'),
  path("qr/wallet/<str:addr>.png", views_qr.wallet_qr_png, name="qr_wallet_png"),
  path("qr/voucher/<str:slug>/<str:addr>.png", views_qr.voucher_qr_png, name="qr_voucher_png")
]
