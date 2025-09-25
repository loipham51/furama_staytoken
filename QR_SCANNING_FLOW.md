# QR Scanning Flow - Updated

## 🔄 **Luồng quét QR mới trên trang chủ**

### **1. User quét QR code**

```javascript
// User nhấn "Scan QR Code"
startQRScanner() → startCameraAndScan() → startScanningLoop()
```

### **2. Camera và QR Detection**

```javascript
// Sử dụng jsQR library để detect QR code
const code = jsQR(imageData.data, imageData.width, imageData.height);
if (code) {
    processQRCode(code.data);
}
```

### **3. Xử lý QR Code**

```javascript
async handleQRCode(qrData) {
    // Parse QR data: "voucher:spa-30off-2025:claim" hoặc "spa-30off-2025_abc123"
    let voucherCode = qrData;
    
    if (qrData.startsWith('voucher:')) {
        const parts = qrData.split(':');
        voucherCode = parts[1]; // Extract voucher slug
    }
    
    // Kiểm tra user đã đăng nhập chưa
    if (!this.loggedIn) {
        // Lưu voucher code vào sessionStorage
        sessionStorage.setItem('pending_voucher_code', voucherCode);
        
        // Redirect đến auth
        window.location.href = `/auth/start?next=${nextUrl}`;
        return;
    }
    
    // User đã đăng nhập, claim ngay
    await this.claimVoucher(voucherCode);
}
```

### **4. Auth Flow với Pending Voucher**

```javascript
// Sau khi user đăng nhập thành công
checkPendingVoucherCode() {
    const pendingCode = sessionStorage.getItem('pending_voucher_code');
    if (pendingCode) {
        sessionStorage.removeItem('pending_voucher_code');
        this.claimVoucher(pendingCode);
    }
}
```

### **5. Claim và Mint**

```javascript
async claimVoucher(code) {
    // Redirect đến claim page để xử lý full flow
    window.location.href = `/claim/${code}/`;
}
```

## 🎯 **Workflow hoàn chỉnh**

### **Scenario 1: User chưa đăng nhập**

```
1. User quét QR code
2. Hệ thống detect QR: "spa-30off-2025_abc123"
3. Lưu code vào sessionStorage
4. Redirect đến /auth/start
5. User nhập OTP
6. Auth thành công → redirect về trang chủ
7. checkPendingVoucherCode() → claim voucher
8. Redirect đến /claim/spa-30off-2025_abc123/
9. Claim và mint voucher
10. Hiển thị success page
```

### **Scenario 2: User đã đăng nhập**

```
1. User quét QR code
2. Hệ thống detect QR: "spa-30off-2025_abc123"
3. User đã đăng nhập → claim ngay
4. Redirect đến /claim/spa-30off-2025_abc123/
5. Claim và mint voucher
6. Hiển thị success page
```

## 🔧 **Technical Implementation**

### **1. QR Scanner Integration**

```html
<!-- Thêm jsQR library -->
<script src="https://cdn.jsdelivr.net/npm/jsqr@1.4.0/dist/jsQR.js"></script>

<!-- Camera view -->
<video x-ref="video" autoplay playsinline></video>
```

### **2. State Management**

```javascript
// QR Scanner state
qrScannerActive: false,
stream: null,
statusMessage: 'Click "Scan QR Code" to start',
```

### **3. Camera Control**

```javascript
// Start camera
async startCameraAndScan() {
    this.stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: 'environment' }
    });
    this.video.srcObject = this.stream;
}

// Stop camera
stopCamera() {
    this.stream.getTracks().forEach(track => track.stop());
    this.qrScannerActive = false;
}
```

### **4. QR Detection**

```javascript
startScanningLoop() {
    const canvas = document.createElement('canvas');
    const context = canvas.getContext('2d');
    
    context.drawImage(video, 0, 0, canvas.width, canvas.height);
    const imageData = context.getImageData(0, 0, canvas.width, canvas.height);
    const code = jsQR(imageData.data, imageData.width, imageData.height);
    
    if (code) {
        this.processQRCode(code.data);
    }
}
```

## ✅ **Lợi ích của luồng mới**

1. **Seamless UX**: User quét QR → auth → claim tự động
2. **No Manual Input**: Không cần nhập code thủ công
3. **Session Persistence**: Voucher code được lưu trong sessionStorage
4. **Real-time Scanning**: Sử dụng jsQR để detect QR code thực
5. **Mobile Friendly**: Camera hoạt động tốt trên mobile

## 🚀 **Cách sử dụng**

1. **User mở trang chủ**
2. **Nhấn "Scan QR Code"**
3. **Cho phép camera access**
4. **Hướng camera vào QR code**
5. **Hệ thống tự động detect và xử lý**

**Kết quả**: User có voucher trong ví sau vài giây!

