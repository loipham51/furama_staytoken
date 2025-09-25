#!/usr/bin/env python3
"""
Script kiểm tra blockchain configuration và contract status
"""

import os
import sys
import django
from web3 import Web3

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'furama_staytoken.settings')
django.setup()

from django.conf import settings

def check_blockchain_config():
    """Kiểm tra cấu hình blockchain"""
    print("🔍 CHECKING BLOCKCHAIN CONFIGURATION")
    print("=" * 50)
    
    # 1. Check RPC URL
    print(f"📡 RPC URL: {settings.ST_RPC_URL}")
    
    # 2. Check Signer
    signer_key = settings.ST_ERC1155_SIGNER
    if signer_key:
        try:
            # Derive address from private key
            from eth_account import Account
            account = Account.from_key(signer_key)
            signer_address = account.address
            print(f"🔑 Signer Address: {signer_address}")
            print(f"🔑 Signer Key (first 10 chars): {signer_key[:10]}...")
        except Exception as e:
            print(f"❌ Signer Key Error: {e}")
            return False
    else:
        print("❌ No signer key found")
        return False
    
    # 3. Check Contract
    contract_address = settings.ST_DEFAULT_CONTRACT
    print(f"📄 Contract Address: {contract_address}")
    
    # 4. Check Chain ID
    print(f"⛓️ Chain ID: {settings.ST_CHAIN_ID}")
    
    return True

def check_web3_connection():
    """Kiểm tra kết nối Web3"""
    print("\n🌐 CHECKING WEB3 CONNECTION")
    print("=" * 50)
    
    try:
        w3 = Web3(Web3.HTTPProvider(settings.ST_RPC_URL))
        
        # Check connection
        if w3.is_connected():
            print("✅ Web3 connection successful")
            
            # Get latest block
            latest_block = w3.eth.get_block('latest')
            print(f"📦 Latest block: {latest_block.number}")
            
            # Get network info
            chain_id = w3.eth.chain_id
            print(f"⛓️ Network Chain ID: {chain_id}")
            
            if chain_id != settings.ST_CHAIN_ID:
                print(f"⚠️ WARNING: Settings chain ID ({settings.ST_CHAIN_ID}) != Network chain ID ({chain_id})")
            
            return w3
        else:
            print("❌ Web3 connection failed")
            return None
            
    except Exception as e:
        print(f"❌ Web3 Error: {e}")
        return None

def check_signer_balance(w3):
    """Kiểm tra balance của signer"""
    print("\n💰 CHECKING SIGNER BALANCE")
    print("=" * 50)
    
    try:
        from eth_account import Account
        account = Account.from_key(settings.ST_ERC1155_SIGNER)
        signer_address = account.address
        
        # Get balance
        balance_wei = w3.eth.get_balance(signer_address)
        balance_eth = w3.from_wei(balance_wei, 'ether')
        
        print(f"👤 Signer Address: {signer_address}")
        print(f"💰 Balance: {balance_eth} ETH ({balance_wei} wei)")
        
        if balance_wei < w3.to_wei(0.001, 'ether'):
            print("⚠️ WARNING: Low balance! Need at least 0.001 ETH for gas")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ Balance Check Error: {e}")
        return False

def check_contract(w3):
    """Kiểm tra contract"""
    print("\n📄 CHECKING CONTRACT")
    print("=" * 50)
    
    contract_address = settings.ST_DEFAULT_CONTRACT
    
    try:
        # Check if contract exists
        code = w3.eth.get_code(contract_address)
        if code == b'':
            print(f"❌ No contract found at {contract_address}")
            return False
        
        print(f"✅ Contract exists at {contract_address}")
        print(f"📄 Contract code size: {len(code)} bytes")
        
        # Try to get contract info (basic ERC1155 functions)
        from eth_account import Account
        account = Account.from_key(settings.ST_ERC1155_SIGNER)
        signer_address = account.address
        
        # Check if signer has MINTER role (this would require contract ABI)
        print(f"👤 Checking permissions for: {signer_address}")
        
        return True
        
    except Exception as e:
        print(f"❌ Contract Check Error: {e}")
        return False

def check_token_id():
    """Kiểm tra token ID"""
    print("\n🎫 CHECKING TOKEN ID")
    print("=" * 50)
    
    from core.models import VoucherType
    
    try:
        voucher = VoucherType.objects.get(slug="spa-30off-2025", active=True)
        print(f"🎫 Voucher: {voucher.name}")
        print(f"🆔 Token ID: {voucher.token_id}")
        print(f"📄 ERC1155 Contract: {voucher.erc1155_contract}")
        
        return True
        
    except Exception as e:
        print(f"❌ Token Check Error: {e}")
        return False

def main():
    print("🚀 BLOCKCHAIN DIAGNOSTIC TOOL")
    print("=" * 50)
    
    # Step 1: Check config
    if not check_blockchain_config():
        print("\n❌ Configuration check failed")
        return
    
    # Step 2: Check Web3 connection
    w3 = check_web3_connection()
    if not w3:
        print("\n❌ Web3 connection failed")
        return
    
    # Step 3: Check signer balance
    if not check_signer_balance(w3):
        print("\n❌ Signer balance check failed")
        return
    
    # Step 4: Check contract
    if not check_contract(w3):
        print("\n❌ Contract check failed")
        return
    
    # Step 5: Check token ID
    if not check_token_id():
        print("\n❌ Token ID check failed")
        return
    
    print("\n✅ ALL CHECKS PASSED!")
    print("\n🔧 POSSIBLE SOLUTIONS:")
    print("1. Ensure signer has MINTER role in contract")
    print("2. Check if token ID exists in contract")
    print("3. Verify contract is properly deployed")
    print("4. Check contract ABI and function signatures")

if __name__ == "__main__":
    main()
