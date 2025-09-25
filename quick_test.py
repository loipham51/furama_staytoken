#!/usr/bin/env python3
import requests
import json

# Test API
url = "http://127.0.0.1:8000/api/test/claim-mint"
data = {
    "voucher_slug": "spa-30off-2025"
}

print("Testing API...")
print(f"URL: {url}")
print(f"Data: {data}")

try:
    response = requests.post(url, json=data, timeout=10)
    print(f"\nStatus Code: {response.status_code}")
    print(f"Headers: {dict(response.headers)}")
    
    # Try to parse as JSON
    try:
        result = response.json()
        print(f"JSON Response: {json.dumps(result, indent=2, ensure_ascii=False)}")
    except:
        print(f"Text Response: {response.text[:500]}")
        
except Exception as e:
    print(f"Error: {e}")
