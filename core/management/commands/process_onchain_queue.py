from decimal import Decimal

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import connection

from core.adapters.erc1155_client import ERC1155Client
from core.models import OnchainTx, VoucherType, Wallet


class Command(BaseCommand):
    help = "Send queued on-chain transactions"

    def handle(self, *args, **opts):
        client = ERC1155Client(
            rpc_url=settings.ST_RPC_URL,
            contract_address=settings.ST_DEFAULT_CONTRACT,
            signer_key=settings.ST_ERC1155_SIGNER,
            chain_id=settings.ST_CHAIN_ID,
        )

        while True:
            tx = (
                OnchainTx.objects
                .filter(status="queued")
                .order_by("created_at")
                .first()
            )
            if not tx:
                self.stdout.write("Queue empty")
                break

            try:
                if tx.kind == "mint1155":
                    voucher = VoucherType.objects.get(id=tx.voucher_type_id)
                    wallet = Wallet.objects.get(id=tx.to_wallet_id)
                    tx_hash = client.mint_to(wallet.address_hex, int(voucher.token_id), tx.amount)
                elif tx.kind == "safeTransfer1155":
                    voucher = VoucherType.objects.get(id=tx.voucher_type_id)
                    wallet = Wallet.objects.get(id=tx.to_wallet_id)
                    tx_hash = client.safe_transfer(wallet.address_hex, int(voucher.token_id), tx.amount)
                else:
                    raise ValueError(f"Unsupported kind {tx.kind}")

                tx_details = client.web3.eth.get_transaction(tx_hash)
                nonce_value = tx_details.get("nonce") if isinstance(tx_details, dict) else tx_details.nonce
                with connection.cursor() as cur:
                    cur.execute(
                        """
                        UPDATE onchain_tx
                        SET status='sent', tx_hash=%s, nonce=%s, updated_at=NOW(), last_error=NULL
                        WHERE id=%s
                        """,
                        [tx_hash, nonce_value, str(tx.id)],
                    )

                receipt = client.wait_for_receipt(tx_hash)
                gas_field = (
                    tx_details.get("maxFeePerGas")
                    if isinstance(tx_details, dict)
                    else getattr(tx_details, "maxFeePerGas", None)
                )
                if gas_field is None:
                    gas_field = (
                        tx_details.get("gasPrice")
                        if isinstance(tx_details, dict)
                        else getattr(tx_details, "gasPrice", None)
                    )
                gas_price_value = None
                if gas_field is not None:
                    gas_price_value = Decimal(gas_field) / Decimal(10 ** 18)

                if receipt.get("status") == 0:
                    raise RuntimeError(f"Transaction {tx_hash} reverted")

                with connection.cursor() as cur:
                    cur.execute(
                        """
                        UPDATE onchain_tx
                        SET status='confirmed', gas_price=%s, updated_at=NOW()
                        WHERE id=%s
                        """,
                        [gas_price_value, str(tx.id)],
                    )
                self.stdout.write(self.style.SUCCESS(f"Confirmed {tx.kind} -> {tx_hash}"))
            except Exception as exc:
                with connection.cursor() as cur:
                    cur.execute(
                        """
                        UPDATE onchain_tx
                        SET status='failed', last_error=%s, updated_at=NOW()
                        WHERE id=%s
                        """,
                        [str(exc), str(tx.id)],
                    )
                self.stderr.write(self.style.ERROR(f"Failed {tx.id}: {exc}"))
