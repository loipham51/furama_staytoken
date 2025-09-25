#!/usr/bin/env python3
"""
Script test API claim và mint
Chạy: python test_api.py
"""

import requests
import json
import sys

# Cấu hình
BASE_URL = "http://127.0.0.1:8000"  # Thay đổi IP nếu cần
# BASE_URL = "https://6629e0aaa90d.ngrok-free.app"  # Hoặc dùng ngrok

def test_claim_mint(email="lanfurma@gmail.com", voucher_slug="spa-30off-2025"):
    """Test API claim và mint"""
    url = f"{BASE_URL}/api/test/claim-mint"
    
    data = {
        "email": email,
        "full_name": "Test User",
        "phone": "0123456789",
        "voucher_slug": voucher_slug
    }
    
    print(f"🧪 Testing API: {url}")
    print(f"📝 Data: {json.dumps(data, indent=2)}")
    print("-" * 50)
    
    try:
        response = requests.post(url, json=data, timeout=30)
        
        print(f"📊 Status Code: {response.status_code}")
        print(f"📋 Headers: {dict(response.headers)}")
        
        try:
            result = response.json()
            print(f"📄 Response: {json.dumps(result, indent=2, ensure_ascii=False)}")
        except:
            print(f"📄 Response (text): {response.text}")
        
        if response.status_code == 200 and result.get("ok"):
            print("✅ SUCCESS! Voucher claimed and minted successfully!")
            if result.get("tx_hash"):
                print(f"🔗 Transaction Hash: {result['tx_hash']}")
            if result.get("explorer"):
                print(f"🌐 Explorer: {result['explorer']}")
        else:
            print("❌ FAILED!")
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Request failed: {e}")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")

def test_different_vouchers():
    """Test với các voucher khác nhau"""
    vouchers = [
        "spa-30off-2025",
        "cafe-indochine-20-off-2025",
        "don-ciprianis-restaurant-italian-dinner-set",
        "hai-van-lounge-free-cocktail",
        "steak-house-the-fan-15-off-premium-steak"
    ]
    
    for i, voucher in enumerate(vouchers, 1):
        print(f"\n🧪 Test {i}/{len(vouchers)}: {voucher}")
        test_claim_mint(f"test{i}@example.com", voucher)
        print("\n" + "="*60)

def test_error_cases():
    """Test các trường hợp lỗi"""
    print("\n🔍 Testing Error Cases...")
    
    # Test missing fields
    print("\n1. Testing missing fields...")
    url = f"{BASE_URL}/api/test/claim-mint"
    try:
        response = requests.post(url, json={})
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}")
    except Exception as e:
        print(f"Error: {e}")
    
    # Test invalid voucher
    print("\n2. Testing invalid voucher...")
    try:
        response = requests.post(url, json={
            "email": "test@example.com",
            "voucher_slug": "invalid-voucher"
        })
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    print("🚀 StayToken API Test Script")
    print("=" * 50)
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "multi":
            test_different_vouchers()
        elif sys.argv[1] == "error":
            test_error_cases()
        else:
            voucher_slug = sys.argv[1]
            test_claim_mint(voucher_slug=voucher_slug)
    else:
        # Test cơ bản
        test_claim_mint()
    
    print("\n✨ Test completed!")
    print("\n📖 Usage:")
    print("  python test_api.py                    # Test cơ bản")
    print("  python test_api.py spa-30off-2025     # Test voucher cụ thể")
    print("  python test_api.py multi              # Test nhiều voucher")
    print("  python test_api.py error              # Test error cases")
