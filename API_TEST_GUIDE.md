# 🧪 API Test Guide - Claim & Mint

## 📋 Tổng quan

API test này cho phép bạn test chức năng claim và mint voucher một cách đơn giản thông qua HTTP POST request.

## 🔗 Endpoint

```
POST /api/test/claim-mint
```

## 📝 Request Format

### Headers
```
Content-Type: application/json
```

### Body (JSON)
```json
{
    "email": "test@example.com",
    "full_name": "Test User",
    "phone": "0123456789",
    "voucher_slug": "spa-30off-2025"
}
```

### Required Fields
- `email`: Email của user (bắt buộc)
- `voucher_slug`: Slug của voucher cần claim (bắt buộc)

### Optional Fields
- `full_name`: Tên đầy đủ của user
- `phone`: Số điện thoại của user

## ✅ Response Format

### Success Response (200)
```json
{
    "ok": true,
    "user_id": 123,
    "user_email": "test@example.com",
    "voucher_name": "Spa 30% Off 2025",
    "voucher_slug": "spa-30off-2025",
    "wallet_address": "0x1234...5678",
    "tx_hash": "0xabcd...efgh",
    "explorer": "https://basescan.org/tx/0xabcd...efgh",
    "claimed_count": 1,
    "limit": 3
}
```

### Error Responses

#### Missing Fields (400)
```json
{
    "ok": false,
    "error": "MISSING_FIELDS",
    "detail": "email and voucher_slug are required"
}
```

#### Voucher Not Found (404)
```json
{
    "ok": false,
    "error": "VOUCHER_NOT_FOUND",
    "detail": "Voucher 'invalid-slug' not found or inactive"
}
```

#### Limit Reached (403)
```json
{
    "ok": false,
    "error": "LIMIT_REACHED",
    "claimed": 3,
    "limit": 3
}
```

#### Rate Limited (429)
```json
{
    "ok": false,
    "error": "RATE_LIMITED",
    "detail": "Too many requests, try again later"
}
```

#### Mint Failed (500)
```json
{
    "ok": false,
    "error": "MINT_FAILED",
    "detail": "Transaction failed: insufficient funds"
}
```

## 🧪 Test Examples

### 1. Test với cURL

```bash
curl -X POST http://192.168.10.164:8000/api/test/claim-mint \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "full_name": "Test User",
    "phone": "0123456789",
    "voucher_slug": "spa-30off-2025"
  }'
```

### 2. Test với ngrok

```bash
curl -X POST https://6629e0aaa90d.ngrok-free.app/api/test/claim-mint \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "full_name": "Test User",
    "voucher_slug": "spa-30off-2025"
  }'
```

### 3. Test với Python requests

```python
import requests
import json

url = "http://192.168.10.164:8000/api/test/claim-mint"
data = {
    "email": "test@example.com",
    "full_name": "Test User",
    "phone": "0123456789",
    "voucher_slug": "spa-30off-2025"
}

response = requests.post(url, json=data)
print(response.json())
```

### 4. Test với JavaScript fetch

```javascript
const testClaim = async () => {
    const response = await fetch('http://192.168.10.164:8000/api/test/claim-mint', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            email: 'test@example.com',
            full_name: 'Test User',
            phone: '0123456789',
            voucher_slug: 'spa-30off-2025'
        })
    });
    
    const result = await response.json();
    console.log(result);
};

testClaim();
```

## 📊 Available Voucher Slugs

Để xem danh sách voucher có sẵn, bạn có thể:

1. Truy cập admin console: `http://192.168.10.164:8000/adv1/admin/vouchers`
2. Hoặc kiểm tra database trực tiếp

Một số voucher slug phổ biến:
- `spa-30off-2025`
- `cafe-indochine-20-off-2025`
- `don-ciprianis-restaurant-italian-dinner-set`
- `hai-van-lounge-free-cocktail`
- `steak-house-the-fan-15-off-premium-steak`

## 🔍 Debug Information

API sẽ log thông tin debug trong console:
- Contract address
- Token ID
- Wallet address
- Signer key (chỉ hiển thị 10 ký tự đầu)

## ⚠️ Lưu ý

1. **Rate Limiting**: API có giới hạn request để tránh spam
2. **Blockchain Config**: Cần cấu hình đầy đủ blockchain settings
3. **Transaction Wait**: API sẽ đợi transaction được confirm trước khi trả về
4. **User Creation**: API sẽ tự động tạo user nếu chưa tồn tại
5. **Claim Limits**: Mỗi user có giới hạn claim voucher theo cấu hình

## 🚀 Quick Test

Để test nhanh, bạn có thể sử dụng:

```bash
# Test cơ bản
curl -X POST http://192.168.10.164:8000/api/test/claim-mint \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","voucher_slug":"spa-30off-2025"}'
```

Happy testing! 🎉

