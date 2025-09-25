from __future__ import annotations

from typing import Iterable, List, Optional, Tuple

from eth_account import Account
from web3 import Web3
from web3.exceptions import ContractLogicError
try:
    # Web3.py v6+
    from web3.middleware import ExtraDataToPOAMiddleware as _POA_MIDDLEWARE  # type: ignore
except Exception:  # pragma: no cover - fallback for older Web3 versions
    try:
        # Web3.py v5 legacy path
        from web3.middleware.geth_poa import geth_poa_middleware as _POA_MIDDLEWARE  # type: ignore
    except Exception:  # pragma: no cover
        # Another v5 style export
        from web3.middleware import geth_poa_middleware as _POA_MIDDLEWARE  # type: ignore
from web3.types import TxParams


class ERC1155Client:
    """Thin Web3 helper around an ERC-1155 contract."""

    DEFAULT_ABI = [
        {
            'inputs': [
                {'internalType': 'address', 'name': 'account', 'type': 'address'},
                {'internalType': 'uint256', 'name': 'id', 'type': 'uint256'},
            ],
            'name': 'balanceOf',
            'outputs': [
                {'internalType': 'uint256', 'name': '', 'type': 'uint256'},
            ],
            'stateMutability': 'view',
            'type': 'function',
        },
        {
            'inputs': [
                {'internalType': 'address', 'name': 'from', 'type': 'address'},
                {'internalType': 'address', 'name': 'to', 'type': 'address'},
                {'internalType': 'uint256', 'name': 'id', 'type': 'uint256'},
                {'internalType': 'uint256', 'name': 'amount', 'type': 'uint256'},
                {'internalType': 'bytes', 'name': 'data', 'type': 'bytes'},
            ],
            'name': 'safeTransferFrom',
            'outputs': [],
            'stateMutability': 'nonpayable',
            'type': 'function',
        },
        {
            'inputs': [
                {'internalType': 'address', 'name': 'to', 'type': 'address'},
                {'internalType': 'uint256', 'name': 'id', 'type': 'uint256'},
                {'internalType': 'uint256', 'name': 'amount', 'type': 'uint256'},
                {'internalType': 'bytes', 'name': 'data', 'type': 'bytes'},
            ],
            'name': 'mint',
            'outputs': [],
            'stateMutability': 'nonpayable',
            'type': 'function',
        },
        {
            'inputs': [
                {'internalType': 'address', 'name': 'to', 'type': 'address'},
                {'internalType': 'uint256', 'name': 'id', 'type': 'uint256'},
                {'internalType': 'uint256', 'name': 'amount', 'type': 'uint256'},
            ],
            'name': 'mint',
            'outputs': [],
            'stateMutability': 'nonpayable',
            'type': 'function',
        },
        {
            'inputs': [
                {'internalType': 'address', 'name': 'to', 'type': 'address'},
                {'internalType': 'uint256', 'name': 'id', 'type': 'uint256'},
                {'internalType': 'uint256', 'name': 'amount', 'type': 'uint256'},
                {'internalType': 'bytes', 'name': 'data', 'type': 'bytes'},
            ],
            'name': 'mintTo',
            'outputs': [],
            'stateMutability': 'nonpayable',
            'type': 'function',
        },
        {
            'inputs': [
                {'internalType': 'address', 'name': 'to', 'type': 'address'},
                {'internalType': 'uint256', 'name': 'id', 'type': 'uint256'},
                {'internalType': 'uint256', 'name': 'amount', 'type': 'uint256'},
            ],
            'name': 'mintTo',
            'outputs': [],
            'stateMutability': 'nonpayable',
            'type': 'function',
        },
    ]

    def __init__(
        self,
        rpc_url: str,
        contract_address: str,
        signer_key: str,
        *,
        chain_id: Optional[int] = None,
        abi: Optional[Iterable[dict]] = None,
        use_poa_middleware: bool = True,
        request_timeout: int = 30,
    ) -> None:
        self.web3 = Web3(Web3.HTTPProvider(rpc_url, request_kwargs={'timeout': request_timeout}))
        if use_poa_middleware:
            try:
                # Works for both v6 (class) and v5 (callable)
                self.web3.middleware_onion.inject(_POA_MIDDLEWARE, layer=0)
            except ValueError:
                # Middleware already injected; ignore.
                pass

        self.account = Account.from_key(signer_key)
        self.address = self.account.address

        self.chain_id = chain_id or self._detect_chain_id(chain_id)

        self.contract = self.web3.eth.contract(
            address=Web3.to_checksum_address(contract_address),
            abi=list(abi) if abi is not None else self.DEFAULT_ABI,
        )

    def get_tx(self, tx_hash: str):
        return self.web3.eth.get_transaction(tx_hash)

    def balance_of(self, account: str, token_id: int) -> int:
        acct = Web3.to_checksum_address(account)
        try:
            fn = self.contract.functions.balanceOf(acct, int(token_id))
            return int(fn.call())
        except Exception as exc:
            raise RuntimeError(f"balanceOf failed: {exc}")

    def _detect_chain_id(self, override: Optional[int]) -> int:
        if override:
            return override
        try:
            cid = self.web3.eth.chain_id
            if cid:
                return cid
        except Exception:
            pass
        raise RuntimeError('Unable to determine chain id; set chain_id explicitly')

    def _prepare_base_tx(self, sender: str) -> TxParams:
        sender_cs = Web3.to_checksum_address(sender)
        nonce = self.web3.eth.get_transaction_count(sender_cs)
        return {
            'from': sender_cs,
            'nonce': nonce,
            'chainId': self.chain_id,
        }

    def _ensure_fee_fields(self, tx: TxParams) -> TxParams:
        if 'gas' not in tx:
            try:
                tx['gas'] = self.web3.eth.estimate_gas(tx)
            except Exception:
                tx['gas'] = 200000
        try:
            latest = self.web3.eth.get_block('latest')
            base_fee = latest.get('baseFeePerGas') if latest else None
        except Exception:
            base_fee = None
        if base_fee:
            priority = Web3.to_wei(2, 'gwei')
            tx.setdefault('maxPriorityFeePerGas', priority)
            tx.setdefault('maxFeePerGas', int(base_fee * 2 + priority))
        else:
            tx.setdefault('gasPrice', self.web3.eth.gas_price)
        return tx

    def _to_bytes(self, value: Optional[bytes]) -> bytes:
        if value is None:
            return b''
        if isinstance(value, bytes):
            return value
        if isinstance(value, bytearray):
            return bytes(value)
        if isinstance(value, str):
            if value.startswith('0x'):
                return bytes.fromhex(value[2:])
            return value.encode('utf-8')
        raise TypeError(f'Unsupported data payload type: {type(value)}')

    def _sign_and_send(self, tx: TxParams) -> str:
        signed = self.account.sign_transaction(tx)
        # Handle both Web3.py v5 and v6
        raw_tx = getattr(signed, 'rawTransaction', None) or getattr(signed, 'raw_transaction', None)
        if raw_tx is None:
            raise RuntimeError("Unable to get raw transaction from signed transaction")
        tx_hash = self.web3.eth.send_raw_transaction(raw_tx)
        return self.web3.to_hex(tx_hash)

    def safe_transfer(
        self,
        to_address: str,
        token_id: int,
        amount: int,
        data: Optional[bytes] = None,
        *,
        from_address: Optional[str] = None,
        wait: bool = False,
        timeout: int = 120,
    ) -> str:
        sender = from_address or self.address
        to_cs = Web3.to_checksum_address(to_address)
        fn = self.contract.functions.safeTransferFrom(
            Web3.to_checksum_address(sender),
            to_cs,
            int(token_id),
            int(amount),
            self._to_bytes(data),
        )
        tx = fn.build_transaction(self._prepare_base_tx(sender))
        tx = self._ensure_fee_fields(tx)
        tx_hash = self._sign_and_send(tx)
        if wait:
            self.wait_for_receipt(tx_hash, timeout=timeout)
        return tx_hash

    def mint_to(
        self,
        to_address: str,
        token_id: int,
        amount: int,
        data: Optional[bytes] = None,
        *,
        wait: bool = False,
        timeout: int = 120,
    ) -> str:
        to_cs = Web3.to_checksum_address(to_address)
        payload = self._to_bytes(data)
        attempts: List[Tuple[str, Tuple]] = [
            ('mint(address,uint256,uint256,bytes)', (to_cs, int(token_id), int(amount), payload)),
            ('mint(address,uint256,uint256)', (to_cs, int(token_id), int(amount))),
            ('mintTo(address,uint256,uint256,bytes)', (to_cs, int(token_id), int(amount), payload)),
            ('mintTo(address,uint256,uint256)', (to_cs, int(token_id), int(amount))),
        ]
        errors: List[str] = []
        for signature, args in attempts:
            try:
                fn = self.contract.get_function_by_signature(signature)
            except ValueError:
                continue
            try:
                tx = fn(*args).build_transaction(self._prepare_base_tx(self.address))
                tx = self._ensure_fee_fields(tx)
                tx_hash = self._sign_and_send(tx)
                if wait:
                    self.wait_for_receipt(tx_hash, timeout=timeout)
                return tx_hash
            except ContractLogicError as exc:
                errors.append(f"{signature}: {exc}")
            except Exception as exc:  # pragma: no cover - best effort logging
                errors.append(f"{signature}: {exc}")
        if errors:
            raise RuntimeError('Unable to mint via available signatures: ' + '; '.join(errors))
        raise RuntimeError('Contract does not expose a supported mint function')

    def wait_for_receipt(self, tx_hash: str, timeout: int = 180, poll_latency: float = 2.0):
        receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash, timeout=timeout, poll_latency=poll_latency)
        if receipt is None:
            raise TimeoutError(f'Timed out waiting for receipt of {tx_hash}')
        status = receipt.get('status') if isinstance(receipt, dict) else getattr(receipt, 'status', None)
        if status == 0:
            raise RuntimeError(f'Transaction {tx_hash} reverted on-chain')
        return receipt
