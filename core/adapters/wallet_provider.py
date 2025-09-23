import json
import os
import re
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from eth_account import Account

try:  # Optional encryption support
    from cryptography.fernet import Fernet, InvalidToken
except Exception:  # pragma: no cover - cryptography may be unavailable in dev
    Fernet = None
    InvalidToken = Exception


class WalletProviderAdapter:
    def __init__(self, provider_name: str, chain_id: int):
        self.provider_name = provider_name
        self.chain_id = chain_id
        self._allow_export = getattr(settings, "ST_ALLOW_KEY_EXPORT", False)
        store = getattr(settings, "ST_WALLET_STORE_DIR", None)
        if not store:
            base = getattr(settings, "BASE_DIR", Path("."))
            store = base / "wallet_store"
        self.store_dir = Path(store)
        self.store_dir.mkdir(parents=True, exist_ok=True)

        enc_key = getattr(settings, "ST_WALLET_ENCRYPTION_KEY", None)
        if enc_key:
            if Fernet is None:
                raise ImproperlyConfigured(
                    "cryptography is required when ST_WALLET_ENCRYPTION_KEY is set",
                )
            try:
                enc_bytes = enc_key.encode("utf-8") if isinstance(enc_key, str) else enc_key
                self._fernet: Optional[Fernet] = Fernet(enc_bytes)
            except Exception as exc:  # pragma: no cover - config error surfaces immediately
                raise ImproperlyConfigured("Invalid ST_WALLET_ENCRYPTION_KEY") from exc
        else:
            self._fernet = None

    def _record_path(self, provider_ref: str) -> Path:
        if not re.fullmatch(r"[a-fA-F0-9]{16,64}", provider_ref):
            raise ValueError("Invalid provider reference")
        return self.store_dir / f"{provider_ref}.json"

    def _write_secure(self, path: Path, payload: bytes) -> None:
        path.write_bytes(payload)
        try:
            os.chmod(path, 0o600)
        except OSError:
            # On some platforms (e.g. Windows) chmod may be unsupported; ignore.
            pass

    def _save_record(self, provider_ref: str, data: Dict[str, Any]) -> None:
        path = self._record_path(provider_ref)
        blob = json.dumps(data, indent=2).encode("utf-8")
        if self._fernet:
            blob = self._fernet.encrypt(blob)
        self._write_secure(path, blob)

    def _load_record(self, provider_ref: str) -> Dict[str, Any]:
        path = self._record_path(provider_ref)
        if not path.exists():
            raise FileNotFoundError(f"Wallet record {provider_ref} not found")
        blob = path.read_bytes()
        if self._fernet:
            try:
                blob = self._fernet.decrypt(blob)
            except InvalidToken as exc:
                raise PermissionError("Unable to decrypt wallet record - invalid key") from exc
        return json.loads(blob.decode("utf-8"))

    def create_wallet(self, user_external_id: str):
        account = Account.create()
        provider_ref = secrets.token_hex(16)
        record = {
            'provider': self.provider_name,
            'user_external_id': user_external_id,
            'chain_id': self.chain_id,
            'address': account.address,
            'private_key': account.key.hex(),
            'created_at': datetime.now(timezone.utc).isoformat(),
            'exportable': self._allow_export,
        }
        self._save_record(provider_ref, record)
        address_bytes = bytes.fromhex(account.address[2:])
        return {
            'provider_ref': provider_ref,
            'address_bytes': address_bytes,
            'address_hex': account.address,
            'exportable': self._allow_export,
        }

    def export_key(self, provider_ref: str) -> str:
        if not self._allow_export:
            raise PermissionError('Export key is disabled by policy')
        record = self._load_record(provider_ref)
        return record['private_key']
