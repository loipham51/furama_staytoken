import os
from django.core.management.base import BaseCommand
from django.conf import settings
from core.qrcode_utils import get_or_make_cached_png
from core.models import VoucherType

class Command(BaseCommand):
    help = "Generate QR code PNG files for all voucher types"

    def handle(self, *args, **options):
        self.generate_all_vouchers()

    def generate_single_voucher(self, slug):
        """Generate QR code for a specific voucher type"""
        try:
            voucher_type = VoucherType.objects.get(slug=slug, active=True)
            self.stdout.write(f"Generating QR code for {voucher_type.name}")
            
            # Create output directory
            out_dir = os.path.join(settings.BASE_DIR, "qr_cache")
            os.makedirs(out_dir, exist_ok=True)
            
            # Create QR code PNG
            qr_data = f"voucher:{slug}:claim"
            png_path = get_or_make_cached_png(f"voucher_{slug}.png", qr_data)
            
            self.stdout.write(self.style.SUCCESS(f"Generated QR code for {slug}"))
            self.stdout.write(f"PNG saved to: {png_path}")
            
        except VoucherType.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"Voucher type '{slug}' not found or not active"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error generating QR code: {e}"))

    def generate_all_vouchers(self):
        """Generate QR codes for all active voucher types"""
        voucher_types = VoucherType.objects.filter(active=True)
        
        if not voucher_types.exists():
            self.stdout.write(self.style.ERROR("No active voucher types found"))
            return
        
        self.stdout.write(f"Found {voucher_types.count()} active voucher types")
        
        for voucher_type in voucher_types:
            self.generate_single_voucher(voucher_type.slug)
        
        self.stdout.write(self.style.SUCCESS("Generated QR codes for all voucher types"))