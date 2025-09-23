import csv, os, secrets, uuid
from django.core.management.base import BaseCommand
from django.conf import settings
from django.db import connection
from core.qrcode_utils import get_or_make_cached_png

class Command(BaseCommand):
    help = "Sinh QR claim một lần cho một voucher_type slug"

    def add_arguments(self, parser):
        parser.add_argument("--slug", required=True, help="voucher_type.slug")
        parser.add_argument("--count", type=int, default=10)

    def handle(self, *args, **opts):
        slug = opts["slug"]
        count = opts["count"]

        # lấy id voucher_type
        with connection.cursor() as cur:
            cur.execute("SELECT id FROM voucher_type WHERE slug=%s", [slug])
            row = cur.fetchone()
            if not row:
                self.stderr.write("Voucher type not found")
                return
            vtid = row[0]

        out_dir = os.path.join(settings.BASE_DIR, "claim_qr")
        os.makedirs(out_dir, exist_ok=True)
        csv_path = os.path.join(out_dir, f"{slug}_qr.csv")

        rows = []
        for _ in range(count):
            code = secrets.token_urlsafe(8)
            new_id = uuid.uuid4()
            with connection.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO qr_claim (id, code, voucher_type_id, status, created_at)
                    VALUES (%s, %s, %s, 'new', NOW())
                    """,
                    [str(new_id), code, str(vtid)],
                )
            # Tạo QR file cho link claim
            claim_url = f"/claim/{code}/"
            get_or_make_cached_png(f"claim_{code}.png", claim_url)
            rows.append({"code": code, "claim_url": claim_url})

        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["code","claim_url"])
            writer.writeheader()
            writer.writerows(rows)

        self.stdout.write(self.style.SUCCESS(f"Generated {count} QR codes -> {csv_path}"))
