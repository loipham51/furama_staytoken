# QR Code Features - Furama StayToken

## Tổng quan

Dự án đã được cập nhật với các tính năng QR code mới để cải thiện trải nghiệm người dùng khi claim voucher tại khách sạn Furama Resort.

## Các tính năng mới

### 1. Giao diện trang chủ mới

- **Thay thế danh sách voucher** bằng button quét QR code
- **Chức năng nhập code thủ công** để claim voucher
- **Giao diện thân thiện** với người dùng di động

### 2. QR Scanner

- **Trang quét QR code** chuyên dụng (`/qr-scanner`)
- **Hỗ trợ camera** để quét QR code tự động
- **Fallback nhập code thủ công** khi camera không hoạt động

### 3. Xuất QR Code PDF

- **Chức năng xuất PDF** trong trang quản lý voucher
- **Tạo QR code** cho từng voucher
- **In ấn dễ dàng** để đặt tại lễ tân khách sạn

### 4. Claim với Auth OTP

- **Xác thực OTP** trước khi claim
- **Mint ngay lập tức** trên blockchain
- **Hiển thị transaction hash** sau khi claim thành công

## Hướng dẫn sử dụng

### Cho khách hàng

1. **Quét QR code**: 
   - Mở trang chủ
   - Nhấn "Scan QR Code"
   - Hướng camera vào QR code voucher
   - Hoặc nhập code thủ công

2. **Xác thực OTP**:
   - Nhập email/số điện thoại
   - Nhận mã OTP
   - Nhập mã để xác thực

3. **Claim voucher**:
   - Voucher sẽ được mint ngay lập tức
   - Hiển thị transaction hash
   - Lưu trữ trong ví custodial

### Cho nhân viên lễ tân

1. **Tạo QR code**:
   - Đăng nhập admin panel
   - Vào "Vouchers" → "Export QR Codes"
   - Tải file PDF chứa QR codes

2. **In và đặt QR code**:
   - In file PDF
   - Đặt tại bàn lễ tân
   - Hướng dẫn khách quét

## Cài đặt

### Dependencies mới

```bash
pip install reportlab>=4.0
```

### Cấu hình

Đảm bảo các settings sau được cấu hình:

```python
# settings.py
ST_QR_CACHE_DIR = "qr_cache"
ST_EXPLORER_TX_PREFIX = "https://explorer.example.com/tx/"
```

## API Endpoints mới

- `GET /qr-scanner` - Trang quét QR code
- `POST /adv1/admin/vouchers/export-qr-pdf` - Xuất QR code PDF

## Workflow hoàn chỉnh

1. **Admin tạo voucher** → **Xuất QR code PDF** → **In và đặt tại lễ tân**
2. **Khách quét QR** → **Auth OTP** → **Claim và mint** → **Nhận voucher**

## Lưu ý kỹ thuật

- QR code chứa format: `voucher:{slug}:claim`
- Sử dụng `mint_erc1155_now` thay vì `enqueue_onchain` để mint ngay lập tức
- Transaction hash được lưu trong session để hiển thị trên trang success
- Hỗ trợ fallback nhập code thủ công khi camera không khả dụng

## Troubleshooting

### Camera không hoạt động
- Sử dụng chức năng nhập code thủ công
- Kiểm tra quyền truy cập camera

### PDF không tạo được
- Kiểm tra quyền ghi file
- Đảm bảo thư viện reportlab được cài đặt

### Mint thất bại
- Kiểm tra cấu hình blockchain
- Xem log để debug chi tiết

