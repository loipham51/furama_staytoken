import secrets

from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = "Ensure every POS terminal has an API key."

    def add_arguments(self, parser):
        parser.add_argument(
            "--rotate",
            action="store_true",
            help="Regenerate keys for all terminals, even if they already have one.",
        )
        parser.add_argument(
            "--prefix",
            default="STPOS",
            help="Optional prefix to embed in generated keys (default: STPOS).",
        )
        parser.add_argument(
            "--length",
            type=int,
            default=32,
            help="Length of the random portion (hex characters, default: 32).",
        )

    def handle(self, *args, **options):
        rotate = options["rotate"]
        prefix = options["prefix"].strip() or "STPOS"
        random_length = max(8, int(options["length"]))

        rows = self._fetch_terminals()
        if not rows:
            self.stdout.write("No POS terminals found.")
            return

        updated = []
        for term_id, code, api_key in rows:
            if not rotate and api_key:
                continue
            new_key = self._generate_key(prefix, code, random_length)
            self._update_key(term_id, new_key)
            updated.append((code, new_key))

        if not updated:
            self.stdout.write("All terminals already have API keys.")
            return

        self.stdout.write(self.style.SUCCESS("Generated API keys:"))
        for code, key in updated:
            self.stdout.write(f"  {code}: {key}")

    def _fetch_terminals(self):
        with connection.cursor() as cur:
            cur.execute("SELECT id, code, api_key FROM pos_terminal ORDER BY code")
            return cur.fetchall()

    def _update_key(self, term_id, api_key):
        with connection.cursor() as cur:
            cur.execute(
                "UPDATE pos_terminal SET api_key=%s WHERE id=%s",
                [api_key, str(term_id)],
            )

    def _generate_key(self, prefix, code, length):
        bytes_needed = (length + 1) // 2
        random_part = secrets.token_hex(bytes_needed)[:length]
        base = prefix.upper()
        code_part = str(code).upper().replace(" ", "")
        return f"{base}_{code_part}_{random_part}"
